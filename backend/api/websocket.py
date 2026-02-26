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


manager = ConnectionManager()


def _normalize_message_role(role: str) -> str:
    if role in {"user", "assistant"}:
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

        state = {
            "session_id": session.id,
            "status": session.status,
            "generated_files_map": files_map,
            "generated_phases": generated_phases,
            "current_phase": current_phase,
            "should_be_generating": session.status == "generating",
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
                return

            if msg_type == "blueprint_generated":
                blueprint = msg.get("blueprint")
                if blueprint is not None:
                    await patch_session(db, session_id, blueprint=blueprint)
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
                return

            if msg_type in {"generation_complete", "generation_stopped"}:
                status = "completed" if msg_type == "generation_complete" else "stopped"
                updates: dict[str, Any] = {"status": status}
                if msg.get("preview_url"):
                    updates["preview_url"] = msg["preview_url"]
                await patch_session(db, session_id, **updates)
                return

            if msg_type in {"error", "sandbox_error"}:
                await patch_session(db, session_id, status="error")
                return

            if msg_type == "conversation_response":
                if not msg.get("isStreaming", False):
                    await _persist_message(session_id, "assistant", msg.get("content", ""))
                return
    except SQLAlchemyError:
        logger.exception("Failed to persist ws event for session %s, type=%s", session_id, msg_type)


async def _run_generation(session_id: str, query: str, template: str):
    """Run the LangGraph code generation pipeline in background."""
    try:
        from agent.graph import run_codegen

        async def ws_send(msg: dict):
            await _persist_ws_event(session_id, msg)
            await manager.send_to_session(session_id, msg)

        await run_codegen(
            session_id=session_id,
            user_query=query,
            template_name=template,
            ws_send_fn=ws_send,
        )
    except asyncio.CancelledError:
        await _persist_ws_event(session_id, {"type": "generation_stopped"})
        await manager.send_to_session(session_id, {"type": "generation_stopped"})
    except Exception as e:
        logger.exception("Code generation failed for session %s", session_id)
        await _persist_ws_event(session_id, {"type": "error", "message": str(e)})
        await manager.send_to_session(session_id, {"type": "error", "message": str(e)})


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
        logger.info("Session initialized: session=%s, query=%s", session_id, query[:80])

    elif msg_type == "generate_all":
        query = data.get("query", "")
        template = data.get("template", "react-vite")

        if not query:
            logger.warning("generate_all with no query, session=%s", session_id)
            return

        from db.crud import patch_session
        from db.database import async_session

        await _persist_message(session_id, "user", query)
        try:
            async with async_session() as db:
                await patch_session(db, session_id, template_name=template)
        except SQLAlchemyError:
            logger.exception("Failed to persist template for session %s", session_id)
        manager.cancel_task(session_id)
        task = asyncio.create_task(_run_generation(session_id, query, template))
        manager._running_tasks[session_id] = task

    elif msg_type == "user_suggestion":
        message = data.get("message", "")
        reply = {
            "type": "conversation_response",
            "content": f"Received your suggestion: \"{message}\". This will be applied in the next iteration.",
            "isStreaming": False,
        }
        await _persist_message(session_id, "user", message)
        await _persist_message(session_id, "assistant", reply["content"])
        await manager.send_to_session(session_id, reply)

    elif msg_type == "stop_generation":
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
        manager.cancel_task(session_id)
