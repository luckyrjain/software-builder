"""Executable Batch 3 per-skill scenario harness.

Loads literal evals/{positive,negative,ambiguous,adversarial,degraded}/cases.yaml
and executes each case against the deterministic dispatcher or capability-loss
simulator. Every dimension must contain exactly one scenario for every
registered skill; missing/duplicate skills fail closed. Adversarial cases also
require one passing guardrail golden per skill; degraded scenarios must match
the canonical per-skill degraded_behavior.yaml policy.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from scripts.evals.dispatcher import RoutingRule, dispatch_with_rules, load_routing_rules, simulate_capability_loss
from scripts.evals.golden import GoldenCase, load_golden_fixtures, run_golden_case
from scripts.evals.types import EvalResult
from scripts.registry.schema import Registry
from scripts.yaml_safety import load_unique_yaml_file, require_mapping

DIMENSIONS = ("positive", "negative", "ambiguous", "adversarial", "degraded")


def _load_cases(root: Path, dimension: str, registry: Registry) -> list[dict[str, Any]]:
    path = root / "evals" / dimension / "cases.yaml"
    raw = require_mapping(load_unique_yaml_file(path), f"{dimension} scenarios")
    if raw.get("schema_version") != 1:
        raise ValueError(f"{path}: schema_version must be 1")
    if raw.get("dimension") != dimension:
        raise ValueError(f"{path}: dimension must be {dimension!r}")
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{path}: cases must be a non-empty list")
    parsed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, case_raw in enumerate(cases):
        case = require_mapping(case_raw, f"{path}: cases[{index}]")
        skill = case.get("skill")
        if not isinstance(skill, str) or skill not in registry.skills:
            raise ValueError(f"{path}: cases[{index}].skill must be a registered skill")
        if skill in seen:
            raise ValueError(f"{path}: duplicate scenario for skill {skill!r}")
        seen.add(skill)
        parsed.append(dict(case))
    registered = set(registry.skills)
    if seen != registered:
        raise ValueError(
            f"{path}: scenarios must cover exactly all registered skills; "
            f"missing={sorted(registered - seen)}, extra={sorted(seen - registered)}",
        )
    return parsed


def _load_degraded_policy(root: Path, registry: Registry) -> dict[str, dict[str, Any]]:
    path = root / "scripts" / "registry" / "degraded_behavior.yaml"
    raw = require_mapping(load_unique_yaml_file(path), "degraded behavior")
    if raw.get("schema_version") != 1:
        raise ValueError("degraded_behavior.schema_version must be 1")
    skills_raw = require_mapping(raw.get("skills"), "degraded behavior.skills")
    registered = set(registry.skills)
    if set(skills_raw) != registered:
        raise ValueError(
            "degraded behavior must cover exactly all registered skills; "
            f"missing={sorted(registered - set(skills_raw))}, extra={sorted(set(skills_raw) - registered)}",
        )
    return {
        skill_id: dict(require_mapping(config, f"degraded behavior.skills.{skill_id}"))
        for skill_id, config in skills_raw.items()
    }


def _routing_case(
    rules: dict[str, RoutingRule],
    dimension: str,
    case: dict[str, Any],
    golden_by_ref: dict[str, GoldenCase],
    golden_results: dict[str, EvalResult],
) -> EvalResult:
    skill = str(case["skill"])
    prompt = case.get("prompt")
    messages: list[str] = []
    if not isinstance(prompt, str) or not prompt.strip():
        return EvalResult(skill, f"scenario-{dimension}", False, ["prompt must be non-empty"])
    result = dispatch_with_rules(rules, prompt)
    expected_status = case.get("expected_status")
    if result.status != expected_status:
        messages.append(f"dispatch status {result.status!r} != expected {expected_status!r}; candidates={list(result.candidates)}")

    if dimension in {"positive", "negative", "adversarial"}:
        expected_owner = case.get("expected_owner")
        if result.owner != expected_owner:
            messages.append(f"dispatch owner {result.owner!r} != expected {expected_owner!r}")
    if dimension == "negative":
        forbidden_owner = case.get("forbidden_owner")
        if forbidden_owner in result.candidates:
            messages.append(f"forbidden owner {forbidden_owner!r} was selected/matched")
    if dimension == "ambiguous":
        expected_candidates = case.get("expected_candidates")
        if not isinstance(expected_candidates, list) or not all(isinstance(item, str) for item in expected_candidates):
            messages.append("expected_candidates must be a string list")
        elif tuple(sorted(result.candidates)) != tuple(sorted(expected_candidates)):
            messages.append(f"dispatch candidates {sorted(result.candidates)} != expected {sorted(expected_candidates)}")
    if dimension == "adversarial":
        golden_ref = case.get("golden_ref")
        if not isinstance(golden_ref, str) or not golden_ref:
            messages.append("golden_ref must be a non-empty string")
        else:
            golden = golden_by_ref.get(golden_ref)
            if golden is None:
                messages.append(f"missing adversarial golden {golden_ref}")
            elif golden.skill != skill:
                messages.append(f"adversarial golden {golden_ref} belongs to {golden.skill}, not {skill}")
            else:
                golden_result = golden_results.get(golden_ref)
                if golden_result is None:
                    golden_result = run_golden_case(golden)
                if not golden_result.passed:
                    messages.append(f"adversarial golden is failing: {golden_ref}: {'; '.join(golden_result.messages)}")
    return EvalResult(skill, f"scenario-{dimension}", not messages, messages)


def _degraded_case(registry: Registry, case: dict[str, Any], policy: dict[str, dict[str, Any]]) -> EvalResult:
    skill = str(case["skill"])
    missing = case.get("missing_capability")
    available = case.get("available_capabilities")
    expected = case.get("expected_behavior")
    messages: list[str] = []
    if not isinstance(missing, str) or not missing:
        messages.append("missing_capability must be non-empty")
    if not isinstance(available, list) or not all(isinstance(item, str) for item in available):
        messages.append("available_capabilities must be a string list")
    if expected not in {"BLOCKED", "DEGRADED", "FALLBACK"}:
        messages.append(f"invalid expected_behavior {expected!r}")

    declared = policy[skill]
    if missing != declared.get("missing_capability"):
        messages.append(f"scenario missing_capability {missing!r} != declared policy {declared.get('missing_capability')!r}")
    if available != declared.get("available_capabilities"):
        messages.append(f"scenario available_capabilities {available!r} != declared policy {declared.get('available_capabilities')!r}")
    if expected != declared.get("behavior"):
        messages.append(f"scenario expected_behavior {expected!r} != declared policy {declared.get('behavior')!r}")

    if messages:
        return EvalResult(skill, "scenario-degraded", False, messages)
    assert isinstance(missing, str)
    assert isinstance(available, list)
    actual = simulate_capability_loss(registry, skill, missing, available)
    if actual != expected:
        messages.append(f"capability-loss behavior {actual!r} != expected {expected!r}")
    return EvalResult(skill, "scenario-degraded", not messages, messages)


def run_per_skill_scenarios(
    root: Path,
    registry: Registry,
    *,
    case_results: Iterable[EvalResult] | None = None,
    golden_cases: Iterable[GoldenCase] | None = None,
) -> list[EvalResult]:
    results: list[EvalResult] = []
    rules = load_routing_rules(root, registry)
    degraded_policy = _load_degraded_policy(root, registry)
    golden_list = list(golden_cases) if golden_cases is not None else load_golden_fixtures(root / "evals" / "golden")
    golden_by_ref = {f"{case.skill}/{case.case_id}": case for case in golden_list}
    golden_results = {
        f"{result.skill}/{result.case_id}": result
        for result in (case_results or [])
        if f"{result.skill}/{result.case_id}" in golden_by_ref
    }
    for dimension in DIMENSIONS:
        for case in _load_cases(root, dimension, registry):
            if dimension == "degraded":
                results.append(_degraded_case(registry, case, degraded_policy))
            else:
                results.append(_routing_case(rules, dimension, case, golden_by_ref, golden_results))
    return results
