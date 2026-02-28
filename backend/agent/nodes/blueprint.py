import asyncio
import json
import logging
import re
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.callback_registry import ws_send
from agent.llm_content import llm_content_to_text
from agent.prompts import BLUEPRINT_SYSTEM_PROMPT, MULTI_BLUEPRINT_SYSTEM_PROMPT
from agent.state import BlueprintVariant, CodeGenState, GeneratedFile

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
    return parsed


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
    updated = dict(blueprint)
    design = updated.get("design_blueprint")
    if not isinstance(design, dict):
        updated["design_blueprint"] = _default_design_blueprint()
        return updated

    merged_design = _default_design_blueprint()
    for key in ("visual_style", "interaction_design"):
        value = design.get(key)
        if isinstance(value, dict):
            merged_design[key].update(value)
    if isinstance(design.get("ui_principles"), list) and design["ui_principles"]:
        merged_design["ui_principles"] = design["ui_principles"]

    updated["design_blueprint"] = merged_design
    return updated


def _merge_design_blueprint(existing: Any, generated: Any) -> dict[str, Any]:
    base = _default_design_blueprint()

    if isinstance(existing, dict):
        existing_norm = _ensure_design_blueprint({"design_blueprint": existing}).get("design_blueprint", {})
        if isinstance(existing_norm, dict):
            for key in ("visual_style", "interaction_design"):
                value = existing_norm.get(key)
                if isinstance(value, dict):
                    base[key].update(value)
            if isinstance(existing_norm.get("ui_principles"), list) and existing_norm["ui_principles"]:
                base["ui_principles"] = existing_norm["ui_principles"]

    if isinstance(generated, dict):
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


def _fallback_blueprint_variants(user_query: str) -> list[BlueprintVariant]:
    """Generate fallback blueprint variants when parsing fails."""
    base = _fallback_blueprint(user_query)
    variants: list[BlueprintVariant] = [
        {
            "variant_id": "variant_1",
            "style_name": "Modern Minimalist",
            "style_description": "Clean, whitespace-heavy design with subtle interactions",
            "project_name": base["project_name"],
            "description": base["description"],
            "design_blueprint": base["design_blueprint"],
            "phases": base["phases"],
            "blueprint_markdown": _blueprint_to_markdown(base),
        },
        {
            "variant_id": "variant_2",
            "style_name": "Vibrant Creative",
            "style_description": "Bold colors and dynamic animations for creative applications",
            "project_name": base["project_name"],
            "description": base["description"],
            "design_blueprint": {
                **base["design_blueprint"],
                "visual_style": {
                    "color_palette": ["#ff6b6b", "#4ecdc4", "#ffe66d", "#1a1a2e"],
                    "typography": "Playful, expressive fonts with varied weights",
                    "spacing": "Dynamic spacing with visual interest",
                },
            },
            "phases": base["phases"],
            "blueprint_markdown": _blueprint_to_markdown(base),
        },
        {
            "variant_id": "variant_3",
            "style_name": "Enterprise Professional",
            "style_description": "Structured, data-dense interface with accessibility focus",
            "project_name": base["project_name"],
            "description": base["description"],
            "design_blueprint": {
                **base["design_blueprint"],
                "visual_style": {
                    "color_palette": ["#1e3a5f", "#2d5a87", "#f5f5f5", "#e8e8e8"],
                    "typography": "Clear, readable fonts optimized for data density",
                    "spacing": "Compact, efficient spacing for information density",
                },
            },
            "phases": base["phases"],
            "blueprint_markdown": _blueprint_to_markdown(base),
        },
    ]
    return variants


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


def _variant_to_blueprint_variant(variant_data: dict[str, Any]) -> BlueprintVariant:
    """Convert raw variant data to BlueprintVariant."""
    phases = variant_data.get("phases", [])
    normalized_phases = [_normalize_phase(p, i) for i, p in enumerate(phases)] if isinstance(phases, list) else []

    blueprint = {
        "project_name": variant_data.get("project_name", "my-app"),
        "description": variant_data.get("description", ""),
        "design_blueprint": variant_data.get("design_blueprint", _default_design_blueprint()),
        "phases": normalized_phases,
    }
    blueprint = _ensure_design_blueprint(blueprint)

    return BlueprintVariant(
        variant_id=variant_data.get("variant_id", str(uuid.uuid4())),
        style_name=variant_data.get("style_name", "Unnamed Style"),
        style_description=variant_data.get("style_description", ""),
        project_name=blueprint["project_name"],
        description=blueprint["description"],
        design_blueprint=blueprint["design_blueprint"],
        phases=normalized_phases,
        blueprint_markdown=_blueprint_to_markdown(blueprint),
    )


def _extract_phases_from_variant(variant: BlueprintVariant, dont_touch: list[str]) -> list[dict[str, Any]]:
    """Extract phase definitions from a variant."""
    phases = []
    for i, phase in enumerate(variant.get("phases", [])):
        normalized_phase = _normalize_phase(phase, i)
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
    return phases


