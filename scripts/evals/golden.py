"""Tier-3 behavioral evals: validate recorded golden model outputs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.evals.types import EvalResult
from scripts.yaml_safety import load_unique_yaml_file

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
    contract_coverage: list[str] = field(default_factory=list)


def parse_golden_fixture(
    path: Path,
    *,
    skill: str | None = None,
    case_id: str | None = None,
    recorded_output: dict[str, Any] | None = None,
) -> GoldenCase:
    """Parse one golden fixture file into a GoldenCase.

    skill/case_id/recorded_output are read from the fixture file by default
    (load_golden_fixtures' directory-scan case). Pass overrides to use values
    from elsewhere instead -- scripts/evals/live_run.py's score_against_golden
    scores a *live* run's fresh output against an existing fixture's
    assertions, so recorded_output must be this run's output, not whatever
    the fixture recorded when it was captured, and skill/case_id come from
    the live case rather than trusting the golden file's own labels.
    """
    raw = load_unique_yaml_file(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: golden fixture root must be a mapping")

    resolved_skill = skill if skill is not None else str(raw.get("skill", ""))
    resolved_case_id = case_id if case_id is not None else str(raw.get("case_id", ""))
    if not resolved_skill or not resolved_case_id:
        raise ValueError(f"{path}: skill and case_id are required")

    resolved_recorded_output = recorded_output if recorded_output is not None else raw.get("recorded_output", {})
    if not isinstance(resolved_recorded_output, dict):
        raise ValueError(f"{path}: recorded_output must be a mapping")

    assertions = raw.get("assertions", [])
    if not isinstance(assertions, list) or not assertions:
        raise ValueError(f"{path}: assertions must be a non-empty list")

    return GoldenCase(
        skill=resolved_skill,
        case_id=resolved_case_id,
        tier=int(raw.get("tier", 3)),
        description=str(raw.get("description", "")),
        recorded_output=resolved_recorded_output,
        assertions=assertions,
        path=path,
        contract_coverage=raw.get("contract_coverage", []),
    )


def load_golden_fixtures(golden_dir: Path) -> list[GoldenCase]:
    if not golden_dir.is_dir():
        return []

    cases: list[GoldenCase] = []
    for path in sorted(golden_dir.rglob("*.yaml")):
        if path.name.startswith("_"):
            continue
        cases.append(parse_golden_fixture(path))
    return cases


def golden_case_index(cases: Iterable[GoldenCase]) -> dict[str, GoldenCase]:
    """Map "skill/case_id" -> GoldenCase, the ref convention used throughout evals/."""
    return {f"{case.skill}/{case.case_id}": case for case in cases}


_PATH_SEGMENT_RE = re.compile(r"^(?P<key>[^\[\]]*)(?P<brackets>(?:\[[^\]]*\])*)$")
_BRACKET_RE = re.compile(r"\[([^\]]*)\]")
_PREDICATE_RE = re.compile(r"^\?\s*([A-Za-z_][A-Za-z0-9_]*)\s*==\s*(.+?)\s*$")


def _split_path_segments(dotted_path: str) -> list[str]:
    """Split on "." like str.split, except a "." inside a [...] bracket (e.g. a
    predicate's quoted file-path value) does not start a new segment."""
    segments: list[str] = []
    current = ""
    depth = 0
    for ch in dotted_path:
        if ch == "[":
            depth += 1
            current += ch
        elif ch == "]":
            depth -= 1
            current += ch
        elif ch == "." and depth == 0:
            segments.append(current)
            current = ""
        else:
            current += ch
    segments.append(current)
    return segments


def _parse_bracket_literal(raw: str) -> Any:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw == "null":
        return None
    for caster in (int, float):
        try:
            return caster(raw)
        except ValueError:
            continue
    return raw


def _apply_bracket_op(current: Any, raw_op: str, dotted_path: str) -> Any:
    """Apply one "[...]" op -- either a list index ("[0]", "[-1]") or a
    predicate ("[?field=='value']") -- to resolve exactly one list item."""
    op = raw_op.strip()
    if op.startswith("?"):
        match = _PREDICATE_RE.match(op)
        if match is None:
            raise ValueError(f"invalid predicate {raw_op!r} in path {dotted_path!r}")
        field, raw_value = match.group(1), match.group(2)
        expected = _parse_bracket_literal(raw_value)
        if not isinstance(current, list):
            raise KeyError(dotted_path)
        matches = [item for item in current if isinstance(item, dict) and item.get(field) == expected]
        if not matches:
            raise KeyError(dotted_path)
        if len(matches) > 1:
            raise ValueError(
                f"ambiguous path {dotted_path!r}: predicate [{op}] matched {len(matches)} "
                f"items, expected exactly 1"
            )
        return matches[0]

    try:
        index = int(op)
    except ValueError as exc:
        raise ValueError(f"invalid list index {raw_op!r} in path {dotted_path!r}") from exc
    if not isinstance(current, list) or index < -len(current) or index >= len(current):
        raise KeyError(dotted_path)
    return current[index]


def resolve_path(data: dict[str, Any], dotted_path: str) -> Any:
    """Walk a dotted path by dict-key lookup, raising KeyError on any missing
    segment. A segment may carry one or more "[...]" ops to reach into a list:
    a plain index ("hypotheses_tested[0]") or a single-field equality predicate
    ("findings[?evidence_status=='OBSERVED']") that must match exactly one item
    -- zero matches is KeyError (consistent with a missing dict key), more than
    one is ValueError, since a fixture assertion is supposed to pin down one
    specific item, not silently pick one out of several.

    Shared by every module that needs to read or compare a nested field in a
    recorded golden output (this file's own assertions, mutation_guard.py's
    mutation targeting, eval_coverage_contract.py's anchor checks) -- one copy so
    path-resolution semantics can't quietly diverge between them.
    """
    current: Any = data
    for segment in _split_path_segments(dotted_path):
        match = _PATH_SEGMENT_RE.match(segment)
        if match is None:
            raise ValueError(f"invalid path segment {segment!r} in path {dotted_path!r}")
        key = match.group("key")
        if key:
            if not isinstance(current, dict) or key not in current:
                raise KeyError(dotted_path)
            current = current[key]
        for raw_op in _BRACKET_RE.findall(match.group("brackets")):
            current = _apply_bracket_op(current, raw_op, dotted_path)
    return current


def _run_golden_assertion(output: dict[str, Any], assertion: dict[str, Any]) -> list[str]:
    atype = str(assertion.get("type", ""))

    if atype == "field_equals":
        path = str(assertion.get("path", ""))
        expected = assertion.get("value")
        try:
            actual = resolve_path(output, path)
        except KeyError:
            return [f"missing field path: {path!r}"]
        if actual != expected:
            return [f"{path} = {actual!r}, expected {expected!r}"]
        return []

    if atype == "field_present":
        path = str(assertion.get("path", ""))
        try:
            resolve_path(output, path)
        except KeyError:
            return [f"missing required field path: {path!r}"]
        return []

    if atype == "forbid_field_value":
        path = str(assertion.get("path", ""))
        forbidden = assertion.get("value")
        try:
            actual = resolve_path(output, path)
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
            actual = resolve_path(output, path)
        except KeyError:
            return [f"missing field path: {path!r}"]
        if actual not in allowed:
            return [f"{path} = {actual!r} not in allowed {allowed!r}"]
        return []

    if atype == "forbid_pattern":
        path = str(assertion.get("path", ""))
        pattern = str(assertion.get("pattern", ""))
        try:
            actual = resolve_path(output, path)
        except KeyError:
            return []
        if _pattern_matches(pattern, str(actual)):
            return [f"{path} matched forbidden pattern: {pattern!r}"]
        return []

    if atype == "require_pattern":
        path = str(assertion.get("path", ""))
        pattern = str(assertion.get("pattern", ""))
        try:
            actual = resolve_path(output, path)
        except KeyError:
            return [f"missing field path: {path!r}"]
        if not _pattern_matches(pattern, str(actual)):
            return [f"{path} did not match required pattern: {pattern!r}"]
        return []

    raise ValueError(f"unknown golden assertion type: {atype!r}")


def field_matches_pattern(data: dict[str, Any], dotted_path: str, pattern: str) -> bool:
    """True if the string field at dotted_path matches pattern.

    Deliberately resolves dotted_path first rather than searching the whole
    serialized fixture -- a mutation anchor's raw_pattern is supposed to prove
    a SPECIFIC field (raw_path) carries dangerous content, not merely that the
    pattern appears somewhere in the fixture. Matching against the whole blob
    lets an anchor pass even when raw_path points at an unrelated, harmless
    field and the pattern happens to match elsewhere in the same fixture.
    Raises KeyError if dotted_path is missing, ValueError if pattern is invalid.
    """
    value = resolve_path(data, dotted_path)
    return _pattern_matches(pattern, str(value))


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


def _case_matches_filters(case: GoldenCase, skill_filter: str | None, tier_filter: int | None) -> bool:
    if skill_filter and case.skill != skill_filter:
        return False
    if tier_filter is not None and case.tier != tier_filter:
        return False
    return True


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
        if not _case_matches_filters(case, skill_filter, tier_filter):
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
                value = str(resolve_path(case.recorded_output, path))
            except KeyError:
                continue
            if "\n" not in value:
                warnings.append(
                    f"{case.path}: {case.case_id}: {atype} on {path!r} uses a (?m)^...$ "
                    f"anchor against a field with no real newline in its current "
                    f"recorded value — worth verifying this can actually fail: {pattern!r}",
                )
    return warnings


DESCRIPTION_LENGTH_WARNING_THRESHOLD = 1200


def find_oversized_descriptions(
    cases: list[GoldenCase],
    *,
    skill_filter: str | None = None,
    tier_filter: int | None = None,
) -> list[str]:
    """Flag fixtures whose description exceeds DESCRIPTION_LENGTH_WARNING_THRESHOLD chars.

    description is meant to state what a fixture verifies, not carry per-assertion
    coverage caveats, cross-fixture regression history, or skill-level design rationale
    unrelated to any specific assertion -- those belong as YAML comments next to the
    assertion or field they actually describe (see e.g. pr-review's and the
    *-test-creator siblings' golden fixtures for the convention: a `# CAVEAT: ...`
    comment directly above the assertion it explains). A long description is the signal
    that content worth relocating has accumulated; this is a heuristic length check, not
    a content classifier, so a genuinely long single-paragraph test-intent explanation
    can still legitimately cross the threshold -- hence a warning, not a failure.

    The threshold sits just above 1191 chars, the longest description among the fixtures
    already migrated to the # CAVEAT: convention (integration-test-creator's) -- picked
    empirically from real, individually-reviewed exemplars rather than guessed, so a
    genuinely multi-site test-intent description that's already been through the
    relocation doesn't itself keep tripping the warning it exists to resolve. A lower
    threshold sounded stricter but had weak discriminating power in practice: length
    alone doesn't distinguish "has a misplaced caveat" from "legitimately describes a
    multi-field injection scenario," so setting it below what clean fixtures actually
    measure just produced noise on fixtures with nothing left to relocate.

    Takes already-loaded cases for the same reason find_vacuous_anchored_patterns does:
    main() also runs the eval suite over them, so a caller that already has them loaded
    shouldn't have to parse the fixture tree twice.
    """
    warnings: list[str] = []
    for case in cases:
        if not _case_matches_filters(case, skill_filter, tier_filter):
            continue
        if len(case.description) > DESCRIPTION_LENGTH_WARNING_THRESHOLD:
            warnings.append(
                f"{case.path}: {case.case_id}: description is {len(case.description)} chars "
                f"(over {DESCRIPTION_LENGTH_WARNING_THRESHOLD}) — consider moving per-assertion "
                f"caveats or regression history into `# CAVEAT:` comments near what they describe",
            )
    return warnings
