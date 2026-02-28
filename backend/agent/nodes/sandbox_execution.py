import asyncio
import hashlib
import logging
from pathlib import Path

from agent.callback_registry import ws_send
from agent.file_constraints import enforce_nextjs_config_filename
from agent.state import CodeGenState
from sandbox.e2b_backend import get_template_id

logger = logging.getLogger(__name__)

MAX_FIX_ATTEMPTS = 3
DEV_SERVER_START_ATTEMPTS = 3
DEV_SERVER_POLL_STEPS = 10
DEV_SERVER_LOG_PATH = "/tmp/devserver.log"
NODE_MAX_OLD_SPACE_MB = 768
LOG_CHUNK_SIZE = 4000


def _with_node_memory(command: str) -> str:
    """Wrap command with NODE_OPTIONS memory limit.

    Note: Don't include 'bash -c' here as E2B's execute_command already handles that.
    Just return the command string to be executed.
    """
    return f"NODE_OPTIONS=--max-old-space-size={NODE_MAX_OLD_SPACE_MB} {command}"


def _package_json_hash(generated_files: dict) -> str | None:
    package_json_entry = generated_files.get("package.json")
    if not isinstance(package_json_entry, dict):
        return None
    content = str(package_json_entry.get("file_contents", ""))
    if not content:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _validation_steps_for_template(template_name: str) -> list[tuple[str, str, int, bool]]:
    """
    Returns (step_name, command, timeout_seconds, optional_if_missing_script).
    """
    if template_name == "nextjs":
        return [
            ("typecheck", _with_node_memory("npx tsc --noEmit"), 240, False),
            ("build", _with_node_memory("npx next build"), 600, False),
        ]
    if template_name == "react-vite":
        return [
            ("typecheck", _with_node_memory("npx tsc --noEmit"), 240, False),
            (
                "lint",
                f"bash -c \"cd /home/user/project && if [ -f eslint.config.js ] || [ -f eslint.config.mjs ] || [ -f eslint.config.cjs ] || [ -f .eslintrc ] || [ -f .eslintrc.js ] || [ -f .eslintrc.cjs ] || [ -f .eslintrc.json ] || [ -f .eslintrc.yaml ] || [ -f .eslintrc.yml ]; then NODE_OPTIONS=--max-old-space-size={NODE_MAX_OLD_SPACE_MB} npm run lint; else echo SKIP_LINT_NO_CONFIG; fi\"",
                180,
                True,
            ),
            ("build", _with_node_memory("npm run build"), 600, False),
        ]
    return [("build", _with_node_memory("npm run build"), 600, False)]


def _is_missing_optional_script(result: dict) -> bool:
    output = f"{result.get('stdout', '')}\n{result.get('stderr', '')}".lower()
    return "missing script" in output and "npm" in output


def _format_validation_errors(failures: list[tuple[str, str]]) -> str:
    lines = ["Validation failed:"]
    for step_name, detail in failures:
        lines.append(f"[{step_name}]")
        lines.append(detail.strip() or "(no output)")
        lines.append("")
    return "\n".join(lines).strip()


async def _send_log_chunks(sid: str, stream: str, text: str, step_name: str | None = None) -> None:
    if not text:
        return
    prefix = f"[{step_name}] " if step_name else ""
    for idx in range(0, len(text), LOG_CHUNK_SIZE):
        chunk = text[idx: idx + LOG_CHUNK_SIZE]
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": stream,
            "text": f"{prefix}{chunk}",
        })


