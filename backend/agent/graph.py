import logging
import os
import hashlib
import time
from functools import wraps
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.nodes.blueprint import blueprint_node
from agent.nodes.code_review import code_review_node
from agent.nodes.finalizing import finalizing_node
from agent.nodes.phase_implementation import phase_implementation_node
from agent.nodes.pre_validation import pre_validation_node
from agent.nodes.sandbox_execution import sandbox_execution_node
from agent.nodes.sandbox_fix import sandbox_fix_node
from agent.state import CodeGenState
from config import settings

logger = logging.getLogger(__name__)

_llm: BaseChatModel | None = None
_llm_blueprint: BaseChatModel | None = None  # For blueprint generation (higher quality)
_llm_generation: BaseChatModel | None = None  # For code generation (faster)

# Maximum limits to prevent infinite loops
MAX_PRE_VALIDATION_ATTEMPTS = 2  # Max retry attempts per phase for pre-validation
MAX_CODE_REVIEW_ATTEMPTS = 2  # Max retry attempts for code review
MAX_GRAPH_RECURSION_LIMIT = 100  # LangGraph recursion limit

# Retry configuration for LLM calls
LLM_MAX_RETRIES = 3
LLM_BASE_DELAY = 2.0  # seconds
LLM_RETRYABLE_ERRORS = (503, 429, 500, 502, 504)  # HTTP status codes to retry


