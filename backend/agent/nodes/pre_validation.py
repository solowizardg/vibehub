"""Pre-validation node for catching TypeScript errors before sandbox execution.

This module provides fast static analysis to catch common TypeScript errors
without needing to run the full tsc compiler in the sandbox.
"""

import logging
import re
from typing import Any

from agent.callback_registry import ws_send
from agent.state import CodeGenState

logger = logging.getLogger(__name__)


def _has_props_type_defined(content: str, component_name: str) -> bool:
    """Check if a component has Props interface or type defined.

    Args:
        content: The file content to check
        component_name: Name of the component (e.g., "Button")

    Returns:
        True if Props type is defined or component doesn't need props
    """
    # Check for interface or type with Props suffix
    props_patterns = [
        rf"interface\s+{component_name}Props\s*{{",
        rf"type\s+{component_name}Props\s*=",
        rf"interface\s+Props\s*{{",
        rf"type\s+Props\s*=",
    ]

    for pattern in props_patterns:
        if re.search(pattern, content):
            return True

    # Check if function parameter already has a type annotation
    # Pattern: export function ComponentName(props: SomeType) or ({ ... }: SomeType)
    func_pattern = rf"export\s+(?:function|const)\s+{component_name}\s*[\(\<]"
    func_match = re.search(func_pattern, content)
    if func_match:
        # Look for type annotation after the opening parenthesis
        start_idx = func_match.end() - 1
        remaining = content[start_idx:start_idx + 200]
        # Check for type annotation like (props: Type) or ({ ... }: Type)
        if re.search(r"[\(\{]\s*\w*\s*\:\s*[A-Z][a-zA-Z0-9]*", remaining):
            return True
        # Check for generic type parameter like <T>(props: T)
        if re.search(r"\<[^>]+\>\s*\(", remaining):
            return True

    return False


def _has_data_vibehub_attributes(content: str, component_name: str) -> bool:
    """Check if a component has data-vibehub-* attributes on its root element.

    Args:
        content: The file content to check
        component_name: Name of the component (e.g., "Button")

    Returns:
        True if data-vibehub attributes are found on root element
    """
    # Find the component function definition (supports both named and default exports)
    func_patterns = [
        rf"export\s+function\s+{component_name}\s*\([^)]*\)\s*{{",
        rf"export\s+const\s+{component_name}\s*=\s*(?:\([^)]*\)\s*=>|{{)",
        rf"export\s+default\s+function\s+{component_name}\s*\([^)]*\)\s*{{",
    ]

    for pattern in func_patterns:
        match = re.search(pattern, content)
        if match:
            # Get content after function definition
            start_idx = match.end()
            remaining = content[start_idx:]

            # Find the return statement and first JSX element
            # Look for return statement followed by JSX
            return_match = re.search(
                r"return\s*\(?\s*(<\w+", remaining
            )
            if return_match:
                # Check if the first JSX element has data-vibehub-component
                jsx_start = remaining[return_match.start():return_match.start() + 500]
                if f'data-vibehub-component="{component_name}"' in jsx_start:
                    return True
                if 'data-vibehub-component=' in jsx_start:
                    return True  # Has some data-vibehub-component attribute

    return False


def _is_missing_param_types(content: str, func_name: str, params: str) -> bool:
    """Check if function parameters are missing type annotations.

    Args:
        content: The file content
        func_name: Name of the function
        params: The parameter string from the regex match

    Returns:
        True if parameters are missing type annotations
    """
    # Skip if no parameters or empty
    if not params or not params.strip():
        return False

    # Skip Next.js special files (page, layout, loading, error, etc.)
    nextjs_special = ["page", "layout", "loading", "error", "not-found", "template", "default"]
    if func_name.lower() in nextjs_special:
        return False

    # Check if params already have type annotations
    # Look for patterns like: (props: Type), ({ a, b }: Type), (a: string, b: number)
    if re.search(r":\s*[A-Z][a-zA-Z0-9_]*(?:<[^>]+>)?", params):
        return False

    # Check for inline type annotations in destructured params
    # e.g., ({ name }: { name: string })
    if re.search(r"\}\s*:\s*\{", params):
        return False

    # Check for React.FC or similar generic type usage
    func_pattern = rf"export\s+const\s+{func_name}\s*:\s*React\.[A-Z]"
    if re.search(func_pattern, content):
        return False

    return True


