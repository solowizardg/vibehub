"""Code review node for LLM-based code review before sandbox execution.

This module provides a third layer of defense in the AI code quality pipeline:
1. Prompt engineering (layer 1)
2. Pre-validation static checks (layer 2)
3. LLM code review (layer 3) <- This module
4. Sandbox execution (layer 4)
"""

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.callback_registry import ws_send
from agent.llm_content import llm_content_to_text
from agent.state import CodeGenState

logger = logging.getLogger(__name__)

CODE_REVIEW_SYSTEM_PROMPT = """You are a senior code reviewer performing pre-merge review.

Review the generated code for this phase and identify issues before they reach production.

Project: {project_name}
Phase: {phase_name}

Files to review:
{files_content}

Design Blueprint (must verify compliance):
{design_blueprint}

Check for these categories of issues:

## 1. Type Safety
- Missing type annotations
- Incorrect generic usage
- Implicit any types
- Incorrect prop types

## 2. Import/Export Consistency
- Importing non-existent exports
- Default vs named import mismatch
- Circular dependencies

## 3. React Best Practices
- Missing keys in lists
- Incorrect hook dependencies
- State mutation issues
- Missing cleanup in useEffect

## 4. Design System Compliance
- Not following color palette from blueprint
- Incorrect spacing/tokens
- Inconsistent component patterns

## 5. Common Gotchas
- Missing "use client" for browser APIs
- Incorrect Framer Motion types
- Missing cn() import
- Accessibility issues

Output format:
{{
  "approved": true/false,
  "issues": [
    {{
      "file": "path/to/file.tsx",
      "line": 42,
      "severity": "error" | "warning",
      "category": "type_safety" | "import_export" | "react" | "design" | "common",
      "message": "Description of the issue",
      "suggested_fix": "The corrected code"
    }}
  ],
  "summary": "Brief review summary"
}}

If no issues found, return approved: true with empty issues array."""


