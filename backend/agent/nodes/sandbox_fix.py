import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agent.callback_registry import ws_send
from agent.file_constraints import enforce_nextjs_config_filename
from agent.llm_content import llm_content_to_text
from agent.nodes.phase_implementation import parse_files_from_response
from agent.prompts import SANDBOX_FIX_SYSTEM_PROMPT
from agent.state import CodeGenState

logger = logging.getLogger(__name__)


async def sandbox_fix_node(state: CodeGenState, config) -> dict:
    """Use the LLM to fix runtime/build errors reported by the sandbox."""
    from agent.graph import get_llm

    sid = state.get("session_id", "")
    generated_files = dict(state.get("generated_files", {}))
    error_output = state.get("sandbox_logs", "")
    fix_attempts = state.get("sandbox_fix_attempts", 0)

    await ws_send(sid, {
        "type": "sandbox_status",
        "status": "fixing",
        "attempt": fix_attempts + 1,
    })

    files_content = ""
    for fp, f in generated_files.items():
        files_content += f"\n===FILE: {fp}===\n{f.get('file_contents', '')}\n===END_FILE===\n"

    prompt = SANDBOX_FIX_SYSTEM_PROMPT.format(
        project_name=state.get("project_name", "my-app"),
        error_output=error_output,
        generated_files_content=files_content,
    )

    llm = get_llm()
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Fix the errors and output only the corrected files."),
    ]

    content = ""
    async for chunk in llm.astream(messages):
        token = llm_content_to_text(chunk.content if hasattr(chunk, "content") else chunk)
        if token:
            content += token
            await ws_send(sid, {"type": "llm_token", "node": "sandbox_fix", "token": token})

    fixed_files = parse_files_from_response(content)
    fixed_files, renamed_config = enforce_nextjs_config_filename(
        fixed_files,
        state.get("template_name", "react-vite"),
    )
    if renamed_config:
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stderr",
            "text": "Enforced next.config.mjs in sandbox fix output.",
        })

    for path, file_data in fixed_files.items():
        file_data["phase_index"] = generated_files.get(path, {}).get("phase_index", 0)
        generated_files[path] = file_data

        await ws_send(sid, {
            "type": "file_generated",
            "filePath": path,
            "fileContents": file_data.get("file_contents", ""),
            "language": file_data.get("language", "plaintext"),
            "phaseIndex": file_data.get("phase_index", 0),
        })

    logger.info(
        "Sandbox fix attempt %d for session %s: %d files updated",
        fix_attempts + 1, sid, len(fixed_files),
    )

    return {
        "generated_files": generated_files,
        "sandbox_fix_attempts": fix_attempts + 1,
        "current_dev_state": "sandbox_executing",
    }
