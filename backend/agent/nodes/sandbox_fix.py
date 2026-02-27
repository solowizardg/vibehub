import logging
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent.callback_registry import ws_send
from agent.file_constraints import enforce_nextjs_config_filename
from agent.llm_content import llm_content_to_text
from agent.nodes.phase_implementation import parse_files_from_response
from agent.prompts import (
    SANDBOX_FIX_BATCH_HUMAN_PROMPT,
    SANDBOX_FIX_FILE_SELECTOR_PROMPT,
    SANDBOX_FIX_SYSTEM_PROMPT,
)
from agent.state import CodeGenState

logger = logging.getLogger(__name__)

KNOWN_DEPENDENCY_VERSIONS: dict[str, str] = {
    "framer-motion": "^12.23.26",
    "zod": "^3.23.8",
    "@hookform/resolvers": "^3.9.0",
    "react-hook-form": "^7.62.0",
    "tailwindcss-animate": "^1.0.7",
    "cmdk": "^1.1.1",
    "embla-carousel-react": "^8.6.0",
    "input-otp": "^1.4.2",
    "next-themes": "^0.4.4",
    "react-day-picker": "^9.11.1",
    "react-resizable-panels": "^3.0.3",
    "sonner": "^2.0.7",
    "vaul": "^1.1.2",
}


def _extract_json_array(text: str) -> list[str]:
    raw = text.strip()
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    if code_block:
        raw = code_block.group(1).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(v).strip() for v in data if isinstance(v, str) and str(v).strip()]
    except Exception:
        pass
    return []


def _extract_paths_from_error(error_output: str) -> list[str]:
    if not error_output:
        return []
    pattern = re.compile(r"([A-Za-z0-9_./-]+\.(?:tsx?|jsx?|json|css|scss|md|mjs|cjs|py|html))")
    found: list[str] = []
    for match in pattern.findall(error_output):
        path = match.strip().lstrip("./")
        if path:
            found.append(path)
    return found


def _extract_missing_modules_from_error(error_output: str) -> list[str]:
    if not error_output:
        return []

    patterns = [
        re.compile(r"Can't resolve ['\"]([^'\"]+)['\"]"),
        re.compile(r"Cannot find module ['\"]([^'\"]+)['\"]"),
    ]
    modules: list[str] = []
    for pattern in patterns:
        for match in pattern.findall(error_output):
            module = str(match).strip()
            if not module:
                continue
            if module.startswith(".") or module.startswith("@/") or module.startswith("node:"):
                continue
            modules.append(module)
    return _dedupe_preserve(modules)


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _auto_patch_package_json_dependencies(
    generated_files: dict[str, dict],
    missing_modules: list[str],
) -> tuple[dict[str, dict], list[str]]:
    package_entry = generated_files.get("package.json")
    if not isinstance(package_entry, dict):
        return generated_files, []

    package_text = str(package_entry.get("file_contents", ""))
    if not package_text.strip():
        return generated_files, []

    try:
        package_json = json.loads(package_text)
    except Exception:
        return generated_files, []
    if not isinstance(package_json, dict):
        return generated_files, []

    dependencies = package_json.get("dependencies")
    dev_dependencies = package_json.get("devDependencies")
    if not isinstance(dependencies, dict):
        dependencies = {}
    if not isinstance(dev_dependencies, dict):
        dev_dependencies = {}

    added: list[str] = []
    for module in missing_modules:
        version = KNOWN_DEPENDENCY_VERSIONS.get(module)
        if not version:
            continue
        if module in dependencies or module in dev_dependencies:
            continue
        dependencies[module] = version
        added.append(module)

    if not added:
        return generated_files, []

    package_json["dependencies"] = dependencies
    if dev_dependencies:
        package_json["devDependencies"] = dev_dependencies

    updated_text = json.dumps(package_json, ensure_ascii=False, indent=2) + "\n"

    updated_files = dict(generated_files)
    updated_files["package.json"] = {
        **package_entry,
        "file_path": "package.json",
        "language": package_entry.get("language", "json"),
        "file_contents": updated_text,
    }
    return updated_files, added


