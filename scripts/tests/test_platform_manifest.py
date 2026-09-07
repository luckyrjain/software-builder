from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry.manifest import (
    _load_platform_contracts,
    _normalize_version,
    build_manifest,
    validate_manifest,
)
from scripts.registry.schema import clear_registry_cache, parse_registry

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
  required_fields: [required_artifacts, required_checks, completed_checks, blocked_conditions, partial_result_behavior]
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
        "completed_checks",
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
        "integrated_revision",
        "assessment_target",
        "normalized_decision",
        "findings",
        "conditions",
        "required_actions",
        "evidence_refs",
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
    with pytest.raises(ValueError, match="semantic version"):
        _normalize_version("0.0.0-0." + ("aa." * 40) + "!")


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
    assert skills["pr-review"]["version"] == "1.2.0"
    assert skills["incident-rca"]["version_source"] == "skill_frontmatter"
    assert skills["incident-rca"]["version"] == "2.0.0"


def test_manifest_rejects_missing_skill_version() -> None:
    with pytest.raises(ValueError, match="skill_version is mandatory"):
        _normalize_version(None)
    with pytest.raises(ValueError, match="skill_version is mandatory"):
        _normalize_version("")


def test_repository_platform_manifest_validates() -> None:
    assert validate_manifest(ROOT) == []


def test_validate_manifest_reports_new_fragment_missing_from_composition_contracts_cleanly() -> None:
    """Regression: a skill that exists only as a fresh scripts/registry/skills.d/<id>.yaml
    fragment (i.e. `make generate` has never run since it was added -- exactly CONTRIBUTING.md's
    documented "add a fragment, then run make generate" first step for a brand-new skill) is
    already visible to load_registry_raw's fragment merge, but skills.yaml's own literal
    `contracts.composition.skills` section -- which `load_contracts` reads verbatim, not
    fragment-aware -- doesn't have an entry for it yet. `_build_manifest` used to index straight
    into that mapping (`composition[skill_id]`), so this state crashed `make generate` with an
    uncaught KeyError and a raw traceback instead of the clean, listed validation error every
    other structural gap for a new skill produces (see validate_composition_runtime's identically
    worded "composition contracts missing skills" message for the runtime-side equivalent of this
    same gap). validate_manifest must report it the same way: a clean error string, not a crash.

    Exercised directly against ROOT (same pattern as test_repository_platform_manifest_validates
    above) rather than an isolated tmp_path copy: validate_canonical_manifest also checks that
    every registered skill's real SKILL.md/reference files exist on disk and that every declared
    host is in agent-hosts.yaml, so a faithful isolated fixture would need to mirror the entire
    checked-in skill tree, not just skills.yaml -- far more than this regression needs. The
    fragment this test adds is read-only from validate_manifest's perspective (it never writes
    skills.yaml) and is always removed in `finally`, registry-cache-cleared on both sides, so no
    other test observes it."""
    fragment_path = (
        ROOT / "scripts" / "registry" / "skills.d" / "orphan-test-skill.yaml"
    )
    skill_dir = ROOT / "orphan-test-skill"
    skill_md_path = skill_dir / "SKILL.md"
    assert not fragment_path.exists(), "unexpected leftover fixture from a prior run"
    assert not skill_dir.exists(), "unexpected leftover fixture from a prior run"
    skill_dir.mkdir()
    # validate_canonical_manifest checks the entrypoint file exists and its frontmatter `name:`
    # matches the skill id *before* _build_manifest ever reaches the composition-contracts check
    # this test targets -- without a real entrypoint, validate_manifest raises on that earlier,
    # unrelated gap instead and this test would never exercise the fixed code path.
    skill_md_path.write_text(
        "---\nname: orphan-test-skill\ndescription: Regression fixture only.\n---\n\n"
        "# Orphan Test Skill\n",
        encoding="utf-8",
    )
    fragment_path.write_text(
        """
orphan-test-skill:
  path: orphan-test-skill
  category: analysis
  extends: read-only-leaf-review
  install:
    requires: []
  composition:
    escalation_targets: []
    consumes: []
  capabilities:
    required: []
    optional: []
  lint:
    skill_md_max_lines: 180
    target: orphan-test-skill
  version: 1.0.0
  type: leaf
  permissions:
    repository: read
    external_actions: read
    unattended: false
    merge: false
  output_contract:
    produces: []
    produce_fields: {}
  dependencies: []
""",
        encoding="utf-8",
    )
    clear_registry_cache()
    try:
        errors = validate_manifest(ROOT)
    finally:
        fragment_path.unlink()
        skill_md_path.unlink()
        skill_dir.rmdir()
        clear_registry_cache()

    assert errors, "a fragment missing from composition contracts must be reported, not silently pass"
    assert any(
        "composition contracts missing skills" in error and "orphan-test-skill" in error
        for error in errors
    ), errors


def test_skill_versions_does_not_hide_malformed_canonical_contracts(tmp_path: Path) -> None:
    (tmp_path / "skills.yaml").write_text(
        "schema_version: 1\nmanifest_kind: canonical\ncontracts: []\nskills: {}\n",
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
