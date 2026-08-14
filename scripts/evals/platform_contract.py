"""Executable checks for the shared P1 evaluation contract.

These checks keep the normative declarations in ``eval_contracts.yaml`` tied to
real deterministic eval cases and the canonical routing table. They do not
pretend to replace live/model evals; they make contract coverage and recorded
behavior drift fail ``python -m scripts.evals`` / ``make lint``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from scripts.evals.types import EvalResult
from scripts.registry.schema import Registry
from scripts.yaml_safety import load_unique_yaml_file

PLATFORM_SKILL = "platform"


def _case_refs(cases: Iterable[Any]) -> set[str]:
    return {f"{case.skill}/{case.case_id}" for case in cases}


def _result(case_id: str, messages: list[str]) -> EvalResult:
    return EvalResult(PLATFORM_SKILL, case_id, not messages, messages)


def _as_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _as_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{label} must be a non-empty list of strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must not contain duplicates")
    return value


def _routing_results(root: Path, registry: Registry, contract: dict[str, Any]) -> list[EvalResult]:
    routing_text = (root / "docs/skill-framework/shared/skill-routing.md").read_text(encoding="utf-8")
    routing_lines = routing_text.splitlines()
    raw_cases = contract.get("routing_collisions")
    if not isinstance(raw_cases, list) or not raw_cases:
        return [_result("routing-collisions", ["routing_collisions must be a non-empty list"])]

    results: list[EvalResult] = []
    seen: set[str] = set()
    for raw in raw_cases:
        messages: list[str] = []
        if not isinstance(raw, dict):
            results.append(_result("routing-invalid", ["routing collision entry must be a mapping"]))
            continue
        collision_id = str(raw.get("id", ""))
        prompt = str(raw.get("prompt", ""))
        owner = str(raw.get("expected_owner", ""))
        route_pattern = str(raw.get("route_pattern", ""))
        if not collision_id:
            collision_id = "routing-missing-id"
            messages.append("routing collision id is required")
        elif collision_id in seen:
            messages.append(f"duplicate routing collision id {collision_id!r}")
        seen.add(collision_id)
        if not prompt.strip():
            messages.append("concrete prompt is required")
        if owner not in registry.skills:
            messages.append(f"expected owner {owner!r} is not a registered skill")
        if not route_pattern:
            messages.append("route_pattern is required")
        else:
            try:
                matching_lines = [line for line in routing_lines if re.search(route_pattern, line, flags=re.IGNORECASE)]
            except re.error as exc:
                messages.append(f"invalid route_pattern {route_pattern!r}: {exc}")
                matching_lines = []
            if not matching_lines:
                messages.append(f"canonical routing table has no row matching {route_pattern!r}")
            elif not any(owner in line for line in matching_lines):
                messages.append(
                    f"canonical routing row matching {route_pattern!r} does not route to {owner!r}",
                )
        results.append(_result(f"routing-{collision_id}", messages))
    return results


def _referenced_case_results(
    contract: dict[str, Any],
    *,
    key: str,
    refs: set[str],
    case_prefix: str,
) -> list[EvalResult]:
    raw = _as_mapping(contract.get(key), key)
    results: list[EvalResult] = []
    for item_id, config_raw in sorted(raw.items()):
        messages: list[str] = []
        config = _as_mapping(config_raw, f"{key}.{item_id}")
        mutation = config.get("mutation")
        if key == "adversarial_classes" and (not isinstance(mutation, str) or not mutation.strip()):
            messages.append("mutation payload is required")
        case_refs = _as_string_list(config.get("case_refs"), f"{key}.{item_id}.case_refs")
        missing = sorted(set(case_refs) - refs)
        if missing:
            messages.append("missing referenced eval cases: " + ", ".join(missing))
        results.append(_result(f"{case_prefix}-{item_id}", messages))
    return results


def _golden_coverage_result(contract: dict[str, Any], golden_cases: Iterable[Any]) -> EvalResult:
    required = set(_as_string_list(contract.get("golden_structural_assertions"), "golden_structural_assertions"))
    covered: set[str] = set()
    for case in golden_cases:
        coverage = getattr(case, "contract_coverage", [])
        if isinstance(coverage, list):
            covered.update(str(item) for item in coverage)
    missing = sorted(required - covered)
    unknown = sorted(covered - required)
    messages: list[str] = []
    if missing:
        messages.append("golden structural requirements without executable coverage: " + ", ".join(missing))
    if unknown:
        messages.append("golden fixtures declare unknown structural coverage: " + ", ".join(unknown))
    return _result("golden-structural-coverage", messages)


def _dimension_result(contract: dict[str, Any], refs: set[str], routing_ok: bool, adversarial_ok: bool) -> EvalResult:
    required = set(_as_string_list(contract.get("required_dimensions"), "required_dimensions"))
    coverage = _as_mapping(contract.get("dimension_coverage"), "dimension_coverage")
    messages: list[str] = []
    if set(coverage) != required:
        messages.append(
            "dimension_coverage keys must exactly match required_dimensions; "
            f"missing={sorted(required - set(coverage))}, extra={sorted(set(coverage) - required)}",
        )
    for dimension, config_raw in coverage.items():
        config = _as_mapping(config_raw, f"dimension_coverage.{dimension}")
        case_refs = config.get("case_refs", [])
        if case_refs:
            refs_for_dimension = _as_string_list(case_refs, f"dimension_coverage.{dimension}.case_refs")
            missing = sorted(set(refs_for_dimension) - refs)
            if missing:
                messages.append(f"{dimension}: missing eval case refs: {', '.join(missing)}")
        contract_gate = config.get("contract_gate")
        if contract_gate == "routing_collisions" and not routing_ok:
            messages.append(f"{dimension}: routing collision gate is not passing")
        elif contract_gate == "adversarial_matrix" and not adversarial_ok:
            messages.append(f"{dimension}: adversarial matrix gate is not passing")
        elif contract_gate not in (None, "routing_collisions", "adversarial_matrix"):
            messages.append(f"{dimension}: unknown contract_gate {contract_gate!r}")
        if not case_refs and contract_gate is None:
            messages.append(f"{dimension}: requires case_refs or contract_gate")
    return _result("required-dimensions", messages)


def run_platform_contract_checks(
    root: Path,
    registry: Registry,
    *,
    fixture_cases: Iterable[Any],
    transcript_cases: Iterable[Any],
    golden_cases: Iterable[Any],
) -> list[EvalResult]:
    """Run deterministic P1 eval-contract checks as normal eval results."""
    raw = load_unique_yaml_file(root / "scripts/registry/eval_contracts.yaml")
    contract = _as_mapping(raw, "eval contracts")
    all_cases = [*fixture_cases, *transcript_cases, *golden_cases]
    refs = _case_refs(all_cases)

    routing_results = _routing_results(root, registry, contract)
    adversarial_results = _referenced_case_results(
        contract,
        key="adversarial_classes",
        refs=refs,
        case_prefix="adversarial-class",
    )
    surface_results = _referenced_case_results(
        contract,
        key="untrusted_surfaces",
        refs=refs,
        case_prefix="untrusted-surface",
    )
    degraded_results = _referenced_case_results(
        contract,
        key="degraded_host_cases",
        refs=refs,
        case_prefix="degraded-host",
    )
    golden_result = _golden_coverage_result(contract, golden_cases)

    routing_ok = all(result.passed for result in routing_results)
    adversarial_ok = all(result.passed for result in [*adversarial_results, *surface_results])
    dimension_result = _dimension_result(contract, refs, routing_ok, adversarial_ok)

    return [
        *routing_results,
        *adversarial_results,
        *surface_results,
        *degraded_results,
        golden_result,
        dimension_result,
    ]
