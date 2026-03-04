import pytest

from agent.nodes import pre_validation as pre_validation_module


@pytest.mark.asyncio
async def test_pre_validation_retries_phase_from_error_file(monkeypatch):
    async def fake_ws_send(session_id, msg):
        del session_id, msg
        return None

    monkeypatch.setattr(pre_validation_module, "ws_send", fake_ws_send)

    state = {
        "session_id": "s1",
        "template_name": "react-vite",
        "phases": [
            {"index": 0, "name": "P1"},
            {"index": 1, "name": "P2"},
            {"index": 2, "name": "P3"},
        ],
        # current_phase_index points to the next phase after generation
        "current_phase_index": 3,
        "generated_files": {
            "src/components/layout/navbar.tsx": {
                "file_contents": "export function Navbar(){ return <motion.div /> }",
                "phase_index": 2,
            },
        },
        "current_phase_validation_attempts": {},
    }

    result = await pre_validation_module.pre_validation_node(state, config={})
    assert result["should_retry_phase"] is True
    assert result["current_phase_index"] == 2
    assert result["current_dev_state"] == "phase_fixing"


@pytest.mark.asyncio
async def test_pre_validation_does_not_jump_back_to_phase_one_for_old_file_errors(monkeypatch):
    async def fake_ws_send(session_id, msg):
        del session_id, msg
        return None

    monkeypatch.setattr(pre_validation_module, "ws_send", fake_ws_send)

    state = {
        "session_id": "s1",
        "template_name": "react-vite",
        "phases": [
            {"index": 0, "name": "P1"},
            {"index": 1, "name": "P2"},
            {"index": 2, "name": "P3"},
            {"index": 3, "name": "P4"},
        ],
        # Full plan done; validating phase 4
        "current_phase_index": 4,
        "generated_files": {
            # Legacy file from phase 1 still has blocking issue
            "src/components/layout/header.tsx": {
                "file_contents": "export function Header(){ return <motion.div /> }",
                "phase_index": 0,
            },
            "src/app/page.tsx": {
                "file_contents": "export default function Page(){ return <main /> }",
                "phase_index": 3,
            },
        },
        "current_phase_validation_attempts": {},
    }

    result = await pre_validation_module.pre_validation_node(state, config={})
    assert result["should_retry_phase"] is True
    # Retry latest completed phase (phase 4), not phase 1
    assert result["current_phase_index"] == 3
    assert result["current_dev_state"] == "phase_fixing"
    assert "src/components/layout/header.tsx" in result["validation_target_files"]


@pytest.mark.asyncio
async def test_pre_validation_attempts_tracked_by_retry_phase_index(monkeypatch):
    async def fake_ws_send(session_id, msg):
        del session_id, msg
        return None

    monkeypatch.setattr(pre_validation_module, "ws_send", fake_ws_send)

    base_state = {
        "session_id": "s1",
        "template_name": "react-vite",
        "phases": [
            {"index": 0, "name": "P1"},
            {"index": 1, "name": "P2"},
            {"index": 2, "name": "P3"},
            {"index": 3, "name": "P4"},
        ],
        # validating latest completed phase (index 3)
        "current_phase_index": 4,
        "generated_files": {
            "src/components/layout/header.tsx": {
                "file_contents": "export function Header(){ return <motion.header /> }",
                "phase_index": 3,
            },
        },
        "current_phase_validation_attempts": {},
    }

    first = await pre_validation_module.pre_validation_node(dict(base_state), config={})
    second_state = dict(base_state)
    second_state["current_phase_validation_attempts"] = first["current_phase_validation_attempts"]
    second = await pre_validation_module.pre_validation_node(second_state, config={})

    assert first["current_phase_validation_attempts"].get(3) == 1
    assert second["current_phase_validation_attempts"].get(3) == 2
