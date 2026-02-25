import logging
import os
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.nodes.blueprint import blueprint_node
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
    graph.add_node("phase_implementation", phase_implementation_node)
    graph.add_node("sandbox_execution", sandbox_execution_node)
    graph.add_node("sandbox_fix", sandbox_fix_node)
    graph.add_node("finalizing", finalizing_node)

    graph.add_edge(START, "blueprint_generation")
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
    ws_send_fn: Any = None,
) -> dict[str, Any]:
    """Run the full code generation pipeline for a session."""
    from agent.callback_registry import register_ws_callback, unregister_ws_callback
    from agent.nodes.phase_implementation import detect_language
    from agent.state import GeneratedFile
    from services.template_service import get_template

    if ws_send_fn:
        register_ws_callback(session_id, ws_send_fn)

    try:
        template = get_template(template_name)

        preloaded_files: dict[str, GeneratedFile] = {}
        template_details: dict[str, Any] = {}

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
                if ws_send_fn:
                    await ws_send_fn({
                        "type": "file_generated",
                        "filePath": path,
                        "fileContents": content,
                        "language": lang,
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

        graph = build_graph()
        checkpointer = MemorySaver()
        compiled = graph.compile(checkpointer=checkpointer)

        initial_state: CodeGenState = {
            "session_id": session_id,
            "user_query": user_query,
            "template_name": template_name,
            "generated_files": preloaded_files,
            "phases": [],
            "current_phase_index": 0,
            "current_dev_state": "blueprint_generating",
            "conversation_messages": [],
            "should_continue": True,
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
