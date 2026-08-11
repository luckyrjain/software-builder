"""Tests for the mock-tool execution harness's control flow — no network, no real model."""

from __future__ import annotations

import pytest

from scripts.evals.live_harness import (
    AnthropicModelClient,
    LiveHarnessError,
    load_mock_tools,
    run_live_case,
)
from scripts.tests.live_test_helpers import ScriptedModelClient, ScriptedTurn

TOOL_DEFS = [
    {
        "name": "list_files",
        "description": "list files",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def test_tool_call_routed_to_mock_response_and_recorded() -> None:
    client = ScriptedModelClient(
        [
            ScriptedTurn(tool_calls=[("list_files", {"dir": "."})]),
            ScriptedTurn(tool_calls=[("record_outcome", {"status": "completed", "output": {"count": 3}})]),
        ],
    )
    mock_tools = load_mock_tools({"list_files": {"files": ["a.py", "b.py"]}})

    result = run_live_case(
        system_prompt="be a good skill",
        scenario_prompt="do the thing",
        tool_defs=TOOL_DEFS,
        mock_tools=mock_tools,
        client=client,
    )

    assert result.events == [
        {"type": "tool", "name": "list_files", "args": {"dir": "."}},
        {"type": "outcome", "status": "completed"},
    ]
    assert result.recorded_output == {"count": 3, "status": "completed"}
    assert result.turns_used == 2

    # the mocked tool result actually reached the model as the next turn's tool_result message
    second_call_messages = client.sent[1]["messages"]
    tool_result_message = second_call_messages[-1]
    assert tool_result_message["role"] == "user"
    assert tool_result_message["content"][0]["tool_use_id"] == "call_1_0"
    assert "a.py" in tool_result_message["content"][0]["content"]


def test_gate_decision_recorded_as_event() -> None:
    client = ScriptedModelClient(
        [
            ScriptedTurn(
                tool_calls=[
                    ("record_gate_decision", {"name": "posting_gate", "decision": "blocked", "reason": "no_evidence"}),
                ],
            ),
            ScriptedTurn(tool_calls=[("record_outcome", {"status": "human_action_required", "output": {}})]),
        ],
    )
    mock_tools = load_mock_tools({})

    result = run_live_case(
        system_prompt="be a good skill",
        scenario_prompt="do the thing",
        tool_defs=[],
        mock_tools=mock_tools,
        client=client,
    )

    assert result.events[0] == {
        "type": "gate",
        "name": "posting_gate",
        "decision": "blocked",
        "reason": "no_evidence",
    }
    assert result.events[1] == {"type": "outcome", "status": "human_action_required"}


def test_unknown_tool_gets_error_result_but_run_continues() -> None:
    client = ScriptedModelClient(
        [
            ScriptedTurn(tool_calls=[("unconfigured_tool", {})]),
            ScriptedTurn(tool_calls=[("record_outcome", {"status": "recovered", "output": {}})]),
        ],
    )
    mock_tools = load_mock_tools({})  # no response configured for unconfigured_tool

    result = run_live_case(
        system_prompt="s",
        scenario_prompt="p",
        tool_defs=[{"name": "unconfigured_tool", "description": "d", "input_schema": {"type": "object"}}],
        mock_tools=mock_tools,
        client=client,
    )

    # the call itself is still recorded as an event even though it had no mock response
    assert result.events[0] == {"type": "tool", "name": "unconfigured_tool", "args": {}}
    assert result.recorded_output["status"] == "recovered"

    first_call_response_message = client.sent[1]["messages"][-1]
    assert first_call_response_message["content"][0]["is_error"] is True


def test_mock_tool_fixture_serves_queued_responses_in_order_then_raises() -> None:
    mock_tools = load_mock_tools({"get_page": ["page1", "page2"]})
    assert mock_tools.respond("get_page") == "page1"
    assert mock_tools.respond("get_page") == "page2"
    with pytest.raises(LiveHarnessError, match="called more times"):
        mock_tools.respond("get_page")


def test_mock_tool_fixture_wraps_scalar_into_single_item_queue() -> None:
    mock_tools = load_mock_tools({"get_page": "only-page"})
    assert mock_tools.respond("get_page") == "only-page"
    with pytest.raises(LiveHarnessError, match="called more times"):
        mock_tools.respond("get_page")


def test_exhausted_turns_raises() -> None:
    client = ScriptedModelClient(
        [
            ScriptedTurn(tool_calls=[("list_files", {})]),
            ScriptedTurn(tool_calls=[("list_files", {})]),
        ],
    )
    mock_tools = load_mock_tools({"list_files": ["a", "b"]})

    with pytest.raises(LiveHarnessError, match="exhausted 2 turns"):
        run_live_case(
            system_prompt="s",
            scenario_prompt="p",
            tool_defs=TOOL_DEFS,
            mock_tools=mock_tools,
            client=client,
            max_turns=2,
        )


def test_model_stopping_without_any_tool_call_raises() -> None:
    client = ScriptedModelClient([ScriptedTurn(text="I'm done!", stop_reason="end_turn", tool_calls=[])])
    mock_tools = load_mock_tools({})

    with pytest.raises(LiveHarnessError, match="without calling record_outcome"):
        run_live_case(
            system_prompt="s",
            scenario_prompt="p",
            tool_defs=[],
            mock_tools=mock_tools,
            client=client,
        )


def test_reserved_tool_name_collision_rejected() -> None:
    client = ScriptedModelClient([ScriptedTurn(tool_calls=[("record_outcome", {"status": "x"})])])
    mock_tools = load_mock_tools({})

    with pytest.raises(LiveHarnessError, match="reserved harness tool name"):
        run_live_case(
            system_prompt="s",
            scenario_prompt="p",
            tool_defs=[{"name": "record_outcome", "description": "d", "input_schema": {}}],
            mock_tools=mock_tools,
            client=client,
        )


def test_anthropic_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LiveHarnessError, match="ANTHROPIC_API_KEY is not set"):
        AnthropicModelClient(model="claude-sonnet-5")


def test_anthropic_client_accepts_explicit_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = AnthropicModelClient(model="claude-sonnet-5", api_key="explicit-key")
    assert client._api_key == "explicit-key"  # noqa: SLF001 - verifying the fallback precedence itself


def test_anthropic_client_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    client = AnthropicModelClient(model="claude-sonnet-5")
    assert client._api_key == "env-key"  # noqa: SLF001