def _defines_cn_locally(content: str) -> bool:
    return bool(
        re.search(r"\b(?:export\s+)?function\s+cn\s*\(", content)
        or re.search(r"\b(?:export\s+)?const\s+cn\s*=", content)
    )


def _is_missing_cn_import(content: str, file_path: str = "") -> bool:
    normalized_path = file_path.replace("\\", "/").lower()
    if normalized_path.endswith("/lib/cn.ts") or normalized_path.endswith("/lib/utils.ts"):
        return False
    if _defines_cn_locally(content):
        return False
    has_import = re.search(r"import\s*\{\s*cn\s*\}\s*from\s*['\"][^'\"]+['\"]", content)
    return has_import is None


# TypeScript error patterns for fast detection (applies to ALL templates)
TS_ERROR_PATTERNS: dict[str, dict[str, Any]] = {
    "missing_cn_import": {
        "pattern": re.compile(r"\bcn\s*\("),
        "check_func": lambda content, match, file_path="": _is_missing_cn_import(content, file_path),
        "message": "Using cn() without importing it",
        "fix_hint": "Add: import { cn } from '@/lib/cn' (Next.js) or '@/lib/utils' (React)",
        "severity": "error",
    },
    "framer_motion_string_ease": {
        "pattern": re.compile(r'ease\s*:\s*"[^"]+"'),
        "check_func": lambda content: True,  # Always flag string ease values
        "message": "Framer Motion ease uses string instead of array literal",
        "fix_hint": "Change to: ease: [0.25, 0.1, 0.25, 1] (or other cubic-bezier array)",
        "severity": "error",
    },
    "implicit_any_params": {
        "pattern": re.compile(r"function\s+\w+\s*\(\s*([^):]*\w+[^):]*)\s*\)(?!\s*:\s*[A-Za-z])"),
        "check_func": lambda content, match: match.groups() and ":" not in (match.group(1) or "") and (match.group(1) or "").strip(),
        "message": "Function parameters lack type annotations",
        "fix_hint": "Add types to parameters, e.g., (props: MyProps) or (name: string)",
        "severity": "warning",
    },
    "inline_props_type": {
        "pattern": re.compile(r"function\s+\w+\s*\(\s*\{\s*[^}]+\s*\}\s*:\s*\{\s*[^}]+\}\s*\)"),
        "check_func": lambda content: True,
        "message": "Using inline type annotation instead of interface",
        "fix_hint": "Extract to interface: interface ComponentNameProps { ... }",
        "severity": "warning",
    },
    "missing_props_interface": {
        "pattern": re.compile(r"export\s+(?:function|const)\s+([A-Z][a-zA-Z0-9]*)\s*[\(\<]"),
        "check_func": lambda content, match: not _has_props_type_defined(content, match.group(1)),
        "message": "Exported React component missing Props interface/type",
        "fix_hint": "Define interface: interface ComponentNameProps { ... } and use it in function parameter",
        "severity": "warning",
    },
    "missing_param_types": {
        "pattern": re.compile(r"export\s+function\s+([A-Z][a-zA-Z0-9]*)\s*\(\s*([^):]*)\)"),
        "check_func": lambda content, match: _is_missing_param_types(content, match.group(1), match.group(2)),
        "message": "Function parameters missing type annotations",
        "fix_hint": "Add type annotations to all parameters, e.g., (props: MyProps) or destructure with types: ({ name }: { name: string })",
        "severity": "warning",
    },
    "any_type_usage": {
        "pattern": re.compile(r":\s*\bany\b"),
        "check_func": lambda content: True,
        "message": "Using 'any' type (avoid if possible)",
        "fix_hint": "Use specific type or 'unknown' instead of 'any'",
        "severity": "warning",
    },
    "invalid_jsx_tag_double_dot": {
        "pattern": re.compile(r"<\w+\.\w+\.\w+"),
        "check_func": lambda content: True,
        "message": "Invalid JSX tag with double dot notation (e.g., <div.div>)",
        "fix_hint": "Use valid JSX tag: <div> for HTML, <Component> for custom, <motion.div> for Framer Motion",
        "severity": "error",
    },
    "invalid_motion_jsx_syntax": {
        "pattern": re.compile(r"<motion\.\s*[>\s]"),
        "check_func": lambda content: True,
        "message": "Incomplete or invalid motion JSX tag",
        "fix_hint": "Use <motion.div> (with element name after dot). Ensure: import { motion } from 'framer-motion'",
        "severity": "error",
    },
    "jsx_identifier_expected_pattern": {
        "pattern": re.compile(r"<\.\w+"),
        "check_func": lambda content: True,
        "message": "JSX tag starting with dot (e.g., <.div>)",
        "fix_hint": "Remove leading dot: use <div> instead of <.div>",
        "severity": "error",
    },
    "motion_without_import": {
        "pattern": re.compile(r"<motion\.\w+"),
        "check_func": lambda content: "import { motion }" not in content and "import * as motion" not in content,
        "message": "Using motion component without importing framer-motion",
        "fix_hint": "Add: import { motion } from 'framer-motion'",
        "severity": "error",
    },
    "nextjs_page_missing_default_export": {
        "pattern": re.compile(r"(?:export\s+function|export\s+const)\s+\w+"),
        "check_func": lambda content, match, file_path="": (
            file_path.endswith(("page.tsx", "page.ts", "layout.tsx", "layout.ts"))
            and "export default" not in content
        ),
        "message": "Next.js App Router page/layout file missing default export",
        "fix_hint": "Add 'export default' to the component, or change 'export function' to 'export default function'",
        "severity": "error",
    },
    "missing_data_vibehub_attributes": {
        "pattern": re.compile(r"export\s+(?:default\s+)?(?:function|const)\s+([A-Z][a-zA-Z0-9]*)"),
        "check_func": lambda content, match: not _has_data_vibehub_attributes(content, match.group(1)),
        "message": "Exported React component missing data-vibehub-* attributes on root element",
        "fix_hint": 'Add to root element: data-vibehub-component="ComponentName" data-vibehub-id="unique-id" data-vibehub-file="src/components/xxx.tsx"',
        "severity": "warning",
    },
}

