from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry.manifest import _normalize_version, build_manifest, validate_manifest
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


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
    assert path_names == {"Kubernetes historical metrics", "Datadog historical metrics"}
    assert capabilities["degraded_modes"]["datadog.query_metrics"] == (
        "continue with equivalent Kubernetes historical metrics when available"
    )


def test_skill_versions_are_normalized_to_semver() -> None:
    assert _normalize_version(None) == "1.0.0"
    assert _normalize_version(2) == "2.0.0"
    assert _normalize_version(1.1) == "1.1.0"
    assert _normalize_version("3.5.0") == "3.5.0"
    with pytest.raises(ValueError, match="semantic version"):
        _normalize_version("v3")


def test_manifest_marks_implicit_and_explicit_version_sources() -> None:
    skills = build_manifest(ROOT)["skills"]
    assert skills["pr-review"]["version_source"] == "implicit_v1"
    assert skills["incident-rca"]["version_source"] == "skill_frontmatter"
    assert skills["incident-rca"]["version"] == "2.0.0"


def test_repository_platform_manifest_validates() -> None:
    assert validate_manifest(ROOT) == []
