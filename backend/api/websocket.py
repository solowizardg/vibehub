import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections per session."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._rebuild_tasks: dict[str, asyncio.Task] = {}
        self._pending_suggestions: dict[str, list[str]] = {}
        self._connection_read_only: dict[WebSocket, bool] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self._connections:
            self._connections[session_id] = []
        self._connections[session_id].append(websocket)
        self._connection_read_only[websocket] = False
        logger.info("WebSocket connected: session=%s", session_id)

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self._connections:
            self._connections[session_id] = [ws for ws in self._connections[session_id] if ws != websocket]
            if not self._connections[session_id]:
                del self._connections[session_id]
                self.cancel_rebuild_task(session_id)
        self._connection_read_only.pop(websocket, None)
        logger.info("WebSocket disconnected: session=%s", session_id)

    def set_read_only(self, websocket: WebSocket, read_only: bool):
        self._connection_read_only[websocket] = read_only

    def is_read_only(self, websocket: WebSocket) -> bool:
        return self._connection_read_only.get(websocket, False)

    async def send_to_session(self, session_id: str, message: dict[str, Any]):
        if session_id not in self._connections:
            return
        data = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in self._connections[session_id]:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, session_id)

    def cancel_task(self, session_id: str):
        task = self._running_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()

    def is_generating(self, session_id: str) -> bool:
        task = self._running_tasks.get(session_id)
        return bool(task and not task.done())

    def start_task(self, session_id: str, coro: Any) -> asyncio.Task:
        current = self._running_tasks.get(session_id)
        current_task = asyncio.current_task()
        if current and not current.done() and current is not current_task:
            current.cancel()
        task = asyncio.create_task(coro)
        self._running_tasks[session_id] = task

        def _cleanup(done_task: asyncio.Task):
            current = self._running_tasks.get(session_id)
            if current is done_task:
                self._running_tasks.pop(session_id, None)

        task.add_done_callback(_cleanup)
        return task

    def cancel_rebuild_task(self, session_id: str):
        task = self._rebuild_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()

    def start_rebuild_task(self, session_id: str, coro: Any) -> asyncio.Task:
        current = self._rebuild_tasks.get(session_id)
        if current and not current.done():
            current.cancel()
        task = asyncio.create_task(coro)
        self._rebuild_tasks[session_id] = task

        def _cleanup(done_task: asyncio.Task):
            current = self._rebuild_tasks.get(session_id)
            if current is done_task:
                self._rebuild_tasks.pop(session_id, None)

        task.add_done_callback(_cleanup)
        return task

    def queue_suggestion(self, session_id: str, suggestion: str):
        if not suggestion:
            return
        self._pending_suggestions.setdefault(session_id, []).append(suggestion)

    def pop_pending_suggestions(self, session_id: str) -> list[str]:
        return self._pending_suggestions.pop(session_id, [])

    def clear_pending_suggestions(self, session_id: str):
        self._pending_suggestions.pop(session_id, None)


manager = ConnectionManager()


async def _send_to_websocket(websocket: WebSocket, message: dict[str, Any]):
    try:
        await websocket.send_text(json.dumps(message))
    except Exception:
        logger.exception("Failed to send message to websocket")


async def _send_read_only_notice(websocket: WebSocket):
    await _send_to_websocket(
        websocket,
        {
            "type": "conversation_response",
            "content": "This historical project is read-only. Create a new project to apply changes.",
            "isStreaming": False,
        },
    )


async def _emit_ws_event(session_id: str, msg: dict[str, Any]):
    await _persist_ws_event(session_id, msg)
    await manager.send_to_session(session_id, msg)


def _normalize_message_role(role: str) -> str:
    if role in {"user", "assistant", "system"}:
        return role
    return "assistant"


async def _persist_message(session_id: str, role: str, content: str):
    if not content:
        return
    from db.crud import add_message
    from db.database import async_session

    try:
        async with async_session() as db:
            await add_message(db, session_id=session_id, role=role, content=content)
    except SQLAlchemyError:
        logger.exception("Failed to persist message for session %s", session_id)


