import logging
import os
import base64
import re
from typing import Any

logger = logging.getLogger(__name__)
DEFAULT_SANDBOX_TIMEOUT = int(os.getenv("E2B_SANDBOX_TIMEOUT", "3600"))

def get_template_id(template_name: str) -> str:
    """Get the E2B template ID for a given template name from settings."""
    from config import settings
    if template_name == "nextjs" and settings.e2b_template_nextjs:
        return settings.e2b_template_nextjs
    if template_name == "react-vite" and settings.e2b_template_react_vite:
        return settings.e2b_template_react_vite
    return "base"



class E2BSandboxManager:
    """Manages E2B sandbox instances for code execution."""

    def __init__(self):
        self._sandboxes: dict[str, Any] = {}
        self._bg_processes: dict[str, Any] = {}

    def get_sandbox_id(self, session_id: str) -> str | None:
        sandbox = self._sandboxes.get(session_id)
        if not sandbox:
            return None
        return getattr(sandbox, "sandbox_id", None) or getattr(sandbox, "id", None)

    async def create_sandbox(
        self,
        session_id: str,
        template: str = "base",
        timeout: int | None = None,
    ) -> str:
        """Create a new E2B sandbox and return its ID."""
        try:
            from e2b import AsyncSandbox
            timeout_seconds = DEFAULT_SANDBOX_TIMEOUT if timeout is None else timeout
            create_kwargs: dict[str, Any] = {"timeout": timeout_seconds}
            if template and template != "base":
                create_kwargs["template"] = template
            sandbox = await AsyncSandbox.create(**create_kwargs)
            self._sandboxes[session_id] = sandbox
            logger.info(
                "Created E2B sandbox for session %s: %s (timeout=%ss)",
                session_id,
                sandbox.sandbox_id,
                timeout_seconds,
            )
            return sandbox.sandbox_id
        except Exception as e:
            logger.error("Failed to create E2B sandbox: %s", e)
            raise

    async def connect_sandbox(self, session_id: str, sandbox_id: str) -> bool:
        """Reconnect to an existing E2B sandbox by sandbox_id."""
        if not sandbox_id:
            return False
        try:
            from e2b import AsyncSandbox

            sandbox = await AsyncSandbox.connect(sandbox_id)
            self._sandboxes[session_id] = sandbox
            logger.info("Reconnected E2B sandbox for session %s: %s", session_id, sandbox_id)
            return True
        except Exception as e:
            logger.warning(
                "Failed to reconnect E2B sandbox for session %s (%s): %s",
                session_id,
                sandbox_id,
                e,
            )
            return False

    async def ensure_sandbox(
        self,
        session_id: str,
        sandbox_id: str | None = None,
        timeout: int | None = None,
        template: str = "base",
    ) -> tuple[str, bool]:
        """
        Ensure a usable sandbox handle exists for this session.

        Returns (sandbox_id, reused_existing_handle).
        """
        current_id = self.get_sandbox_id(session_id)
        if current_id:
            return current_id, True

        if sandbox_id and await self.connect_sandbox(session_id, sandbox_id):
            return sandbox_id, True

        created_id = await self.create_sandbox(session_id, template=template, timeout=timeout)
        return created_id, False

    async def write_files(self, session_id: str, files: dict[str, str]) -> None:
        """Write multiple files to the sandbox."""
        sandbox = self._sandboxes.get(session_id)
        if not sandbox:
            raise RuntimeError(f"No sandbox for session {session_id}")
        for path, content in files.items():
            await sandbox.files.write(f"/home/user/project/{path}", content)
        # Trigger filesystem events for dev server HMR by touching files
        # E2B files.write() uses API which doesn't trigger fs watchers
        if files:
            paths_str = " ".join(f'"{p}"' for p in files.keys())
            try:
                await sandbox.commands.run(
                    f"bash -c 'cd /home/user/project && touch -c {paths_str}'",
                    timeout=10,
                )
            except Exception:
                # Ignore touch errors, files are already written
                pass

    async def write_file(self, session_id: str, file_path: str, content: str) -> None:
        """Write a single file to the sandbox."""
        sandbox = self._sandboxes.get(session_id)
        if not sandbox:
            raise RuntimeError(f"No sandbox for session {session_id}")
        await sandbox.files.write(f"/home/user/project/{file_path}", content)
        # Trigger filesystem event for dev server HMR
        try:
            await sandbox.commands.run(
                f"bash -c 'touch -c \"/home/user/project/{file_path}\"'",
                timeout=5,
            )
        except Exception:
            pass

    async def execute_command(
        self,
        session_id: str,
        command: str,
        cwd: str = "/home/user/project",
        timeout: int = 120,
    ) -> dict:
        """Execute a command in the sandbox."""
        sandbox = self._sandboxes.get(session_id)
        if not sandbox:
            raise RuntimeError(f"No sandbox for session {session_id}")
        try:
            result = await sandbox.commands.run(command, cwd=cwd, timeout=timeout)
            return {
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
                "exit_code": result.exit_code,
            }
        except Exception as e:
            err_str = str(e)
            exit_code = int(getattr(e, "exit_code", 1) or 1)
            stdout = str(getattr(e, "stdout", "") or "")
            stderr = str(getattr(e, "stderr", "") or "")

            if not stderr and err_str:
                stderr = err_str

            # E2B sometimes returns only a generic string like:
            # "Command exited with code X and error:" without actual stderr.
            # Do one diagnostic rerun that always exits 0 and prints full output.
            generic_failure = bool(
                re.search(r"Command exited with code \d+ and error:\s*$", stderr, re.IGNORECASE),
            )
            no_useful_output = not (stdout or stderr.strip())
            if (generic_failure or no_useful_output) and exit_code != 0:
                recovered_stdout, recovered_stderr, recovered_exit_code = await self._diagnose_failed_command(
                    sandbox=sandbox,
                    command=command,
                    cwd=cwd,
                    timeout=timeout,
                )
                if recovered_stdout:
                    stdout = recovered_stdout
                if recovered_stderr:
                    stderr = recovered_stderr
                if recovered_exit_code is not None:
                    exit_code = recovered_exit_code

            logger.warning("Command failed in sandbox for session %s: %s", session_id, (stderr or err_str)[:300])
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
            }

    async def _diagnose_failed_command(
        self,
        sandbox: Any,
        command: str,
        cwd: str,
        timeout: int,
    ) -> tuple[str, str, int | None]:
        marker = "__VIBEHUB_EXIT_CODE__="
        encoded = base64.b64encode(command.encode("utf-8")).decode("ascii")
        diag_command = (
            "bash -lc \"set +e; "
            f"CMD=$(printf '%s' '{encoded}' | base64 -d); "
            "eval \\\"$CMD\\\" > /tmp/vibehub_cmd_diag.log 2>&1; "
            "RC=$?; "
            "cat /tmp/vibehub_cmd_diag.log 2>/dev/null || true; "
            f"echo '{marker}'$RC; "
            "exit 0\""
        )
        try:
            result = await sandbox.commands.run(diag_command, cwd=cwd, timeout=timeout)
            raw_stdout = str(result.stdout or "")
            raw_stderr = str(result.stderr or "")

            recovered_exit: int | None = None
            recovered_stdout = raw_stdout
            idx = raw_stdout.rfind(marker)
            if idx >= 0:
                recovered_stdout = raw_stdout[:idx].rstrip()
                tail = raw_stdout[idx + len(marker):].strip().splitlines()
                if tail:
                    try:
                        recovered_exit = int(tail[0].strip())
                    except Exception:
                        recovered_exit = None

            return recovered_stdout, raw_stderr, recovered_exit
        except Exception as diag_error:
            return "", str(diag_error), None

    async def run_background(
        self,
        session_id: str,
        command: str,
        cwd: str = "/home/user/project",
    ) -> Any:
        """Start a long-running process in the background (e.g. dev server)."""
        sandbox = self._sandboxes.get(session_id)
        if not sandbox:
            raise RuntimeError(f"No sandbox for session {session_id}")
        # Prefer run(background=True) to avoid long-running request timeouts.
        try:
            handle = await sandbox.commands.run(command, background=True, cwd=cwd, timeout=0)
        except TypeError:
            handle = await sandbox.commands.run(command, background=True, cwd=cwd)
        except Exception:
            # Fallback for SDKs where run(background=True) is unreliable.
            if hasattr(sandbox.commands, "start"):
                handle = await sandbox.commands.start(command, cwd=cwd)
            else:
                raise
        self._bg_processes[session_id] = handle
        logger.info("Started background command for session %s: %s", session_id, command)
        return handle

    async def is_port_open(self, session_id: str, port: int) -> bool:
        """Check from inside the sandbox whether a port is actually listening."""
        result = await self.execute_command(
            session_id,
            f"curl -sf http://localhost:{port} -o /dev/null -w '%{{http_code}}'",
            timeout=5,
        )
        if result["exit_code"] == 0:
            return True
        result2 = await self.execute_command(
            session_id,
            f"python3 -c \"import socket; s=socket.socket(); s.settimeout(1); s.connect(('localhost', {port})); s.close(); print('OK')\"",
            timeout=5,
        )
        return "OK" in result2["stdout"]

    async def is_process_running(self, session_id: str, pattern: str) -> bool:
        """Check if a process matching the pattern is running inside the sandbox."""
        result = await self.execute_command(
            session_id, f"pgrep -f '{pattern}' > /dev/null 2>&1 && echo RUNNING || echo STOPPED", timeout=5,
        )
        return "RUNNING" in result["stdout"]

    async def extend_timeout(self, session_id: str, timeout: int | None = None) -> None:
        """Extend sandbox timeout (e.g. after dev server starts successfully)."""
        sandbox = self._sandboxes.get(session_id)
        if not sandbox:
            return
        try:
            if hasattr(sandbox, "set_timeout"):
                timeout_seconds = DEFAULT_SANDBOX_TIMEOUT if timeout is None else timeout
                await sandbox.set_timeout(timeout_seconds)
                logger.info("Extended sandbox timeout to %ds for session %s", timeout_seconds, session_id)
        except Exception as e:
            logger.warning("Failed to extend sandbox timeout for session %s: %s", session_id, e)

    async def get_preview_url(self, session_id: str, port: int = 3000) -> str | None:
        """Get the preview URL for a running dev server."""
        sandbox = self._sandboxes.get(session_id)
        if not sandbox:
            return None
        try:
            host = sandbox.get_host(port)
            return f"https://{host}"
        except Exception:
            return None

    async def cleanup(self, session_id: str) -> None:
        """Destroy the sandbox for a session."""
        sandbox = self._sandboxes.pop(session_id, None)
        if sandbox:
            try:
                await sandbox.kill()
                logger.info("Destroyed E2B sandbox for session %s", session_id)
            except Exception as e:
                logger.warning("Failed to destroy sandbox for session %s: %s", session_id, e)


sandbox_manager = E2BSandboxManager()
