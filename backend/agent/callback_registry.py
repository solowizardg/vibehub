"""Global callback registry for WebSocket push functions.

Since LangGraph checkpointer serializes state, we cannot store callables
in the graph state. Instead, we register ws_send callbacks keyed by session_id
and look them up at runtime inside graph nodes.
"""

from typing import Any, Callable, Coroutine

_callbacks: dict[str, Callable[[dict[str, Any]], Coroutine[Any, Any, None]]] = {}


def register_ws_callback(session_id: str, callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]]):
    _callbacks[session_id] = callback


def unregister_ws_callback(session_id: str):
    _callbacks.pop(session_id, None)


async def ws_send(session_id: str, message: dict[str, Any]):
    cb = _callbacks.get(session_id)
    if cb:
        await cb(message)
