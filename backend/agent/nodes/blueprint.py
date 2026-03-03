import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.callback_registry import ws_send
from agent.llm_content import llm_content_to_text
from agent.prompts import BLUEPRINT_SYSTEM_PROMPT
from agent.state import CodeGenState, GeneratedFile

logger = logging.getLogger(__name__)


def parse_json_from_response(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Blueprint response must be a JSON object")
    return _clean_dict_keys(parsed)


def _clean_dict_keys(obj: Any) -> Any:
    """Recursively clean dictionary keys by stripping whitespace.

    This fixes issues where LLM might generate keys with surrounding spaces
    like ' motion ' instead of 'motion'.
    """
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for key, value in obj.items():
            if isinstance(key, str):
                clean_key = key.strip()
                if key != clean_key:
                    logger.debug(f"Cleaned dict key: {repr(key)} -> {repr(clean_key)}")
                cleaned[clean_key] = _clean_dict_keys(value)
            else:
                cleaned[key] = _clean_dict_keys(value)
        return cleaned
    elif isinstance(obj, list):
        return [_clean_dict_keys(item) for item in obj]
    else:
        return obj


def build_template_context(template_details: dict[str, Any]) -> str:
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


def _default_design_blueprint() -> dict[str, Any]:
    return {
        "visual_style": {
            "color_palette": ["#0f172a", "#2563eb", "#f8fafc"],
            "typography": "Use a clear heading/body hierarchy with readable sizing.",
            "spacing": "Use consistent spacing rhythm across sections and components.",
        },
        "interaction_design": {
            "core_patterns": ["Clear primary actions and predictable navigation"],
            "component_states": ["hover", "focus", "active", "loading", "error"],
            "motion": "Use subtle transitions for visibility and feedback.",
        },
        "ui_principles": [
            "Maintain consistency with prior screens and components.",
            "Prefer clarity and predictable interactions over novelty.",
        ],
    }


def _ensure_design_blueprint(blueprint: dict[str, Any]) -> dict[str, Any]:
    # Clean any keys with surrounding whitespace
    blueprint = _clean_dict_keys(blueprint)
    updated = dict(blueprint)
    design = updated.get("design_blueprint")
    if not isinstance(design, dict):
        updated["design_blueprint"] = _default_design_blueprint()
        return updated

    merged_design = _default_design_blueprint()
    for key in ("visual_style", "interaction_design"):
        value = design.get(key)
        if isinstance(value, dict):
            # Clean nested dict keys as well
            cleaned_value = _clean_dict_keys(value)
            merged_design[key].update(cleaned_value)
    if isinstance(design.get("ui_principles"), list) and design["ui_principles"]:
        merged_design["ui_principles"] = design["ui_principles"]

    updated["design_blueprint"] = merged_design
    return updated


def _merge_design_blueprint(existing: Any, generated: Any) -> dict[str, Any]:
    base = _default_design_blueprint()

    if isinstance(existing, dict):
        existing = _clean_dict_keys(existing)
        existing_norm = _ensure_design_blueprint({"design_blueprint": existing}).get("design_blueprint", {})
        if isinstance(existing_norm, dict):
            for key in ("visual_style", "interaction_design"):
                value = existing_norm.get(key)
                if isinstance(value, dict):
                    base[key].update(value)
            if isinstance(existing_norm.get("ui_principles"), list) and existing_norm["ui_principles"]:
                base["ui_principles"] = existing_norm["ui_principles"]

    if isinstance(generated, dict):
        generated = _clean_dict_keys(generated)
        generated_norm = _ensure_design_blueprint({"design_blueprint": generated}).get("design_blueprint", {})
        if isinstance(generated_norm, dict):
            for key in ("visual_style", "interaction_design"):
                value = generated_norm.get(key)
                if isinstance(value, dict):
                    base[key].update(value)
            if isinstance(generated_norm.get("ui_principles"), list) and generated_norm["ui_principles"]:
                base["ui_principles"] = generated_norm["ui_principles"]

    return base


def _fallback_blueprint(user_query: str) -> dict[str, Any]:
    return {
        "project_name": "my-app",
        "description": user_query[:200],
        "design_blueprint": _default_design_blueprint(),
        "phases": [
            {
                "name": "Core Components",
                "description": "Build the core application components",
                "files": ["src/App.tsx", "src/components/Layout.tsx"],
            }
        ],
    }


def _normalize_phase(phase: Any, idx: int) -> dict[str, Any]:
    if not isinstance(phase, dict):
        return {
            "name": f"Phase {idx + 1}",
            "description": "",
            "files": [],
        }
    files = _as_string_list(phase.get("files"))
    return {
        "name": str(phase.get("name", f"Phase {idx + 1}")).strip() or f"Phase {idx + 1}",
        "description": str(phase.get("description", "")).strip(),
        "files": files,
    }


def _phase_signature(phase: dict[str, Any]) -> str:
    name = str(phase.get("name", "")).strip().lower()
    desc = str(phase.get("description", "")).strip().lower()
    files = sorted(_as_string_list(phase.get("files")))
    return f"{name}|{desc}|{'|'.join(files)}"


def _merge_phases(existing: list[Any], generated: list[Any]) -> list[dict[str, Any]]:
    normalized_existing = [_normalize_phase(p, i) for i, p in enumerate(existing)]
    merged = list(normalized_existing)
    seen = {_phase_signature(p) for p in normalized_existing}

    for i, phase in enumerate(generated):
        normalized = _normalize_phase(phase, len(merged) + i)
        sig = _phase_signature(normalized)
        if sig in seen:
            continue
        merged.append(normalized)
        seen.add(sig)
    return merged


def _merge_blueprints(existing: dict[str, Any] | None, generated: dict[str, Any], user_query: str) -> dict[str, Any]:
    generated = _ensure_design_blueprint(generated)
    if not existing:
        phases = generated.get("phases", [])
        if not isinstance(phases, list):
            generated["phases"] = _fallback_blueprint(user_query)["phases"]
        else:
            generated["phases"] = [_normalize_phase(p, i) for i, p in enumerate(phases)]
        return generated

    merged = dict(existing)

    if generated.get("project_name"):
        merged["project_name"] = generated["project_name"]
    if generated.get("description"):
        merged["description"] = generated["description"]
    existing_phases = merged.get("phases", [])
    if not isinstance(existing_phases, list):
        existing_phases = []
    generated_phases = generated.get("phases", [])
    if not isinstance(generated_phases, list):
        generated_phases = []
    if generated_phases:
        merged["phases"] = _merge_phases(existing_phases, generated_phases)
    elif existing_phases:
        merged["phases"] = [_normalize_phase(p, i) for i, p in enumerate(existing_phases)]

    merged["design_blueprint"] = _merge_design_blueprint(
        merged.get("design_blueprint"),
        generated.get("design_blueprint"),
    )

    if not isinstance(merged.get("phases"), list) or not merged.get("phases"):
        merged["phases"] = _fallback_blueprint(user_query)["phases"]

    return _ensure_design_blueprint(merged)


def _existing_blueprint_text(existing_blueprint: dict[str, Any] | None) -> str:
    if not existing_blueprint:
        return "(none)"
    try:
        return json.dumps(existing_blueprint, ensure_ascii=False, indent=2)
    except Exception:
        return "(existing blueprint present but serialization failed)"


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if isinstance(v, str) and v.strip()]


