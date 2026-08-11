"""Scripted ModelClient stub shared by the live-harness tests — never touches the network."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scripts.evals.live_harness import ModelResponse, ToolCall


@dataclass
class ScriptedTurn:
    tool_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    text: str = ""
    stop_reason: str = "tool_use"


class ScriptedModelClient:
    """Structurally satisfies live_harness.ModelClient by returning pre-scripted turns in order."""

    def __init__(self, turns: list[ScriptedTurn]) -> None:
        self._turns = list(turns)
        self._index = 0
        self.sent: list[dict[str, Any]] = []

    def send(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        # Snapshot the list itself — `messages` is the caller's mutable list, and it grows again
        # (assistant reply, tool results) right after this call returns, so storing the same
        # reference would make every past entry in `self.sent` retroactively reflect later state.
        self.sent.append({"system": system, "messages": list(messages), "tools": tools})
        if self._index >= len(self._turns):
            raise AssertionError("ScriptedModelClient ran out of scripted turns")
        turn = self._turns[self._index]
        self._index += 1

        content: list[dict[str, Any]] = []
        if turn.text:
            content.append({"type": "text", "text": turn.text})

        tool_calls: list[ToolCall] = []
        for call_index, (name, args) in enumerate(turn.tool_calls):
            call_id = f"call_{self._index}_{call_index}"
            content.append({"type": "tool_use", "id": call_id, "name": name, "input": args})
            tool_calls.append(ToolCall(id=call_id, name=name, args=args))

        return ModelResponse(stop_reason=turn.stop_reason, text=turn.text, tool_calls=tool_calls, raw_content=content)
