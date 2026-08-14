"""Batch 3 evaluation coverage gates.

Batch 3 turns the shared evaluation policy into an all-skills completeness
contract. The checks are deterministic CI gates: they prove every registered
skill participates in all five contract dimensions, has a passing golden
fixture, and that mutation/degraded coverage declarations remain executable.
Live/model quality remains a separate tier.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from scripts.evals.golden import GoldenCase
from scripts.evals.types import EvalResult
from scripts.registry.schema import Registry
from scripts.yaml_safety import load_unique_yaml_file, require_mapping

BATCH3_SKILL = "batch3"
REQUIRED_DIMENSIONS = ("positive", "negative", "ambiguous", "adversarial", "degraded")


def _result(case_id: str, messages: list[str]) -> EvalResult:
    return EvalResult(BATCH3_SKILL, case_id, not messages, messages)


def _result_map(results: Iterable[EvalResult]) -> dict[str, EvalResult]:
    return {f"{result.skill}/{result.case_id}": result for result in results}


def _all_skill_dimensions(registry: Registry, results: dict[str, EvalResult]) -> EvalResult:
    messages: list[str] = []
    for skill_id in sorted(registry.skills):
        for dimension in REQUIRED_DIMENSIONS:
            ref = f"{skill_id}/global-{dimension}"
            result = results.get(ref)
            if result is None:
                messages.append(f"{skill_id}: missing {dimension} eval case")
            elif not result.passed:
                messages.append(f"{skill_id}: {dimension} eval case is failing")
    return _result("all-skill-dimensions", messages)


def _all_skill_golden(
    registry: Registry,
    results: dict[str, EvalResult],
    golden_cases: Iterable[GoldenCase],
) -> EvalResult:
    messages: list[str] = []
    by_skill: dict[str, list[GoldenCase]] = {}
    for case in golden_cases:
        by_skill.setdefault(case.skill, []).append(case)

    for skill_id in sorted(registry.skills):
        cases = by_skill.get(skill_id, [])
        if not cases:
            messages.append(f"{skill_id}: no golden fixture")
            continue
        refs = [f"{case.skill}/{case.case_id}" for case in cases]
        passing = [ref for ref in refs if ref in results and results[ref].passed]
        if not passing:
            messages.append(f"{skill_id}: no passing golden fixture")
    return _result("all-skill-golden", messages)


def _mutation_matrix(root: Path, results: dict[str, EvalResult]) -> EvalResult:
    contract = require_mapping(
        load_unique_yaml_file(root / "scripts" / "registry" / "eval_contracts.yaml"),
        "eval contracts",
    )
    classes = require_mapping(contract.get("adversarial_classes"), "adversarial_classes")
    messages: list[str] = []
    seen_mutations: set[str] = set()
    for class_id, raw in sorted(classes.items()):
        config = require_mapping(raw, f"adversarial_classes.{class_id}")
        mutation = config.get("mutation")
        if not isinstance(mutation, str) or not mutation.strip():
            messages.append(f"{class_id}: missing mutation payload")
            continue
        normalized = mutation.strip().casefold()
        if normalized in seen_mutations:
            messages.append(f"{class_id}: mutation payload duplicates another class")
        seen_mutations.add(normalized)
        refs = config.get("case_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
            messages.append(f"{class_id}: case_refs must be a non-empty list")
            continue
        for ref in refs:
            result = results.get(ref)
            if result is None:
                messages.append(f"{class_id}: missing mutation regression case {ref}")
            elif not result.passed:
                messages.append(f"{class_id}: mutation regression case is failing: {ref}")
    return _result("mutation-matrix", messages)


def _degraded_matrix(root: Path, registry: Registry, results: dict[str, EvalResult]) -> EvalResult:
    """Require every skill's degraded contract case plus declared host scenarios.

    The per-skill global-degraded case validates the skill's capability metadata.
    The repository-level degraded_host_cases keep concrete high-risk scenarios
    tied to passing regression fixtures.
    """
    contract = require_mapping(
        load_unique_yaml_file(root / "scripts" / "registry" / "eval_contracts.yaml"),
        "eval contracts",
    )
    scenarios = require_mapping(contract.get("degraded_host_cases"), "degraded_host_cases")
    messages: list[str] = []
    for skill_id in sorted(registry.skills):
        ref = f"{skill_id}/global-degraded"
        result = results.get(ref)
        if result is None or not result.passed:
            messages.append(f"{skill_id}: degraded capability contract is not passing")
    for scenario_id, raw in sorted(scenarios.items()):
        config = require_mapping(raw, f"degraded_host_cases.{scenario_id}")
        refs = config.get("case_refs")
        if not isinstance(refs, list) or not refs:
            messages.append(f"{scenario_id}: degraded scenario requires case_refs")
            continue
        for ref in refs:
            result = results.get(str(ref))
            if result is None:
                messages.append(f"{scenario_id}: missing degraded regression case {ref}")
            elif not result.passed:
                messages.append(f"{scenario_id}: degraded regression case is failing: {ref}")
    return _result("degraded-matrix", messages)


def run_batch3_contract_checks(
    root: Path,
    registry: Registry,
    *,
    case_results: Iterable[EvalResult],
    golden_cases: Iterable[GoldenCase],
) -> list[EvalResult]:
    """Run Batch 3 completeness checks after normal deterministic eval cases."""
    result_map = _result_map(case_results)
    return [
        _all_skill_dimensions(registry, result_map),
        _all_skill_golden(registry, result_map, golden_cases),
        _mutation_matrix(root, result_map),
        _degraded_matrix(root, registry, result_map),
    ]
