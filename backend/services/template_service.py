import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


@dataclass
class TemplateDetails:
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    all_files: dict[str, str] = field(default_factory=dict)  # path -> content
    important_files: list[str] = field(default_factory=list)
    dont_touch_files: list[str] = field(default_factory=list)
    selection_prompt: str = ""
    usage_prompt: str = ""


def list_templates() -> list[dict]:
    """List all available templates with their metadata."""
    templates = []
    if not TEMPLATES_DIR.exists():
        return templates

    for entry in sorted(TEMPLATES_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith(".") or entry.name == "__pycache__":
            continue
        meta_path = entry / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                templates.append({
                    "name": entry.name,
                    "description": meta.get("description", ""),
                    "tags": meta.get("tags", []),
                })
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read meta for template %s: %s", entry.name, e)
        else:
            templates.append({"name": entry.name, "description": "", "tags": []})

    return templates


def get_template(name: str) -> TemplateDetails | None:
    """Load a template's full details including all files."""
    template_dir = TEMPLATES_DIR / name
    if not template_dir.exists() or not template_dir.is_dir():
        return None

    # Load metadata
    meta: dict = {}
    meta_path = template_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Load file lists
    important_files: list[str] = []
    important_path = template_dir / ".important_files.json"
    if important_path.exists():
        try:
            important_files = json.loads(important_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    dont_touch_files: list[str] = []
    donttouch_path = template_dir / ".donttouch_files.json"
    if donttouch_path.exists():
        try:
            dont_touch_files = json.loads(donttouch_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Load prompts
    selection_prompt = ""
    selection_path = template_dir / "prompts" / "selection.md"
    if selection_path.exists():
        selection_prompt = selection_path.read_text(encoding="utf-8")

    usage_prompt = ""
    usage_path = template_dir / "prompts" / "usage.md"
    if usage_path.exists():
        usage_prompt = usage_path.read_text(encoding="utf-8")

    # Load all template source files
    all_files: dict[str, str] = {}
    skip_names = {"meta.json", ".important_files.json", ".donttouch_files.json", "__pycache__"}
    skip_dirs = {"prompts", "__pycache__", "node_modules", ".git"}

    for root, dirs, files in os.walk(template_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if fname in skip_names:
                continue
            full_path = Path(root) / fname
            rel_path = str(full_path.relative_to(template_dir)).replace("\\", "/")
            try:
                content = full_path.read_text(encoding="utf-8")
                all_files[rel_path] = content
            except (UnicodeDecodeError, OSError):
                logger.debug("Skipping binary/unreadable file: %s", rel_path)

    return TemplateDetails(
        name=name,
        description=meta.get("description", ""),
        tags=meta.get("tags", []),
        all_files=all_files,
        important_files=important_files,
        dont_touch_files=dont_touch_files,
        selection_prompt=selection_prompt,
        usage_prompt=usage_prompt,
    )