async def sandbox_execution_node(state: CodeGenState, config) -> dict:
    """Write all generated files to E2B sandbox, install deps, and start dev server."""
    from sandbox.e2b_backend import sandbox_manager

    sid = state.get("session_id", "")
    generated_files = dict(state.get("generated_files", {}))
    fix_attempts = state.get("sandbox_fix_attempts", 0)
    template_name = state.get("template_name", "react-vite")
    deps_installed = bool(state.get("sandbox_deps_installed", False))
    previous_pkg_hash = state.get("sandbox_package_json_hash")

    generated_files, renamed_config = enforce_nextjs_config_filename(generated_files, template_name)
    if renamed_config:
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stderr",
            "text": "Enforced next.config.mjs before writing files to sandbox.",
        })

    await ws_send(sid, {"type": "sandbox_status", "status": "creating"})

    sandbox_id = state.get("sandbox_id")
    template_id = get_template_id(template_name)
    sandbox_id, reused_existing = await sandbox_manager.ensure_sandbox(sid, sandbox_id, template=template_id)
    if not reused_existing:
        deps_installed = False

    await ws_send(sid, {"type": "sandbox_status", "status": "writing_files"})

    # Build file map from generated files
    file_map = {
        path: f.get("file_contents", "")
        for path, f in generated_files.items()
    }

    # Inject overlay.js for visual editing
    # Read overlay.js from frontend static directory and add to sandbox
    overlay_js_path = Path(__file__).parent.parent.parent.parent / "frontend" / "static" / "overlay.js"
    if overlay_js_path.exists():
        file_map["public/overlay.js"] = overlay_js_path.read_text(encoding="utf-8")
        logger.debug("Injected overlay.js into sandbox public directory")
    else:
        # Fallback: try alternative path
        alt_overlay_path = Path(__file__).parent.parent.parent.parent / "static" / "overlay.js"
        if alt_overlay_path.exists():
            file_map["public/overlay.js"] = alt_overlay_path.read_text(encoding="utf-8")
            logger.debug("Injected overlay.js from static directory")
        else:
            logger.warning("overlay.js not found, visual editing will not work")

    # Ensure template UI components and lib files are included (for vite dev type checking)
    template_details = state.get("template_details", {})
    template_all_files = template_details.get("all_files", {})
    dont_touch_files = template_details.get("dont_touch_files", [])

    # Add template files that are not in generated_files (e.g., UI components, lib utils)
    for template_path in template_all_files:
        if template_path not in file_map and template_path not in dont_touch_files:
            # Try to get content from generated_files first, then from template service
            if template_path in generated_files:
                file_map[template_path] = generated_files[template_path].get("file_contents", "")
            else:
                # Load from template service
                from services.template_service import get_template
                template = get_template(template_name)
                if template and template_path in template.all_files:
                    file_map[template_path] = template.all_files[template_path]
                    logger.debug("Adding template file to sandbox: %s", template_path)

    # Inject overlay.js script tag into index.html or Next.js layout for visual editing
    index_html_path = None
    layout_path = None
    for path in file_map:
        lower_path = path.lower()
        if lower_path.endswith('index.html') or lower_path.endswith('index.htm'):
            index_html_path = path
        elif 'layout.tsx' in lower_path or 'layout.jsx' in lower_path:
            layout_path = path

    script_tag = '<script src="/overlay.js"></script>'

    if index_html_path and index_html_path in file_map:
        # Vite/React projects: inject into index.html
        index_content = file_map[index_html_path]
        if '</body>' in index_content:
            index_content = index_content.replace('</body>', f'{script_tag}\n</body>')
            file_map[index_html_path] = index_content
            logger.debug("Injected overlay.js script tag into %s", index_html_path)
        elif '</head>' in index_content:
            index_content = index_content.replace('</head>', f'{script_tag}\n</head>')
            file_map[index_html_path] = index_content
            logger.debug("Injected overlay.js script tag into %s head", index_html_path)
    elif layout_path and layout_path in file_map:
        # Next.js projects: inject into layout.tsx/jsx using next/script
        layout_content = file_map[layout_path]
        # Add Script import if not present
        if 'next/script' not in layout_content:
            # Try to find import section and add Script import
            import_match = layout_content.find('import ')
            if import_match != -1:
                # Add after the last import
                last_import = layout_content.rfind('import ')
                last_import_end = layout_content.find('\n', last_import) + 1
                script_import = "import Script from 'next/script';\n"
                layout_content = layout_content[:last_import_end] + script_import + layout_content[last_import_end:]

        # Add Script component before closing </html> or </body> or at the end
        script_component = '<Script src="/overlay.js" strategy="beforeInteractive" />'
        if '</body>' in layout_content:
            layout_content = layout_content.replace('</body>', f'{script_component}\n</body>')
            file_map[layout_path] = layout_content
            logger.debug("Injected overlay.js Script component into %s", layout_path)
        elif '</html>' in layout_content:
            layout_content = layout_content.replace('</html>', f'{script_component}\n</html>')
            file_map[layout_path] = layout_content
            logger.debug("Injected overlay.js Script component into %s", layout_path)

    await sandbox_manager.write_files(sid, file_map)

    current_pkg_hash = _package_json_hash(generated_files)
    package_changed = bool(current_pkg_hash and current_pkg_hash != previous_pkg_hash)
    needs_install = (not deps_installed) or package_changed
    if package_changed:
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stderr",
            "text": "Detected package.json changes; reinstalling dependencies.",
        })
    if not needs_install:
        node_modules_check = await sandbox_manager.execute_command(
            sid,
            "bash -lc \"cd /home/user/project && if [ -d node_modules ]; then echo READY; else echo MISSING; fi\"",
            timeout=10,
        )
        needs_install = "READY" not in (node_modules_check.get("stdout") or "")

    if needs_install:
        await ws_send(sid, {"type": "sandbox_status", "status": "installing"})
        install_result = await sandbox_manager.execute_command(
            sid,
            "bash -lc \"cd /home/user/project && npm install\"",
            timeout=120,
        )
    else:
        install_result = {"stdout": "Reusing existing node_modules; skipping npm install.", "stderr": "", "exit_code": 0}
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stdout",
            "text": install_result["stdout"],
        })

    if install_result["stdout"] and needs_install:
        await _send_log_chunks(sid, "stdout", install_result["stdout"])
    if install_result["stderr"]:
        await _send_log_chunks(sid, "stderr", install_result["stderr"])

    if install_result["exit_code"] != 0:
        error_msg = install_result["stderr"] or install_result["stdout"]
        logger.warning("npm install failed for session %s: %s", sid, error_msg[:300])
        await ws_send(sid, {"type": "sandbox_error", "message": error_msg})

        if fix_attempts < MAX_FIX_ATTEMPTS:
            return {
                "generated_files": generated_files,
                "sandbox_id": sandbox_id,
                "sandbox_deps_installed": deps_installed,
                "sandbox_package_json_hash": current_pkg_hash,
                "sandbox_logs": error_msg,
                "current_dev_state": "sandbox_fixing",
            }
        return {
            "generated_files": generated_files,
            "sandbox_id": sandbox_id,
            "sandbox_deps_installed": deps_installed,
            "sandbox_package_json_hash": current_pkg_hash,
            "sandbox_logs": error_msg,
            "error": f"npm install failed after {fix_attempts} fix attempts",
            "current_dev_state": "finalizing",
        }
    deps_installed = True

    await ws_send(sid, {"type": "sandbox_status", "status": "validating"})
    validation_failures: list[tuple[str, str]] = []
    for step_name, command, timeout, optional in _validation_steps_for_template(template_name):
        result = await sandbox_manager.execute_command(sid, command, timeout=timeout)
        stdout = (result.get("stdout") or "").strip()
        stderr = (result.get("stderr") or "").strip()

        if stdout:
            await _send_log_chunks(sid, "stdout", stdout, step_name=step_name)
        if stderr:
            await _send_log_chunks(sid, "stderr", stderr, step_name=step_name)

        if int(result.get("exit_code", 1)) == 0:
            continue
        if optional and _is_missing_optional_script(result):
            await ws_send(sid, {
                "type": "sandbox_log",
                "stream": "stderr",
                "text": f"[{step_name}] optional step skipped (script missing).",
            })
            continue

        detail = "\n".join(part for part in [stderr, stdout] if part).strip() or "Command failed"
        validation_failures.append((step_name, detail))

    if validation_failures:
        error_msg = _format_validation_errors(validation_failures)
        await ws_send(sid, {"type": "sandbox_error", "message": error_msg})
        if fix_attempts < MAX_FIX_ATTEMPTS:
            return {
                "generated_files": generated_files,
                "sandbox_id": sandbox_id,
                "sandbox_deps_installed": deps_installed,
                "sandbox_package_json_hash": current_pkg_hash,
                "sandbox_logs": error_msg,
                "current_dev_state": "sandbox_fixing",
            }
        return {
            "generated_files": generated_files,
            "sandbox_id": sandbox_id,
            "sandbox_deps_installed": deps_installed,
            "sandbox_package_json_hash": current_pkg_hash,
            "sandbox_logs": error_msg,
            "error": "Validation/build failed after retries",
            "current_dev_state": "finalizing",
        }


    # Determine start command and port based on template
    # Using vite dev/next dev for HMR (Hot Module Replacement) support
    if template_name == "nextjs":
        dev_commands = [
            f"NODE_OPTIONS='--max-old-space-size={NODE_MAX_OLD_SPACE_MB}' npx next dev -H 0.0.0.0 -p 3000",
            f"NODE_OPTIONS='--max-old-space-size={NODE_MAX_OLD_SPACE_MB}' npm run dev -- -H 0.0.0.0 -p 3000",
        ]
        dev_port = 3000
        dev_process = "next"
    else:
        dev_commands = [
            f"NODE_OPTIONS='--max-old-space-size={NODE_MAX_OLD_SPACE_MB}' npx vite dev --host 0.0.0.0 --port 5173",
            f"NODE_OPTIONS='--max-old-space-size={NODE_MAX_OLD_SPACE_MB}' npm run dev -- --host 0.0.0.0 --port 5173",
        ]
        dev_port = 5173
        dev_process = "vite"

    await ws_send(sid, {"type": "sandbox_status", "status": "starting_server"})
    preview_url = None
    last_server_logs = ""
    await sandbox_manager.execute_command(sid, f"rm -f {DEV_SERVER_LOG_PATH} || true", timeout=10)

    for start_attempt in range(1, DEV_SERVER_START_ATTEMPTS + 1):
        already_open = await sandbox_manager.is_port_open(sid, dev_port)
        if already_open:
            preview_url = await sandbox_manager.get_preview_url(sid, port=dev_port)
            await ws_send(sid, {
                "type": "sandbox_status",
                "status": "server_already_running",
                "attempt": start_attempt,
            })
            break

        await ws_send(sid, {
            "type": "sandbox_status",
            "status": "starting_server_attempt",
            "attempt": start_attempt,
        })
        await sandbox_manager.execute_command(
            sid,
            f"pkill -f '{dev_process}' >/dev/null 2>&1 || true",
            timeout=10,
        )
        cmd_idx = (start_attempt - 1) % len(dev_commands)
        dev_command = dev_commands[cmd_idx]
        try:
            await sandbox_manager.run_background(
                sid,
                f"bash -lc \"cd /home/user/project && {dev_command} > {DEV_SERVER_LOG_PATH} 2>&1\"",
            )
            await ws_send(sid, {
                "type": "sandbox_status",
                "status": "server_command_started",
                "attempt": start_attempt,
                "command_index": cmd_idx + 1,
                "command": dev_command,
            })
        except Exception:
            logger.exception(
                "Failed to start dev server for session %s (attempt %d command %d)",
                sid, start_attempt, cmd_idx + 1,
            )
            await ws_send(sid, {
                "type": "sandbox_error",
                "message": f"Dev server launch command failed on attempt {start_attempt} (command {cmd_idx + 1})",
            })
            continue

        for poll_idx in range(DEV_SERVER_POLL_STEPS):
            await asyncio.sleep(2)
            port_open = await sandbox_manager.is_port_open(sid, dev_port)
            if port_open:
                preview_url = await sandbox_manager.get_preview_url(sid, port=dev_port)
                await sandbox_manager.extend_timeout(sid, timeout=3600)
                break
            if poll_idx >= 3:
                still_running = await sandbox_manager.is_process_running(sid, dev_process)
                if not still_running:
                    logger.warning("%s process died for session %s (attempt %d)", dev_process, sid, start_attempt)
                    break
            logger.debug(
                "Waiting for dev server (attempt %d/%d poll %d/%d) session %s",
                start_attempt,
                DEV_SERVER_START_ATTEMPTS,
                poll_idx + 1,
                DEV_SERVER_POLL_STEPS,
                sid,
            )
        if preview_url:
            break

        logs_result = await sandbox_manager.execute_command(
            sid,
            f"tail -n 120 {DEV_SERVER_LOG_PATH} || true",
            timeout=10,
        )
        last_server_logs = (logs_result.get("stdout", "") + "\n" + logs_result.get("stderr", "")).strip()
        if last_server_logs:
            await _send_log_chunks(
                sid,
                "stderr",
                last_server_logs,
                step_name=f"start attempt {start_attempt}",
            )
        await ws_send(sid, {
            "type": "sandbox_error",
            "message": f"Dev server start attempt {start_attempt} failed",
        })

    logger.info("Sandbox ready for session %s: preview=%s", sid, preview_url)

    if preview_url:
        await ws_send(sid, {"type": "sandbox_preview", "url": preview_url})
    else:
        error_msg = last_server_logs or "Dev server failed to start after retries"
        if fix_attempts < MAX_FIX_ATTEMPTS:
            return {
                "generated_files": generated_files,
                "sandbox_id": sandbox_id,
                "sandbox_deps_installed": deps_installed,
                "sandbox_package_json_hash": current_pkg_hash,
                "sandbox_logs": error_msg,
                "current_dev_state": "sandbox_fixing",
            }
        return {
            "generated_files": generated_files,
            "sandbox_id": sandbox_id,
            "sandbox_deps_installed": deps_installed,
            "sandbox_package_json_hash": current_pkg_hash,
            "sandbox_logs": error_msg,
            "error": "Dev server failed to start after retries",
            "current_dev_state": "finalizing",
        }

    return {
        "generated_files": generated_files,
        "sandbox_id": sandbox_id,
        "sandbox_deps_installed": deps_installed,
        "sandbox_package_json_hash": current_pkg_hash,
        "preview_url": preview_url,
        "sandbox_logs": "",
        "current_dev_state": "finalizing",
    }