def _blueprint_to_markdown(blueprint: dict[str, Any]) -> str:
    # Clean any keys with surrounding whitespace
    blueprint = _clean_dict_keys(blueprint)
    project_name = str(blueprint.get("project_name", "Untitled Project")).strip() or "Untitled Project"
    description = str(blueprint.get("description", "")).strip()
    design = blueprint.get("design_blueprint", {})
    phases = blueprint.get("phases", [])

    lines: list[str] = [f"# {project_name}", ""]

    if description:
        lines.extend(["## Overview", description, ""])

    if isinstance(design, dict):
        visual_style = design.get("visual_style", {})
        interaction_design = design.get("interaction_design", {})
        ui_principles = _as_string_list(design.get("ui_principles"))

        lines.append("## Design Blueprint")
        lines.append("")

        if isinstance(visual_style, dict):
            lines.append("### Visual Style")
            palette = _as_string_list(visual_style.get("color_palette"))
            if palette:
                lines.append(f"- Color Palette: {', '.join(palette)}")
            typography = str(visual_style.get("typography", "")).strip()
            if typography:
                lines.append(f"- Typography: {typography}")
            spacing = str(visual_style.get("spacing", "")).strip()
            if spacing:
                lines.append(f"- Spacing: {spacing}")
            lines.append("")

        if isinstance(interaction_design, dict):
            lines.append("### Interaction Design")
            patterns = _as_string_list(interaction_design.get("core_patterns"))
            if patterns:
                lines.append("- Core Patterns:")
                for p in patterns:
                    lines.append(f"  - {p}")
            states = _as_string_list(interaction_design.get("component_states"))
            if states:
                lines.append(f"- Component States: {', '.join(states)}")
            motion = str(interaction_design.get("motion", "")).strip()
            if motion:
                lines.append(f"- Motion: {motion}")
            lines.append("")

        if ui_principles:
            lines.append("### UI Principles")
            for principle in ui_principles:
                lines.append(f"- {principle}")
            lines.append("")

    if isinstance(phases, list) and phases:
        lines.append("## Implementation Phases")
        lines.append("")
        for idx, phase in enumerate(phases, start=1):
            if not isinstance(phase, dict):
                continue
            name = str(phase.get("name", f"Phase {idx}")).strip() or f"Phase {idx}"
            phase_desc = str(phase.get("description", "")).strip()
            phase_files = _as_string_list(phase.get("files"))

            lines.append(f"### {idx}. {name}")
            if phase_desc:
                lines.append(phase_desc)
            if phase_files:
                lines.append("")
                lines.append("Files:")
                for file_path in phase_files:
                    lines.append(f"- `{file_path}`")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


