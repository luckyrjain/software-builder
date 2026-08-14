"""Batch 3 evaluation coverage gates.

Batch 3 turns the shared evaluation policy into an all-skills completeness
contract. These deterministic checks prove every registered skill participates
in positive, negative, ambiguous, adversarial, and degraded evaluation; every
skill has passing golden coverage; and routing, behavior, mutation,
untrusted-surface, and degraded-host declarations remain tied to passing cases.

This is intentionally not a live/model-quality benchmark. Tier-2/3 live evals
remain the place to measure model judgement and prompt quality.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from scripts.evals.golden import GoldenCase
from scripts.evals.types import EvalResult
from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.schema import Registry
from scripts.registry.skill_frontmatter_schema import PLATFORM_CONTRACT, automation_only_guard_errors
from scripts.yaml_safety import load_unique_yaml_file, require_mapping

BATCH3_SKILL = "batch3"
REQUIRED_DIMENSIONS = ("positive", "negative", "ambiguous", "adversarial", "degraded")
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


def _result(case_id: str, messages: list[str], *, skill: str = BATCH3_SKILL) -> EvalResult:
    return EvalResult(skill, case_id, not messages, messages)


def _result_map(results: Iterable[EvalResult]) -> dict[str, EvalResult]:
    return {f"{result.skill}/{result.case_id}": result for result in results}


def _eval_contract(root: Path) -> dict[str, Any]:
    return require_mapping(
        load_unique_yaml_file(root / "scripts" / "registry" / "eval_contracts.yaml"),
        "eval contracts",
    )


def _platform_data(root: Path) -> dict[str, Any]:
    return require_mapping(
        load_unique_yaml_file(root / "scripts" / "registry" / "platform_contracts.yaml"),
        "platform contracts",
    )


def _composition_data(root: Path) -> dict[str, Any]:
    return require_mapping(
        load_unique_yaml_file(root / "scripts" / "registry" / "composition_runtime.yaml"),
        "composition runtime",
    )


def _positive_case(skill_id: str, results: dict[str, EvalResult]) -> EvalResult:
    ref = f"{skill_id}/global-happy"
    result = results.get(ref)
    messages: list[str] = []
    if result is None:
        messages.append("missing global-happy baseline")
    elif not result.passed:
        messages.append("global-happy baseline is failing")
    return _result("batch3-positive", messages, skill=skill_id)


def _negative_case(registry: Registry, skill_id: str, platform: dict[str, Any]) -> EvalResult:
    """Verify the skill cannot silently widen its declared authority boundary."""
    messages: list[str] = []
    permissions = require_mapping(platform.get("skill_permissions"), "skill_permissions")
    permission = require_mapping(permissions.get(skill_id), f"skill_permissions.{skill_id}")
    risks = set(registry.skills[skill_id].risk_class)

    repository = permission.get("repository")
    external = permission.get("external_actions")
    unattended = permission.get("unattended")
    merge = permission.get("merge")
    if (repository == "write") != bool({"repository-write", "merge"} & risks):
        messages.append("repository permission does not match risk_class")
    if unattended != ("unattended" in risks):
        messages.append("unattended permission does not match risk_class")
    if merge != ("merge" in risks):
        messages.append("merge permission does not match risk_class")
    if "posting" in risks and external != "write":
        messages.append("posting risk does not require external write permission")
    if external == "write" and not ({"posting", "merge", "repository-write", "unattended"} & risks):
        messages.append("external write permission has no matching risk declaration")
    return _result("batch3-negative", messages, skill=skill_id)


def _ambiguous_case(root: Path, registry: Registry, skill_id: str, composition: dict[str, Any]) -> EvalResult:
    """Verify routing/invocation metadata remains explicit under ambiguous prompts."""
    messages: list[str] = []
    entry = registry.skills[skill_id]
    if entry.invocation not in {"ambient", "automation-only"}:
        messages.append(f"unknown invocation mode {entry.invocation!r}")
    skill_types = require_mapping(composition.get("skill_types"), "skill_types")
    skill_type = skill_types.get(skill_id)
    if skill_type not in {"leaf", "router", "orchestrator", "trigger"}:
        messages.append(f"missing or invalid composition skill type {skill_type!r}")
    frontmatter = load_skill_frontmatter(root / entry.path / "SKILL.md")
    messages.extend(automation_only_guard_errors(entry.invocation, frontmatter))
    return _result("batch3-ambiguous", messages, skill=skill_id)


def _adversarial_case(root: Path, registry: Registry, skill_id: str, results: dict[str, EvalResult]) -> EvalResult:
    """Verify inherited guardrails and the per-skill adversarial baseline."""
    messages: list[str] = []
    baseline = results.get(f"{skill_id}/global-adversarial")
    if baseline is None:
        messages.append("missing global-adversarial baseline")
    elif not baseline.passed:
        messages.append("global-adversarial baseline is failing")
    frontmatter = load_skill_frontmatter(root / registry.skills[skill_id].path / "SKILL.md")
    if frontmatter.get("platform_contract") != PLATFORM_CONTRACT:
        messages.append("skill does not inherit the platform guardrail contract")
    return _result("batch3-adversarial", messages, skill=skill_id)


def _declared_capability_names(entry: Any) -> set[str]:
    names = set(entry.capabilities.required)
    names.update(optional.name for optional in entry.capabilities.optional)
    for path in entry.capabilities.any_of:
        names.update(path.required)
        names.update(optional.name for optional in path.optional)
    return names


def _degraded_case(registry: Registry, skill_id: str) -> EvalResult:
    """Verify degraded-mode declarations cannot point at imaginary capabilities."""
    entry = registry.skills[skill_id]
    declared = _declared_capability_names(entry)
    messages: list[str] = []
    for capability, behavior in sorted(entry.capabilities.degraded_modes.items()):
        if capability not in declared:
            messages.append(f"degraded mode references undeclared capability {capability!r}")
        if not isinstance(behavior, str) or not behavior.strip():
            messages.append(f"degraded mode for {capability!r} is empty")
    for path in entry.capabilities.any_of:
        if not path.required:
            messages.append(f"capability path {path.name!r} has no required capability")
    return _result("batch3-degraded", messages, skill=skill_id)


def _all_skill_dimensions(
    root: Path,
    registry: Registry,
    results: dict[str, EvalResult],
) -> list[EvalResult]:
    platform = _platform_data(root)
    composition = _composition_data(root)
    output: list[EvalResult] = []
    for skill_id in sorted(registry.skills):
        output.extend(
            [
                _positive_case(skill_id, results),
                _negative_case(registry, skill_id, platform),
                _ambiguous_case(root, registry, skill_id, composition),
                _adversarial_case(root, registry, skill_id, results),
                _degraded_case(registry, skill_id),
            ],
        )
    return output


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
    """Require the ten item-24 behavior scenarios to be executable and passing."""
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
            "adversarial_matrix": "platform/adversarial-class-",
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


def _referenced_matrix(
    root: Path,
    results: dict[str, EvalResult],
    *,
    key: str,
    case_id: str,
    require_mutation: bool = False,
) -> EvalResult:
    contract = _eval_contract(root)
    matrix = require_mapping(contract.get(key), key)
    messages: list[str] = []
    seen_mutations: set[str] = set()
    for item_id, raw in sorted(matrix.items()):
        config = require_mapping(raw, f"{key}.{item_id}")
        if require_mutation:
            mutation = config.get("mutation")
            if not isinstance(mutation, str) or not mutation.strip():
                messages.append(f"{item_id}: missing mutation payload")
            else:
                normalized = mutation.strip().casefold()
                if normalized in seen_mutations:
                    messages.append(f"{item_id}: mutation payload duplicates another class")
                seen_mutations.add(normalized)
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


def _mutation_anchor_matrix(
    root: Path,
    results: dict[str, EvalResult],
    golden_cases: Iterable[GoldenCase],
) -> EvalResult:
    """Prove each mutation class is anchored to genuinely dangerous recorded input."""
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

    golden_by_ref = {f"{case.skill}/{case.case_id}": case for case in golden_cases}
    for class_id, raw in sorted(anchors.items()):
        config = require_mapping(raw, f"mutation anchors.{class_id}")
        case_ref = config.get("case_ref")
        raw_pattern = config.get("raw_pattern")
        if not isinstance(case_ref, str) or not case_ref:
            messages.append(f"{class_id}: case_ref is required")
            continue
        if not isinstance(raw_pattern, str) or not raw_pattern:
            messages.append(f"{class_id}: raw_pattern is required")
            continue
        result = results.get(case_ref)
        if result is None:
            messages.append(f"{class_id}: anchored eval result is missing: {case_ref}")
            continue
        if not result.passed:
            messages.append(f"{class_id}: anchored eval result is failing: {case_ref}")
        fixture = golden_by_ref.get(case_ref)
        if fixture is None:
            messages.append(f"{class_id}: anchor must reference a golden fixture: {case_ref}")
            continue
        try:
            recorded = json.dumps(fixture.recorded_output, sort_keys=True)
            if not re.search(raw_pattern, recorded, flags=re.IGNORECASE | re.MULTILINE):
                messages.append(
                    f"{class_id}: recorded_output does not contain dangerous raw pattern {raw_pattern!r}",
                )
        except re.error as exc:
            messages.append(f"{class_id}: invalid raw_pattern {raw_pattern!r}: {exc}")
    return _result("mutation-anchor-matrix", messages)


def _routing_matrix(root: Path, results: dict[str, EvalResult]) -> EvalResult:
    contract = _eval_contract(root)
    collisions = contract.get("routing_collisions")
    messages: list[str] = []
    if not isinstance(collisions, list) or not collisions:
        return _result("routing-collision-suite", ["routing_collisions must be non-empty"])
    for raw in collisions:
        if not isinstance(raw, dict):
            messages.append("routing collision entry must be a mapping")
            continue
        collision_id = str(raw.get("id", ""))
        ref = f"platform/routing-{collision_id}"
        result = results.get(ref)
        if result is None:
            messages.append(f"missing routing collision result {ref}")
        elif not result.passed:
            messages.append(f"routing collision is failing: {collision_id}")
    return _result("routing-collision-suite", messages)


def run_batch3_contract_checks(
    root: Path,
    registry: Registry,
    *,
    case_results: Iterable[EvalResult],
    golden_cases: Iterable[GoldenCase],
) -> list[EvalResult]:
    """Run Batch 3 completeness checks after the existing deterministic harness."""
    result_map = _result_map(case_results)
    golden_list = list(golden_cases)
    return [
        *_all_skill_dimensions(root, registry, result_map),
        _all_skill_golden(registry, result_map, golden_list),
        _behavior_scenario_matrix(root, result_map),
        _routing_matrix(root, result_map),
        _referenced_matrix(
            root,
            result_map,
            key="adversarial_classes",
            case_id="mutation-matrix",
            require_mutation=True,
        ),
        _mutation_anchor_matrix(root, result_map, golden_list),
        _referenced_matrix(
            root,
            result_map,
            key="untrusted_surfaces",
            case_id="untrusted-surface-matrix",
        ),
        _referenced_matrix(
            root,
            result_map,
            key="degraded_host_cases",
            case_id="degraded-host-matrix",
        ),
    ]
