import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.callback_registry import ws_send
from agent.graph import get_llm
from agent.llm_content import llm_content_to_text
from agent.prompts import CMS_SETUP_SYSTEM_PROMPT
from agent.state import CodeGenState, StrapiContentType, StrapiSchema

logger = logging.getLogger(__name__)


def _should_enable_cms(blueprint: dict[str, Any]) -> bool:
    """Determine if CMS should be enabled based on blueprint analysis."""
    # Check if blueprint explicitly requests CMS
    description = str(blueprint.get("description", "")).lower()
    project_name = str(blueprint.get("project_name", "")).lower()

    cms_keywords = [
        "cms", "content management", "blog", "article", "post",
        "news", "publication", "editorial", "magazine",
        "e-commerce", "product", "catalog", "inventory",
        "portfolio", "gallery", "showcase",
        "documentation", "docs", "wiki", "knowledge base",
        "event", "booking", "reservation",
        "user generated", "user content", "submission",
        "headless", "strapi", "admin panel", "dashboard",
    ]

    for keyword in cms_keywords:
        if keyword in description or keyword in project_name:
            return True

    # Check phases for CMS-related files or descriptions
    phases = blueprint.get("phases", [])
    if isinstance(phases, list):
        for phase in phases:
            if not isinstance(phase, dict):
                continue
            phase_desc = str(phase.get("description", "")).lower()
            phase_name = str(phase.get("name", "")).lower()
            for keyword in cms_keywords:
                if keyword in phase_desc or keyword in phase_name:
                    return True

    return False


def _parse_strapi_schema(content: str) -> StrapiSchema | None:
    """Parse Strapi schema from LLM response."""
    content = content.strip()

    # Try to extract JSON from markdown code blocks
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
    if match:
        content = match.group(1)

    try:
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return None

        content_types = parsed.get("contentTypes", [])
        if not isinstance(content_types, list):
            return None

        # Validate and normalize content types
        validated_types: list[StrapiContentType] = []
        for ct in content_types:
            if not isinstance(ct, dict):
                continue

            singular = ct.get("singularName", "")
            plural = ct.get("pluralName", "")
            display = ct.get("displayName", "")

            if not singular or not plural:
                continue

            validated_ct: StrapiContentType = {
                "singularName": str(singular),
                "pluralName": str(plural),
                "displayName": str(display) if display else str(singular).capitalize(),
                "description": str(ct.get("description", "")),
                "attributes": ct.get("attributes", {}),
            }
            validated_types.append(validated_ct)

        if not validated_types:
            return None

        return {
            "contentTypes": validated_types,
            "apiBaseUrl": "http://localhost:1337",
        }
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse Strapi schema: %s", e)
        return None


def _generate_default_schema(blueprint: dict[str, Any]) -> StrapiSchema:
    """Generate a default Strapi schema based on blueprint analysis."""
    project_name = str(blueprint.get("project_name", "my-app"))

    # Default content types for common use cases
    content_types: list[StrapiContentType] = [
        {
            "singularName": "page",
            "pluralName": "pages",
            "displayName": "Page",
            "description": "Static pages",
            "attributes": {
                "title": {"type": "string", "required": True},
                "slug": {"type": "uid", "targetField": "title", "required": True},
                "content": {"type": "richtext"},
                "seo": {"type": "component", "component": "seo.meta"},
            },
        },
        {
            "singularName": "post",
            "pluralName": "posts",
            "displayName": "Post",
            "description": "Blog posts or articles",
            "attributes": {
                "title": {"type": "string", "required": True},
                "slug": {"type": "uid", "targetField": "title", "required": True},
                "excerpt": {"type": "text"},
                "content": {"type": "richtext"},
                "coverImage": {"type": "media", "multiple": False},
                "publishedAt": {"type": "datetime"},
                "seo": {"type": "component", "component": "seo.meta"},
            },
        },
    ]

    return {
        "contentTypes": content_types,
        "apiBaseUrl": "http://localhost:1337",
    }


def _schema_to_json_files(schema: StrapiSchema) -> dict[str, str]:
    """Convert Strapi schema to JSON files for the sandbox."""
    files: dict[str, str] = {}

    for ct in schema.get("contentTypes", []):
        singular = ct.get("singularName", "")
        if not singular:
            continue

        # Create schema.json for each content type
        schema_json = {
            "kind": "collectionType",
            "collectionName": ct.get("pluralName", f"{singular}s"),
            "info": {
                "singularName": singular,
                "pluralName": ct.get("pluralName", f"{singular}s"),
                "displayName": ct.get("displayName", singular.capitalize()),
                "description": ct.get("description", ""),
            },
            "options": {
                "draftAndPublish": True,
            },
            "pluginOptions": {},
            "attributes": ct.get("attributes", {}),
        }

        file_path = f"src/api/{singular}/content-types/{singular}/schema.json"
        files[file_path] = json.dumps(schema_json, indent=2, ensure_ascii=False)

    return files


async def cms_setup_node(state: CodeGenState, config) -> dict[str, Any]:
    """Set up Strapi CMS by generating content-type schemas from the blueprint."""
    sid = state.get("session_id", "")
    blueprint = state.get("blueprint", {})
    user_query = state.get("user_query", "")

    # Check if CMS should be enabled
    if not _should_enable_cms(blueprint):
        logger.info("CMS not enabled for session %s", sid)
        return {
            "cms_enabled": False,
            "cms_schema": None,
            "cms_api_url": None,
            "cms_sandbox_port": None,
            "current_dev_state": "phase_implementing",
            "should_continue": True,
        }

    await ws_send(sid, {"type": "cms_status", "status": "analyzing"})

    try:
        blueprint_json = json.dumps(blueprint, ensure_ascii=False, indent=2)
    except Exception:
        blueprint_json = str(blueprint)

    llm = get_llm()

    system_prompt = CMS_SETUP_SYSTEM_PROMPT.format(
        blueprint_json=blueprint_json,
        user_query=user_query,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Generate Strapi Content-Type schemas for this project."),
    ]

    await ws_send(sid, {"type": "cms_status", "status": "generating_schema"})

    try:
        response = await llm.ainvoke(messages)
        raw_content = response.content if hasattr(response, "content") else response
        content = llm_content_to_text(raw_content)

        schema = _parse_strapi_schema(content)

        if schema is None:
            logger.warning("Failed to parse LLM schema response, using default")
            schema = _generate_default_schema(blueprint)

        # Generate JSON files for Strapi
        schema_files = _schema_to_json_files(schema)

        await ws_send(
            sid,
            {
                "type": "cms_schema_generated",
                "schema": schema,
                "fileCount": len(schema_files),
            },
        )

        return {
            "cms_enabled": True,
            "cms_schema": schema,
            "cms_api_url": "http://localhost:1337",
            "cms_sandbox_port": 1337,
            "current_dev_state": "phase_implementing",
            "should_continue": True,
        }

    except Exception as e:
        logger.error("Error in cms_setup_node: %s", e)
        # Return default schema on error
        schema = _generate_default_schema(blueprint)

        await ws_send(
            sid,
            {
                "type": "cms_schema_generated",
                "schema": schema,
                "fileCount": len(schema.get("contentTypes", [])),
                "warning": "Using default schema due to generation error",
            },
        )

        return {
            "cms_enabled": True,
            "cms_schema": schema,
            "cms_api_url": "http://localhost:1337",
            "cms_sandbox_port": 1337,
            "current_dev_state": "phase_implementing",
            "should_continue": True,
        }
