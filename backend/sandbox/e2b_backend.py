import logging
from typing import Any

logger = logging.getLogger(__name__)


class E2BSandboxManager:
    """Manages E2B sandbox instances for code execution."""

    def __init__(self):
        self._sandboxes: dict[str, Any] = {}
        self._bg_processes: dict[str, Any] = {}

    async def create_sandbox(self, session_id: str, template: str = "base") -> str:
        """Create a new E2B sandbox and return its ID."""
        try:
            from e2b import AsyncSandbox
            sandbox = await AsyncSandbox.create(timeout=900)
            self._sandboxes[session_id] = sandbox
            logger.info("Created E2B sandbox for session %s: %s", session_id, sandbox.sandbox_id)
            return sandbox.sandbox_id
        except Exception as e:
            logger.error("Failed to create E2B sandbox: %s", e)
            raise

    async def write_files(self, session_id: str, files: dict[str, str]) -> None:
        """Write multiple files to the sandbox."""
        sandbox = self._sandboxes.get(session_id)
        if not sandbox:
            raise RuntimeError(f"No sandbox for session {session_id}")
        for path, content in files.items():
            await sandbox.files.write(f"/home/user/project/{path}", content)

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
            logger.warning("Command failed in sandbox for session %s: %s", session_id, err_str[:200])
            return {
                "stdout": "",
                "stderr": err_str,
                "exit_code": getattr(e, "exit_code", 1),
            }

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

    async def extend_timeout(self, session_id: str, timeout: int = 900) -> None:
        """Extend sandbox timeout (e.g. after dev server starts successfully)."""
        sandbox = self._sandboxes.get(session_id)
        if not sandbox:
            return
        try:
            if hasattr(sandbox, "set_timeout"):
                await sandbox.set_timeout(timeout)
                logger.info("Extended sandbox timeout to %ds for session %s", timeout, session_id)
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