def _event_to_system_message(msg_type: str, msg: dict[str, Any]) -> str | None:
    if msg_type == "generation_started":
        return "Starting generation..."
    if msg_type == "blueprint_variants_generating":
        count = int(msg.get("count", 3))
        return f"Generating {count} blueprint variants..."
    if msg_type == "blueprint_variants_generated":
        return "Blueprint variants ready. Please select one to continue."
    if msg_type == "blueprint_selected":
        variant_id = str(msg.get("variant_id", "")).strip()
        return f"Variant selected: {variant_id}. Starting implementation..."
    if msg_type == "blueprint_generated":
        blueprint = msg.get("blueprint", {})
        if isinstance(blueprint, dict):
            project_name = str(blueprint.get("project_name", "")).strip()
            if project_name:
                return f"Blueprint ready: {project_name}"
        return "Blueprint ready."
    if msg_type == "phase_generating":
        phase = msg.get("phase", {})
        if isinstance(phase, dict):
            index = int(phase.get("index", 0)) + 1
            name = str(phase.get("name", f"Phase {index}")).strip()
            return f"Planning phase {index}: {name}"
        return "Planning next phase..."
    if msg_type == "phase_implementing":
        phase_index = int(msg.get("phase_index", -1))
        if phase_index >= 0:
            return f"Implementing phase {phase_index + 1}..."
        return "Implementing phase..."
    if msg_type == "phase_implemented":
        phase_index = int(msg.get("phase_index", -1))
        if phase_index >= 0:
            return f"Phase {phase_index + 1} completed."
        return "Phase completed."
    if msg_type == "phase_validated":
        phase_index = int(msg.get("phase_index", -1))
        if phase_index >= 0:
            return f"Phase {phase_index + 1} validated."
        return "Phase validated."
    if msg_type == "sandbox_status":
        status = str(msg.get("status", "")).strip()
        labels: dict[str, str] = {
            "creating": "Creating sandbox environment...",
            "writing_files": "Writing files to sandbox...",
            "installing": "Installing dependencies...",
            "validating": "Running validation checks...",
            "building": "Building project...",
            "starting_server": "Starting preview server...",
            "starting_server_attempt": f"Starting preview server (attempt {msg.get('attempt', '?')})...",
            "server_command_started": f"Preview command launched (attempt {msg.get('attempt', '?')})...",
            "server_already_running": "Preview server already running.",
            "fixing": f"Fixing sandbox issues (attempt {msg.get('attempt', '?')})...",
        }
        return labels.get(status, f"Sandbox: {status}") if status else None
    if msg_type == "sandbox_preview":
        url = str(msg.get("url", "")).strip()
        return f"Preview ready: {url}" if url else "Preview ready."
    if msg_type == "generation_complete":
        return "Generation completed."
    if msg_type == "generation_stopped":
        return "Generation stopped."
    if msg_type == "error":
        err = str(msg.get("message", "")).strip()
        return f"Generation error: {err}" if err else "Generation error."
    if msg_type == "sandbox_error":
        err = str(msg.get("message", "")).strip()
        return f"Sandbox error: {err}" if err else "Sandbox error."
    return None


async def _build_agent_state(session_id: str) -> tuple[dict[str, Any] | None, str | None]:
    from db.crud import get_session
    from db.database import async_session

    async with async_session() as db:
        session = await get_session(db, session_id)
        if not session:
            return None, None

        files_map: dict[str, dict[str, Any]] = {}
        sorted_files = sorted(session.files, key=lambda f: (f.phase_index, f.file_path))
        for f in sorted_files:
            files_map[f.file_path] = {
                "filePath": f.file_path,
                "fileContents": f.file_contents,
                "language": f.language,
                "phaseIndex": f.phase_index,
            }

        sorted_phases = sorted(session.phases, key=lambda p: p.phase_index)
        generated_phases = [
            {
                "index": p.phase_index,
                "name": p.name,
                "description": p.description,
                "status": p.status,
                "files": p.files or [],
            }
            for p in sorted_phases
        ]

        current_phase = len(generated_phases)
        for phase in generated_phases:
            if phase["status"] != "completed":
                current_phase = phase["index"]
                break

        sorted_messages = sorted(session.messages, key=lambda m: m.created_at)
        conversation_messages = [
            {
                "role": _normalize_message_role(m.role),
                "content": m.content,
            }
            for m in sorted_messages
        ]

        should_be_generating = session.status == "generating" or manager.is_generating(session_id)
        status = "generating" if should_be_generating else session.status

        state = {
            "session_id": session.id,
            "status": status,
            "blueprint": session.blueprint,
            "blueprint_markdown": session.blueprint_markdown,
            "generated_files_map": files_map,
            "generated_phases": generated_phases,
            "current_phase": current_phase,
            "should_be_generating": should_be_generating,
            "conversation_messages": conversation_messages,
        }
        return state, session.preview_url


