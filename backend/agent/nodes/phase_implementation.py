import json
import logging
import posixpath
import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent.callback_registry import ws_send
from agent.few_shot_examples import inject_examples_into_prompt
from agent.file_constraints import enforce_nextjs_config_filename
from agent.llm_content import llm_content_to_text
from agent.prompts import PHASE_IMPLEMENTATION_SYSTEM_PROMPT
from agent.state import CodeGenState, GeneratedFile

logger = logging.getLogger(__name__)

MAX_PHASE_GENERATION_ATTEMPTS = 2
MAX_CONTEXT_FILES = 48
FILE_SUMMARY_SNIPPET_CHARS = 120000
MAX_VALIDATION_ERRORS_FEEDBACK = 16
NODE_BUILTIN_MODULES = {
    "assert",
    "buffer",
    "child_process",
    "console",
    "constants",
    "crypto",
    "dgram",
    "dns",
    "events",
    "fs",
    "http",
    "https",
    "module",
    "net",
    "os",
    "path",
    "process",
    "querystring",
    "readline",
    "stream",
    "string_decoder",
    "timers",
    "tls",
    "tty",
    "url",
    "util",
    "vm",
    "zlib",
}
ALWAYS_ALLOWED_EXTERNAL_PACKAGES = {
    "client-only",
    "server-only",
    "styled-jsx",
}


def _is_protected_component(path: str) -> bool:
    """Check if a path is a protected UI component.

    Protected components are base UI primitives (Button, Card, Input, etc.)
    that should not be regenerated.
    """
    return path.startswith("src/components/ui/") or "/ui/" in path


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


def _extract_export_info(file_content: str) -> tuple[bool, set[str]]:
    has_default = bool(re.search(r"\bexport\s+default\b", file_content))
    named: set[str] = set()

    for match in re.findall(
        r"\bexport\s+(?:const|function|class|type|interface|enum)\s+([A-Za-z_$][\w$]*)",
        file_content,
    ):
        named.add(match)

    for block in re.findall(r"\bexport\s*\{([^}]+)\}", file_content):
        for piece in block.split(","):
            token = piece.strip()
            if not token:
                continue
            if " as " in token:
                token = token.split(" as ", 1)[1].strip()
            token = token.strip()
            if re.match(r"^[A-Za-z_$][\w$]*$", token):
                named.add(token)

    return has_default, named


def _normalize_package_name(module_name: str) -> str:
    module_name = module_name.strip()
    if not module_name:
        return ""
    if module_name.startswith("@"):
        parts = module_name.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return module_name
    return module_name.split("/", 1)[0]


def _module_requires_declared_dependency(module_name: str) -> bool:
    if not module_name:
        return False
    if module_name.startswith(("@/", "./", "../", "/", "node:", "http:", "https:", "#")):
        return False
    return True


