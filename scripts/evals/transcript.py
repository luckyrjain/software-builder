"""Tier-2 behavioral evals: replay transcript fixtures and assert policy invariants."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from scripts.evals.types import EvalResult

TRANSCRIPTS_DIR_NAME = "transcripts"


@dataclass(frozen=True)
class TranscriptEvent:
    event_type: str
    data: dict[str, Any]


@dataclass(frozen=True)
class TranscriptCase:
    skill: str
    case_id: str
    tier: int
    description: str
    events: list[TranscriptEvent]
    assertions: list[dict[str, Any]]
    path: Path


def _parse_event(raw: dict[str, Any]) -> TranscriptEvent:
    event_type = str(raw.get("type", ""))
    if not event_type:
        raise ValueError("transcript event missing type")
    data = {key: value for key, value in raw.items() if key != "type"}
    return TranscriptEvent(event_type=event_type, data=data)


def load_transcript_fixtures(transcripts_dir: Path) -> list[TranscriptCase]:
    if not transcripts_dir.is_dir():
        return []

    cases: list[TranscriptCase] = []
    for path in sorted(transcripts_dir.rglob("*.yaml")):
        if path.name.startswith("_"):
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: transcript fixture root must be a mapping")

        skill = str(raw.get("skill", ""))
        case_id = str(raw.get("case_id", ""))
        if not skill or not case_id:
            raise ValueError(f"{path}: skill and case_id are required")

        events_raw = raw.get("events", [])
        if not isinstance(events_raw, list) or not events_raw:
            raise ValueError(f"{path}: events must be a non-empty list")

        assertions = raw.get("assertions", [])
        if not isinstance(assertions, list) or not assertions:
            raise ValueError(f"{path}: assertions must be a non-empty list")

        events = [_parse_event(event) for event in events_raw if isinstance(event, dict)]
        if len(events) != len(events_raw):
            raise ValueError(f"{path}: every event must be a mapping")

        cases.append(
            TranscriptCase(
                skill=skill,
                case_id=case_id,
                tier=int(raw.get("tier", 2)),
                description=str(raw.get("description", "")),
                events=events,
                assertions=assertions,
                path=path,
            ),
        )
    return cases


def _events_of_type(events: list[TranscriptEvent], event_type: str) -> list[TranscriptEvent]:
    return [event for event in events if event.event_type == event_type]


def _tool_name(event: TranscriptEvent) -> str:
    return str(event.data.get("name", ""))


def _args_subset(actual: Any, expected: Any) -> bool:
    if not isinstance(expected, dict):
        return actual == expected
    if not isinstance(actual, dict):
        return False
    for key, value in expected.items():
        if key not in actual or not _args_subset(actual[key], value):
            return False
    return True


def _run_transcript_assertion(
    events: list[TranscriptEvent],
    assertion: dict[str, Any],
) -> list[str]:
    atype = str(assertion.get("type", ""))

    if atype == "tool_called":
        name = str(assertion.get("name", ""))
        if not any(_tool_name(event) == name for event in _events_of_type(events, "tool")):
            return [f"expected tool {name!r} to be called"]
        return []

    if atype == "tool_not_called":
        name = str(assertion.get("name", ""))
        if any(_tool_name(event) == name for event in _events_of_type(events, "tool")):
            return [f"forbidden tool {name!r} was called"]
        return []

    if atype == "tool_order":
        tools = assertion.get("tools", [])
        if not isinstance(tools, list) or len(tools) < 2:
            raise ValueError("tool_order requires a list of at least two tool names")
        tool_events = _events_of_type(events, "tool")
        indices: list[int] = []
        for tool_name in tools:
            found = next(
                (index for index, event in enumerate(tool_events) if _tool_name(event) == str(tool_name)),
                None,
            )
            if found is None:
                return [f"tool_order missing tool {tool_name!r}"]
            indices.append(found)
        if indices != sorted(indices):
            return [f"tool_order violated: expected {tools!r} in sequence"]
        return []

    if atype == "tool_args_match":
        name = str(assertion.get("name", ""))
        expected_args = assertion.get("args", {})
        if not isinstance(expected_args, dict):
            raise ValueError("tool_args_match requires args mapping")
        for event in _events_of_type(events, "tool"):
            if _tool_name(event) != name:
                continue
            actual_args = event.data.get("args", {})
            if _args_subset(actual_args, expected_args):
                return []
        return [f"no call to {name!r} matched args subset {expected_args!r}"]

    if atype == "tool_call_count":
        name = str(assertion.get("name", ""))
        count = sum(1 for event in _events_of_type(events, "tool") if _tool_name(event) == name)
        has_bound = False
        if "count" in assertion:
            has_bound = True
            if count != int(assertion["count"]):
                return [f"tool {name!r} call count {count} != expected {assertion['count']}"]
        if "max" in assertion:
            has_bound = True
            if count > int(assertion["max"]):
                return [f"tool {name!r} call count {count} exceeds max {assertion['max']}"]
        if "min" in assertion:
            has_bound = True
            if count < int(assertion["min"]):
                return [f"tool {name!r} call count {count} below min {assertion['min']}"]
        if not has_bound:
            return ["tool_call_count requires count, min, or max"]
        return []

    if atype == "gate_decision":
        gate_name = str(assertion.get("name", ""))
        expected = str(assertion.get("decision", ""))
        for event in _events_of_type(events, "gate"):
            if str(event.data.get("name", "")) != gate_name:
                continue
            actual = str(event.data.get("decision", ""))
            if actual == expected:
                return []
        return [f"gate {gate_name!r} decision {expected!r} not recorded"]

    if atype == "outcome_status":
        expected = str(assertion.get("status", ""))
        outcomes = _events_of_type(events, "outcome")
        if not outcomes:
            return ["missing outcome event"]
        actual = str(outcomes[-1].data.get("status", ""))
        if actual != expected:
            return [f"outcome status {actual!r} != expected {expected!r}"]
        return []

    if atype == "forbid_tool_before_gate":
        forbidden = str(assertion.get("tool", ""))
        gate_name = str(assertion.get("gate", ""))
        gate_index = next(
            (
                index
                for index, event in enumerate(events)
                if event.event_type == "gate" and str(event.data.get("name", "")) == gate_name
            ),
            None,
        )
        if gate_index is None:
            return [f"forbid_tool_before_gate: gate {gate_name!r} not found"]
        for index, event in enumerate(events[:gate_index]):
            if event.event_type == "tool" and _tool_name(event) == forbidden:
                return [
                    f"tool {forbidden!r} called before gate {gate_name!r} at event index {index}",
                ]
        return []

    raise ValueError(f"unknown transcript assertion type: {atype!r}")


def run_transcript_case(case: TranscriptCase) -> EvalResult:
    messages: list[str] = []
    for index, assertion in enumerate(case.assertions):
        try:
            messages.extend(_run_transcript_assertion(case.events, assertion))
        except ValueError as exc:
            messages.append(f"assertion[{index}] failed: {exc}")
    return EvalResult(case.skill, case.case_id, not messages, messages)
