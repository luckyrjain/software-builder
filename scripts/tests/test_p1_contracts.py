from __future__ import annotations

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
    assert "review-bugbot" not in routing
    assert "ddsetup" not in routing
    assert "ddconfig" not in routing
