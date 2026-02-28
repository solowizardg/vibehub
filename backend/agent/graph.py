import logging
import os
import hashlib
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.nodes.blueprint import blueprint_node, process_selected_variant
from agent.nodes.finalizing import finalizing_node
from agent.nodes.phase_implementation import phase_implementation_node
from agent.nodes.sandbox_execution import sandbox_execution_node
from agent.nodes.sandbox_fix import sandbox_fix_node
from agent.state import CodeGenState

logger = logging.getLogger(__name__)

_llm: BaseChatModel | None = None


def get_llm() -> BaseChatModel:
    """Get the configured LLM instance (lazy singleton)."""
    global _llm
    if _llm is not None:
        return _llm

    gemini_key = os.getenv("GOOGLE_API_KEY", "")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3-flash")

    if gemini_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        _llm = ChatGoogleGenerativeAI(
            model=gemini_model,
            google_api_key=gemini_key,
            temperature=0.2,
        )
    else:
        # Old OpenRouter implementation (kept for quick rollback if needed):
        # openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        # openrouter_model = os.getenv("OPENROUTER_MODEL", "moonshotai/kimi-k2.5")
        # if openrouter_key:
        #     from langchain_openrouter import ChatOpenRouter
        #     _llm = ChatOpenRouter(
        #         model=openrouter_model,
        #         api_key=openrouter_key,
        #         max_tokens=8192,
        #     )
        # else:
        #     raise RuntimeError("No LLM API key configured. Set OPENROUTER_API_KEY in .env")
        raise RuntimeError("No LLM API key configured. Set GOOGLE_API_KEY in .env")

    return _llm


def route_start(state: CodeGenState) -> str:
    """Determine where to start based on current state.

    If we have existing phases and files, skip blueprint generation and go straight
    to phase implementation for incremental updates.
    """
    phases = state.get("phases", [])
    current_dev_state = state.get("current_dev_state", "")

    # If already in phase_implementing state with existing phases, skip blueprint
    if phases and current_dev_state == "phase_implementing":
        logger.info("Skipping blueprint generation, continuing with %d existing phases", len(phases))
        return "phase_implementation"

    # Otherwise, start with blueprint generation
    return "blueprint_generation"


def route_after_blueprint(state: CodeGenState) -> str:
    """After blueprint generation: proceed directly to implementation (simplified)."""
    # Simplified: always proceed to implementation, no waiting for variant selection
    return "phase_implementation"


def route_after_variant_selection(state: CodeGenState) -> str:
    """After variant selection: proceed to phase implementation."""
    return "phase_implementation"


def route_after_phase(state: CodeGenState) -> str:
    """After phase implementation: more phases or sandbox execution."""
    phases = state.get("phases", [])
    current_idx = state.get("current_phase_index", 0)
    if current_idx < len(phases):
        return "phase_implementation"
    return "sandbox_execution"


def route_after_sandbox(state: CodeGenState) -> str:
    """After sandbox execution: fix errors or finalize."""
    dev_state = state.get("current_dev_state", "finalizing")
    if dev_state == "sandbox_fixing":
        return "sandbox_fix"
    return "finalizing"


def build_graph() -> StateGraph:
    """Build the code generation state graph."""
    graph = StateGraph(CodeGenState)

    graph.add_node("blueprint_generation", blueprint_node)
    graph.add_node("variant_selection", process_selected_variant)
    graph.add_node("phase_implementation", phase_implementation_node)
    graph.add_node("sandbox_execution", sandbox_execution_node)
    graph.add_node("sandbox_fix", sandbox_fix_node)
    graph.add_node("finalizing", finalizing_node)

    # Use conditional edge from START to allow skipping blueprint for incremental updates
    graph.add_conditional_edges(
        START,
        route_start,
        {
            "blueprint_generation": "blueprint_generation",
            "phase_implementation": "phase_implementation",
        }
    )
    # Simplified: always proceed to implementation (no multi-variant selection)
    graph.add_edge("blueprint_generation", "phase_implementation")
    graph.add_conditional_edges("phase_implementation", route_after_phase)
    graph.add_conditional_edges("sandbox_execution", route_after_sandbox)
    graph.add_edge("sandbox_fix", "sandbox_execution")
    graph.add_edge("finalizing", END)

    return graph