async def _persist_ws_event(session_id: str, msg: dict[str, Any]):
    from db.crud import get_phase, patch_session, upsert_file, upsert_phase
    from db.database import async_session

    msg_type = msg.get("type", "")

    try:
        async with async_session() as db:
            if msg_type == "generation_started":
                await patch_session(db, session_id, status="generating")
                event_text = _event_to_system_message(msg_type, msg)
                if event_text:
                    await _persist_message(session_id, "system", event_text)
                return

            if msg_type == "blueprint_generated":
                blueprint = msg.get("blueprint")
                blueprint_markdown = msg.get("blueprint_markdown")
                updates: dict[str, Any] = {}
                if blueprint is not None:
                    updates["blueprint"] = blueprint
                if isinstance(blueprint_markdown, str):
                    updates["blueprint_markdown"] = blueprint_markdown
                if updates:
                    await patch_session(db, session_id, **updates)
                event_text = _event_to_system_message(msg_type, msg)
                if event_text:
                    await _persist_message(session_id, "system", event_text)
                return

            if msg_type == "blueprint_variants_generated":
                variants = msg.get("variants")
                if isinstance(variants, list):
                    await patch_session(db, session_id, blueprint_variants=variants)
                event_text = "Generated multiple blueprint variants for selection"
                await _persist_message(session_id, "system", event_text)
                return

            if msg_type == "phase_generating":
                phase = msg.get("phase", {})
                phase_index = int(phase.get("index", -1))
                if phase_index >= 0:
                    await upsert_phase(
                        db,
                        session_id=session_id,
                        phase_index=phase_index,
                        name=phase.get("name", f"Phase {phase_index + 1}"),
                        description=phase.get("description", ""),
                        status=phase.get("status", "generating"),
                        files=phase.get("files", []),
                    )
                event_text = _event_to_system_message(msg_type, msg)
                if event_text:
                    await _persist_message(session_id, "system", event_text)
                return

            if msg_type in {"phase_implementing", "phase_implemented"}:
                phase_index = int(msg.get("phase_index", -1))
                if phase_index >= 0:
                    existing = await get_phase(db, session_id, phase_index)
                    existing_name = existing.name if existing else f"Phase {phase_index + 1}"
                    existing_description = existing.description if existing else ""
                    existing_files = existing.files if existing else []
                    next_status = "implementing" if msg_type == "phase_implementing" else "completed"
                    await upsert_phase(
                        db,
                        session_id=session_id,
                        phase_index=phase_index,
                        name=existing_name,
                        description=existing_description,
                        status=next_status,
                        files=existing_files,
                    )
                event_text = _event_to_system_message(msg_type, msg)
                if event_text:
                    await _persist_message(session_id, "system", event_text)
                return

            if msg_type == "phase_validated":
                event_text = _event_to_system_message(msg_type, msg)
                if event_text:
                    await _persist_message(session_id, "system", event_text)
                return

            if msg_type == "file_generated":
                file_path = msg.get("filePath")
                file_contents = msg.get("fileContents", "")
                if file_path:
                    phase_index = int(msg.get("phaseIndex", 0))
                    await upsert_file(
                        db,
                        session_id=session_id,
                        file_path=file_path,
                        file_contents=file_contents,
                        language=msg.get("language", "plaintext"),
                        phase_index=phase_index,
                    )
                return

            if msg_type == "sandbox_preview":
                url = msg.get("url")
                if url:
                    await patch_session(db, session_id, preview_url=url)
                event_text = _event_to_system_message(msg_type, msg)
                if event_text:
                    await _persist_message(session_id, "system", event_text)
                return

            if msg_type == "sandbox_status":
                event_text = _event_to_system_message(msg_type, msg)
                if event_text:
                    await _persist_message(session_id, "system", event_text)
                return

            if msg_type in {"generation_complete", "generation_stopped"}:
                status = "completed" if msg_type == "generation_complete" else "stopped"
                updates: dict[str, Any] = {"status": status}
                if msg.get("preview_url"):
                    updates["preview_url"] = msg["preview_url"]
                await patch_session(db, session_id, **updates)
                event_text = _event_to_system_message(msg_type, msg)
                if event_text:
                    await _persist_message(session_id, "system", event_text)
                return

            if msg_type in {"error", "sandbox_error"}:
                await patch_session(db, session_id, status="error")
                event_text = _event_to_system_message(msg_type, msg)
                if event_text:
                    await _persist_message(session_id, "system", event_text)
                return

            if msg_type == "conversation_response":
                if not msg.get("isStreaming", False):
                    await _persist_message(session_id, "assistant", msg.get("content", ""))
                return
    except SQLAlchemyError:
        logger.exception("Failed to persist ws event for session %s, type=%s", session_id, msg_type)


