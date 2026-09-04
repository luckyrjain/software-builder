from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[2]
SURFACES = (
    "cross_file_impact",
    "hidden_consumers",
    "schema_migration_compatibility",
    "rollout_rollback",
    "test_quality",
    "dependency_config_iac",
)


def _load_validator():
    path = ROOT / "pr-review/scripts/validate_review_coverage.py"
    spec = importlib.util.spec_from_file_location("validate_review_coverage", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(**overrides):
    value = {
        "schema_version": 1,
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "merge_base_sha": "a" * 40,
        "normalized_diff_fingerprint": "c" * 64,
        "changed_paths": ["src/a.py"],
        "generated_paths": [],
        "dependency_changes": [],
        "config_changes": [],
    }
    value.update(overrides)
    return value


def _plan(*, status="complete", mandatory=True):
    return {
        surface: {
            "triggered": True,
            "reason": "test trigger",
            "mandatory": mandatory,
            "evidence_sources": [f"diff:{surface}"],
            "status": status,
        }
        for surface in SURFACES
    }


def _evidence(identity=None, *, inspection_status="complete", inspected=None, unable=None, findings=None):
    return {
        "schema_version": 1,
        "change_identity": identity or _identity(),
        "requirements_ref": None,
        "review_mode": "normal",
        "inspection_status": inspection_status,
        "inspected_surfaces": list(SURFACES) if inspected is None else inspected,
        "unable_to_inspect": [] if unable is None else unable,
        "findings": findings or {"defect": [], "suggestion": [], "question": []},
        "generated_at": "2026-08-19T00:00:00Z",
    }


def test_complete_plan_and_evidence_validate_cleanly():
    validator = _load_validator()
    assert validator.validate_review_coverage(_plan(), _evidence(), current_identity=_identity()) == []


def test_triggered_surface_cannot_be_not_applicable():
    validator = _load_validator()
    plan = _plan()
    plan["hidden_consumers"]["status"] = "not_applicable"
    errors = validator.validate_review_coverage(plan, _evidence(), current_identity=_identity())
    assert any("hidden_consumers" in error and "not_applicable" in error for error in errors)


def test_complete_surface_requires_evidence_source():
    validator = _load_validator()
    plan = _plan()
    plan["cross_file_impact"]["evidence_sources"] = []
    errors = validator.validate_review_coverage(plan, _evidence(), current_identity=_identity())
    assert any("cross_file_impact" in error and "evidence_sources" in error for error in errors)


def test_unable_surface_requires_matching_machine_annotation():
    validator = _load_validator()
    plan = _plan(status="complete")
    plan["hidden_consumers"]["status"] = "unable"
    plan["hidden_consumers"]["evidence_sources"] = []
    evidence = _evidence(
        inspection_status="partial",
        inspected=[surface for surface in SURFACES if surface != "hidden_consumers"],
    )
    errors = validator.validate_review_coverage(plan, evidence, current_identity=_identity())
    assert any("hidden_consumers" in error and "unable_to_inspect" in error for error in errors)


def test_matching_unable_annotation_allows_partial_review():
    validator = _load_validator()
    plan = _plan(status="complete")
    plan["hidden_consumers"]["status"] = "unable"
    plan["hidden_consumers"]["evidence_sources"] = []
    unable = [{"surface": "hidden_consumers", "reason": "repo search unavailable", "mandatory": True}]
    evidence = _evidence(
        inspection_status="partial",
        inspected=[surface for surface in SURFACES if surface != "hidden_consumers"],
        unable=unable,
    )
    assert validator.validate_review_coverage(plan, evidence, current_identity=_identity()) == []


def test_complete_envelope_rejects_pending_mandatory_surface():
    validator = _load_validator()
    plan = _plan()
    plan["schema_migration_compatibility"]["status"] = "pending"
    plan["schema_migration_compatibility"]["evidence_sources"] = []
    errors = validator.validate_review_coverage(plan, _evidence(), current_identity=_identity())
    assert any("pending mandatory" in error for error in errors)


def test_stale_shared_change_identity_is_rejected():
    validator = _load_validator()
    current = _identity(normalized_diff_fingerprint="d" * 64)
    errors = validator.validate_review_coverage(_plan(), _evidence(), current_identity=current)
    assert any("stale change_identity" in error for error in errors)


def test_unknown_surface_fails_closed():
    validator = _load_validator()
    plan = _plan()
    plan["future_surface"] = plan["cross_file_impact"].copy()
    errors = validator.validate_review_coverage(plan, _evidence(), current_identity=_identity())
    assert any("unknown inspection surfaces" in error for error in errors)


def test_duplicate_inspected_surfaces_fail_closed():
    validator = _load_validator()
    inspected = list(SURFACES) + [SURFACES[0]]
    errors = validator.validate_review_coverage(
        _plan(), _evidence(inspected=inspected), current_identity=_identity()
    )
    assert any("inspected_surfaces" in error and "duplicates" in error for error in errors)


def test_duplicate_unable_annotations_for_same_surface_fail_closed():
    validator = _load_validator()
    plan = _plan()
    plan["hidden_consumers"]["status"] = "unable"
    plan["hidden_consumers"]["evidence_sources"] = []
    unable = [
        {"surface": "hidden_consumers", "reason": "search unavailable", "mandatory": True},
        {"surface": "hidden_consumers", "reason": "graph unavailable", "mandatory": True},
    ]
    evidence = _evidence(
        inspection_status="partial",
        inspected=[surface for surface in SURFACES if surface != "hidden_consumers"],
        unable=unable,
    )
    errors = validator.validate_review_coverage(plan, evidence, current_identity=_identity())
    assert any("hidden_consumers" in error and "duplicate unable_to_inspect" in error for error in errors)


def test_partial_status_requires_at_least_one_unable_triggered_surface():
    validator = _load_validator()
    errors = validator.validate_review_coverage(
        _plan(), _evidence(inspection_status="partial"), current_identity=_identity()
    )
    assert any("inspection_status partial requires" in error for error in errors)


def test_unable_status_requires_meaningful_unavailable_surface_alignment():
    validator = _load_validator()
    plan = _plan()
    plan["hidden_consumers"]["status"] = "unable"
    plan["hidden_consumers"]["evidence_sources"] = []
    unable = [{"surface": "hidden_consumers", "reason": "search unavailable", "mandatory": True}]
    evidence = _evidence(
        inspection_status="unable",
        inspected=[surface for surface in SURFACES if surface != "hidden_consumers"],
        unable=unable,
    )
    errors = validator.validate_review_coverage(plan, evidence, current_identity=_identity())
    assert any("inspection_status unable" in error and "primary" in error for error in errors)


def test_valid_content_derived_suggestion_and_question_ids_pass():
    validator = _load_validator()
    suggestion_summary = "  Add   consumer contract test "
    suggestion_evidence = "src/a.py:12; tests/test_a.py:8"
    question_summary = "Which consumer owns this event?"
    question_evidence = "surface:hidden_consumers; reason:registry unavailable"
    suggestion_id = validator._content_finding_id("suggestion", suggestion_summary, suggestion_evidence)
    question_id = validator._content_finding_id("question", question_summary, question_evidence)
    findings = {
        "defect": [{"id": "PRR-API-001", "category": "defect", "summary": "Broken response", "evidence": "src/a.py:12"}],
        "suggestion": [{"id": suggestion_id, "category": "suggestion", "summary": suggestion_summary, "evidence": suggestion_evidence}],
        "question": [{"id": question_id, "category": "question", "summary": question_summary, "evidence": question_evidence}],
    }
    assert validator.validate_review_coverage(_plan(), _evidence(findings=findings), current_identity=_identity()) == []


def test_forged_suggestion_id_fails_closed():
    validator = _load_validator()
    findings = {
        "defect": [],
        "suggestion": [{"id": "PRS-000000000000", "category": "suggestion", "summary": "Add test", "evidence": "src/a.py:12"}],
        "question": [],
    }
    errors = validator.validate_review_coverage(_plan(), _evidence(findings=findings), current_identity=_identity())
    assert any("deterministic content id" in error for error in errors)


def test_non_prr_defect_id_fails_closed():
    validator = _load_validator()
    findings = {
        "defect": [{"id": "DEF-001", "category": "defect", "summary": "Broken", "evidence": "src/a.py:12"}],
        "suggestion": [],
        "question": [],
    }
    errors = validator.validate_review_coverage(_plan(), _evidence(findings=findings), current_identity=_identity())
    assert any("preserve PRR" in error for error in errors)
