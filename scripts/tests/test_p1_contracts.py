from __future__ import annotations

import json
from pathlib import Path

from scripts.registry.p1_validation import (
    EVAL_DIMENSIONS,
    EXECUTION_FIELDS,
    HANDOFF_FIELDS,
    HOSTS,
    HOST_CAPABILITIES,
    RESULT_FIELDS,
    STATE_VALUES,
    validate_p1_contracts,
)
from scripts.registry.routing_sync import validate_skill_routing_references
from scripts.registry.schema import parse_registry
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def test_p1_contracts_validate_repository() -> None:
    assert validate_p1_contracts(ROOT) == []


def test_p1_portable_contract_sets_are_complete() -> None:
    assert RESULT_FIELDS == {
        "skill",
        "version",
        "status",
        "confidence",
        "source_revision",
        "evidence_status",
        "artifacts",
        "blockers",
        "recommended_next_skill",
        "artifact_schema_version",
        "state_semantic",
    }
    assert HANDOFF_FIELDS == {
        "target_skill",
        "reason",
        "inputs",
        "evidence_refs",
        "assumptions",
        "unresolved",
    }
    assert EXECUTION_FIELDS == {"invocation_id", "parent_skill", "visited_skills", "depth"}
    assert STATE_VALUES == {"current_state", "proposed_state", "desired_state", "transitional_state"}


def test_p1_eval_and_host_coverage_are_explicit() -> None:
    assert EVAL_DIMENSIONS == {"positive", "negative", "ambiguous", "adversarial", "degraded"}
    assert HOSTS == {"cursor", "claude", "codex", "chatgpt", "kiro", "generic"}
    assert HOST_CAPABILITIES == {
        "discover_files",
        "read_repo",
        "write_repo",
        "git",
        "scm",
        "subagents",
        "task_isolation",
        "terminal",
        "browser",
        "connectors",
    }


def test_skill_routing_inherits_p1_contracts() -> None:
    routing = (ROOT / "docs/skill-framework/shared/skill-routing.md").read_text(encoding="utf-8")
    assert "runtime-contract.md" in routing
    assert "host-adapter-contract.md" in routing
    assert "eval-contract.md" in routing


def test_skill_routing_has_no_dangling_or_missing_skill_references() -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    assert validate_skill_routing_references(ROOT, registry) == []


def test_host_packages_point_at_canonical_skill_tree() -> None:
    claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert claude["name"] == "software-builder"
    assert codex["name"] == "software-builder"
    assert codex["skills"] == "./"

    skill_ids = set(parse_registry(ROOT / "skills.yaml").skills)
    assert {path.stem for path in (ROOT / ".cursor/rules").glob("*.mdc")} == skill_ids
    assert {path.stem for path in (ROOT / ".kiro/steering").glob("*.md")} == skill_ids


def test_eval_contract_covers_required_collision_suite() -> None:
    raw = load_unique_yaml_file(ROOT / "scripts/registry/eval_contracts.yaml")
    collisions = raw["routing_collisions"]
    assert {item["id"] for item in collisions} == {
        "architecture-vs-code-review",
        "prd-vs-code-review",
        "pr-number-review",
        "prod-failure-vs-sizing",
        "resource-safety-vs-incident",
        "write-tests-vs-test-review",
        "current-state-before-change",
    }
    assert set(raw["adversarial_classes"]) == {
        "instruction_override",
        "gate_bypass",
        "security_gate_bypass",
        "confidence_forcing",
        "unauthorized_external_action",
        "merge_forcing",
    }


def test_portable_package_roots_exist() -> None:
    assert (ROOT / "skills.yaml").is_file()
    assert (ROOT / "scripts/install.sh").is_file()
    assert (ROOT / "docs/skill-framework/shared/skill-routing.md").is_file()
