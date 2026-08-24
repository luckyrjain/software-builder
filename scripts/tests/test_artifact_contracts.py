from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

import scripts.registry.artifact_contracts as artifact_contracts
from scripts.registry.artifact_contracts import (
    validate_artifact_contracts,
    validate_artifact_result,
)


ROOT = Path(__file__).resolve().parents[2]


def _valid_result() -> dict:
    return {
        "skill_result": {
            "skill": "pr-review",
            "version": "1.1.0",
            "status": "SUCCESS",
            "confidence": "HIGH",
            "source_revision": "a" * 40,
            "evidence_status": "OBSERVED",
            "artifacts": ["mr_review_report"],
            "blockers": [],
            "recommended_next_skill": None,
            "artifact_schema_version": 1,
            "state_semantic": "current_state",
        },
        "provenance": {
            "source_revision": "a" * 40,
            "sources": ["github.pull_request"],
        },
        "freshness": {
            "observed_at": "2026-08-22T00:00:00Z",
            "source_revision": "a" * 40,
            "source_environment": "github",
        },
        "definition_of_done": {
            "required_artifacts": ["mr_review_report"],
            "required_checks": ["review_complete"],
            "completed_checks": ["review_complete"],
            "blocked_conditions": [],
            "partial_result_behavior": "return PARTIAL with blockers",
        },
        "authority": {
            "write_authority": "comment",
            "canonical_owner": "pr-review",
        },
        "payload": {
            "review_metadata": {},
            "posted": False,
            "head_sha": "a" * 40,
            "posting_mode": "chat-only",
        },
    }


def _validate(result: object, artifact_type: str = "mr_review_report", producer_skill: str = "pr-review") -> list[str]:
    return validate_artifact_result(ROOT, artifact_type, result, producer_skill=producer_skill)


def test_every_durable_artifact_has_one_runtime_contract() -> None:
    assert validate_artifact_contracts(ROOT) == []


def test_valid_durable_artifact_result_passes() -> None:
    assert _validate(_valid_result()) == []


def test_result_requires_trusted_producer_identity() -> None:
    result = _valid_result()

    assert any("trusted producer context" in error for error in validate_artifact_result(ROOT, "mr_review_report", result))
    assert any("does not match trusted producer" in error for error in _validate(result, producer_skill="pr-gatekeeper"))


def test_result_rejects_provenance_freshness_and_authority_drift() -> None:
    result = _valid_result()
    result["freshness"]["source_revision"] = "b" * 40
    result["authority"]["write_authority"] = "repository-write"

    errors = _validate(result)

    assert any("source revisions must match" in error for error in errors)
    assert any("write_authority" in error for error in errors)


def test_result_rejects_weakly_typed_metadata() -> None:
    result = _valid_result()
    result["skill_result"]["artifacts"] = "mr_review_report"
    result["provenance"]["sources"] = "github.pull_request"
    result["definition_of_done"]["required_checks"] = "review_complete"

    errors = _validate(result)

    assert any("result.artifacts must be a list" in error for error in errors)
    assert any("provenance.sources must be a list" in error for error in errors)
    assert any("definition_of_done.required_checks must be a list" in error for error in errors)


def test_result_rejects_payload_missing_artifact_schema_fields() -> None:
    result = _valid_result()
    del result["payload"]["head_sha"]

    errors = _validate(result)

    assert any("payload missing schema fields: head_sha" in error for error in errors)


def test_result_rejects_payload_value_type_drift() -> None:
    result = _valid_result()
    result["payload"]["posted"] = "false"

    errors = _validate(result)

    assert any("payload.posted must be boolean" in error for error in errors)


def test_result_rejects_unowned_claims_and_extra_payload_fields() -> None:
    result = _valid_result()
    result["skill_result"]["artifacts"] = ["mr_review_report", "rca_report"]
    result["payload"]["uncontracted"] = "ignored"

    errors = _validate(result)

    assert any("not all produced by the skill" in error for error in errors)
    assert any("payload contains undeclared fields" in error for error in errors)


def test_blocked_result_may_have_empty_payload() -> None:
    result = _valid_result()
    result["skill_result"].update(status="BLOCKED", blockers=["missing capability"])
    result["payload"] = {}

    assert _validate(result) == []


