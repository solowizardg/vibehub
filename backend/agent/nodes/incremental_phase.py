import logging
from typing import Any

from agent.callback_registry import ws_send
from agent.state import CodeGenState

logger = logging.getLogger(__name__)


async def incremental_phase_node(state: CodeGenState, config) -> dict[str, Any]:
    """
    增量生成：只重新生成受影响的 phases
    复用现有的 phase_implementation_node 逻辑
    """
    sid = state.get("session_id", "")
    phases_to_regenerate = state.get("phases_to_regenerate", [])

    logger.info(f"Incremental phase generation for: {phases_to_regenerate}")

    await ws_send(sid, {
        "type": "incremental_generation_start",
        "phases": phases_to_regenerate
    })

    # 简化版：调用现有的 phase_implementation 逻辑
    # 标记需要重新生成的 phases
    if phases_to_regenerate:
        state["current_phase_index"] = min(phases_to_regenerate)

    return {
        "current_dev_state": "phase_implementing",
        "is_incremental": True
    }