async def _handle_file_edit(session_id: str, file_path: str, file_contents: str):
    """Handle file edit from client: persist to DB and write to sandbox."""
    from db.crud import upsert_file
    from db.database import async_session
    from sandbox.e2b_backend import sandbox_manager

    # Persist to database
    try:
        async with async_session() as db:
            await upsert_file(
                db,
                session_id=session_id,
                file_path=file_path,
                file_contents=file_contents,
                language="plaintext",  # Language detection can be improved
                phase_index=0,  # User edits are considered phase 0
            )
    except SQLAlchemyError:
        logger.exception("Failed to persist file edit for session %s, file %s", session_id, file_path)
        return

    # Write to sandbox if it exists
    try:
        sandbox_id = sandbox_manager.get_sandbox_id(session_id)
        if sandbox_id:
            await sandbox_manager.write_file(session_id, file_path, file_contents)
            await manager.send_to_session(session_id, {
                "type": "sandbox_log",
                "stream": "stdout",
                "text": f"File updated: {file_path}",
            })
    except Exception:
        logger.exception("Failed to write file to sandbox for session %s, file %s", session_id, file_path)


async def _handle_variant_selection(session_id: str, variant_id: str):
    """Handle user selection of a blueprint variant and continue generation."""
    from db.crud import get_session, patch_session
    from db.database import async_session
    from sqlalchemy.exc import SQLAlchemyError

    logger.info("Handling variant selection: session=%s, variant_id=%s", session_id, variant_id)

    try:
        # Persist the selected variant to database
        async with async_session() as db:
            await patch_session(db, session_id, selected_variant_id=variant_id)

        # Load session context
        session = None
        async with async_session() as db:
            session = await get_session(db, session_id)

        if not session:
            logger.error("Session not found for variant selection: %s", session_id)
            await manager.send_to_session(session_id, {
                "type": "error",
                "message": "Session not found",
            })
            return

        # Check if we have variants
        blueprint_variants = session.blueprint_variants if isinstance(session.blueprint_variants, list) else []
        if not blueprint_variants:
            logger.error("No blueprint variants found for session %s", session_id)
            await manager.send_to_session(session_id, {
                "type": "error",
                "message": "No blueprint variants available",
            })
            return

        # Find the selected variant
        selected_variant = next((v for v in blueprint_variants if v.get("variant_id") == variant_id), None)
        if not selected_variant:
            logger.error("Selected variant %s not found in session %s", variant_id, session_id)
            await manager.send_to_session(session_id, {
                "type": "error",
                "message": f"Variant {variant_id} not found",
            })
            return

        # Get query from session
        user_query = session.title or "Continue implementation"

        # Notify frontend that variant is selected and generation is resuming
        await manager.send_to_session(session_id, {
            "type": "blueprint_selected",
            "variant_id": variant_id,
            "blueprint": selected_variant,
            "blueprint_markdown": selected_variant.get("blueprint_markdown", ""),
        })

        # Start generation with selected variant
        manager.start_task(
            session_id,
            _run_generation_with_variant(session_id, user_query, session.template_name or "react-vite", blueprint_variants, variant_id)
        )

    except SQLAlchemyError as e:
        logger.exception("Database error during variant selection for session %s", session_id)
        await manager.send_to_session(session_id, {
            "type": "error",
            "message": f"Failed to save variant selection: {str(e)}",
        })
    except Exception as e:
        logger.exception("Error during variant selection for session %s", session_id)
        await manager.send_to_session(session_id, {
            "type": "error",
            "message": f"Failed to process variant selection: {str(e)}",
        })


