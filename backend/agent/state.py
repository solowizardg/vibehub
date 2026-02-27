from typing import Any

from typing_extensions import TypedDict


class PhaseDefinition(TypedDict, total=False):
    index: int
    name: str
    description: str
    files: list[str]
    status: str


class GeneratedFile(TypedDict, total=False):
    file_path: str
    file_contents: str
    language: str
    phase_index: int


class TemplateDetails(TypedDict, total=False):
    name: str
    description: str
    all_files: dict[str, str]
    important_files: list[str]
    dont_touch_files: list[str]
    usage_prompt: str
    selection_prompt: str


class CodeGenState(TypedDict, total=False):
    session_id: str
    user_query: str
    blueprint: dict[str, Any]
    blueprint_markdown: str
    project_name: str
    template_name: str
    generated_files: dict[str, GeneratedFile]
    phases: list[PhaseDefinition]
    current_phase_index: int
    current_dev_state: str
    conversation_messages: list[dict[str, str]]
    sandbox_id: str | None
    sandbox_bootstrapped: bool
    sandbox_deps_installed: bool
    sandbox_package_json_hash: str | None
    sandbox_fix_attempts: int
    sandbox_logs: str
    preview_url: str | None
    template_details: TemplateDetails
    should_continue: bool
    error: str | None
