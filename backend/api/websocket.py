import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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


async def _run_generation(session_id: str, query: str, template: str):
    """Run the LangGraph code generation pipeline in background."""
    try:
        from agent.graph import run_codegen

        async def ws_send(msg: dict):
            await manager.send_to_session(session_id, msg)

        await run_codegen(
            session_id=session_id,
            user_query=query,
            template_name=template,
            ws_send_fn=ws_send,
        )
    except asyncio.CancelledError:
        await manager.send_to_session(session_id, {"type": "generation_stopped"})
    except Exception as e:
        logger.exception("Code generation failed for session %s", session_id)
        await manager.send_to_session(session_id, {"type": "error", "message": str(e)})


async def handle_client_message(session_id: str, data: dict[str, Any], websocket: WebSocket):
    """Process incoming WebSocket messages from the client."""
    msg_type = data.get("type", "")

    if msg_type == "session_init":
        query = data.get("query", "")
        template = data.get("template", "react-vite")
        await manager.send_to_session(session_id, {
            "type": "agent_connected",
            "state": {
                "session_id": session_id,
                "status": "idle",
                "generated_files_map": {},
                "generated_phases": [],
                "current_phase": 0,
                "should_be_generating": False,
                "conversation_messages": [],
            },
        })
        logger.info("Session initialized: session=%s, query=%s", session_id, query[:80])

    elif msg_type == "generate_all":
        query = data.get("query", "")
        template = data.get("template", "react-vite")

        if not query:
            logger.warning("generate_all with no query, session=%s", session_id)
            return

        manager.cancel_task(session_id)
        task = asyncio.create_task(_run_generation(session_id, query, template))
        manager._running_tasks[session_id] = task

    elif msg_type == "user_suggestion":
        message = data.get("message", "")
        await manager.send_to_session(session_id, {
            "type": "conversation_response",
            "content": f"Received your suggestion: \"{message}\". This will be applied in the next iteration.",
            "isStreaming": False,
        })

    elif msg_type == "stop_generation":
        manager.cancel_task(session_id)
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