async def _run_generation_with_variant(
    session_id: str,
    query: str,
    template: str,
    blueprint_variants: list[dict],
    selected_variant_id: str,
):
    """Run generation with a specific blueprint variant selected."""
    try:
        from agent.graph import run_codegen

        effective_query = query
        template_name = template
        existing_files: dict[str, Any] = {}
        existing_sandbox_id: str | None = None

        # Load existing files and sandbox
        from db.crud import get_session
        from db.database import async_session

        async with async_session() as db:
            session = await get_session(db, session_id)
            if session:
                template_name = session.template_name or template_name
                existing_sandbox_id = session.sandbox_id
                for f in session.files:
                    existing_files[f.file_path] = {
                        "file_path": f.file_path,
                        "file_contents": f.file_contents,
                        "language": f.language,
                        "phase_index": f.phase_index,
                    }

        async def ws_send(msg: dict):
            await _emit_ws_event(session_id, msg)

        final_state = await run_codegen(
            session_id=session_id,
            user_query=effective_query,
            template_name=template_name,
            existing_files=existing_files,
            existing_blueprint=None,  # Will be set from selected variant
            existing_sandbox_id=existing_sandbox_id,
            ws_send_fn=ws_send,
            blueprint_variants=blueprint_variants,
            selected_variant_id=selected_variant_id,
        )

        sandbox_id = final_state.get("sandbox_id") if isinstance(final_state, dict) else None
        if isinstance(sandbox_id, str) and sandbox_id.strip():
            try:
                async with async_session() as db:
                    await patch_session(db, session_id, sandbox_id=sandbox_id.strip())
            except SQLAlchemyError:
                logger.exception("Failed to persist sandbox_id for session %s after generation", session_id)

    except asyncio.CancelledError:
        await _persist_ws_event(session_id, {"type": "generation_stopped"})
        await manager.send_to_session(session_id, {"type": "generation_stopped"})
    except Exception as e:
        logger.exception("Code generation failed for session %s", session_id)
        await _persist_ws_event(session_id, {"type": "error", "message": str(e)})
        await manager.send_to_session(session_id, {"type": "error", "message": str(e)})


async def _load_generation_context(
    session_id: str,
    fallback_query: str,
    fallback_template: str,
) -> tuple[str, str, dict[str, Any], dict[str, Any] | None, str | None]:
    from db.crud import get_session
    from db.database import async_session

    async with async_session() as db:
        session = await get_session(db, session_id)

    template_name = fallback_template or "react-vite"
    effective_query = fallback_query.strip()
    existing_files: dict[str, Any] = {}
    existing_blueprint: dict[str, Any] | None = None
    existing_sandbox_id: str | None = None

    if session:
        template_name = session.template_name or template_name
        existing_sandbox_id = session.sandbox_id
        if isinstance(session.blueprint, dict):
            existing_blueprint = session.blueprint
        for f in session.files:
            existing_files[f.file_path] = {
                "file_path": f.file_path,
                "file_contents": f.file_contents,
                "language": f.language,
                "phase_index": f.phase_index,
            }
        if not effective_query:
            user_messages = [m for m in session.messages if m.role == "user" and m.content.strip()]
            user_messages.sort(key=lambda m: m.created_at, reverse=True)
            if user_messages:
                effective_query = user_messages[0].content.strip()
            elif session.title:
                effective_query = session.title.strip()

    if not effective_query:
        effective_query = "Please continue improving the current project implementation."

    return effective_query, template_name, existing_files, existing_blueprint, existing_sandbox_id


async def _drain_pending_suggestions(session_id: str, template_name: str):
    pending = manager.pop_pending_suggestions(session_id)
    if not pending:
        return

    follow_up_query = "Please continue improving the current project and satisfy these additional requirements:\n" + "\n".join(f"- {s}" for s in pending)
    notify = "Captured your in-progress requests and starting the next modification round."

    await _persist_message(session_id, "assistant", notify)
    await manager.send_to_session(session_id, {
        "type": "conversation_response",
        "content": notify,
        "isStreaming": False,
    })
    manager.start_task(session_id, _run_generation(session_id, follow_up_query, template_name))


async def _run_generation(session_id: str, query: str, template: str):
    """Run the LangGraph code generation pipeline in background."""
    effective_query = query
    template_name = template
    try:
        from agent.graph import run_codegen

        effective_query, template_name, existing_files, existing_blueprint, existing_sandbox_id = await _load_generation_context(
            session_id=session_id,
            fallback_query=query,
            fallback_template=template,
        )

        async def ws_send(msg: dict):
            await _emit_ws_event(session_id, msg)

        final_state = await run_codegen(
            session_id=session_id,
            user_query=effective_query,
            template_name=template_name,
            existing_files=existing_files,
            existing_blueprint=existing_blueprint,
            existing_sandbox_id=existing_sandbox_id,
            ws_send_fn=ws_send,
        )

        sandbox_id = final_state.get("sandbox_id") if isinstance(final_state, dict) else None
        if isinstance(sandbox_id, str) and sandbox_id.strip():
            from db.crud import patch_session
            from db.database import async_session

            try:
                async with async_session() as db:
                    await patch_session(db, session_id, sandbox_id=sandbox_id.strip())
            except SQLAlchemyError:
                logger.exception("Failed to persist sandbox_id for session %s after generation", session_id)

        await _drain_pending_suggestions(session_id, template_name)
    except asyncio.CancelledError:
        await _persist_ws_event(session_id, {"type": "generation_stopped"})
        await manager.send_to_session(session_id, {"type": "generation_stopped"})
    except Exception as e:
        logger.exception("Code generation failed for session %s", session_id)
        await _persist_ws_event(session_id, {"type": "error", "message": str(e)})
        await manager.send_to_session(session_id, {"type": "error", "message": str(e)})


