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
        self._pending_suggestions: dict[str, list[str]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self._connections:
            self._connections[session_id] = []
        self._connections[session_id].append(websocket)
        logger.info("WebSocket connected: session=%s", session_id)

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self._connections:
            self._connections[session_id] = [ws for ws in self._connections[session_id] if ws != websocket]
            if not self._connections[session_id]:
                del self._connections[session_id]
        logger.info("WebSocket disconnected: session=%s", session_id)

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

    def queue_suggestion(self, session_id: str, suggestion: str):
        if not suggestion:
            return
        self._pending_suggestions.setdefault(session_id, []).append(suggestion)

    def pop_pending_suggestions(self, session_id: str) -> list[str]:
        return self._pending_suggestions.pop(session_id, [])

    def clear_pending_suggestions(self, session_id: str):
        self._pending_suggestions.pop(session_id, None)


manager = ConnectionManager()


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


async def _load_generation_context(
    session_id: str,
    fallback_query: str,
    fallback_template: str,
) -> tuple[str, str, dict[str, Any], dict[str, Any] | None]:
    from db.crud import get_session
    from db.database import async_session

    async with async_session() as db:
        session = await get_session(db, session_id)

    template_name = fallback_template or "react-vite"
    effective_query = fallback_query.strip()
    existing_files: dict[str, Any] = {}
    existing_blueprint: dict[str, Any] | None = None

    if session:
        template_name = session.template_name or template_name
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

    return effective_query, template_name, existing_files, existing_blueprint


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

        effective_query, template_name, existing_files, existing_blueprint = await _load_generation_context(
            session_id=session_id,
            fallback_query=query,
            fallback_template=template,
        )

        async def ws_send(msg: dict):
            await _persist_ws_event(session_id, msg)
            await manager.send_to_session(session_id, msg)

        await run_codegen(
            session_id=session_id,
            user_query=effective_query,
            template_name=template_name,
            existing_files=existing_files,
            existing_blueprint=existing_blueprint,
            ws_send_fn=ws_send,
        )
        await _drain_pending_suggestions(session_id, template_name)
    except asyncio.CancelledError:
        await _persist_ws_event(session_id, {"type": "generation_stopped"})
        await manager.send_to_session(session_id, {"type": "generation_stopped"})
    except Exception as e:
        logger.exception("Code generation failed for session %s", session_id)
        await _persist_ws_event(session_id, {"type": "error", "message": str(e)})
        await manager.send_to_session(session_id, {"type": "error", "message": str(e)})


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
        state, preview_url = await _build_agent_state(session_id)
        if state is None:
            await manager.send_to_session(session_id, {"type": "error", "message": "Session not found"})
            return
        payload: dict[str, Any] = {
            "type": "agent_connected",
            "state": state,
        }
        if preview_url:
            payload["preview_url"] = preview_url
        await manager.send_to_session(session_id, payload)
        resumed = await _resume_generation_if_needed(session_id)
        if resumed:
            await manager.send_to_session(session_id, {
                "type": "conversation_response",
                "content": "Detected an unfinished generation task and resumed it automatically.",
                "isStreaming": False,
            })
        logger.info("Session initialized: session=%s, query=%s", session_id, query[:80])

    elif msg_type == "generate_all":
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
        manager.clear_pending_suggestions(session_id)
        manager.cancel_task(session_id)
        await _persist_ws_event(session_id, {"type": "generation_stopped"})
        await manager.send_to_session(session_id, {"type": "generation_stopped"})

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
