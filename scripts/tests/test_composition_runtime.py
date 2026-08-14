from __future__ import annotations

from pathlib import Path

import yaml

from scripts.registry.composition_runtime import (
    RUNTIME_PATH,
    handoff_allowed,
    render_dependency_graph,
    validate_composition_runtime,
)
from scripts.registry.load import load_registry

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "scripts" / "registry" / "composition_contracts.yaml"


def _runtime() -> dict:
    return yaml.safe_load(RUNTIME_PATH.read_text(encoding="utf-8"))


def _write_runtime(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "composition_runtime.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_batch2_runtime_contracts_validate_for_all_registered_skills() -> None:
    registry = load_registry(ROOT)
    assert validate_composition_runtime(registry, contracts_path=CONTRACTS) == []
    assert set(_runtime()["skill_types"]) == set(registry.skills)


def test_missing_skill_type_fails_closed(tmp_path: Path) -> None:
    registry = load_registry(ROOT)
    data = _runtime()
    data["skill_types"].pop("pr-review")
    errors = validate_composition_runtime(
        registry,
        runtime_path=_write_runtime(tmp_path, data),
        contracts_path=CONTRACTS,
    )
    assert any("missing skill types: pr-review" in error for error in errors)


def test_missing_live_handoff_contract_is_rejected(tmp_path: Path) -> None:
    registry = load_registry(ROOT)
    data = _runtime()
    del data["handoffs"]["pr-gatekeeper"]["pr-review"]
    errors = validate_composition_runtime(
        registry,
        runtime_path=_write_runtime(tmp_path, data),
        contracts_path=CONTRACTS,
    )
    assert any("pr-gatekeeper" in error and "missing handoff contract" in error for error in errors)


def test_recursion_guard_cannot_fail_open(tmp_path: Path) -> None:
    registry = load_registry(ROOT)
    data = _runtime()
    data["recursion_guard"]["default_max_depth"] = 0
    data["recursion_guard"]["block_revisit_by_default"] = False
    errors = validate_composition_runtime(
        registry,
        runtime_path=_write_runtime(tmp_path, data),
        contracts_path=CONTRACTS,
    )
    assert any("default_max_depth" in error for error in errors)
    assert any("block_revisit_by_default" in error for error in errors)


def test_executable_recursion_guard_blocks_depth_and_revisits() -> None:
    allowed, reason = handoff_allowed("pr-review", visited_skills=["release-readiness-checker"], depth=1)
    assert allowed is True and reason is None

    allowed, reason = handoff_allowed("pr-review", visited_skills=["pr-review"], depth=1)
    assert allowed is False and "already visited" in str(reason)

    allowed, reason = handoff_allowed("pr-review", visited_skills=[], depth=3)
    assert allowed is False and "maximum composition depth" in str(reason)


def test_artifact_owner_must_produce_owned_artifact(tmp_path: Path) -> None:
    registry = load_registry(ROOT)
    data = _runtime()
    data["artifact_ownership"]["prd_report"] = {"mode": "canonical", "owners": ["incident-rca"]}
    errors = validate_composition_runtime(
        registry,
        runtime_path=_write_runtime(tmp_path, data),
        contracts_path=CONTRACTS,
    )
    assert any("prd_report" in error and "does not produce artifact" in error for error in errors)


def test_canonical_artifact_requires_declared_delegated_producers(tmp_path: Path) -> None:
    registry = load_registry(ROOT)
    data = _runtime()
    data["artifact_ownership"]["mr_review_report"].pop("delegates")
    errors = validate_composition_runtime(
        registry,
        runtime_path=_write_runtime(tmp_path, data),
        contracts_path=CONTRACTS,
    )
    assert any("mr_review_report" in error and "undeclared delegated producers" in error for error in errors)


def test_dependency_graph_contains_types_handoffs_and_artifact_edges() -> None:
    registry = load_registry(ROOT)
    graph = render_dependency_graph(registry, contracts_path=CONTRACTS)
    assert 'test-writer["test-writer<br/>router"]' in graph
    assert "pr-gatekeeper ==>|handoff| pr-review" in graph
    assert "pr-review -->|mr_review_report| release-readiness-checker" in graph