async def _rebuild_history_sandbox(session_id: str):
    """Rebuild sandbox preview environment from persisted historical files."""
    from sandbox.e2b_backend import sandbox_manager

    DEV_SERVER_START_ATTEMPTS = 3
    DEV_SERVER_POLL_STEPS = 10
    DEV_SERVER_LOG_PATH = "/tmp/devserver.log"

    try:
        _, template_name, existing_files, _, existing_sandbox_id = await _load_generation_context(
            session_id=session_id,
            fallback_query="",
            fallback_template="react-vite",
        )
        file_map = {
            path: str(file.get("file_contents", ""))
            for path, file in existing_files.items()
        }
        if not file_map:
            from services.template_service import get_template
            template = get_template(template_name)
            if not template or not template.all_files:
                await _emit_ws_event(session_id, {
                    "type": "sandbox_error",
                    "message": "No persisted files found for this historical project, and template fallback is unavailable.",
                })
                return

            file_map = dict(template.all_files)
            await manager.send_to_session(session_id, {
                "type": "sandbox_log",
                "stream": "stderr",
                "text": "No persisted files found; falling back to template snapshot for historical preview rebuild.",
            })

            # Backfill template snapshot so future historical opens can rebuild directly from DB.
            try:
                from db.crud import upsert_file
                from db.database import async_session

                async with async_session() as db:
                    for path, content in file_map.items():
                        await upsert_file(
                            db,
                            session_id=session_id,
                            file_path=path,
                            file_contents=content,
                            language="plaintext",
                            phase_index=-1,
                        )
            except SQLAlchemyError:
                logger.exception("Failed to backfill template snapshot for session %s", session_id)

        await _emit_ws_event(session_id, {"type": "sandbox_status", "status": "creating"})

        from sandbox.e2b_backend import get_template_id
        template_id = get_template_id(template_name)

        sandbox_id, _ = await sandbox_manager.ensure_sandbox(session_id, existing_sandbox_id, template=template_id)

        try:
            from db.crud import patch_session
            from db.database import async_session

            async with async_session() as db:
                await patch_session(db, session_id, sandbox_id=sandbox_id, preview_url=None)
        except SQLAlchemyError:
            logger.exception("Failed to persist sandbox_id for session %s", session_id)

        quick_port = 3000 if template_name == "nextjs" else 5173
        try:
            if await sandbox_manager.is_port_open(session_id, quick_port):
                preview_url = await sandbox_manager.get_preview_url(session_id, port=quick_port)
                if preview_url:
                    await sandbox_manager.extend_timeout(session_id, timeout=3600)
                    await _emit_ws_event(session_id, {"type": "sandbox_preview", "url": preview_url})
                    return
        except Exception:
            logger.exception("Failed quick sandbox reuse check for session %s", session_id)

        await _emit_ws_event(session_id, {"type": "sandbox_status", "status": "writing_files"})
        await sandbox_manager.write_files(session_id, file_map)

        await _emit_ws_event(session_id, {"type": "sandbox_status", "status": "installing"})
        install_result = await sandbox_manager.execute_command(session_id, "npm install", timeout=180)
        if install_result.get("stdout"):
            await manager.send_to_session(session_id, {
                "type": "sandbox_log",
                "stream": "stdout",
                "text": install_result["stdout"],
            })
        if install_result.get("stderr"):
            await manager.send_to_session(session_id, {
                "type": "sandbox_log",
                "stream": "stderr",
                "text": install_result["stderr"],
            })
        if int(install_result.get("exit_code", 1)) != 0:
            error_msg = (install_result.get("stderr") or install_result.get("stdout") or "npm install failed").strip()
            await _emit_ws_event(session_id, {"type": "sandbox_error", "message": error_msg})
            return

        # Note: Using vite dev/next dev for HMR (Hot Module Replacement) support
        # No need to run build first - dev server handles compilation on the fly
        if template_name == "nextjs":
            dev_commands = [
                "NODE_OPTIONS='--max-old-space-size=4096' npx next dev -H 0.0.0.0 -p 3000",
                "NODE_OPTIONS='--max-old-space-size=4096' npm run dev -- -H 0.0.0.0 -p 3000",
            ]
            dev_port = 3000
            dev_process = "next"
        else:
            dev_commands = [
                "NODE_OPTIONS='--max-old-space-size=4096' npx vite dev --host 0.0.0.0 --port 5173",
                "NODE_OPTIONS='--max-old-space-size=4096' npm run dev -- --host 0.0.0.0 --port 5173",
            ]
            dev_port = 5173
            dev_process = "vite"

        await _emit_ws_event(session_id, {"type": "sandbox_status", "status": "starting_server"})
        await sandbox_manager.execute_command(session_id, f"rm -f {DEV_SERVER_LOG_PATH} || true", timeout=10)

        preview_url = None
        last_server_logs = ""
        for start_attempt in range(1, DEV_SERVER_START_ATTEMPTS + 1):
            already_open = await sandbox_manager.is_port_open(session_id, dev_port)
            if already_open:
                preview_url = await sandbox_manager.get_preview_url(session_id, port=dev_port)
                await _emit_ws_event(session_id, {
                    "type": "sandbox_status",
                    "status": "server_already_running",
                    "attempt": start_attempt,
                })
                break

            await _emit_ws_event(session_id, {
                "type": "sandbox_status",
                "status": "starting_server_attempt",
                "attempt": start_attempt,
            })
            await sandbox_manager.execute_command(
                session_id,
                f"pkill -f '{dev_process}' >/dev/null 2>&1 || true",
                timeout=10,
            )

            launch_ok = False
            for cmd_idx, dev_command in enumerate(dev_commands, start=1):
                try:
                    await sandbox_manager.run_background(
                        session_id,
                        f"bash -lc \"cd /home/user/project && {dev_command} > {DEV_SERVER_LOG_PATH} 2>&1\"",
                    )
                    await _emit_ws_event(session_id, {
                        "type": "sandbox_status",
                        "status": "server_command_started",
                        "attempt": start_attempt,
                        "command_index": cmd_idx,
                    })
                    launch_ok = True
                    break
                except Exception:
                    logger.exception(
                        "Failed to start historical preview for session %s (attempt %d command %d)",
                        session_id, start_attempt, cmd_idx,
                    )
            if not launch_ok:
                await _emit_ws_event(session_id, {
                    "type": "sandbox_error",
                    "message": f"Dev server launch command failed on attempt {start_attempt}",
                })
                continue

            for poll_idx in range(DEV_SERVER_POLL_STEPS):
                await asyncio.sleep(2)
                if await sandbox_manager.is_port_open(session_id, dev_port):
                    preview_url = await sandbox_manager.get_preview_url(session_id, port=dev_port)
                    await sandbox_manager.extend_timeout(session_id, timeout=3600)
                    break
                if poll_idx >= 3:
                    still_running = await sandbox_manager.is_process_running(session_id, dev_process)
                    if not still_running:
                        break
            if preview_url:
                break

            logs_result = await sandbox_manager.execute_command(
                session_id,
                f"tail -n 120 {DEV_SERVER_LOG_PATH} || true",
                timeout=10,
            )
            last_server_logs = ((logs_result.get("stdout") or "") + "\n" + (logs_result.get("stderr") or "")).strip()
            if last_server_logs:
                await manager.send_to_session(session_id, {
                    "type": "sandbox_log",
                    "stream": "stderr",
                    "text": f"[start attempt {start_attempt}] {last_server_logs}",
                })
            await _emit_ws_event(session_id, {
                "type": "sandbox_error",
                "message": f"Dev server start attempt {start_attempt} failed",
            })

        if preview_url:
            await _emit_ws_event(session_id, {"type": "sandbox_preview", "url": preview_url})
        else:
            await _emit_ws_event(session_id, {
                "type": "sandbox_error",
                "message": last_server_logs or "Dev server failed to start after retries",
            })
    except asyncio.CancelledError:
        logger.info("Historical sandbox rebuild cancelled for session %s", session_id)
    except Exception as e:
        logger.exception("Historical sandbox rebuild failed for session %s", session_id)
        await _emit_ws_event(session_id, {"type": "sandbox_error", "message": str(e)})


