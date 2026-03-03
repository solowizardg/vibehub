import logging
from typing import Any

from agent.callback_registry import ws_send
from agent.state import CodeGenState

logger = logging.getLogger(__name__)


async def conversation_edit_node(state: CodeGenState, config) -> dict[str, Any]:
    """
    接收用户的可视化编辑请求，解析意图并准备蓝图更新
    """
    sid = state.get("session_id", "")
    edit_request = state.get("edit_request", "")
    selected_component = state.get("selected_component", "")

    logger.info(f"Conversation edit request: {edit_request} for {selected_component}")

    # 发送状态给前端
    await ws_send(sid, {
        "type": "edit_analyzing",
        "message": f"分析修改请求: {edit_request}",
        "selected_component": selected_component
    })

    # 分析影响范围（简化版：直接返回继续）
    return {
        "current_dev_state": "blueprint_update",
        "analysis_complete": True
    }