# Template-specific pattern overrides
# Structure: {template_name: {error_type: config_override}}
# Only ADD patterns here (override with additional checks)
TEMPLATE_SPECIFIC_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "nextjs": {
        # Next.js App Router requires "use client" for hooks and browser APIs
        "missing_use_client_hooks": {
            "pattern": re.compile(r"\b(useState|useEffect|useCallback|useMemo|useRef|useReducer|useContext|useLayoutEffect)\s*\("),
            "check_func": lambda content: '"use client"' not in content,
            "message": "React hooks used without 'use client' directive in Next.js",
            "fix_hint": 'Add "use client" as the FIRST line before imports',
            "severity": "error",
        },
        "missing_use_client_browser_api": {
            "pattern": re.compile(r"\b(window|document|localStorage|sessionStorage|navigator|location)\b"),
            "check_func": lambda content: '"use client"' not in content,
            "message": "Browser API used without 'use client' directive in Next.js",
            "fix_hint": 'Add "use client" as the FIRST line before imports',
            "severity": "error",
        },
        "missing_use_client_events": {
            "pattern": re.compile(r"\bon([A-Z][a-zA-Z]+)\s*=\s*\{"),
            "check_func": lambda content: '"use client"' not in content,
            "message": "Event handlers used without 'use client' directive in Next.js",
            "fix_hint": 'Add "use client" as the FIRST line before imports',
            "severity": "warning",
        },
    },
    # React Vite does NOT check for "use client" - it's not required
}


