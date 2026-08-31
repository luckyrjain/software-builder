"""Batch 3 evaluation completeness gates.

The common harness executes five concrete scenario dimensions for every
registered skill before these repository-level checks run. This module verifies
that those behavioral results are complete and passing, then checks golden,
routing, mutation, untrusted-surface, and degraded-host coverage.

This remains deterministic CI. Live/model evals measure model judgement and
host-specific routing quality separately.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from scripts.evals.dispatcher import dispatch_prompt
from scripts.evals.golden import GoldenCase, field_matches_pattern, golden_case_index
from scripts.evals.scenario_harness import DIMENSIONS
from scripts.evals.types import EvalResult
from scripts.registry.schema import Registry
from scripts.yaml_safety import load_unique_yaml_file, require_mapping

BATCH3_SKILL = "batch3"
REQUIRED_DIMENSIONS = DIMENSIONS
REQUIRED_BEHAVIOR_SCENARIOS = {
    "correct_invocation",
    "correct_non_invocation",
    "routing",
    "insufficient_evidence",
    "tool_failure",
    "prompt_injection",
    "missing_permissions",
    "output_schema",
    "cancellation",
    "stale_evidence",
}


def _result(case_id: str, messages: list[str]) -> EvalResult:
    return EvalResult(BATCH3_SKILL, case_id, not messages, messages)


def _result_map(results: Iterable[EvalResult]) -> dict[str, EvalResult]:
    return {f"{result.skill}/{result.case_id}": result for result in results}


def _eval_contract(root: Path) -> dict[str, Any]:
    return require_mapping(
        load_unique_yaml_file(root / "scripts" / "registry" / "eval_contracts.yaml"),
        "eval contracts",
    )


def _all_skill_scenarios(registry: Registry, results: dict[str, EvalResult]) -> EvalResult:
    messages: list[str] = []
    for skill_id in sorted(registry.skills):
        for dimension in REQUIRED_DIMENSIONS:
            ref = f"{skill_id}/scenario-{dimension}"
            result = results.get(ref)
            if result is None:
                messages.append(f"{skill_id}: missing executable {dimension} scenario")
            elif not result.passed:
                messages.append(f"{skill_id}: {dimension} scenario is failing: {'; '.join(result.messages)}")
    expected = len(registry.skills) * len(REQUIRED_DIMENSIONS)
    actual = sum(
        1
        for ref in results
        if any(ref == f"{skill_id}/scenario-{dimension}" for skill_id in registry.skills for dimension in REQUIRED_DIMENSIONS)
    )
    if actual != expected:
        messages.append(f"scenario result count {actual} != expected {expected}")
    return _result("all-skill-five-dimension-scenarios", messages)


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
        if not any(ref in results and results[ref].passed for ref in refs):
            messages.append(f"{skill_id}: no passing golden fixture")
    return _result("all-skill-golden", messages)


def _behavior_scenario_matrix(root: Path, results: dict[str, EvalResult]) -> EvalResult:
    contract = _eval_contract(root)
    scenarios = require_mapping(contract.get("behavior_scenarios"), "behavior_scenarios")
    messages: list[str] = []
    if set(scenarios) != REQUIRED_BEHAVIOR_SCENARIOS:
        messages.append(
            "behavior scenarios must exactly match Batch 3 requirements; "
            f"missing={sorted(REQUIRED_BEHAVIOR_SCENARIOS - set(scenarios))}, "
            f"extra={sorted(set(scenarios) - REQUIRED_BEHAVIOR_SCENARIOS)}",
        )
    for scenario_id, raw in sorted(scenarios.items()):
        config = require_mapping(raw, f"behavior_scenarios.{scenario_id}")
        refs = config.get("case_refs")
        gate = config.get("contract_gate")
        has_refs = isinstance(refs, list) and bool(refs)
        has_gate = isinstance(gate, str) and bool(gate)
        if has_refs == has_gate:
            messages.append(f"{scenario_id}: declare exactly one of case_refs or contract_gate")
            continue
        if has_refs:
            assert isinstance(refs, list)
            for ref in refs:
                if not isinstance(ref, str) or not ref:
                    messages.append(f"{scenario_id}: invalid case_ref {ref!r}")
                    continue
                result = results.get(ref)
                if result is None:
                    messages.append(f"{scenario_id}: missing eval result {ref}")
                elif not result.passed:
                    messages.append(f"{scenario_id}: eval result is failing: {ref}")
            continue
        prefix_by_gate = {
            "routing_collisions": "platform/routing-",
            "adversarial_matrix": "batch3-mutation/",
        }
        prefix = prefix_by_gate.get(str(gate))
        if prefix is None:
            messages.append(f"{scenario_id}: unknown contract_gate {gate!r}")
            continue
        matching = [result for ref, result in results.items() if ref.startswith(prefix)]
        if not matching:
            messages.append(f"{scenario_id}: contract gate {gate!r} has no executable results")
        elif any(not result.passed for result in matching):
            messages.append(f"{scenario_id}: contract gate {gate!r} is failing")
    return _result("behavior-scenario-matrix", messages)


def _routing_matrix(root: Path, registry: Registry) -> EvalResult:
    """Execute the seven collision prompts through the deterministic dispatcher."""
    contract = _eval_contract(root)
    collisions = contract.get("routing_collisions")
    messages: list[str] = []
    if not isinstance(collisions, list) or not collisions:
        return _result("routing-collision-suite", ["routing_collisions must be non-empty"])
    seen: set[str] = set()
    for raw in collisions:
        if not isinstance(raw, dict):
            messages.append("routing collision entry must be a mapping")
            continue
        collision_id = str(raw.get("id", ""))
        prompt = str(raw.get("prompt", ""))
        expected = str(raw.get("expected_owner", ""))
        if not collision_id or collision_id in seen:
            messages.append(f"invalid/duplicate routing collision id {collision_id!r}")
            continue
        seen.add(collision_id)
        result = dispatch_prompt(root, registry, prompt)
        if result.status != "selected" or result.owner != expected:
            messages.append(
                f"{collision_id}: dispatcher returned status={result.status}, "
                f"candidates={list(result.candidates)}; expected owner={expected}",
            )
    return _result("routing-collision-suite", messages)


def _referenced_matrix(
    root: Path,
    results: dict[str, EvalResult],
    *,
    key: str,
    case_id: str,
) -> EvalResult:
    contract = _eval_contract(root)
    matrix = require_mapping(contract.get(key), key)
    messages: list[str] = []
    for item_id, raw in sorted(matrix.items()):
        config = require_mapping(raw, f"{key}.{item_id}")
        refs = config.get("case_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
            messages.append(f"{item_id}: case_refs must be a non-empty list")
            continue
        for ref in refs:
            result = results.get(ref)
            if result is None:
                messages.append(f"{item_id}: missing regression case {ref}")
            elif not result.passed:
                messages.append(f"{item_id}: regression case is failing: {ref}")
    return _result(case_id, messages)


def _mutation_matrix(root: Path, results: dict[str, EvalResult]) -> EvalResult:
    contract = _eval_contract(root)
    adversarial = require_mapping(contract.get("adversarial_classes"), "adversarial_classes")
    messages: list[str] = []
    for class_id in sorted(adversarial):
        ref = f"batch3-mutation/{class_id}"
        result = results.get(ref)
        if result is None:
            messages.append(f"missing executable mutation result {ref}")
        elif not result.passed:
            messages.append(f"mutation result is failing: {ref}: {'; '.join(result.messages)}")
    return _result("mutation-matrix", messages)


def _mutation_anchor_matrix(
    root: Path,
    results: dict[str, EvalResult],
    golden_cases: Iterable[GoldenCase],
) -> EvalResult:
    contract = _eval_contract(root)
    adversarial = require_mapping(contract.get("adversarial_classes"), "adversarial_classes")
    anchor_doc = require_mapping(
        load_unique_yaml_file(root / "scripts" / "registry" / "mutation_anchors.yaml"),
        "mutation anchors",
    )
    if anchor_doc.get("schema_version") != 1:
        return _result("mutation-anchor-matrix", ["mutation_anchors.schema_version must be 1"])
    anchors = require_mapping(anchor_doc.get("anchors"), "mutation anchors.anchors")
    messages: list[str] = []
    if set(anchors) != set(adversarial):
        messages.append(
            "mutation anchor classes must exactly match adversarial_classes; "
            f"missing={sorted(set(adversarial) - set(anchors))}, extra={sorted(set(anchors) - set(adversarial))}",
        )
    golden_by_ref = golden_case_index(golden_cases)
    for class_id, raw in sorted(anchors.items()):
        config = require_mapping(raw, f"mutation anchors.{class_id}")
        case_ref = config.get("case_ref")
        raw_pattern = config.get("raw_pattern")
        raw_path = config.get("raw_path")
        if not isinstance(case_ref, str) or not case_ref:
            messages.append(f"{class_id}: case_ref is required")
            continue
        if not isinstance(raw_pattern, str) or not raw_pattern:
            messages.append(f"{class_id}: raw_pattern is required")
            continue
        if not isinstance(raw_path, str) or not raw_path:
            messages.append(f"{class_id}: raw_path is required")
            continue
        result = results.get(case_ref)
        if result is None or not result.passed:
            messages.append(f"{class_id}: anchor fixture must exist and pass: {case_ref}")
        fixture = golden_by_ref.get(case_ref)
        if fixture is None:
            messages.append(f"{class_id}: anchor must reference a golden fixture: {case_ref}")
            continue
        try:
            # Scoped to raw_path, not the whole serialized fixture -- proving
            # the pattern appears SOMEWHERE doesn't prove raw_path (the field
            # the mutation actually targets) carries dangerous content; a
            # pattern coincidentally matching an unrelated field would
            # otherwise pass vacuously. See golden.field_matches_pattern.
            if not field_matches_pattern(fixture.recorded_output, raw_path, raw_pattern):
                messages.append(f"{class_id}: raw_path {raw_path!r} lacks raw pattern {raw_pattern!r}")
        except KeyError:
            messages.append(f"{class_id}: raw_path does not exist: {raw_path!r}")
        except ValueError as exc:
            messages.append(f"{class_id}: invalid raw_pattern {raw_pattern!r}: {exc}")
    return _result("mutation-anchor-matrix", messages)


def run_batch3_contract_checks(
    root: Path,
    registry: Registry,
    *,
    case_results: Iterable[EvalResult],
    mutation_results: Iterable[EvalResult],
    golden_cases: Iterable[GoldenCase],
) -> list[EvalResult]:
    result_map = _result_map(case_results)
    # Mutation results get their own map rather than relying on the caller having already
    # merged them into case_results in the right order -- see the regression this caused in
    # commit 80e588a ("dedupe mutation evals"): an implicit "case_results must already contain
    # batch3-mutation/* by now" requirement enforced only by call order, not the signature.
    mutation_map = _result_map(mutation_results)
    golden_list = list(golden_cases)
    return [
        _all_skill_scenarios(registry, result_map),
        _all_skill_golden(registry, result_map, golden_list),
        _behavior_scenario_matrix(root, result_map),
        _routing_matrix(root, registry),
        _mutation_matrix(root, mutation_map),
        _mutation_anchor_matrix(root, result_map, golden_list),
        _referenced_matrix(root, result_map, key="untrusted_surfaces", case_id="untrusted-surface-matrix"),
        _referenced_matrix(root, result_map, key="degraded_host_cases", case_id="degraded-host-matrix"),
    ]