async def _start_generation(
    session_id: str,
    query: str,
    template: str,
    persist_user_query: bool,
):
    from db.crud import patch_session
    from db.database import async_session

    if persist_user_query:
        await _persist_message(session_id, "user", query)

    try:
        async with async_session() as db:
            await patch_session(
                db,
                session_id,
                template_name=template,
                status="generating",
            )
    except SQLAlchemyError:
        logger.exception("Failed to persist generation start for session %s", session_id)

    manager.start_task(session_id, _run_generation(session_id, query, template))


async def _resume_generation_if_needed(session_id: str) -> bool:
    if manager.is_generating(session_id):
        return False

    from db.crud import get_session
    from db.database import async_session

    async with async_session() as db:
        session = await get_session(db, session_id)
        if not session or session.status != "generating":
            return False
        template_name = session.template_name or "react-vite"

    manager.start_task(session_id, _run_generation(session_id, "", template_name))
    return True


async def handle_client_message(session_id: str, data: dict[str, Any], websocket: WebSocket):
    """Process incoming WebSocket messages from the client."""
    msg_type = data.get("type", "")

    if msg_type == "session_init":
        query = data.get("query", "")
        read_only = bool(data.get("read_only", False))
        rebuild_sandbox = bool(data.get("rebuild_sandbox", False))
        manager.set_read_only(websocket, read_only)
        state, preview_url = await _build_agent_state(session_id)
        if state is None:
            await manager.send_to_session(session_id, {"type": "error", "message": "Session not found"})
            return
        state["read_only"] = read_only
        payload: dict[str, Any] = {
            "type": "agent_connected",
            "state": state,
        }
        if preview_url:
            payload["preview_url"] = preview_url
        await manager.send_to_session(session_id, payload)
        resumed = False
        if not read_only:
            resumed = await _resume_generation_if_needed(session_id)
        should_rebuild = (read_only or rebuild_sandbox) and not resumed and not manager.is_generating(session_id)
        if should_rebuild:
            manager.start_rebuild_task(session_id, _rebuild_history_sandbox(session_id))
        if resumed:
            await manager.send_to_session(session_id, {
                "type": "conversation_response",
                "content": "Detected an unfinished generation task and resumed it automatically.",
                "isStreaming": False,
            })
        logger.info("Session initialized: session=%s, query=%s", session_id, query[:80])

    elif msg_type == "generate_all":
        if manager.is_read_only(websocket):
            await _send_read_only_notice(websocket)
            return

        query = data.get("query", "")
        template = data.get("template", "react-vite")

        if not query:
            logger.warning("generate_all with no query, session=%s", session_id)
            return

        manager.clear_pending_suggestions(session_id)
        await _start_generation(
            session_id=session_id,
            query=query,
            template=template,
            persist_user_query=True,
        )

    elif msg_type == "user_suggestion":
        if manager.is_read_only(websocket):
            await _send_read_only_notice(websocket)
            return

        message = data.get("message", "").strip()
        if not message:
            return

        await _persist_message(session_id, "user", message)

        if manager.is_generating(session_id):
            manager.queue_suggestion(session_id, message)
            reply_text = "Request recorded. It will be applied automatically in the next round after current generation."
            await _persist_message(session_id, "assistant", reply_text)
            await manager.send_to_session(session_id, {
                "type": "conversation_response",
                "content": reply_text,
                "isStreaming": False,
            })
        else:
            from db.crud import get_session
            from db.database import async_session

            template = "react-vite"
            async with async_session() as db:
                session = await get_session(db, session_id)
                if session and session.template_name:
                    template = session.template_name

            reply_text = "Request received. Starting a new modification round based on the current code."
            await _persist_message(session_id, "assistant", reply_text)
            await manager.send_to_session(session_id, {
                "type": "conversation_response",
                "content": reply_text,
                "isStreaming": False,
            })
            await _start_generation(
                session_id=session_id,
                query=message,
                template=template,
                persist_user_query=False,
            )

    elif msg_type == "stop_generation":
        if manager.is_read_only(websocket):
            await _send_read_only_notice(websocket)
            return

        manager.clear_pending_suggestions(session_id)
        manager.cancel_task(session_id)
        await _persist_ws_event(session_id, {"type": "generation_stopped"})
        await manager.send_to_session(session_id, {"type": "generation_stopped"})

    elif msg_type == "select_blueprint_variant":
        """Handle user selection of a blueprint variant."""
        if manager.is_read_only(websocket):
            await _send_read_only_notice(websocket)
            return

        variant_id = data.get("variantId", "")
        if not variant_id:
            logger.warning("select_blueprint_variant with no variant_id, session=%s", session_id)
            return

        await _handle_variant_selection(session_id, variant_id)

    elif msg_type == "file_edit":
        if manager.is_read_only(websocket):
            await _send_read_only_notice(websocket)
            return

        file_path = data.get("filePath", "")
        file_contents = data.get("fileContents", "")
        if not file_path:
            return

        await _handle_file_edit(session_id, file_path, file_contents)

    else:
        logger.warning("Unknown message type: %s", msg_type)


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await handle_client_message(session_id, data, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