def quick_typescript_check(
    file_path: str,
    content: str,
    template_name: str,
) -> list[dict[str, Any]]:
    """Perform fast TypeScript error detection without running tsc.

    Args:
        file_path: Path to the file being checked
        content: File content
        template_name: Template type (nextjs, react-vite, etc.)

    Returns:
        List of error dictionaries with file, line, type, message, fix_hint
    """
    errors: list[dict[str, Any]] = []

    # Skip non-TypeScript files
    if not file_path.endswith((".ts", ".tsx")):
        return errors

    # Get patterns for this template
    patterns = dict(TS_ERROR_PATTERNS)
    template_overrides = TEMPLATE_SPECIFIC_OVERRIDES.get(template_name, {})
    # Apply template-specific overrides
    for error_type, override_config in template_overrides.items():
        if error_type in patterns:
            patterns[error_type] = override_config

    for error_type, config in patterns.items():
        pattern = config["pattern"]
        check_func = config["check_func"]

        for match in pattern.finditer(content):
            try:
                # Check function may need the match object and/or file_path
                # Use co_argcount to determine which parameters to pass
                arg_count = check_func.__code__.co_argcount
                if arg_count >= 3:
                    result = check_func(content, match, file_path)
                elif arg_count >= 2:
                    result = check_func(content, match)
                else:
                    result = check_func(content)
            except Exception as e:
                # Fail open - if check throws, assume no error
                logger.debug(f"Pre-validation check {error_type} failed: {e}")
                result = False

            if result:
                line_num = content[: match.start()].count("\n") + 1
                errors.append({
                    "file": file_path,
                    "line": line_num,
                    "type": error_type,
                    "message": config["message"],
                    "fix_hint": config["fix_hint"],
                    "severity": config.get("severity", "error"),
                    "column": match.start() - content.rfind("\n", 0, match.start()),
                })
                # Only report first occurrence of each error type per file
                break

    return errors


def validate_all_files(
    generated_files: dict[str, dict[str, Any]],
    template_name: str,
) -> list[dict[str, Any]]:
    """Validate all generated files for TypeScript errors.

    Args:
        generated_files: Dictionary of file path -> file data
        template_name: Template type

    Returns:
        List of all errors found
    """
    all_errors: list[dict[str, Any]] = []

    for file_path, file_data in generated_files.items():
        try:
            # Handle both dict with file_contents and direct string content
            if isinstance(file_data, dict):
                content = str(file_data.get("file_contents", ""))
            else:
                content = str(file_data)
            errors = quick_typescript_check(file_path, content, template_name)
            all_errors.extend(errors)
        except Exception as e:
            # Log but don't fail validation if checking a single file errors
            logger.warning(f"Pre-validation failed for {file_path}: {e}")
            continue

    return all_errors


def _determine_retry_phase_index(current_idx: int, phases_count: int) -> int:
    """Retry from the phase that just completed (0-based)."""
    if phases_count <= 0:
        return 0
    return max(0, min(current_idx - 1, phases_count - 1))


def _sanitize_error(err: dict[str, Any]) -> dict[str, Any]:
    """Ensure error data is JSON serializable."""
    return {
        "file": str(err.get("file", "")),
        "line": int(err.get("line", 0)),
        "type": str(err.get("type", "")),
        "message": str(err.get("message", "")),
        "fix_hint": str(err.get("fix_hint", "")),
        "severity": str(err.get("severity", "error")),
        "column": int(err.get("column", 0)),
    }


