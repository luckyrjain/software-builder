"""Tier-3 behavioral evals: validate recorded golden model outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from scripts.evals.types import EvalResult

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
        if _pattern_matches(pattern, str(actual)):
            return [f"{path} matched forbidden pattern: {pattern!r}"]
        return []

    if atype == "require_pattern":
        path = str(assertion.get("path", ""))
        pattern = str(assertion.get("pattern", ""))
        try:
            actual = _resolve_path(output, path)
        except KeyError:
            return [f"missing field path: {path!r}"]
        if not _pattern_matches(pattern, str(actual)):
            return [f"{path} did not match required pattern: {pattern!r}"]
        return []

    raise ValueError(f"unknown golden assertion type: {atype!r}")


def _pattern_matches(pattern: str, text: str) -> bool:
    try:
        return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None
    except re.error as exc:
        raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc


def run_golden_case(case: GoldenCase) -> EvalResult:
    messages: list[str] = []
    for index, assertion in enumerate(case.assertions):
        try:
            messages.extend(_run_golden_assertion(case.recorded_output, assertion))
        except ValueError as exc:
            messages.append(f"assertion[{index}] failed: {exc}")
    return EvalResult(case.skill, case.case_id, not messages, messages)


_MULTILINE_FLAG_RE = re.compile(r"\(\?[a-zA-Z]*m[a-zA-Z]*\)")
_BARE_CARET_RE = re.compile(r"(?<!\\)(?<!\[)\^")
_BARE_DOLLAR_RE = re.compile(r"(?<!\\)\$")


def _looks_like_multiline_anchor(pattern: str) -> bool:
    """Best-effort check for a (?m)^...$ multiline-anchor pattern shape. Not a full
    regex parser — a ^ elsewhere inside a character class, or a $ preceded by an
    already-escaped-away (even) run of backslashes, can still fool this — but it
    excludes the two false-positive shapes a bare ".*^.*$" substring match had: a ^
    used only to negate a character class ([^x]), and an escaped literal $ (\\$).
    """
    if not _MULTILINE_FLAG_RE.search(pattern):
        return False
    return bool(_BARE_CARET_RE.search(pattern) and _BARE_DOLLAR_RE.search(pattern))


def find_vacuous_anchored_patterns(
    cases: list[GoldenCase],
    *,
    skill_filter: str | None = None,
    tier_filter: int | None = None,
) -> list[str]:
    """Flag require_pattern/forbid_pattern assertions whose pattern uses a (?m)^...$
    multiline anchor against a target field that currently has no real newline
    character. re's ^/$ only anchor at real line boundaries, so — unless the field can
    legitimately gain a real newline on some reachable code path (a full-passthrough
    regression, for instance) — the pattern can never match regardless of content, and
    forbid_pattern passes vacuously even when escaping is completely broken. This is a
    heuristic screening pass, not proof: it flags every currently-zero-newline field as
    worth a second look, including cases that ARE reachable via a real regression path
    and so aren't actually vacuous (verify by hand, or by simulating the regression, the
    way the PR #102 review did — see that review for the scale of this issue found
    repo-wide when this check was added).

    Takes already-loaded cases (rather than a directory to load itself) so a caller
    that also needs the same cases for something else — main() also runs the eval
    suite over them — doesn't have to parse the fixture tree twice.
    """
    warnings: list[str] = []
    for case in cases:
        if skill_filter and case.skill != skill_filter:
            continue
        if tier_filter is not None and case.tier != tier_filter:
            continue
        for assertion in case.assertions:
            atype = str(assertion.get("type", ""))
            if atype not in ("require_pattern", "forbid_pattern"):
                continue
            pattern = str(assertion.get("pattern", ""))
            if not _looks_like_multiline_anchor(pattern):
                continue
            path = str(assertion.get("path", ""))
            try:
                value = str(_resolve_path(case.recorded_output, path))
            except KeyError:
                continue
            if "\n" not in value:
                warnings.append(
                    f"{case.path}: {case.case_id}: {atype} on {path!r} uses a (?m)^...$ "
                    f"anchor against a field with no real newline in its current "
                    f"recorded value — worth verifying this can actually fail: {pattern!r}",
                )
    return warnings