def _create_gemini_llm(model_name: str, timeout: int = 300) -> BaseChatModel:
    """Create a Gemini LLM instance."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    gemini_key = settings.google_api_key

    if not gemini_key:
        raise RuntimeError("No LLM API key configured. Set GOOGLE_API_KEY in .env")

    logger.info(f"[LLM] Initializing Gemini model: {model_name} (timeout={timeout}s)")
    try:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=gemini_key,
            temperature=0.2,
            timeout=timeout,
            max_retries=0,  # We handle retries ourselves
        )
        logger.info(f"[LLM] Gemini model {model_name} initialized successfully")
        return llm
    except Exception as e:
        logger.error(f"[LLM] Failed to initialize Gemini model {model_name}: {e}")
        raise


def get_llm() -> BaseChatModel:
    """Get the default LLM instance (for backward compatibility)."""
    global _llm
    if _llm is not None:
        return _llm

    gemini_model = settings.gemini_model or "gemini-3-flash-preview"
    _llm = _create_gemini_llm(gemini_model)
    return _llm


def get_llm_blueprint() -> BaseChatModel:
    """Get LLM for blueprint generation (uses high-quality model)."""
    global _llm_blueprint
    if _llm_blueprint is not None:
        return _llm_blueprint

    # Use 3.1 pro for blueprint, fallback to default if not set
    blueprint_model = settings.gemini_blueprint_model or "gemini-3.1-pro-preview"
    _llm_blueprint = _create_gemini_llm(blueprint_model, timeout=600)  # 10 min for complex blueprints
    return _llm_blueprint


def get_llm_generation() -> BaseChatModel:
    """Get LLM for code generation (uses faster model)."""
    global _llm_generation
    if _llm_generation is not None:
        return _llm_generation

    # Use flash-preview for generation (correct model name)
    generation_model = settings.gemini_generation_model or "gemini-3-flash-preview"
    _llm_generation = _create_gemini_llm(generation_model, timeout=300)  # 5 min for generation
    return _llm_generation


class RetryableLLMWrapper:
    """Wrapper around LLM that adds retry logic for transient errors."""

    def __init__(self, llm: BaseChatModel):
        self._llm = llm

    async def ainvoke(self, *args, **kwargs) -> BaseMessage:
        """Invoke LLM with retry logic for transient errors."""
        last_exception = None

        # Log the model being used and request details
        model_name = getattr(self._llm, 'model', 'unknown')
        logger.info(f"[LLM] Starting ainvoke with model: {model_name}")
        logger.info(f"[LLM] NOTE: gemini-3.1-pro-preview may take 30-60s for first response, please wait...")
        logger.debug(f"[LLM] Request args length: {len(str(args))}, kwargs: {list(kwargs.keys())}")

        for attempt in range(LLM_MAX_RETRIES):
            logger.info(f"[LLM] Attempt {attempt + 1}/{LLM_MAX_RETRIES} starting...")
            start_time = time.time()
            last_progress_time = start_time
            try:
                # Use asyncio.wait_for to add a progress heartbeat
                import asyncio
                result = await self._llm.ainvoke(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f"[LLM] Success after {elapsed:.2f}s on attempt {attempt + 1}")
                # Log result size
                result_content = getattr(result, 'content', str(result))
                logger.debug(f"[LLM] Response size: {len(str(result_content))} chars")
                return result
            except Exception as e:
                last_exception = e
                error_str = str(e)

                # Check if error is retryable
                is_retryable = False
                for code in LLM_RETRYABLE_ERRORS:
                    if str(code) in error_str or f"{code}" in error_str:
                        is_retryable = True
                        break

                # Also check for common transient error patterns
                if any(pattern in error_str.lower() for pattern in [
                    "unavailable", "high demand", "rate limit", "too many requests",
                    "temporary", "overloaded", "timeout", "deadline exceeded"
                ]):
                    is_retryable = True

                if not is_retryable:
                    elapsed = time.time() - start_time
                    logger.error(f"[LLM] Non-retryable error after {elapsed:.2f}s: {error_str}")
                    raise  # Non-retryable error, raise immediately

                if attempt < LLM_MAX_RETRIES - 1:
                    delay = LLM_BASE_DELAY * (2 ** attempt)  # Exponential backoff
                    elapsed = time.time() - start_time
                    logger.warning(
                        "[LLM] Attempt %d/%d failed after %.2fs: %s. Retrying in %.1fs...",
                        attempt + 1, LLM_MAX_RETRIES, elapsed, error_str, delay
                    )
                    time.sleep(delay)
                else:
                    elapsed = time.time() - start_time
                    logger.error(
                        "[LLM] All %d attempts failed. Last error after %.2fs: %s",
                        LLM_MAX_RETRIES, elapsed, error_str
                    )

        raise last_exception

    def __getattr__(self, name):
        """Delegate other attributes to the wrapped LLM."""
        return getattr(self._llm, name)


def get_llm_with_retry() -> RetryableLLMWrapper:
    """Get LLM wrapped with retry logic."""
    return RetryableLLMWrapper(get_llm())


def route_after_phase(state: CodeGenState) -> str:
    """After phase implementation: more phases or pre-validation."""
    phases = state.get("phases", [])
    current_idx = state.get("current_phase_index", 0)
    if current_idx < len(phases):
        return "phase_implementation"
    return "pre_validation"


def route_after_pre_validation(state: CodeGenState) -> str:
    """After pre-validation: retry if errors (up to max attempts), else go to code review."""
    should_retry = state.get("should_retry_phase", False)
    validation_errors = state.get("validation_errors", [])
    current_idx = state.get("current_phase_index", 0)

    if should_retry and validation_errors:
        # Check if we've exceeded max attempts for this phase
        phase_attempts = state.get("current_phase_validation_attempts", {})
        attempts_for_phase = phase_attempts.get(current_idx, 0)

        if attempts_for_phase < MAX_PRE_VALIDATION_ATTEMPTS:
            logger.info(
                "Pre-validation failed for phase %d, attempt %d/%d. Retrying...",
                current_idx, attempts_for_phase, MAX_PRE_VALIDATION_ATTEMPTS
            )
            return "phase_implementation"
        else:
            logger.warning(
                "Pre-validation failed for phase %d after %d attempts. Proceeding to code review.",
                current_idx, attempts_for_phase
            )
            # Reset for next phase and continue to code review
            return "code_review"

    return "code_review"


def route_after_sandbox(state: CodeGenState) -> str:
    """After sandbox execution: fix errors or finalize."""
    dev_state = state.get("current_dev_state", "finalizing")
    if dev_state == "sandbox_fixing":
        return "sandbox_fix"
    return "finalizing"


def route_after_code_review(state: CodeGenState) -> str:
    """After code review: retry if issues found (up to max attempts), else go to sandbox."""
    dev_state = state.get("current_dev_state", "finalizing")
    current_idx = state.get("current_phase_index", 0)

    # If code review found issues and set state to code_review_fixing
    if dev_state == "code_review_fixing":
        # Check if we've exceeded max attempts for code review
        code_review_attempts = state.get("code_review_attempts", 0)
        if code_review_attempts < MAX_CODE_REVIEW_ATTEMPTS:
            logger.info(
                "Code review failed for phase %d, attempt %d/%d. Retrying...",
                current_idx, code_review_attempts, MAX_CODE_REVIEW_ATTEMPTS
            )
            return "code_review_fix"
        else:
            logger.warning(
                "Code review failed for phase %d after %d attempts. Proceeding to sandbox.",
                current_idx, code_review_attempts
            )
            return "sandbox_execution"

    return "sandbox_execution"


def route_after_code_review_fix(state: CodeGenState) -> str:
    """After code review fix: go back to code review for re-validation."""
    return "code_review"


def build_graph() -> StateGraph:
    """Build the code generation state graph."""
    graph = StateGraph(CodeGenState)

    graph.add_node("blueprint_generation", blueprint_node)
    graph.add_node("phase_implementation", phase_implementation_node)
    graph.add_node("pre_validation", pre_validation_node)
    graph.add_node("code_review", code_review_node)
    graph.add_node("code_review_fix", code_review_node)  # Same node, different state
    graph.add_node("sandbox_execution", sandbox_execution_node)
    graph.add_node("sandbox_fix", sandbox_fix_node)
    graph.add_node("finalizing", finalizing_node)

    graph.add_edge(START, "blueprint_generation")
    graph.add_edge("blueprint_generation", "phase_implementation")
    # After phase implementation, go to pre-validation instead of directly to sandbox
    graph.add_conditional_edges("phase_implementation", route_after_phase)
    # After pre-validation, either retry phase implementation or go to code review
    graph.add_conditional_edges("pre_validation", route_after_pre_validation)
    # After code review, either retry with fixes or go to sandbox
    graph.add_conditional_edges("code_review", route_after_code_review)
    # After code review fix, go back to code review for re-validation
    graph.add_conditional_edges("code_review_fix", route_after_code_review_fix)
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

        initial_state: CodeGenState = {
            "session_id": session_id,
            "user_query": user_query,
            "blueprint": existing_blueprint or {},
            "template_name": template_name,
            "generated_files": preloaded_files,
            "phases": [],
            "current_phase_index": 0,
            "current_dev_state": "blueprint_generating",
            "conversation_messages": [],
            "should_continue": True,
            "sandbox_id": existing_sandbox_id,
            "sandbox_bootstrapped": bool(existing_sandbox_id),
            "sandbox_deps_installed": bool(existing_sandbox_id),
            "sandbox_package_json_hash": package_json_hash,
            "sandbox_fix_attempts": 0,
            "template_details": template_details,
            # Pre-validation fields initialization
            "validation_errors": [],
            "detailed_validation_errors": [],
            "should_retry_phase": False,
            "pre_validation_attempts": 0,
            "current_phase_validation_attempts": {},
            # Code review fields initialization
            "review_issues": [],
            "review_error_messages": [],
            "code_review_attempts": 0,
        }

        config = {
            "configurable": {
                "thread_id": session_id,
                "recursion_limit": MAX_GRAPH_RECURSION_LIMIT,
            }
        }

        final_state = None
        logger.info(f"[Graph] Session {session_id}: Starting graph execution...")
        try:
            step = 0
            async for event in compiled.astream(initial_state, config, stream_mode="values"):
                step += 1
                dev_state = event.get("current_dev_state", "unknown") if isinstance(event, dict) else "unknown"
                phase_idx = event.get("current_phase_index", -1) if isinstance(event, dict) else -1
                logger.info(f"[Graph] Session {session_id}: Step {step}, state={dev_state}, phase={phase_idx}")
                final_state = event
            logger.info(f"[Graph] Session {session_id}: Graph execution completed after {step} steps")
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            logger.error(f"[Graph] Session {session_id}: Execution failed at step {step}. Error type={error_type}")
            logger.error(f"[Graph] Session {session_id}: Error message: {error_msg[:500]}")
            logger.exception("[Graph] Session %s: Full traceback", session_id)
            # Send error to websocket if callback is registered
            if ws_send_fn:
                try:
                    await ws_send_fn({
                        "type": "error",
                        "message": f"Code generation pipeline error: {str(e)}",
                    })
                except Exception:
                    pass
            raise

        return final_state or {}
    finally:
        unregister_ws_callback(session_id)
