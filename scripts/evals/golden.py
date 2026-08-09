"""Tier-3 behavioral evals: validate recorded golden model outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from scripts.evals.__main__ import EvalResult

GOLDEN_DIR_NAME = "golden"


@dataclass(frozen=True)
class GoldenCase:
    skill: str
    case_id: str
    tier: int
    description: str
    recorded_output: dict[str, Any]
    assertions: list[dict[str, Any]]
    path: Path


def load_golden_fixtures(golden_dir: Path) -> list[GoldenCase]:
    if not golden_dir.is_dir():
        return []

    cases: list[GoldenCase] = []
    for path in sorted(golden_dir.rglob("*.yaml")):
        if path.name.startswith("_"):
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: golden fixture root must be a mapping")

        skill = str(raw.get("skill", ""))
        case_id = str(raw.get("case_id", ""))
        if not skill or not case_id:
            raise ValueError(f"{path}: skill and case_id are required")

        recorded_output = raw.get("recorded_output", {})
        if not isinstance(recorded_output, dict):
            raise ValueError(f"{path}: recorded_output must be a mapping")

        assertions = raw.get("assertions", [])
        if not isinstance(assertions, list) or not assertions:
            raise ValueError(f"{path}: assertions must be a non-empty list")

        cases.append(
            GoldenCase(
                skill=skill,
                case_id=case_id,
                tier=int(raw.get("tier", 3)),
                description=str(raw.get("description", "")),
                recorded_output=recorded_output,
                assertions=assertions,
                path=path,
            ),
        )
    return cases


def _resolve_path(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for segment in dotted_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise KeyError(dotted_path)
        current = current[segment]
    return current


def _run_golden_assertion(output: dict[str, Any], assertion: dict[str, Any]) -> list[str]:
    atype = str(assertion.get("type", ""))

    if atype == "field_equals":
        path = str(assertion.get("path", ""))
        expected = assertion.get("value")
        try:
            actual = _resolve_path(output, path)
        except KeyError:
            return [f"missing field path: {path!r}"]
        if actual != expected:
            return [f"{path} = {actual!r}, expected {expected!r}"]
        return []

    if atype == "field_present":
        path = str(assertion.get("path", ""))
        try:
            _resolve_path(output, path)
        except KeyError:
            return [f"missing required field path: {path!r}"]
        return []

    if atype == "forbid_field_value":
        path = str(assertion.get("path", ""))
        forbidden = assertion.get("value")
        try:
            actual = _resolve_path(output, path)
        except KeyError:
            return []
        if actual == forbidden:
            return [f"{path} must not equal {forbidden!r}"]
        return []

    if atype == "field_in":
        path = str(assertion.get("path", ""))
        allowed = assertion.get("values", [])
        if not isinstance(allowed, list):
            raise ValueError("field_in requires values list")
        try:
            actual = _resolve_path(output, path)
        except KeyError:
            return [f"missing field path: {path!r}"]
        if actual not in allowed:
            return [f"{path} = {actual!r} not in allowed {allowed!r}"]
        return []

    if atype == "forbid_pattern":
        path = str(assertion.get("path", ""))
        pattern = str(assertion.get("pattern", ""))
        try:
            actual = _resolve_path(output, path)
        except KeyError:
            return []
        text = str(actual)
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            return [f"{path} matched forbidden pattern: {pattern!r}"]
        return []

    raise ValueError(f"unknown golden assertion type: {atype!r}")


def run_golden_case(case: GoldenCase) -> EvalResult:
    messages: list[str] = []
    for index, assertion in enumerate(case.assertions):
        try:
            messages.extend(_run_golden_assertion(case.recorded_output, assertion))
        except ValueError as exc:
            messages.append(f"assertion[{index}] failed: {exc}")
    return EvalResult(case.skill, case.case_id, not messages, messages)
