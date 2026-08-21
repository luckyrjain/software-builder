from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
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


def _lens(identity, evidence):
    return {
        "status": "CLEAN",
        "reviewed_change_identity": identity,
        "review_evidence": evidence,
        "isolation_status": "ISOLATED",
        "isolation_exception_authorized": False,
        "isolation_exception_provenance": None,
        "isolation_exception_change_identity": None,
    }


def _state(identity=None):
    identity = identity or _identity()
    evidence = _evidence(identity)
    return {
        "task": {"status": "VALIDATING", "requirements_ref": None},
        "workspace": {
            "current_head_commit": identity["head_sha"],
            "change_identity": identity,
            "conflict_resolution_occurred": False,
            "conflict_resolution_provenance": "provider history confirms conflict-free transition",
            "third_party_change_detected": False,
            "third_party_change_checked_head": identity["head_sha"],
        },
        "review": {
            "lens_a": _lens(identity, evidence),
            "lens_b": _lens(identity, evidence),
        },
        "ci": {"commit": identity["head_sha"], "required_checks_green": True},
        "merge_readiness": {
            "acceptance_criteria_complete": True,
            "accepted_blocking_findings_open": 0,
            "security_sensitive_needs_evidence_unresolved": 0,
            "required_approvals_present": True,
            "blocking_threads_open": 0,
            "integration_state_valid": True,
            "circuit_breaker_active": False,
            "ready": False,
        },
    }


def test_pre_ready_state_passes_only_when_all_lifecycle_requirements_hold():
    assert _load().validate_lifecycle_state(_state()) == []


def test_pre_ready_state_rejects_unclean_lens_and_non_green_ci():
    state = _state()
    state["review"]["lens_a"]["status"] = "NOT_RUN"
    state["ci"]["required_checks_green"] = False
    errors = _load().validate_lifecycle_state(state)
    assert any("lens_a must be CLEAN" in error for error in errors)
    assert any("required checks must be green" in error for error in errors)


def test_clean_lens_rejects_partial_or_unable_inspection_evidence():
    state = _state()
    evidence = state["review"]["lens_a"]["review_evidence"]
    evidence["inspection_status"] = "partial"
    evidence["unable_to_inspect"] = [
        {"surface": "one-hop consumer", "reason": "consumer repository unavailable", "mandatory": False}
    ]
    errors = _load().validate_lifecycle_state(state)
    assert any("CLEAN requires review_evidence.inspection_status=complete" in error for error in errors)
    assert any("CLEAN requires no unable_to_inspect surfaces" in error for error in errors)


def test_clean_lens_rejects_proposed_blocking_defect_evidence():
    state = _state()
    state["review"]["lens_a"]["review_evidence"]["findings"]["defect"] = [
        {"id": "AUTHZ-001", "category": "defect", "summary": "Authorization bypass", "evidence": "src/a.py:10"}
    ]
    errors = _load().validate_lifecycle_state(state)
    assert any("lens_a CLEAN requires zero defect findings" in error for error in errors)


def test_not_isolated_lens_requires_explicit_human_exception():
    state = _state()
    state["review"]["lens_a"]["isolation_status"] = "NOT_ISOLATED"
    errors = _load().validate_lifecycle_state(state)
    assert any("NOT_ISOLATED blocks lifecycle readiness" in error for error in errors)


def test_not_isolated_lens_can_proceed_only_with_explicit_human_exception_provenance():
    state = _state()
    lens = state["review"]["lens_a"]
    lens["isolation_status"] = "NOT_ISOLATED"
    lens["isolation_exception_authorized"] = True
    lens["isolation_exception_provenance"] = "human accepted degraded isolation in current session"
    lens["isolation_exception_change_identity"] = lens["reviewed_change_identity"]
    assert _load().validate_lifecycle_state(state) == []


def test_isolation_exception_without_provenance_fails_closed():
    state = _state()
    lens = state["review"]["lens_a"]
    lens["isolation_status"] = "NOT_ISOLATED"
    lens["isolation_exception_authorized"] = True
    lens["isolation_exception_change_identity"] = lens["reviewed_change_identity"]
    errors = _load().validate_lifecycle_state(state)
    assert any("isolation exception requires non-empty human authorization provenance" in error for error in errors)