async def blueprint_node(state: CodeGenState, config) -> dict[str, Any]:
    """Generate the project blueprint from user query."""
    from agent.graph import get_llm_with_retry

    sid = state.get("session_id", "")

    # 检查是否是增量更新模式
    if state.get("edit_request") and state.get("blueprint"):
        # 增量更新模式
        logger.info("Incremental blueprint update mode")
        current_blueprint = state["blueprint"]

        # 简化：标记所有 phases 需要重新生成
        # 实际应该分析影响范围
        all_phases = list(range(len(current_blueprint.get("phases", []))))

        await ws_send(sid, {
            "type": "blueprint_incremental_update",
            "message": "增量更新蓝图",
            "phases_to_regenerate": all_phases
        })

        return {
            "blueprint": current_blueprint,  # 保持原蓝图
            "phases_to_regenerate": all_phases,
            "current_dev_state": "incremental_phase"
        }

    try:
        user_query = state["user_query"]
        template_name = state.get("template_name", "react-vite")
        template_details = state.get("template_details", {})
        existing_blueprint = state.get("blueprint")

        template_context = build_template_context(template_details)
        dont_touch = template_details.get("dont_touch_files", [])
        dont_touch_str = ", ".join(dont_touch) if dont_touch else "(none)"

        existing_files = state.get("generated_files", {})
        if existing_files:
            existing_list = "\n".join(f"  - {p}" for p in sorted(existing_files.keys()))
        else:
            existing_list = "(none)"

        logger.info(f"[Blueprint] Session {sid}: Getting LLM with retry wrapper (blueprint model)...")
        from agent.graph import get_llm_blueprint, RetryableLLMWrapper
        llm = RetryableLLMWrapper(get_llm_blueprint())

        system_prompt = BLUEPRINT_SYSTEM_PROMPT.format(
            template_name=template_name,
            template_context=template_context,
            dont_touch_files=dont_touch_str,
            existing_template_files=existing_list,
            existing_blueprint=_existing_blueprint_text(existing_blueprint),
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Build or update the following application:\n\n{user_query}"),
        ]

        logger.info(f"[Blueprint] Session {sid}: Sending generation_started event")
        await ws_send(sid, {"type": "generation_started"})

        logger.info(f"[Blueprint] Session {sid}: Calling LLM ainvoke with {len(messages)} messages...")
        try:
            response = await llm.ainvoke(messages)
            logger.info(f"[Blueprint] Session {sid}: LLM response received successfully")
        except Exception as e:
            logger.error(f"[Blueprint] Session {sid}: LLM call failed: {e}")
            raise
        raw_content = response.content if hasattr(response, "content") else response
        content = llm_content_to_text(raw_content)

        try:
            generated_blueprint = parse_json_from_response(content)
        except (json.JSONDecodeError, ValueError):
            logger.error("Failed to parse blueprint JSON: %s", content[:500])
            generated_blueprint = _fallback_blueprint(user_query)

        blueprint = _merge_blueprints(existing_blueprint, generated_blueprint, user_query)
        blueprint_markdown = _blueprint_to_markdown(blueprint)

        existing_signatures: set[str] = set()
        if isinstance(existing_blueprint, dict):
            for i, phase in enumerate(existing_blueprint.get("phases", []) if isinstance(existing_blueprint.get("phases"), list) else []):
                existing_signatures.add(_phase_signature(_normalize_phase(phase, i)))

        phases = []
        for i, phase in enumerate(blueprint.get("phases", [])):
            normalized_phase = _normalize_phase(phase, i)
            signature = _phase_signature(normalized_phase)
            if signature in existing_signatures:
                continue

            phase_files = normalized_phase.get("files", [])
            if dont_touch:
                phase_files = [f for f in phase_files if f not in dont_touch]
            phase_def = {
                "index": i,
                "name": normalized_phase.get("name", f"Phase {i + 1}"),
                "description": normalized_phase.get("description", ""),
                "files": phase_files,
                "status": "pending",
            }
            phases.append(phase_def)

        if not phases and isinstance(blueprint.get("phases"), list):
            # If no new phase is detected, regenerate the last phase so follow-up
            # requests that target existing files can still be applied.
            last_index = len(blueprint["phases"]) - 1
            if last_index >= 0:
                last_phase = _normalize_phase(blueprint["phases"][last_index], last_index)
                phase_files = [f for f in last_phase.get("files", []) if f not in dont_touch]
                phases = [{
                    "index": last_index,
                    "name": last_phase.get("name", f"Phase {last_index + 1}"),
                    "description": last_phase.get("description", ""),
                    "files": phase_files,
                    "status": "pending",
                }]

        await ws_send(
            sid,
            {
                "type": "blueprint_generated",
                "blueprint": blueprint,
                "blueprint_markdown": blueprint_markdown,
            },
        )

        for phase in phases:
            await ws_send(sid, {"type": "phase_generating", "phase": phase})

        return {
            "blueprint": blueprint,
            "blueprint_markdown": blueprint_markdown,
            "project_name": blueprint.get("project_name", "my-app"),
            "phases": phases,
            "current_phase_index": 0,
            "current_dev_state": "phase_implementing",
            "should_continue": True,
        }
    except Exception as e:
        logger.exception("Blueprint generation failed for session %s: %s", sid, str(e)[:200])
        try:
            await ws_send(sid, {"type": "error", "message": f"Blueprint generation failed: {str(e)}"})
        except Exception:
            pass
        # Return fallback state to prevent pipeline failure
        fallback = _fallback_blueprint(state.get("user_query", "unknown"))
        return {
            "blueprint": fallback,
            "blueprint_markdown": _blueprint_to_markdown(fallback),
            "project_name": fallback.get("project_name", "my-app"),
            "phases": [],
            "current_phase_index": 0,
            "current_dev_state": "finalizing",
            "should_continue": False,
            "error": str(e),
        }
