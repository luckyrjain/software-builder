"""Mock-tool execution harness: run a skill against a real model, tools answered from a fixture.

Every existing eval tier (ADR 0003) is static: Tier 1 checks file shape, Tier 2 replays a
hand-authored event list, Tier 3 replays a hand-captured output dict — none of them ever actually
run a skill. This module does: it drives a real agentic tool-use loop against a `ModelClient` (the
skill's SKILL.md as system prompt, a scenario prompt as the opening user turn), answering every tool
call from a `MockToolFixture` instead of a live MCP server, and captures the resulting `tool`/`gate`/
`outcome` events in the same schema Tier 2's `transcript.py` already consumes.

Deliberately never called by `make lint`/CI — see docs/evals/LIVE-HARNESS.md and ADR 0004. Tests
exercise the control flow below via a scripted `ModelClient` stub, never a real network call, so this
module's own correctness is still covered by the deterministic suite `make lint` runs.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_MAX_TOKENS = 4096
DEFAULT_MAX_TURNS = 12

GATE_TOOL_NAME = "record_gate_decision"
OUTCOME_TOOL_NAME = "record_outcome"

HARNESS_TOOLS: list[dict[str, Any]] = [
    {
        "name": GATE_TOOL_NAME,
        "description": (
            "Record a policy gate decision reached while following this skill's guardrails. Call this "
            "every time the skill's instructions say to make an explicit gate/authorization decision."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "the gate's name, e.g. merge_authorization"},
                "decision": {"type": "string", "description": "e.g. allowed, blocked, escalated"},
                "reason": {"type": "string"},
            },
            "required": ["name", "decision"],
        },
    },
    {
        "name": OUTCOME_TOOL_NAME,
        "description": (
            "Record this run's final outcome. Call this exactly once, as the last tool call, with the "
            "skill's final structured result — never just describe the result in prose instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "output": {"type": "object", "description": "structured fields a Tier-3 golden case would assert on"},
            },
            "required": ["status"],
        },
    },
]


class LiveHarnessError(RuntimeError):
    """Raised for both harness misconfiguration and unrecoverable model behavior during a live run."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ModelResponse:
    stop_reason: str
    text: str
    tool_calls: list[ToolCall]
    raw_content: list[dict[str, Any]]