def test_result_rejects_malformed_enum_and_timestamp_values() -> None:
    result = _valid_result()
    result["skill_result"]["status"] = []
    result["freshness"]["observed_at"] = "2026-08-22"

    errors = _validate(result)

    assert any("invalid result.status" in error for error in errors)
    assert any("ISO-8601 datetime with timezone" in error for error in errors)


def test_result_rejects_unknown_or_duplicate_artifact_ids_and_next_skill() -> None:
    result = _valid_result()
    result["skill_result"]["artifacts"] = ["mr_review_report", "mr_review_report", "forged_artifact"]
    result["skill_result"]["recommended_next_skill"] = "not-registered"

    errors = _validate(result)

    assert any("must not contain duplicates" in error for error in errors)
    assert any("contains unknown types" in error for error in errors)
    assert any("recommended_next_skill must be a registered skill" in error for error in errors)


def test_result_rejects_unknown_dod_artifacts() -> None:
    result = _valid_result()
    result["definition_of_done"]["required_artifacts"] = ["mr_review_report", "forged_artifact"]

    errors = _validate(result)

    assert any("required_artifacts contains unknown types" in error for error in errors)


def test_unknown_provenance_is_allowed_for_unknown_evidence() -> None:
    result = _valid_result()
    result["skill_result"]["source_revision"] = None
    result["skill_result"]["confidence"] = "UNKNOWN"
    result["skill_result"]["evidence_status"] = "UNKNOWN"
    result["provenance"]["source_revision"] = None
    result["provenance"]["sources"] = []
    result["freshness"] = {
        "observed_at": None,
        "source_revision": None,
        "source_environment": None,
    }

    assert _validate(result) == []


def test_delegated_producer_uses_its_declared_partial_payload() -> None:
    result = _valid_result()
    result["skill_result"].update(skill="pr-gatekeeper", version="1.0.0")
    result["authority"]["canonical_owner"] = "pr-review"
    result["payload"] = {"review_metadata": {}, "posted": False, "head_sha": "a" * 40}

    assert _validate(result, producer_skill="pr-gatekeeper") == []


def test_same_major_producer_version_remains_readable() -> None:
    result = _valid_result()
    result["skill_result"]["version"] = "1.0.0"

    assert _validate(result) == []


def test_external_inputs_are_not_durable_results() -> None:
    errors = _validate(_valid_result(), artifact_type="mr_context")

    assert any("external input" in error for error in errors)


def test_cli_validates_a_runtime_result_file(tmp_path: Path) -> None:
    from scripts.registry.cli import cmd_validate_artifact

    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(_valid_result()), encoding="utf-8")

    assert cmd_validate_artifact(ROOT, "mr_review_report", result_path, "pr-review") == 0


def test_allowed_state_semantics_accepts_declared_alternate_state(monkeypatch) -> None:
    manifest = artifact_contracts.load_canonical_manifest(ROOT)
    runtime = manifest["contracts"]["platform"]["artifact_runtime"]
    runtime["allowed_state_semantics"] = {"mr_review_report": ["current_state", "proposed_state"]}
    monkeypatch.setattr(artifact_contracts, "load_canonical_manifest", lambda _root: manifest)
    result = _valid_result()
    result["skill_result"]["state_semantic"] = "proposed_state"
    assert _validate(result) == []


def test_artifact_without_allowed_set_remains_exact() -> None:
    result = _valid_result()
    result["skill_result"]["state_semantic"] = "proposed_state"
    errors = _validate(result)
    assert any("state semantic" in error for error in errors)


def test_catalog_rejects_scalar_ownership_without_traceback(tmp_path: Path) -> None:
    shutil.copy2(ROOT / "skills.yaml", tmp_path / "skills.yaml")
    manifest = yaml.safe_load((tmp_path / "skills.yaml").read_text(encoding="utf-8"))
    manifest["contracts"]["composition_runtime"]["artifact_ownership"]["mr_review_report"]["owners"] = 1
    (tmp_path / "skills.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    errors = validate_artifact_contracts(tmp_path)

    assert any("ownership must declare owners" in error for error in errors)
