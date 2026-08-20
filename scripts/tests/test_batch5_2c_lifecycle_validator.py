from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "loop-task-implementer/scripts/validate_loop_lifecycle.py"


def _load():
    spec = importlib.util.spec_from_file_location("loop_lifecycle", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(*, base="a" * 40, head="b" * 40, merge_base="a" * 40):
    return {
        "schema_version": 1,
        "base_sha": base,
        "head_sha": head,
        "merge_base_sha": merge_base,
        "normalized_diff_fingerprint": "c" * 64,
        "changed_paths": ["src/a.py"],
        "generated_paths": [],
        "dependency_changes": [],
        "config_changes": [],
    }


def _evidence(identity):
    return {
        "schema_version": 1,
        "change_identity": identity,
        "requirements_ref": None,
        "review_mode": "normal",
        "inspection_status": "complete",
        "inspected_surfaces": ["assigned_lens"],
        "unable_to_inspect": [],
        "findings": {"defect": [], "suggestion": [], "question": []},
        "generated_at": "2026-08-20T00:00:00Z",
    }


def _state(identity=None):
    identity = identity or _identity()
    evidence = _evidence(identity)
    return {
        "task": {"status": "READY", "requirements_ref": None},
        "workspace": {
            "current_head_commit": identity["head_sha"],
            "change_identity": identity,
            "conflict_resolution_occurred": False,
            "conflict_resolution_provenance": "provider history confirms conflict-free transition",
            "third_party_change_detected": False,
        },
        "review": {
            "lens_a": {"status": "CLEAN", "reviewed_change_identity": identity, "review_evidence": evidence},
            "lens_b": {"status": "CLEAN", "reviewed_change_identity": identity, "review_evidence": evidence},
        },
        "ci": {"commit": identity["head_sha"], "required_checks_green": True},
        "merge_readiness": {"ready": True},
    }


def test_ready_state_passes_when_both_lenses_and_ci_match_current_identity():
    errors = _load().validate_lifecycle_state(_state())
    assert errors == []


def test_ready_state_rejects_ci_green_for_old_head():
    state = _state()
    state["ci"]["commit"] = "d" * 40
    errors = _load().validate_lifecycle_state(state)
    assert any("ci.commit must equal current_head_commit" in error for error in errors)


def test_ready_state_rejects_unresolved_third_party_branch_change():
    state = _state()
    state["workspace"]["third_party_change_detected"] = True
    errors = _load().validate_lifecycle_state(state)
    assert any("third_party_change_detected blocks lifecycle readiness" in error for error in errors)


def test_ready_state_rejects_missing_requirements_ref_state():
    state = _state()
    del state["task"]["requirements_ref"]
    errors = _load().validate_lifecycle_state(state)
    assert any("task.requirements_ref must be present" in error for error in errors)


def test_ready_state_rejects_unknown_third_party_change_state():
    state = _state()
    del state["workspace"]["third_party_change_detected"]
    errors = _load().validate_lifecycle_state(state)
    assert any("third_party_change_detected must be an explicit boolean" in error for error in errors)
    assert any("ready cannot be true unless third_party_change_detected is explicitly false" in error for error in errors)


def test_sha_transition_with_unknown_conflict_status_fails_closed():
    reviewed = _identity()
    current = _identity(base="d" * 40, merge_base="d" * 40)
    state = _state(current)
    state["workspace"]["conflict_resolution_occurred"] = None
    state["workspace"]["conflict_resolution_provenance"] = None
    state["review"]["lens_a"]["reviewed_change_identity"] = reviewed
    state["review"]["lens_a"]["review_evidence"] = _evidence(reviewed)
    state["review"]["lens_b"]["reviewed_change_identity"] = reviewed
    state["review"]["lens_b"]["review_evidence"] = _evidence(reviewed)
    errors = _load().validate_lifecycle_state(state)
    assert sum("conflict_resolution_occurred is unknown" in error for error in errors) == 2


def test_sha_transition_requires_provenance_even_when_no_conflict_occurred():
    reviewed = _identity()
    current = _identity(base="d" * 40, merge_base="d" * 40)
    state = _state(current)
    state["workspace"]["conflict_resolution_occurred"] = False
    state["workspace"]["conflict_resolution_provenance"] = None
    for lens in ("lens_a", "lens_b"):
        state["review"][lens]["reviewed_change_identity"] = reviewed
        state["review"][lens]["review_evidence"] = _evidence(reviewed)
    errors = _load().validate_lifecycle_state(state)
    assert sum("identity SHA transition requires conflict_resolution_provenance" in error for error in errors) == 2


def test_fresh_evidence_after_prior_conflict_is_not_permanently_invalidated():
    state = _state()
    state["workspace"]["conflict_resolution_occurred"] = True
    state["workspace"]["conflict_resolution_provenance"] = "merge conflict resolved before both lenses reran"
    errors = _load().validate_lifecycle_state(state)
    assert errors == []