def _extract_external_modules(file_content: str) -> set[str]:
    modules: set[str] = set()
    patterns = [
        r"\bfrom\s+['\"]([^'\"]+)['\"]",
        r"\bimport\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
        r"\brequire\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, file_content):
            module_name = str(match).strip()
            if _module_requires_declared_dependency(module_name):
                modules.add(module_name)
    return modules


def _extract_css_external_modules(file_content: str) -> set[str]:
    modules: set[str] = set()
    for pattern in (
        r"@plugin\s+['\"]([^'\"]+)['\"]",
        r"@import\s+['\"]([^'\"]+)['\"]",
    ):
        for match in re.findall(pattern, file_content):
            module_name = str(match).strip()
            if not module_name:
                continue
            if module_name.startswith((".", "/", "http:", "https:")):
                continue
            modules.add(module_name)
    return modules


def _declared_packages_from_generated_files(generated_files: dict[str, GeneratedFile]) -> set[str]:
    package_file = generated_files.get("package.json")
    if not isinstance(package_file, dict):
        return set()

    package_text = str(package_file.get("file_contents", ""))
    if not package_text.strip():
        return set()

    try:
        package_json = json.loads(package_text)
    except Exception:
        return set()
    if not isinstance(package_json, dict):
        return set()

    declared: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        dep_map = package_json.get(key)
        if isinstance(dep_map, dict):
            declared.update(str(dep).strip() for dep in dep_map.keys() if str(dep).strip())

    return declared


def _build_declared_dependencies_text(generated_files: dict[str, GeneratedFile], max_items: int = 200) -> str:
    declared = sorted(_declared_packages_from_generated_files(generated_files))
    if not declared:
        return "(none)"
    if len(declared) > max_items:
        shown = ", ".join(declared[:max_items])
        return f"{shown}, ... ({len(declared) - max_items} more)"
    return ", ".join(declared)


def _detect_undeclared_dependency_issues(
    source_file: str,
    file_content: str,
    declared_packages: set[str],
) -> list[str]:
    issues: list[str] = []
    external_modules = _extract_external_modules(file_content)

    for module_name in sorted(external_modules):
        package_name = _normalize_package_name(module_name)
        if not package_name:
            continue
        if package_name in declared_packages:
            continue
        if package_name in NODE_BUILTIN_MODULES:
            continue
        if package_name in ALWAYS_ALLOWED_EXTERNAL_PACKAGES:
            continue
        issues.append(
            f"{source_file}: imports '{module_name}' but '{package_name}' is not declared in package.json",
        )

    return issues


def _detect_undeclared_css_dependency_issues(
    source_file: str,
    file_content: str,
    declared_packages: set[str],
) -> list[str]:
    issues: list[str] = []
    css_modules = _extract_css_external_modules(file_content)
    for module_name in sorted(css_modules):
        package_name = _normalize_package_name(module_name)
        if not package_name:
            continue
        if package_name in declared_packages:
            continue
        issues.append(
            f"{source_file}: references CSS package '{module_name}' but '{package_name}' is not declared in package.json",
        )
    return issues


def _resolve_import_path(
    source_file: str,
    module_path: str,
    existing_paths: set[str],
) -> str | None:
    if module_path.startswith("@/"):
        base = "src/" + module_path[2:]
    elif module_path.startswith("./") or module_path.startswith("../"):
        source_dir = posixpath.dirname(source_file)
        base = posixpath.normpath(posixpath.join(source_dir, module_path))
    else:
        return None

    candidates = [base]
    for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        candidates.append(base + ext)
    for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        candidates.append(posixpath.join(base, "index" + ext))

    for candidate in candidates:
        normalized = candidate.lstrip("./")
        if normalized in existing_paths:
            return normalized
    return None


def _detect_import_export_issues(
    source_file: str,
    file_content: str,
    generated_files: dict[str, GeneratedFile],
) -> list[str]:
    export_map: dict[str, tuple[bool, set[str]]] = {}
    for path, f in generated_files.items():
        text = str(f.get("file_contents", ""))
        export_map[path] = _extract_export_info(text)

    issues: list[str] = []
    import_lines = re.findall(
        r"^\s*import\s+(.+?)\s+from\s+['\"]([^'\"]+)['\"]\s*;?\s*$",
        file_content,
        re.MULTILINE,
    )
    known_paths = set(export_map.keys())
    for imports_part_raw, module in import_lines:
        imports_part = imports_part_raw.strip()
        default_import: str | None = None
        named_imports: list[str] = []

        if imports_part.startswith("* as "):
            continue
        if imports_part.startswith("{"):
            named_block = imports_part
        elif "{" in imports_part:
            left, right = imports_part.split("{", 1)
            default_candidate = left.rstrip(", ").strip()
            if default_candidate and re.match(r"^[A-Za-z_$][\w$]*$", default_candidate):
                default_import = default_candidate
            named_block = "{" + right
        else:
            if re.match(r"^[A-Za-z_$][\w$]*$", imports_part):
                default_import = imports_part
            named_block = ""

        if named_block.startswith("{") and "}" in named_block:
            inside = named_block[1:named_block.index("}")]
            for piece in inside.split(","):
                token = piece.strip()
                if not token:
                    continue
                if token.startswith("type "):
                    token = token[5:].strip()
                if " as " in token:
                    token = token.split(" as ", 1)[0].strip()
                if re.match(r"^[A-Za-z_$][\w$]*$", token):
                    named_imports.append(token)

        resolved = _resolve_import_path(source_file, module, known_paths)
        if not resolved:
            continue
        has_default, named_exports = export_map.get(resolved, (False, set()))

        if default_import and not has_default:
            issues.append(
                f"{source_file}: default import '{default_import}' from '{module}' but target has no default export",
            )

        for name in named_imports:
            if name not in named_exports:
                issues.append(
                    f"{source_file}: named import '{name}' from '{module}' not found in exports",
                )

    return issues


def _build_known_exports_text(generated_files: dict[str, GeneratedFile], max_files: int = 160) -> str:
    lines: list[str] = []
    for idx, path in enumerate(sorted(generated_files.keys())):
        if idx >= max_files:
            lines.append("... (truncated)")
            break
        file_data = generated_files[path]
        content = str(file_data.get("file_contents", ""))
        has_default, named = _extract_export_info(content)
        named_text = ", ".join(sorted(named)[:16]) if named else "(none)"
        lines.append(
            f"- {path}: default_export={'yes' if has_default else 'no'}, named_exports={named_text}",
        )
    return "\n".join(lines) if lines else "(none)"


def _safe_phase_index(file_data: GeneratedFile) -> int:
    try:
        return int(file_data.get("phase_index", -1))
    except Exception:
        return -1


def _extract_export_summary(file_content: str) -> str:
    """Extract export signatures from file content.

    Returns a summary like "Exports: default Button, ButtonProps, ButtonVariant"
    """
    import re

    exports = []

    # Check for default export
    if re.search(r'\bexport\s+default\b', file_content):
        # Try to find the name of the default export
        match = re.search(r'export\s+default\s+(?:function|class|const)?\s*(\w+)', file_content)
        if match:
            exports.append(f"default {match.group(1)}")
        else:
            exports.append("default")

    # Find named exports
    for match in re.finditer(
        r'\bexport\s+(?:const|function|class|type|interface|enum)\s+([A-Za-z_$][\w$]*)',
        file_content,
    ):
        exports.append(match.group(1))

    if exports:
        return f"Exports: {', '.join(exports[:8])}"  # Limit to 8 exports
    return "Exports: (none)"


def _build_existing_files_summary(
    generated_files: dict[str, GeneratedFile],
    current_phase_files: list[str] | None = None,
) -> str:
    if not generated_files:
        return "(No files generated yet)"

    paths = sorted(
        generated_files.keys(),
        key=lambda p: (-_safe_phase_index(generated_files[p]), p),
    )[:MAX_CONTEXT_FILES]

    chunks: list[str] = []
    current_set = set(current_phase_files or [])

    for path in paths:
        content = str(generated_files[path].get("file_contents", ""))

        if path in current_set:
            # File being modified - provide full content
            chunks.append(f"\n--- MODIFYING: {path} ---\n{content[:FILE_SUMMARY_SNIPPET_CHARS]}\n")
        else:
            # Reference file - provide export summary only
            export_summary = _extract_export_summary(content)
            chunks.append(f"\n--- REFERENCE: {path} ---\n{export_summary}\n")

    omitted = len(generated_files) - len(paths)
    if omitted > 0:
        chunks.append(f"\n... ({omitted} more files omitted)\n")
    return "".join(chunks)


def _build_blueprint_document_text(blueprint_document: dict) -> str:
    try:
        return json.dumps(blueprint_document, ensure_ascii=False, indent=2)
    except Exception:
        return "{}"


def _normalize_phase_files(phase_files: list[str], template_name: str) -> list[str]:
    if template_name != "nextjs":
        return phase_files
    normalized: list[str] = []
    for path in phase_files:
        normalized.append("next.config.mjs" if path == "next.config.ts" else path)
    # Preserve order while deduplicating.
    return list(dict.fromkeys(normalized))


def _validate_phase_files(
    required_files: list[str],
    candidate_files: dict[str, GeneratedFile],
    generated_files: dict[str, GeneratedFile],
) -> list[str]:
    errors: list[str] = []

    if not candidate_files:
        return ["No valid file blocks found in the model response."]

    missing = [path for path in required_files if path not in candidate_files]
    if missing:
        errors.append(f"Missing required files: {', '.join(missing)}")

    merged = dict(generated_files)
    for path, file_data in candidate_files.items():
        merged[path] = {
            "file_path": path,
            "file_contents": str(file_data.get("file_contents", "")),
            "language": file_data.get("language", detect_language(path)),
            "phase_index": file_data.get("phase_index", 0),
        }

    declared_packages = _declared_packages_from_generated_files(merged)

    for path, file_data in candidate_files.items():
        contents = str(file_data.get("file_contents", ""))
        issues = _detect_import_export_issues(path, contents, merged)
        errors.extend(issues)
        errors.extend(_detect_undeclared_dependency_issues(path, contents, declared_packages))
        if path.endswith(".css"):
            errors.extend(_detect_undeclared_css_dependency_issues(path, contents, declared_packages))

    return errors


async def phase_implementation_node(state: CodeGenState, config) -> dict:
    """Implement the current phase using one LLM call for all phase files."""
    from agent.graph import get_llm_generation, RetryableLLMWrapper

    sid = state.get("session_id", "")
    phases = state.get("phases", [])
    current_idx = state.get("current_phase_index", 0)
    generated_files = dict(state.get("generated_files", {}))

    if current_idx >= len(phases):
        return {"current_dev_state": "finalizing", "should_continue": False}

    phase = phases[current_idx]
    phase_index = int(phase.get("index", current_idx))
    await ws_send(sid, {"type": "phase_implementing", "phase_index": phase_index})

    template_name = state.get("template_name", "react-vite")
    template_details = state.get("template_details", {})
    dont_touch = template_details.get("dont_touch_files", []) or []
    usage_prompt = template_details.get("usage_prompt", "")
    usage_section = f"Template usage guide:\n{usage_prompt}" if usage_prompt else ""
    declared_dependencies_text = _build_declared_dependencies_text(generated_files)
    dont_touch_str = ", ".join(dont_touch) if dont_touch else "(none)"
    blueprint_document_text = _build_blueprint_document_text(state.get("blueprint", {}) or {})

    phase_files_raw = [f for f in phase.get("files", []) if f not in dont_touch]
    required_phase_files = _normalize_phase_files(phase_files_raw, template_name)

    # Auto-protect existing UI components from regeneration
    # These are base UI primitives that should be reused, not regenerated
    protected_existing = [
        f for f in required_phase_files
        if f in generated_files and _is_protected_component(f)
    ]
    if protected_existing:
        logger.info(
            f"Auto-protecting {len(protected_existing)} existing UI components from regeneration: "
            f"{protected_existing}"
        )
        required_phase_files = [f for f in required_phase_files if f not in protected_existing]

    if not required_phase_files:
        updated_phases = list(phases)
        updated_phases[current_idx] = {**phase, "status": "completed"}
        await ws_send(sid, {"type": "phase_implemented", "phase_index": phase_index})
        return {
            "generated_files": generated_files,
            "phases": updated_phases,
            "current_phase_index": current_idx + 1,
            "current_dev_state": "phase_implementing",
        }

    for target_file in required_phase_files:
        await ws_send(sid, {"type": "file_generating", "filePath": target_file})

    llm = RetryableLLMWrapper(get_llm_generation())
    parsed_phase_files: dict[str, GeneratedFile] = {}
    validation_errors: list[str] = []

    for attempt in range(1, MAX_PHASE_GENERATION_ATTEMPTS + 1):
        existing_summary = _build_existing_files_summary(
            generated_files,
            current_phase_files=required_phase_files,
        )
        known_exports = _build_known_exports_text(generated_files)

        prompt = PHASE_IMPLEMENTATION_SYSTEM_PROMPT.format(
            phase_index=phase_index + 1,
            project_name=state.get("project_name", "my-app"),
            template_name=template_name,
            phase_name=phase.get("name", f"Phase {phase_index + 1}"),
            phase_description=phase.get("description", ""),
            phase_files=", ".join(required_phase_files),
            existing_files_summary=existing_summary,
            known_exports=known_exports,
            declared_dependencies=declared_dependencies_text,
            usage_prompt_section=usage_section,
            dont_touch_files=dont_touch_str,
            blueprint_document=blueprint_document_text,
        )

        # Inject relevant few-shot examples to improve code quality
        prompt = inject_examples_into_prompt(
            base_prompt=prompt,
            template_name=template_name,
            phase_description=phase.get("description", ""),
            phase_files=", ".join(required_phase_files),
        )

        human_prompt = "Generate all files for this phase now."
        if validation_errors:
            feedback = "\n- ".join(validation_errors[:MAX_VALIDATION_ERRORS_FEEDBACK])
            human_prompt += "\n\nFix these validation errors:\n- " + feedback

        response = await llm.ainvoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=human_prompt),
            ],
        )
        raw_content = response.content if hasattr(response, "content") else response
        content = llm_content_to_text(raw_content)

        parsed_files = parse_files_from_response(content)
        parsed_files, renamed_config = enforce_nextjs_config_filename(parsed_files, template_name)
        if renamed_config:
            await ws_send(
                sid,
                {
                    "type": "sandbox_log",
                    "stream": "stderr",
                    "text": "Enforced next.config.mjs (renamed from next.config.ts).",
                },
            )

        selected: dict[str, GeneratedFile] = {}
        for required_path in required_phase_files:
            file_data = parsed_files.get(required_path)
            if file_data:
                selected[required_path] = file_data
        if "package.json" in parsed_files and "package.json" not in dont_touch:
            selected["package.json"] = parsed_files["package.json"]

        validation_errors = _validate_phase_files(required_phase_files, selected, generated_files)
        if not validation_errors:
            parsed_phase_files = selected
            break

        logger.warning(
            "Phase %d generation attempt %d failed validation: %s",
            phase_index,
            attempt,
            "; ".join(validation_errors[:4]),
        )

    if not parsed_phase_files:
        logger.warning("Phase %d generation failed, applying placeholders for required files", phase_index)
        for required_path in required_phase_files:
            parsed_phase_files[required_path] = GeneratedFile(
                file_path=required_path,
                file_contents=f"// TODO: Generated content for {required_path}",
                language=detect_language(required_path),
            )

    for path, file_data in parsed_phase_files.items():
        file_data["phase_index"] = phase_index
        generated_files[path] = file_data

        contents = str(file_data.get("file_contents", ""))
        chunk_size = 200
        for i in range(0, len(contents), chunk_size):
            await ws_send(
                sid,
                {
                    "type": "file_chunk_generated",
                    "filePath": path,
                    "chunk": contents[i : i + chunk_size],
                },
            )
        await ws_send(
            sid,
            {
                "type": "file_generated",
                "filePath": path,
                "fileContents": contents,
                "language": file_data.get("language", "plaintext"),
                "phaseIndex": phase_index,
            },
        )

    updated_phases = list(phases)
    updated_phases[current_idx] = {**phase, "status": "completed"}
    await ws_send(sid, {"type": "phase_implemented", "phase_index": phase_index})

    return {
        "generated_files": generated_files,
        "phases": updated_phases,
        "current_phase_index": current_idx + 1,
        # Keep this state so graph continues generating remaining phases.
        "current_dev_state": "phase_implementing",
    }