def format_errors_for_feedback(errors: list[dict[str, Any]]) -> str:
    """Format errors for inclusion in LLM feedback prompt."""
    if not errors:
        return ""

    lines = ["\n## PRE-VALIDATION ERRORS DETECTED\n"]
    lines.append("Fix these issues before generating code:\n")

    for err in errors:
        severity_emoji = "❌" if err["severity"] == "error" else "⚠️"
        lines.append(
            f"{severity_emoji} {err['file']}:{err['line']}: {err['message']}"
        )
        lines.append(f"   💡 {err['fix_hint']}\n")

    return "\n".join(lines)


async def pre_validation_node(state: CodeGenState, config) -> dict[str, Any]:
    """Pre-validation node to catch TypeScript errors before sandbox.

    This node runs after phase implementation but before sandbox execution
to catch common TypeScript errors early.
    """
    sid = state.get("session_id", "")
    generated_files = dict(state.get("generated_files", {}))
    template_name = state.get("template_name", "react-vite")
    phases = state.get("phases", [])
    current_idx = state.get("current_phase_index", 0)
    retry_phase_index = _determine_retry_phase_index(current_idx, len(phases))

    # Get current phase for context
    # Note: current_idx has already been incremented by phase_implementation_node
    # So current_idx - 1 is the index of the phase we just processed
    if current_idx > 0 and current_idx <= len(phases):
        current_phase = phases[current_idx - 1]
        phase_index = int(current_phase.get("index", current_idx - 1))
    else:
        phase_index = 0

    # Track validation attempts for the phase being retried.
    # Key by retry_phase_index so retries are counted consistently.
    phase_attempts = dict(state.get("current_phase_validation_attempts", {}))
    attempts_for_phase = phase_attempts.get(retry_phase_index, 0) + 1
    phase_attempts[retry_phase_index] = attempts_for_phase

    await ws_send(sid, {
        "type": "phase_validating",
        "phase_index": phase_index,
        "attempt": attempts_for_phase,
    })

    # Run validation
    errors = validate_all_files(generated_files, template_name)

    # Filter to only errors (not warnings) for blocking
    blocking_errors = [e for e in errors if e["severity"] == "error"]

    if blocking_errors:
        target_files = list(
            dict.fromkeys(
                str(err.get("file", "")).strip()
                for err in blocking_errors
                if str(err.get("file", "")).strip() in generated_files
            ),
        )
        logger.warning(
            (
                "Pre-validation found %d blocking errors for session %s "
                "(phase %d, attempt %d). Retrying phase %d with %d target files."
            ),
            len(blocking_errors),
            sid,
            phase_index,
            attempts_for_phase,
            retry_phase_index,
            len(target_files),
        )

        # Send validation errors to frontend
        await ws_send(sid, {
            "type": "validation_errors",
            "phase_index": phase_index,
            "errors": errors,
            "blocking_count": len(blocking_errors),
            "attempt": attempts_for_phase,
        })

        # Format errors for state
        error_messages = [
            f"{e['file']}:{e['line']}: {e['message']}"
            for e in blocking_errors
        ]

        # Ensure all error data is JSON serializable
        sanitized_errors = [_sanitize_error(err) for err in errors]

        return {
            "validation_errors": error_messages,
            "detailed_validation_errors": sanitized_errors,
            "current_dev_state": "phase_fixing",
            "current_phase_index": retry_phase_index,
            "validation_target_files": target_files,
            "should_retry_phase": True,
            "pre_validation_attempts": state.get("pre_validation_attempts", 0) + 1,
            "current_phase_validation_attempts": dict(phase_attempts),
        }

    # No blocking errors - proceed to sandbox
    await ws_send(sid, {
        "type": "phase_validation_passed",
        "phase_index": phase_index,
        "attempt": attempts_for_phase,
    })

    # Ensure all error data is JSON serializable
    sanitized_errors = [_sanitize_error(err) for err in errors]

    return {
        "validation_errors": [],
        "detailed_validation_errors": sanitized_errors,  # Include warnings
        "validation_target_files": [],
        "current_dev_state": "sandbox_executing",
        "should_retry_phase": False,
    }