async def code_review_node(state: CodeGenState, config) -> dict[str, Any]:
    """Review generated code before sandbox execution.

    This node performs LLM-based code review to catch issues that static
    analysis might miss, such as:
    - Cross-file consistency issues
    - Design system compliance
    - React best practices
    - Logic errors

    Args:
        state: Current code generation state
        config: LangGraph config

    Returns:
        State updates with review results and next state transition
    """
    from agent.graph import get_llm

    sid = state.get("session_id", "")
    phases = state.get("phases", [])
    current_idx = state.get("current_phase_index", 0)
    generated_files = dict(state.get("generated_files", {}))

    if current_idx >= len(phases):
        return {"current_dev_state": "sandbox_executing"}

    # Current phase was already incremented by phase_implementation_node
    # So current_idx - 1 is the index of the phase we just processed
    phase = phases[current_idx - 1]
    phase_index = int(phase.get("index", current_idx - 1))

    # Track review attempts for this phase
    review_attempts = state.get("code_review_attempts", 0)
    max_review_attempts = 2  # Maximum number of review-fix cycles

    await ws_send(sid, {
        "type": "phase_reviewing",
        "phase_index": phase_index,
        "attempt": review_attempts + 1,
    })

    # Get files from current phase
    phase_files = []
    for path, file_data in generated_files.items():
        if file_data.get("phase_index") == phase_index:
            phase_files.append((path, file_data))

    if not phase_files:
        logger.debug("No files found for phase %d, skipping code review", phase_index)
        return {"current_dev_state": "sandbox_executing"}

    # Build file content for review
    files_content = []
    for path, file_data in phase_files:
        content = str(file_data.get("file_contents", ""))
        files_content.append(f"=== {path} ===\n{content}\n")
    files_content_str = "\n".join(files_content)

    # Get design blueprint
    blueprint = state.get("blueprint", {})
    design_blueprint = blueprint.get("design_blueprint", {})

    llm = get_llm()

    prompt = CODE_REVIEW_SYSTEM_PROMPT.format(
        project_name=state.get("project_name", "my-app"),
        phase_name=phase.get("name", f"Phase {phase_index}"),
        files_content=files_content_str,
        design_blueprint=json.dumps(design_blueprint, ensure_ascii=False, indent=2),
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Review the code and provide feedback in the specified JSON format."),
        ])
    except Exception as e:
        logger.warning("LLM code review failed for session %s: %s", sid, str(e)[:200])
        # Fail open - proceed to sandbox if review fails
        await ws_send(sid, {
            "type": "phase_review_skipped",
            "phase_index": phase_index,
            "reason": "llm_error",
        })
        return {
            "review_issues": [],
            "current_dev_state": "sandbox_executing",
        }

    content = llm_content_to_text(response.content if hasattr(response, "content") else response)

    # Parse review result
    try:
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            review_result = json.loads(json_match.group())
        else:
            review_result = json.loads(content)

        approved = review_result.get("approved", False)
        issues = review_result.get("issues", [])

        # Filter to only error severity for blocking (warnings don't block)
        blocking_issues = [i for i in issues if i.get("severity") == "error"]

        if not approved and blocking_issues:
            # Format issues for feedback
            error_messages = []
            for issue in blocking_issues:
                file_path = issue.get("file", "unknown")
                line = issue.get("line", "?")
                severity = issue.get("severity", "error")
                message = issue.get("message", "")
                error_messages.append(f"[{severity}] {file_path}:{line}: {message}")

            logger.warning(
                "Code review found %d blocking issues for session %s (phase %d, attempt %d)",
                len(blocking_issues),
                sid,
                phase_index,
                review_attempts + 1,
            )

            await ws_send(sid, {
                "type": "phase_review_failed",
                "phase_index": phase_index,
                "issues": issues,
                "summary": review_result.get("summary", ""),
                "attempt": review_attempts + 1,
            })

            # Check if we've exceeded max review attempts
            if review_attempts >= max_review_attempts:
                logger.warning(
                    "Max code review attempts (%d) reached for session %s, proceeding to sandbox",
                    max_review_attempts,
                    sid,
                )
                await ws_send(sid, {
                    "type": "phase_review_max_attempts",
                    "phase_index": phase_index,
                    "message": "Max review attempts reached, proceeding to sandbox execution",
                })
                return {
                    "review_issues": [],
                    "current_dev_state": "sandbox_executing",
                    "code_review_attempts": 0,  # Reset for next phase
                }

            return {
                "review_issues": issues,
                "review_error_messages": error_messages,
                "current_dev_state": "code_review_fixing",
                "code_review_attempts": review_attempts + 1,
            }

        # Review passed or no blocking issues
        await ws_send(sid, {
            "type": "phase_review_passed",
            "phase_index": phase_index,
            "summary": review_result.get("summary", "Code review passed"),
            "warnings_count": len([i for i in issues if i.get("severity") == "warning"]),
        })

        return {
            "review_issues": [],
            "current_dev_state": "sandbox_executing",
            "code_review_attempts": 0,  # Reset for next phase
        }

    except json.JSONDecodeError as e:
        logger.warning("Failed to parse code review JSON for session %s: %s", sid, str(e)[:200])
        # Fail open - proceed to sandbox if review parsing fails
        await ws_send(sid, {
            "type": "phase_review_skipped",
            "phase_index": phase_index,
            "reason": "parse_error",
        })
        return {
            "review_issues": [],
            "current_dev_state": "sandbox_executing",
        }
    except Exception as e:
        logger.warning("Unexpected error in code review for session %s: %s", sid, str(e)[:200])
        # Fail open - proceed to sandbox if review fails
        await ws_send(sid, {
            "type": "phase_review_skipped",
            "phase_index": phase_index,
            "reason": "error",
        })
        return {
            "review_issues": [],
            "current_dev_state": "sandbox_executing",
        }
