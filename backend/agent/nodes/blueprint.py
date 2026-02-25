import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent.callback_registry import ws_send
from agent.llm_content import llm_content_to_text
from agent.prompts import BLUEPRINT_SYSTEM_PROMPT
from agent.state import CodeGenState, GeneratedFile

logger = logging.getLogger(__name__)


def parse_json_from_response(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    return json.loads(text)


def build_template_context(template_details: dict) -> str:
    """Build template context string for the blueprint prompt."""
    if not template_details:
        return ""

    parts = []

    desc = template_details.get("description", "")
    if desc:
        parts.append(f"Template description: {desc}")

    all_files = template_details.get("all_files", {})
    if all_files:
        tree = "\n".join(f"  {p}" for p in sorted(all_files.keys()))
        parts.append(f"Template file tree:\n{tree}")

    important = template_details.get("important_files", [])
    if important:
        important_content = []
        for fp in important:
            content = all_files.get(fp, "")
            if content:
                important_content.append(f"--- {fp} ---\n{content[:800]}")
        if important_content:
            parts.append("Important template files:\n" + "\n".join(important_content))

    usage = template_details.get("usage_prompt", "")
    if usage:
        parts.append(f"Template usage guide:\n{usage}")

    return "\n\n".join(parts)


async def blueprint_node(state: CodeGenState, config) -> dict:
    """Generate the project blueprint from user query."""
    from agent.graph import get_llm

    sid = state.get("session_id", "")
    user_query = state["user_query"]
    template_name = state.get("template_name", "react-vite")
    template_details = state.get("template_details", {})

    template_context = build_template_context(template_details)
    dont_touch = template_details.get("dont_touch_files", [])
    dont_touch_str = ", ".join(dont_touch) if dont_touch else "(none)"

    existing_files = state.get("generated_files", {})
    if existing_files:
        existing_list = "\n".join(f"  - {p}" for p in sorted(existing_files.keys()))
    else:
        existing_list = "(none)"

    llm = get_llm()

    system_prompt = BLUEPRINT_SYSTEM_PROMPT.format(
        template_name=template_name,
        template_context=template_context,
        dont_touch_files=dont_touch_str,
        existing_template_files=existing_list,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Build the following application:\n\n{user_query}"),
    ]

    await ws_send(sid, {"type": "generation_started"})

    response = await llm.ainvoke(messages)
    raw_content = response.content if hasattr(response, "content") else response
    content = llm_content_to_text(raw_content)

    try:
        blueprint = parse_json_from_response(content)
    except (json.JSONDecodeError, ValueError):
        logger.error("Failed to parse blueprint JSON: %s", content[:500])
        blueprint = {
            "project_name": "my-app",
            "description": user_query[:200],
            "phases": [
                {
                    "name": "Core Components",
                    "description": "Build the core application components",
                    "files": ["src/App.tsx", "src/components/Layout.tsx"],
                }
            ],
        }

    phases = []
    for i, phase in enumerate(blueprint.get("phases", [])):
        phase_files = phase.get("files", [])
        if dont_touch:
            phase_files = [f for f in phase_files if f not in dont_touch]
        phase_def = {
            "index": i,
            "name": phase.get("name", f"Phase {i + 1}"),
            "description": phase.get("description", ""),
            "files": phase_files,
            "status": "pending",
        }
        phases.append(phase_def)

    await ws_send(sid, {"type": "blueprint_generated", "blueprint": blueprint})

    for phase in phases:
        await ws_send(sid, {"type": "phase_generating", "phase": phase})

    return {
        "blueprint": blueprint,
        "project_name": blueprint.get("project_name", "my-app"),
        "phases": phases,
        "current_phase_index": 0,
        "current_dev_state": "phase_implementing",
        "should_continue": True,
    }