async def run_codegen(
    session_id: str,
    user_query: str,
    template_name: str,
    existing_files: dict[str, "GeneratedFile"] | None = None,
    existing_blueprint: dict[str, Any] | None = None,
    existing_sandbox_id: str | None = None,
    ws_send_fn: Any = None,
    blueprint_variants: list[dict[str, Any]] | None = None,
    selected_variant_id: str | None = None,
) -> dict[str, Any]:
    """Run the full code generation pipeline for a session."""
    from agent.callback_registry import register_ws_callback, unregister_ws_callback
    from agent.nodes.phase_implementation import detect_language
    from agent.state import BlueprintVariant, GeneratedFile
    from services.template_service import get_template

    if ws_send_fn:
        register_ws_callback(session_id, ws_send_fn)

    try:
        template = get_template(template_name)

        preloaded_files: dict[str, GeneratedFile] = {}
        template_details: dict[str, Any] = {}

        has_existing_files = bool(existing_files)

        if template:
            logger.info("Loading template '%s' with %d files", template_name, len(template.all_files))
            for path, content in template.all_files.items():
                lang = detect_language(path)
                preloaded_files[path] = GeneratedFile(
                    file_path=path,
                    file_contents=content,
                    language=lang,
                    phase_index=-1,
                )
                if ws_send_fn and not has_existing_files:
                    await ws_send_fn({
                        "type": "file_generated",
                        "filePath": path,
                        "fileContents": content,
                        "language": lang,
                        "phaseIndex": -1,
                    })
            template_details = {
                "description": template.description,
                "all_files": {p: "" for p in template.all_files},
                "important_files": template.important_files,
                "dont_touch_files": template.dont_touch_files,
                "usage_prompt": template.usage_prompt,
                "selection_prompt": template.selection_prompt,
            }
        else:
            logger.warning("Template '%s' not found, starting from scratch", template_name)

        if existing_files:
            # Continue from the latest persisted project snapshot rather than
            # regenerating from template-only baseline.
            preloaded_files.update(existing_files)

        package_json_hash: str | None = None
        package_json_entry = preloaded_files.get("package.json")
        if package_json_entry:
            pkg_contents = str(package_json_entry.get("file_contents", ""))
            if pkg_contents:
                package_json_hash = hashlib.sha256(pkg_contents.encode("utf-8")).hexdigest()

        graph = build_graph()
        checkpointer = MemorySaver()
        compiled = graph.compile(checkpointer=checkpointer)

        # Prepare blueprint variants if provided
        variants: list[BlueprintVariant] = []
        if blueprint_variants:
            variants = [BlueprintVariant(**v) for v in blueprint_variants]

        # Determine initial dev state based on whether we have a selected variant
        initial_dev_state = "blueprint_generating"
        if selected_variant_id:
            initial_dev_state = "variant_selection"

        # Extract existing phases from blueprint if available
        # This ensures incremental updates preserve previous work
        existing_phases = []
        if existing_blueprint and isinstance(existing_blueprint, dict):
            blueprint_phases = existing_blueprint.get("phases", [])
            if isinstance(blueprint_phases, list):
                for i, phase in enumerate(blueprint_phases):
                    if isinstance(phase, dict):
                        existing_phases.append({
                            "index": phase.get("index", i),
                            "name": phase.get("name", f"Phase {i + 1}"),
                            "description": phase.get("description", ""),
                            "files": phase.get("files", []),
                            "status": phase.get("status", "completed"),
                        })

        # Check if this is an incremental update (has existing phases and files)
        is_incremental = bool(existing_phases) and len(preloaded_files) > len(template.all_files if template else {})

        if is_incremental:
            # For incremental updates, add a new phase to handle the new requirements
            # Mark all existing phases as completed
            for phase in existing_phases:
                phase["status"] = "completed"

            # Create a new phase for the incremental update
            new_phase_index = len(existing_phases)
            incremental_phase = {
                "index": new_phase_index,
                "name": "Incremental Update",
                "description": f"Add new features based on user request: {user_query}",
                "files": [],  # Will be determined by LLM during implementation
                "status": "pending",
            }
            existing_phases.append(incremental_phase)
            logger.info("Added incremental update phase %d for session %s", new_phase_index, session_id)

        initial_state: CodeGenState = {
            "session_id": session_id,
            "user_query": user_query,
            "blueprint": existing_blueprint or {},
            "blueprint_variants": variants,
            "selected_variant_id": selected_variant_id,
            "template_name": template_name,
            "generated_files": preloaded_files,
            "phases": existing_phases,
            "current_phase_index": len(existing_phases) - 1 if is_incremental else 0,
            "current_dev_state": "phase_implementing" if existing_phases else initial_dev_state,
            "conversation_messages": [],
            "should_continue": True,
            "sandbox_id": existing_sandbox_id,
            "sandbox_bootstrapped": bool(existing_sandbox_id),
            "sandbox_deps_installed": bool(existing_sandbox_id),
            "sandbox_package_json_hash": package_json_hash,
            "sandbox_fix_attempts": 0,
            "template_details": template_details,
        }

        config = {"configurable": {"thread_id": session_id}}

        final_state = None
        async for event in compiled.astream(initial_state, config, stream_mode="values"):
            final_state = event

        return final_state or {}
    finally:
        unregister_ws_callback(session_id)
