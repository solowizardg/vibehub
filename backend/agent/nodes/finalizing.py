import logging

from agent.callback_registry import ws_send
from agent.state import CodeGenState

logger = logging.getLogger(__name__)


async def finalizing_node(state: CodeGenState, config) -> dict:
    """Finalize the code generation process."""
    sid = state.get("session_id", "")
    preview_url = state.get("preview_url")

    logger.info(
        "Finalizing session %s: %d files generated, preview=%s",
        sid,
        len(state.get("generated_files", {})),
        preview_url,
    )

    payload: dict = {"type": "generation_complete"}
    if preview_url:
        payload["preview_url"] = preview_url
    if state.get("error"):
        payload["error"] = state["error"]

    await ws_send(sid, payload)

    return {
        "current_dev_state": "idle",
        "should_continue": False,
    }