def test_isolation_exception_authorized_requires_explicit_boolean():
    for value in (0, 1, "yes", None):
        state = _state()
        state["review"]["lens_a"]["isolation_exception_authorized"] = value
        errors = _load().validate_lifecycle_state(state)
        assert any("isolation_exception_authorized must be an explicit boolean" in error for error in errors)


def test_isolation_exception_is_bound_to_the_reviewed_change_identity():
    state = _state()
    lens = state["review"]["lens_a"]
    lens["isolation_status"] = "NOT_ISOLATED"
    lens["isolation_exception_authorized"] = True
    lens["isolation_exception_provenance"] = "human accepted degraded isolation for an earlier review"
    lens["isolation_exception_change_identity"] = _identity(head="d" * 40)
    errors = _load().validate_lifecycle_state(state)
    assert any("isolation exception must be bound to the current reviewed_change_identity" in error for error in errors)


def test_security_sensitive_needs_evidence_must_be_resolved_before_readiness():
    state = _state()
    state["merge_readiness"]["security_sensitive_needs_evidence_unresolved"] = 1
    errors = _load().validate_lifecycle_state(state)
    assert any("security_sensitive_needs_evidence_unresolved must be integer 0" in error for error in errors)


def test_pre_ready_state_rejects_existing_completion_policy_blockers():
    state = _state()
    state["merge_readiness"].update(
        acceptance_criteria_complete=False,
        accepted_blocking_findings_open=1,
        required_approvals_present=False,
        blocking_threads_open=1,
        integration_state_valid=False,
        circuit_breaker_active=True,
    )
    errors = _load().validate_lifecycle_state(state)
    for token in (
        "acceptance criteria must be complete",
        "accepted_blocking_findings_open must be integer 0",
        "required approvals must be satisfied",
        "blocking_threads_open must be integer 0",
        "integration state must be valid",
        "circuit breaker must be explicitly inactive",
    ):
        assert any(token in error for error in errors)


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


def test_ready_state_rejects_third_party_check_not_bound_to_current_head():
    state = _state()
    state["workspace"]["third_party_change_checked_head"] = "d" * 40
    errors = _load().validate_lifecycle_state(state)
    assert any("third-party branch-change evidence is stale" in error for error in errors)


def test_ready_state_rejects_missing_third_party_checked_head():
    state = _state()
    del state["workspace"]["third_party_change_checked_head"]
    errors = _load().validate_lifecycle_state(state)
    assert any("third_party_change_checked_head must be present" in error for error in errors)


def test_conflict_status_rejects_integer_boolean_aliases():
    for value in (0, 1):
        state = _state()
        state["workspace"]["conflict_resolution_occurred"] = value
        errors = _load().validate_lifecycle_state(state)
        assert any("conflict_resolution_occurred must be boolean or null" in error for error in errors)


def test_sha_transition_with_unknown_conflict_status_fails_closed():
    reviewed = _identity()
    current = _identity(base="d" * 40, merge_base="d" * 40)
    state = _state(current)
    state["workspace"]["conflict_resolution_occurred"] = None
    state["workspace"]["conflict_resolution_provenance"] = None
    for lens in ("lens_a", "lens_b"):
        state["review"][lens]["reviewed_change_identity"] = reviewed
        state["review"][lens]["review_evidence"] = _evidence(reviewed)
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
    assert _load().validate_lifecycle_state(state) == []


def test_cli_returns_zero_only_for_valid_state(tmp_path: Path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(_state()), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--state", str(state_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_cli_returns_nonzero_for_invalid_state(tmp_path: Path):
    state = _state()
    state["ci"]["required_checks_green"] = False
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--state", str(state_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "required checks must be green" in result.stderr


def test_cli_fails_closed_on_malformed_state(tmp_path: Path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{not-json", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--state", str(state_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "failed closed" in result.stderr


def test_main_classifies_unexpected_runtime_failure_as_fail_closed(tmp_path: Path, monkeypatch, capsys):
    module = _load()
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(_state()), encoding="utf-8")

    def incompatible_runtime(_state):
        raise TypeError("runtime contract incompatible")

    monkeypatch.setattr(module, "validate_lifecycle_state", incompatible_runtime)
    assert module.main(["--state", str(state_path)]) == 2
    assert "lifecycle validation failed closed: runtime contract incompatible" in capsys.readouterr().err
