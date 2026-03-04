import pytest

from agent.nodes import phase_implementation as phase_impl_module


@pytest.mark.asyncio
async def test_phase_implementation_includes_retry_feedback_in_human_prompt(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_ws_send(session_id, msg):
        del session_id, msg
        return None

    class FakeResponse:
        content = (
            "===FILE: src/components/layout/navbar.tsx===\n"
            "export function Navbar() { return <nav /> }\n"
            "===END_FILE==="
        )

    class FakeWrapper:
        def __init__(self, llm):
            del llm

        async def ainvoke(self, messages):
            captured["system_prompt"] = str(messages[0].content)
            captured["human_prompt"] = str(messages[1].content)
            return FakeResponse()

    monkeypatch.setattr(phase_impl_module, "ws_send", fake_ws_send)
    monkeypatch.setattr(phase_impl_module, "inject_examples_into_prompt", lambda **kwargs: kwargs["base_prompt"])
    monkeypatch.setattr("agent.graph.get_llm_generation", lambda: object())
    monkeypatch.setattr("agent.graph.RetryableLLMWrapper", FakeWrapper)

    state = {
        "session_id": "s1",
        "phases": [
            {
                "index": 0,
                "name": "Layout",
                "description": "Add navbar",
                "files": ["src/components/layout/navbar.tsx"],
            },
        ],
        "current_phase_index": 0,
        "generated_files": {
            "package.json": {
                "file_contents": "{\n  \"name\": \"demo\",\n  \"dependencies\": {\n    \"react\": \"^19.0.0\"\n  }\n}",
                "language": "json",
                "phase_index": -1,
            },
        },
        "project_name": "demo",
        "template_name": "react-vite",
        "template_details": {},
        "blueprint": {},
        "validation_errors": ["src/components/layout/navbar.tsx:30: Using motion component without importing framer-motion"],
        "validation_target_files": ["src/components/layout/header.tsx"],
        "review_error_messages": ["[error] src/components/layout/navbar.tsx:44: Exported component missing Props interface/type"],
        "review_issues": [],
    }

    await phase_impl_module.phase_implementation_node(state, config={})
    human_prompt = captured.get("human_prompt", "")
    system_prompt = captured.get("system_prompt", "")
    assert "Fix these code review findings first" in human_prompt
    assert "Fix these validation errors" in human_prompt
    assert "src/components/layout/header.tsx" in system_prompt


@pytest.mark.asyncio
async def test_phase_fix_mode_targets_only_validation_files(monkeypatch):
    events: list[dict] = []

    async def fake_ws_send(session_id, msg):
        del session_id
        events.append(msg)
        return None

    class FakeResponse:
        content = (
            "===FILE: src/components/layout/header.tsx===\n"
            "export function Header() { return <header /> }\n"
            "===END_FILE==="
        )

    class FakeWrapper:
        def __init__(self, llm):
            del llm

        async def ainvoke(self, messages):
            del messages
            return FakeResponse()

    monkeypatch.setattr(phase_impl_module, "ws_send", fake_ws_send)
    monkeypatch.setattr(phase_impl_module, "inject_examples_into_prompt", lambda **kwargs: kwargs["base_prompt"])
    monkeypatch.setattr("agent.graph.get_llm_generation", lambda: object())
    monkeypatch.setattr("agent.graph.RetryableLLMWrapper", FakeWrapper)

    state = {
        "session_id": "s1",
        "phases": [
            {
                "index": 0,
                "name": "Layout",
                "description": "Layout shell",
                "files": [
                    "src/app/layout.tsx",
                    "src/components/layout/header.tsx",
                    "src/components/layout/footer.tsx",
                ],
            },
        ],
        "current_phase_index": 0,
        "generated_files": {
            "package.json": {
                "file_contents": "{\n  \"name\": \"demo\",\n  \"dependencies\": {\n    \"react\": \"^19.0.0\"\n  }\n}",
                "language": "json",
                "phase_index": -1,
            },
        },
        "project_name": "demo",
        "template_name": "react-vite",
        "template_details": {},
        "blueprint": {},
        "should_retry_phase": True,
        "current_dev_state": "phase_fixing",
        "validation_errors": ["src/components/layout/header.tsx:30: Using motion component without importing framer-motion"],
        "validation_target_files": ["src/components/layout/header.tsx"],
        "review_error_messages": [],
        "review_issues": [],
    }

    await phase_impl_module.phase_implementation_node(state, config={})
    phase_events = [e for e in events if e.get("type") in {"phase_implementing", "phase_fixing"}]
    file_generating = [e.get("filePath") for e in events if e.get("type") == "file_generating"]

    assert phase_events and phase_events[0]["type"] == "phase_fixing"
    assert file_generating == ["src/components/layout/header.tsx"]


@pytest.mark.asyncio
async def test_phase_fix_auto_injects_motion_import(monkeypatch):
    async def fake_ws_send(session_id, msg):
        del session_id, msg
        return None

    class FakeResponse:
        content = (
            "===FILE: src/components/layout/header.tsx===\n"
            "export function Header() {\n"
            "  return <motion.header />\n"
            "}\n"
            "===END_FILE==="
        )

    class FakeWrapper:
        def __init__(self, llm):
            del llm

        async def ainvoke(self, messages):
            del messages
            return FakeResponse()

    monkeypatch.setattr(phase_impl_module, "ws_send", fake_ws_send)
    monkeypatch.setattr(phase_impl_module, "inject_examples_into_prompt", lambda **kwargs: kwargs["base_prompt"])
    monkeypatch.setattr("agent.graph.get_llm_generation", lambda: object())
    monkeypatch.setattr("agent.graph.RetryableLLMWrapper", FakeWrapper)

    state = {
        "session_id": "s1",
        "phases": [
            {
                "index": 0,
                "name": "Layout",
                "description": "Layout shell",
                "files": ["src/components/layout/header.tsx"],
            },
        ],
        "current_phase_index": 0,
        "generated_files": {
            "package.json": {
                "file_contents": "{\n  \"name\": \"demo\",\n  \"dependencies\": {\n    \"react\": \"^19.0.0\"\n  }\n}",
                "language": "json",
                "phase_index": -1,
            },
        },
        "project_name": "demo",
        "template_name": "react-vite",
        "template_details": {},
        "blueprint": {},
        "should_retry_phase": True,
        "current_dev_state": "phase_fixing",
        "validation_errors": ["src/components/layout/header.tsx:30: Using motion component without importing framer-motion"],
        "validation_target_files": ["src/components/layout/header.tsx"],
        "review_error_messages": [],
        "review_issues": [],
    }

    result = await phase_impl_module.phase_implementation_node(state, config={})
    content = result["generated_files"]["src/components/layout/header.tsx"]["file_contents"]
    package_json = result["generated_files"]["package.json"]["file_contents"]
    assert "import { motion } from 'framer-motion'" in content
    assert '"framer-motion"' in package_json