class ModelClient(Protocol):
    def send(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse: ...


@dataclass
class MockToolFixture:
    """A tool name's queue of canned responses, consumed in call order."""

    responses: dict[str, list[Any]]
    _cursor: dict[str, int] = field(default_factory=dict)

    def respond(self, name: str) -> Any:
        queue = self.responses.get(name)
        if queue is None:
            raise LiveHarnessError(f"no mock response configured for tool {name!r}")
        index = self._cursor.get(name, 0)
        if index >= len(queue):
            raise LiveHarnessError(
                f"tool {name!r} called more times ({index + 1}) than mock responses provided ({len(queue)})",
            )
        self._cursor[name] = index + 1
        return queue[index]


def load_mock_tools(raw: dict[str, Any]) -> MockToolFixture:
    responses: dict[str, list[Any]] = {}
    for name, value in raw.items():
        responses[name] = list(value) if isinstance(value, list) else [value]
    return MockToolFixture(responses=responses)


@dataclass(frozen=True)
class LiveRunResult:
    events: list[dict[str, Any]]
    recorded_output: dict[str, Any]
    turns_used: int


def _tool_result(tool_use_id: str, content: Any, *, is_error: bool = False) -> dict[str, Any]:
    payload = content if isinstance(content, str) else json.dumps(content)
    result: dict[str, Any] = {"type": "tool_result", "tool_use_id": tool_use_id, "content": payload}
    if is_error:
        result["is_error"] = True
    return result


def run_live_case(
    *,
    system_prompt: str,
    scenario_prompt: str,
    tool_defs: list[dict[str, Any]],
    mock_tools: MockToolFixture,
    client: ModelClient,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> LiveRunResult:
    reserved = {GATE_TOOL_NAME, OUTCOME_TOOL_NAME}
    collisions = sorted(reserved & {str(tool.get("name")) for tool in tool_defs})
    if collisions:
        raise LiveHarnessError(f"tool_defs may not use reserved harness tool name(s): {collisions}")

    all_tools = [*tool_defs, *HARNESS_TOOLS]
    messages: list[dict[str, Any]] = [{"role": "user", "content": scenario_prompt}]
    events: list[dict[str, Any]] = []

    for turn in range(1, max_turns + 1):
        response = client.send(system=system_prompt, messages=messages, tools=all_tools)
        messages.append({"role": "assistant", "content": response.raw_content})

        if not response.tool_calls:
            raise LiveHarnessError(
                f"model stopped (stop_reason={response.stop_reason!r}) at turn {turn} without calling "
                f"{OUTCOME_TOOL_NAME}",
            )

        tool_results: list[dict[str, Any]] = []
        recorded_output: dict[str, Any] = {}
        outcome_this_turn = False

        for call in response.tool_calls:
            if call.name == GATE_TOOL_NAME:
                events.append(
                    {
                        "type": "gate",
                        "name": str(call.args.get("name", "")),
                        "decision": str(call.args.get("decision", "")),
                        "reason": str(call.args.get("reason", "")),
                    },
                )
                tool_results.append(_tool_result(call.id, "recorded"))
                continue

            if call.name == OUTCOME_TOOL_NAME:
                status = str(call.args.get("status", ""))
                events.append({"type": "outcome", "status": status})
                recorded_output = dict(call.args.get("output") or {})
                recorded_output.setdefault("status", status)
                outcome_this_turn = True
                tool_results.append(_tool_result(call.id, "recorded"))
                continue

            events.append({"type": "tool", "name": call.name, "args": call.args})
            try:
                mock_result = mock_tools.respond(call.name)
            except LiveHarnessError as exc:
                tool_results.append(_tool_result(call.id, str(exc), is_error=True))
                continue
            tool_results.append(_tool_result(call.id, mock_result))

        if outcome_this_turn:
            return LiveRunResult(events=events, recorded_output=recorded_output, turns_used=turn)

        messages.append({"role": "user", "content": tool_results})

    raise LiveHarnessError(f"exhausted {max_turns} turns without the skill calling {OUTCOME_TOOL_NAME}")


class AnthropicModelClient:
    """Talks to the real Messages API over stdlib `urllib` — no SDK dependency for one JSON call."""

    def __init__(self, *, model: str, api_key: str | None = None, timeout: float = 120) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LiveHarnessError(
                "ANTHROPIC_API_KEY is not set — the live harness needs a real API key and is never "
                "exercised by `make lint`/CI, see docs/evals/LIVE-HARNESS.md",
            )
        self._model = model
        self._api_key = key
        self._timeout = timeout

    def send(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        body = json.dumps(
            {
                "model": self._model,
                "max_tokens": ANTHROPIC_MAX_TOKENS,
                "system": system,
                "messages": messages,
                "tools": tools,
            },
        ).encode("utf-8")
        request = urllib.request.Request(
            ANTHROPIC_API_URL,
            data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 - fixed https host
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise LiveHarnessError(f"Anthropic API error {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            # A stall during urlopen()'s own connect phase surfaces as URLError (wrapping the
            # underlying OSError in .reason); a stall during response.read() — after a successful
            # connection — surfaces as a bare TimeoutError instead, which is not a URLError
            # subclass, so both need to be caught here to keep every network failure mapped to
            # LiveHarnessError rather than an unhandled traceback.
            reason = getattr(exc, "reason", exc)
            raise LiveHarnessError(f"Anthropic API request failed: {reason}") from exc

        content = payload.get("content", [])
        text = "".join(block.get("text", "") for block in content if block.get("type") == "text")
        tool_calls = [
            ToolCall(id=block["id"], name=block["name"], args=block.get("input", {}))
            for block in content
            if block.get("type") == "tool_use"
        ]
        return ModelResponse(
            stop_reason=str(payload.get("stop_reason", "")),
            text=text,
            tool_calls=tool_calls,
            raw_content=content,
        )