async def _generate_single_blueprint_variant(
    variant_style: dict[str, str],
    user_query: str,
    template_name: str,
    template_context: str,
    dont_touch_str: str,
    existing_list: str,
    existing_blueprint_text: str,
    llm,
) -> BlueprintVariant:
    """Generate a single blueprint variant with specific style."""
    style_name = variant_style["name"]
    style_description = variant_style["description"]

    system_prompt = MULTI_BLUEPRINT_SYSTEM_PROMPT.format(
        template_name=template_name,
        template_context=template_context,
        dont_touch_files=dont_touch_str,
        existing_template_files=existing_list,
        existing_blueprint=existing_blueprint_text,
    )

    human_prompt = f"""Build the following application with the specified style:

User Request: {user_query}

Style for this variant:
- Name: {style_name}
- Description: {style_description}

Generate a complete blueprint following the JSON structure with variants array containing this single variant."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]

    response = await llm.ainvoke(messages)
    raw_content = response.content if hasattr(response, "content") else response
    content = llm_content_to_text(raw_content)

    try:
        parsed = parse_json_from_response(content)
        variants = parsed.get("variants", [])
        if variants and len(variants) > 0:
            variant_data = variants[0]
            variant_data["variant_id"] = variant_data.get("variant_id", f"variant_{uuid.uuid4().hex[:8]}")
            variant_data["style_name"] = variant_data.get("style_name", style_name)
            variant_data["style_description"] = variant_data.get("style_description", style_description)
            return _variant_to_blueprint_variant(variant_data)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse variant blueprint JSON: %s", str(e))

    # Fallback
    fallback = _fallback_blueprint(user_query)
    return BlueprintVariant(
        variant_id=f"variant_{uuid.uuid4().hex[:8]}",
        style_name=style_name,
        style_description=style_description,
        project_name=fallback["project_name"],
        description=fallback["description"],
        design_blueprint=fallback["design_blueprint"],
        phases=[_normalize_phase(p, i) for i, p in enumerate(fallback["phases"])],
        blueprint_markdown=_blueprint_to_markdown(fallback),
    )


async def blueprint_node(state: CodeGenState, config) -> dict[str, Any]:
    """Generate a single project blueprint from user query (simplified version)."""
    from agent.graph import get_llm

    sid = state.get("session_id", "")
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

    llm = get_llm()

    await ws_send(sid, {"type": "generation_started"})

    # Generate single blueprint (simplified - no multi-variant)
    system_prompt = BLUEPRINT_SYSTEM_PROMPT.format(
        template_name=template_name,
        template_context=template_context,
        dont_touch_files=dont_touch_str,
        existing_template_files=existing_list,
        existing_blueprint=_existing_blueprint_text(existing_blueprint),
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query),
    ]

    response = await llm.ainvoke(messages)
    raw_content = response.content if hasattr(response, "content") else response
    content = llm_content_to_text(raw_content)

    try:
        parsed = parse_json_from_response(content)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse blueprint JSON: %s", str(e))
        parsed = _fallback_blueprint(user_query)

    blueprint = _merge_blueprints(existing_blueprint, parsed, user_query)
    blueprint = _ensure_design_blueprint(blueprint)
    blueprint_markdown = _blueprint_to_markdown(blueprint)

    # Extract phases
    phases = []
    for i, phase in enumerate(blueprint.get("phases", [])):
        normalized_phase = _normalize_phase(phase, i)
        phase_files = normalized_phase.get("files", [])
        if dont_touch:
            phase_files = [f for f in phase_files if f not in dont_touch]
        phases.append({
            "index": i,
            "name": normalized_phase.get("name", f"Phase {i + 1}"),
            "description": normalized_phase.get("description", ""),
            "files": phase_files,
            "status": "pending",
        })

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

    # Continue directly - no waiting for user selection
    return {
        "blueprint": blueprint,
        "blueprint_markdown": blueprint_markdown,
        "project_name": blueprint["project_name"],
        "phases": phases,
        "current_phase_index": 0,
        "current_dev_state": "phase_implementing",
        "should_continue": True,
    }


async def process_selected_variant(state: CodeGenState, config) -> dict[str, Any]:
    """Process the user-selected blueprint variant and continue with phase implementation."""
    sid = state.get("session_id", "")
    selected_variant_id = state.get("selected_variant_id")
    variants = state.get("blueprint_variants", [])
    template_details = state.get("template_details", {})
    dont_touch = template_details.get("dont_touch_files", [])

    if not selected_variant_id or not variants:
        return {
            "error": "No variant selected",
            "should_continue": False,
        }

    selected_variant = next(
        (v for v in variants if v.get("variant_id") == selected_variant_id),
        None
    )

    if not selected_variant:
        return {
            "error": f"Selected variant {selected_variant_id} not found",
            "should_continue": False,
        }

    # Extract blueprint data from selected variant
    blueprint = {
        "project_name": selected_variant.get("project_name", "my-app"),
        "description": selected_variant.get("description", ""),
        "design_blueprint": selected_variant.get("design_blueprint", _default_design_blueprint()),
        "phases": selected_variant.get("phases", []),
    }
    blueprint = _ensure_design_blueprint(blueprint)
    blueprint_markdown = selected_variant.get("blueprint_markdown", _blueprint_to_markdown(blueprint))

    # Extract phases
    phases = _extract_phases_from_variant(selected_variant, dont_touch)

    # If no phases detected, regenerate the last phase
    if not phases and isinstance(blueprint.get("phases"), list) and blueprint["phases"]:
        last_index = len(blueprint["phases"]) - 1
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
            "type": "blueprint_selected",
            "variant_id": selected_variant_id,
            "blueprint": blueprint,
            "blueprint_markdown": blueprint_markdown,
        },
    )

    for phase in phases:
        await ws_send(sid, {"type": "phase_generating", "phase": phase})

    return {
        "blueprint": blueprint,
        "blueprint_markdown": blueprint_markdown,
        "project_name": blueprint["project_name"],
        "phases": phases,
        "current_phase_index": 0,
        "current_dev_state": "phase_implementing",
        "should_continue": True,
    }
