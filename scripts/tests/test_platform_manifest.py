from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry.manifest import (
    _load_platform_contracts,
    _normalize_version,
    build_manifest,
    validate_manifest,
)
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]

_VALID_PLATFORM_CONTRACTS = """
schema_version: 1
evidence:
  statuses: [OBSERVED, INFERRED, UNKNOWN, CONFLICTED, NOT_APPLICABLE]
  required_fields: [claim, status, provenance, limitations]
  insufficient_evidence_status: UNKNOWN
  conflicting_evidence_status: CONFLICTED
completion:
  statuses: [SUCCESS, PARTIAL, BLOCKED, FAILED, ESCALATED]
  required_fields: [status, evidence_status, blockers, artifacts, recommended_next_skill]
action_gates:
  read_only: none
  local_reversible_write: explicit_task_authorization
  remote_non_destructive_write: explicit_task_authorization
  destructive_or_high_impact: explicit_action_authorization
definition_of_done:
  required_fields: [required_artifacts, required_checks, blocked_conditions, partial_result_behavior]
skill_types:
  demo: leaf
"""


def test_build_manifest_covers_registered_skills() -> None:
    manifest = build_manifest(ROOT)
    registry = parse_registry(ROOT / "skills.yaml")

    assert manifest["manifest_schema_version"] == 1
    assert set(manifest["skills"]) == set(registry.skills)
    assert manifest["skills"]["test-writer"]["type"] == "router"
    assert manifest["skills"]["pr-gatekeeper"]["type"] == "trigger"
    assert manifest["skills"]["loop-task-implementer"]["type"] == "orchestrator"
    assert manifest["skills"]["pr-review"]["type"] == "leaf"


def test_manifest_exposes_shared_contracts() -> None:
    contracts = build_manifest(ROOT)["contracts"]
    assert set(contracts["evidence"]["statuses"]) == {
        "OBSERVED",
        "INFERRED",
        "UNKNOWN",
        "CONFLICTED",
        "NOT_APPLICABLE",
    }
    assert set(contracts["evidence"]["required_fields"]) == {
        "claim",
        "status",
        "provenance",
        "limitations",
    }
    assert contracts["evidence"]["insufficient_evidence_status"] == "UNKNOWN"
    assert set(contracts["completion"]["statuses"]) == {
        "SUCCESS",
        "PARTIAL",
        "BLOCKED",
        "FAILED",
        "ESCALATED",
    }
    assert contracts["action_gates"]["destructive_or_high_impact"] == "explicit_action_authorization"
    assert set(contracts["definition_of_done"]["required_fields"]) == {
        "required_artifacts",
        "required_checks",
        "blocked_conditions",
        "partial_result_behavior",
    }


def test_manifest_reuses_write_authority_and_artifact_contracts() -> None:
    skills = build_manifest(ROOT)["skills"]
    assert skills["pr-review"]["authority"] == "comment"
    assert skills["incident-rca"]["authority"] == "read-only"
    assert skills["loop-task-implementer"]["authority"] == "repository-write"

    assert skills["pr-review"]["artifacts"]["produces"] == ["mr_review_report"]
    assert skills["pr-review"]["artifacts"]["consumes"] == ["mr_context"]
    assert skills["pr-review"]["artifacts"]["produce_fields"]["mr_review_report"] == [
        "review_metadata",
        "posted",
        "head_sha",
        "posting_mode",
    ]
    assert "implementation_task" in skills["loop-task-implementer"]["artifacts"]["consumes"]


def test_manifest_preserves_capability_semantics() -> None:
    capabilities = build_manifest(ROOT)["skills"]["k8s-overprovisioning-datadog"]["capabilities"]
    path_names = {path["name"] for path in capabilities["any_of"]}
    assert path_names == {"Kubernetes history-capable evidence", "Datadog historical evidence"}
    kubernetes_path = next(
        path for path in capabilities["any_of"] if path["name"] == "Kubernetes history-capable evidence"
    )
    assert kubernetes_path["required"] == ["kubernetes.metrics.history"]
    assert capabilities["degraded_modes"]["datadog.query_metrics"] == (
        "continue only when Kubernetes exposes equivalent historical metrics and aggregation"
    )


def test_skill_versions_are_normalized_to_semver() -> None:
    assert _normalize_version(2) == "2.0.0"
    assert _normalize_version("1.1") == "1.1.0"
    assert _normalize_version("3.5.0") == "3.5.0"
    assert _normalize_version("1.2.3-alpha.1+build.5") == "1.2.3-alpha.1+build.5"
    with pytest.raises(ValueError, match="semantic version"):
        _normalize_version("v3")
    with pytest.raises(ValueError, match="semantic version string or integer major"):
        _normalize_version(1.10)
    with pytest.raises(ValueError, match="semantic version string or integer major"):
        _normalize_version(True)
    with pytest.raises(ValueError, match="semantic version"):
        _normalize_version("01.2.3")
    with pytest.raises(ValueError, match="semantic version"):
        _normalize_version("1.2.3-01")


def test_platform_contracts_reject_duplicate_canonical_values(tmp_path: Path) -> None:
    path = tmp_path / "platform_contracts.yaml"
    path.write_text(
        _VALID_PLATFORM_CONTRACTS.replace(
            "statuses: [OBSERVED, INFERRED, UNKNOWN, CONFLICTED, NOT_APPLICABLE]",
            "statuses: [OBSERVED, INFERRED, UNKNOWN, CONFLICTED, NOT_APPLICABLE, UNKNOWN]",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exactly once"):
        _load_platform_contracts(path)


def test_platform_contracts_reject_non_scalar_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "platform_contracts.yaml"
    path.write_text(
        _VALID_PLATFORM_CONTRACTS.replace("schema_version: 1", "schema_version: [1]", 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema_version must be an integer"):
        _load_platform_contracts(path)


def test_manifest_marks_explicit_version_sources() -> None:
    skills = build_manifest(ROOT)["skills"]
    assert skills["pr-review"]["version_source"] == "skill_frontmatter_legacy_numeric"
    assert skills["pr-review"]["version"] == "1.1.0"
    assert skills["incident-rca"]["version_source"] == "skill_frontmatter"
    assert skills["incident-rca"]["version"] == "2.0.0"


def test_manifest_rejects_missing_skill_version() -> None:
    with pytest.raises(ValueError, match="skill_version is mandatory"):
        _normalize_version(None)
    with pytest.raises(ValueError, match="skill_version is mandatory"):
        _normalize_version("")


def test_repository_platform_manifest_validates() -> None:
    assert validate_manifest(ROOT) == []


def test_skill_versions_does_not_hide_malformed_canonical_contracts(tmp_path: Path) -> None:
    (tmp_path / "skills.yaml").write_text(
        "schema_version: 1\ncontracts: []\nskills: {}\n",
        encoding="utf-8",
    )

    from scripts.registry.manifest import skill_versions

    with pytest.raises(ValueError, match="canonical manifest.contracts"):
        skill_versions(tmp_path)


def test_registry_rejects_non_string_skill_ids(tmp_path: Path) -> None:
    (tmp_path / "skills.yaml").write_text(
        "schema_version: 1\nskills:\n  123: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="skill id must be a string"):
        parse_registry(tmp_path / "skills.yaml")
