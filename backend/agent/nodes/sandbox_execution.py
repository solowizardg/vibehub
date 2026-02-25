import asyncio
import logging

from agent.callback_registry import ws_send
from agent.file_constraints import enforce_nextjs_config_filename
from agent.state import CodeGenState

logger = logging.getLogger(__name__)

MAX_FIX_ATTEMPTS = 3
DEV_SERVER_START_ATTEMPTS = 3
DEV_SERVER_POLL_STEPS = 10
DEV_SERVER_LOG_PATH = "/tmp/devserver.log"


async def sandbox_execution_node(state: CodeGenState, config) -> dict:
    """Write all generated files to E2B sandbox, install deps, and start dev server."""
    from sandbox.e2b_backend import sandbox_manager

    sid = state.get("session_id", "")
    generated_files = dict(state.get("generated_files", {}))
    fix_attempts = state.get("sandbox_fix_attempts", 0)
    template_name = state.get("template_name", "react-vite")

    generated_files, renamed_config = enforce_nextjs_config_filename(generated_files, template_name)
    if renamed_config:
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stderr",
            "text": "Enforced next.config.mjs before writing files to sandbox.",
        })

    await ws_send(sid, {"type": "sandbox_status", "status": "creating"})

    sandbox_id = state.get("sandbox_id")
    if not sandbox_id:
        sandbox_id = await sandbox_manager.create_sandbox(sid)

    await ws_send(sid, {"type": "sandbox_status", "status": "writing_files"})

    file_map = {
        path: f.get("file_contents", "")
        for path, f in generated_files.items()
    }
    await sandbox_manager.write_files(sid, file_map)

    await ws_send(sid, {"type": "sandbox_status", "status": "installing"})
    install_result = await sandbox_manager.execute_command(sid, "npm install", timeout=120)

    await ws_send(sid, {
        "type": "sandbox_log",
        "stream": "stdout",
        "text": install_result["stdout"],
    })
    if install_result["stderr"]:
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stderr",
            "text": install_result["stderr"],
        })

    if install_result["exit_code"] != 0:
        error_msg = install_result["stderr"] or install_result["stdout"]
        logger.warning("npm install failed for session %s: %s", sid, error_msg[:300])
        await ws_send(sid, {"type": "sandbox_error", "message": error_msg})

        if fix_attempts < MAX_FIX_ATTEMPTS:
            return {
                "generated_files": generated_files,
                "sandbox_id": sandbox_id,
                "sandbox_logs": error_msg,
                "current_dev_state": "sandbox_fixing",
            }
        return {
            "generated_files": generated_files,
            "sandbox_id": sandbox_id,
            "sandbox_logs": error_msg,
            "error": f"npm install failed after {fix_attempts} fix attempts",
            "current_dev_state": "finalizing",
        }

    # Build first, then run production-style server.
    if template_name == "nextjs":
        build_command = "npm run build"
    else:
        build_command = "npm run build"

    await ws_send(sid, {"type": "sandbox_status", "status": "building"})
    build_result = await sandbox_manager.execute_command(sid, build_command, timeout=600)
    if build_result["stdout"]:
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stdout",
            "text": build_result["stdout"],
        })
    if build_result["stderr"]:
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stderr",
            "text": build_result["stderr"],
        })

    if build_result["exit_code"] != 0:
        error_msg = (build_result["stderr"] or build_result["stdout"]).strip() or "Build failed"
        await ws_send(sid, {"type": "sandbox_error", "message": error_msg})
        if fix_attempts < MAX_FIX_ATTEMPTS:
            return {
                "generated_files": generated_files,
                "sandbox_id": sandbox_id,
                "sandbox_logs": error_msg,
                "current_dev_state": "sandbox_fixing",
            }
        return {
            "generated_files": generated_files,
            "sandbox_id": sandbox_id,
            "sandbox_logs": error_msg,
            "error": "Build failed after retries",
            "current_dev_state": "finalizing",
        }

    # Determine start command and port based on template
    if template_name == "nextjs":
        dev_commands = [
            "npm run start -- -H 0.0.0.0 -p 3000",
            "npx next start -H 0.0.0.0 -p 3000",
        ]
        dev_port = 3000
        dev_process = "next"
    else:
        dev_commands = [
            "npm run preview -- --host 0.0.0.0 --port 4173",
            "npx vite preview --host 0.0.0.0 --port 4173",
        ]
        dev_port = 4173
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
        launch_ok = False
        for cmd_idx, dev_command in enumerate(dev_commands, start=1):
            try:
                await sandbox_manager.run_background(
                    sid,
                    f"bash -lc \"cd /home/user/project && {dev_command} > {DEV_SERVER_LOG_PATH} 2>&1\"",
                )
                await ws_send(sid, {
                    "type": "sandbox_status",
                    "status": "server_command_started",
                    "attempt": start_attempt,
                    "command_index": cmd_idx,
                })
                launch_ok = True
                break
            except Exception:
                logger.exception(
                    "Failed to start dev server for session %s (attempt %d command %d)",
                    sid, start_attempt, cmd_idx,
                )
        if not launch_ok:
            await ws_send(sid, {
                "type": "sandbox_error",
                "message": f"Dev server launch command failed on attempt {start_attempt}",
            })
            continue

        for poll_idx in range(DEV_SERVER_POLL_STEPS):
            await asyncio.sleep(2)
            port_open = await sandbox_manager.is_port_open(sid, dev_port)
            if port_open:
                preview_url = await sandbox_manager.get_preview_url(sid, port=dev_port)
                await sandbox_manager.extend_timeout(sid, timeout=900)
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
            await ws_send(sid, {
                "type": "sandbox_log",
                "stream": "stderr",
                "text": f"[start attempt {start_attempt}] {last_server_logs}",
            })
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
                "sandbox_logs": error_msg,
                "current_dev_state": "sandbox_fixing",
            }
        return {
            "generated_files": generated_files,
            "sandbox_id": sandbox_id,
            "sandbox_logs": error_msg,
            "error": "Dev server failed to start after retries",
            "current_dev_state": "finalizing",
        }

    return {
        "generated_files": generated_files,
        "sandbox_id": sandbox_id,
        "preview_url": preview_url,
        "sandbox_logs": "",
        "current_dev_state": "finalizing",
    }
