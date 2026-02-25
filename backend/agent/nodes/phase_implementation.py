import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent.callback_registry import ws_send
from agent.file_constraints import enforce_nextjs_config_filename
from agent.llm_content import llm_content_to_text
from agent.prompts import PHASE_IMPLEMENTATION_SYSTEM_PROMPT
from agent.state import CodeGenState, GeneratedFile

logger = logging.getLogger(__name__)


def parse_files_from_response(text: str) -> dict[str, GeneratedFile]:
    """Parse ===FILE: path=== blocks from LLM response."""
    files: dict[str, GeneratedFile] = {}
    pattern = r"===FILE:\s*(.+?)===\s*\n(.*?)\n===END_FILE==="
    matches = re.findall(pattern, text, re.DOTALL)

    for file_path, file_contents in matches:
        file_path = file_path.strip()
        file_contents = file_contents.strip()
        lang = detect_language(file_path)
        files[file_path] = GeneratedFile(
            file_path=file_path,
            file_contents=file_contents,
            language=lang,
        )

    return files


def detect_language(path: str) -> str:
    ext_map = {
        ".tsx": "typescriptreact",
        ".ts": "typescript",
        ".jsx": "javascriptreact",
        ".js": "javascript",
        ".json": "json",
        ".css": "css",
        ".html": "html",
        ".md": "markdown",
        ".py": "python",
    }
    for ext, lang in ext_map.items():
        if path.endswith(ext):
            return lang
    return "plaintext"


async def phase_implementation_node(state: CodeGenState, config) -> dict:
    """Implement the current phase by generating file contents."""
    from agent.graph import get_llm

    sid = state.get("session_id", "")
    phases = state.get("phases", [])
    current_idx = state.get("current_phase_index", 0)
    generated_files = dict(state.get("generated_files", {}))

    if current_idx >= len(phases):
        return {"current_dev_state": "finalizing", "should_continue": False}

    phase = phases[current_idx]

    await ws_send(sid, {"type": "phase_implementing", "phase_index": current_idx})

    template_details = state.get("template_details", {})
    dont_touch = template_details.get("dont_touch_files", [])
    usage_prompt = template_details.get("usage_prompt", "")

    phase_files = [f for f in phase.get("files", []) if f not in dont_touch]

    existing_summary = ""
    for path, f in generated_files.items():
        existing_summary += f"\n--- {path} ---\n{f.get('file_contents', '')[:500]}\n"
    if not existing_summary:
        existing_summary = "(No files generated yet)"

    usage_section = f"Template usage guide:\n{usage_prompt}" if usage_prompt else ""
    dont_touch_str = ", ".join(dont_touch) if dont_touch else "(none)"

    prompt = PHASE_IMPLEMENTATION_SYSTEM_PROMPT.format(
        phase_index=current_idx + 1,
        project_name=state.get("project_name", "my-app"),
        template_name=state.get("template_name", "react-vite"),
        phase_name=phase["name"],
        phase_description=phase.get("description", ""),
        phase_files=", ".join(phase_files),
        existing_files_summary=existing_summary,
        usage_prompt_section=usage_section,
        dont_touch_files=dont_touch_str,
    )

    llm = get_llm()
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Generate all the files for this phase now."),
    ]

    for fp in phase.get("files", []):
        await ws_send(sid, {"type": "file_generating", "filePath": fp})

    response = await llm.ainvoke(messages)
    raw_content = response.content if hasattr(response, "content") else response
    content = llm_content_to_text(raw_content)

    new_files = parse_files_from_response(content)
    new_files, renamed_config = enforce_nextjs_config_filename(
        new_files,
        state.get("template_name", "react-vite"),
    )
    if renamed_config:
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stderr",
            "text": "Enforced next.config.mjs (renamed from next.config.ts).",
        })

    if not new_files and phase.get("files"):
        logger.warning("No files parsed from LLM response for phase %d, falling back", current_idx)
        for fp in phase.get("files", []):
            new_files[fp] = GeneratedFile(
                file_path=fp,
                file_contents=f"// TODO: Generated content for {fp}",
                language=detect_language(fp),
            )

    for path, file_data in new_files.items():
        file_data["phase_index"] = current_idx
        generated_files[path] = file_data

        contents = file_data.get("file_contents", "")
        chunk_size = 200
        for i in range(0, len(contents), chunk_size):
            await ws_send(sid, {
                "type": "file_chunk_generated",
                "filePath": path,
                "chunk": contents[i : i + chunk_size],
            })
        await ws_send(sid, {
            "type": "file_generated",
            "filePath": path,
            "fileContents": contents,
            "language": file_data.get("language", "plaintext"),
        })

    updated_phases = list(phases)
    updated_phases[current_idx] = {**phase, "status": "completed"}

    await ws_send(sid, {"type": "phase_implemented", "phase_index": current_idx})

    next_idx = current_idx + 1

    return {
        "generated_files": generated_files,
        "phases": updated_phases,
        "current_phase_index": next_idx,
        "current_dev_state": "phase_implementing",
    }