def _build_target_files_payload(files: list[str], generated_files: dict[str, dict]) -> str:
    parts: list[str] = []
    for path in files:
        content = str(generated_files.get(path, {}).get("file_contents", ""))
        parts.append(f"===FILE: {path}===\n{content}\n===END_FILE===")
    return "\n\n".join(parts)


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

    llm = get_llm()
    all_files = sorted(generated_files.keys())
    available_files_text = "\n".join(all_files[:400])

    error_paths = _extract_paths_from_error(error_output)
    selector_messages = [
        SystemMessage(
            content=SANDBOX_FIX_FILE_SELECTOR_PROMPT.format(
                error_output=error_output,
                available_files=available_files_text,
            )
        ),
        HumanMessage(content="Return the file list now."),
    ]
    selector_response = await llm.ainvoke(selector_messages)
    selector_text = llm_content_to_text(
        selector_response.content if hasattr(selector_response, "content") else selector_response,
    )
    model_paths = _extract_json_array(selector_text)

    candidate_files = _dedupe_preserve(error_paths + model_paths)
    candidate_files = [p for p in candidate_files if p in generated_files]

    missing_modules = _extract_missing_modules_from_error(error_output)
    generated_files, auto_added_modules = _auto_patch_package_json_dependencies(generated_files, missing_modules)
    if auto_added_modules:
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stderr",
            "text": f"Auto-added missing dependencies to package.json: {', '.join(auto_added_modules)}",
        })
        pkg = generated_files.get("package.json", {})
        await ws_send(sid, {
            "type": "file_generated",
            "filePath": "package.json",
            "fileContents": str(pkg.get("file_contents", "")),
            "language": str(pkg.get("language", "json")),
            "phaseIndex": int(pkg.get("phase_index", 0)),
        })

    if missing_modules and "package.json" in generated_files and "package.json" not in candidate_files:
        # Force dependency declaration repair when module resolution fails.
        candidate_files = ["package.json", *candidate_files]
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stderr",
            "text": f"Detected missing modules: {', '.join(missing_modules)}. Including package.json in fix targets.",
        })

    template_details = state.get("template_details", {})
    dont_touch = set(template_details.get("dont_touch_files", []) or [])
    candidate_files = [p for p in candidate_files if p not in dont_touch]

    if not candidate_files:
        fallback_candidates = [p for p in all_files if p not in dont_touch][:3]
        candidate_files = fallback_candidates
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stderr",
            "text": "Could not infer exact error files; applying batch fallback fixes to first available files.",
        })

    project_manifest = "\n".join(f"- {p}" for p in all_files[:400])
    system_prompt = SANDBOX_FIX_SYSTEM_PROMPT.format(
        project_name=state.get("project_name", "my-app"),
        error_output=error_output,
        generated_files_content=f"Project files:\n{project_manifest}",
    )

    for target_file in candidate_files:
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stdout",
            "text": f"Selected for fix: {target_file}",
        })

    batch_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=SANDBOX_FIX_BATCH_HUMAN_PROMPT.format(
                target_files="\n".join(f"- {p}" for p in candidate_files),
                target_files_content=_build_target_files_payload(candidate_files, generated_files),
                error_output=error_output,
            )
        ),
    ]
    response = await llm.ainvoke(batch_messages)
    content = llm_content_to_text(response.content if hasattr(response, "content") else response)

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

    applied_files = 0
    for effective_path, file_data in fixed_files.items():
        prior = generated_files.get(effective_path, {})
        previous_content = str(prior.get("file_contents", ""))
        new_content = str(file_data.get("file_contents", ""))
        if new_content == previous_content:
            continue

        file_data["phase_index"] = prior.get("phase_index", 0)
        generated_files[effective_path] = file_data
        applied_files += 1

        await ws_send(sid, {
            "type": "file_generated",
            "filePath": effective_path,
            "fileContents": new_content,
            "language": file_data.get("language", "plaintext"),
            "phaseIndex": file_data.get("phase_index", 0),
        })

    if applied_files == 0:
        await ws_send(sid, {
            "type": "sandbox_log",
            "stream": "stderr",
            "text": "Batch fix produced no concrete file updates; retrying validation to gather fresher errors.",
        })

    logger.info(
        "Sandbox fix attempt %d for session %s: %d files updated",
        fix_attempts + 1, sid, applied_files,
    )

    return {
        "generated_files": generated_files,
        "sandbox_fix_attempts": fix_attempts + 1,
        # Re-evaluate dependency install in next sandbox execution if package.json changed.
        "sandbox_package_json_hash": state.get("sandbox_package_json_hash"),
        "current_dev_state": "sandbox_executing",
    }
