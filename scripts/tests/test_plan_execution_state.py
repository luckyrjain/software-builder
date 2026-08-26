from __future__ import annotations

from copy import deepcopy

from scripts.implementation_plan import (
    advance_plan_execution_state,
    canonical_plan_digest,
    derive_plan_id,
    execution_branch_name,
    execution_identity,
    handle_push_collision,
    initial_plan_execution_state,
    merge_plan_state,
    normalize_input,
    normalize_plan_task,
    prepare_remote_write,
    reconcile_plan_execution_state,
    reconcile_plan_state,
    reconcile_remote_claim,
    select_eligible_task,
    select_task,
    task_contract_digest,
    validate_plan_execution_state,
)


def _task(task_id: str, dependencies: list[str] | None = None, target_paths: list[str] | None = None) -> dict[str, object]:
    return {
        "task_id": task_id,
        "title": f"Implement {task_id}",
        "task_type": "code",
        "executor": "loop-task-implementer",
        "scope": "Implement the bounded task.",
        "target_paths": target_paths or ["src/checkout.py"],
        "acceptance_criteria": ["The task behavior is implemented."],
        "dependencies": dependencies or [],
        "required_tests": ["pytest -q tests/test_checkout.py"],
        "verification": ["Run the focused test command."],
        "rollout_notes": ["Deploy behind the existing release gate."],
        "completion_evidence": ["Focused test output and review evidence."],
        "source_condition_refs": ["condition:timeout-budget"],
        "source_action_refs": ["action:implement-timeout"],
        "estimated_scope": {
            "estimate_known": True,
            "files_upper_bound": 1,
            "changed_lines_upper_bound": 50,
            "confidence": "HIGH",
        },
    }


def _plan() -> dict[str, object]:
    plan_set_id = "PLANSET-123456789abc"
    target_repo = "https://github.com/acme/checkout"
    return {
        "plan_set_id": plan_set_id,
        "plan_id": derive_plan_id(plan_set_id, target_repo),
        "title": "Checkout resilience implementation",
        "readiness": "READY",
        "assessment_target": {"repo": "github.com/acme/checkout"},
        "target_repo": target_repo,
        "external_dependencies": [],
        "source_refs": ["change-impact:abc", "system-design:def", "architecture:ghi"],
        "tasks": [_task("TASK-001"), _task("TASK-002", ["TASK-001"])],
        "execution_waves": [["TASK-001"], ["TASK-002"]],
        "sequencing_constraints": ["Run TASK-001 before TASK-002."],
        "verification_gates": ["All required tests pass."],
        "traceability": {
            "condition_coverage": {"condition:timeout-budget": ["TASK-001"]},
            "action_coverage": {"action:implement-timeout": ["TASK-001"]},
            "required_test_coverage": {"pytest -q tests/test_checkout.py": ["TASK-001"]},
        },
    }


# -- plan_execution_state validation and reconciliation (Task 5) ------------------------------


def test_execution_state_requires_plan_digest_and_monotonic_generation() -> None:
    plan = _plan()
    state = {
        "schema_version": 1,
        "plan_id": plan["plan_id"],
        "plan_digest": canonical_plan_digest(plan),
        "target_repo": plan["target_repo"],
        "state_generation": 2,
        "current_task_id": "TASK-001",
        "task_statuses": {"TASK-001": "IN_PROGRESS", "TASK-002": "PENDING"},
        "completed_evidence_refs": [],
        "observed_head_revision": "a" * 40,
        "blocked_reason": None,
        "updated_at": "2026-08-26T00:00:00Z",
    }
    assert validate_plan_execution_state(state, plan, current_head="a" * 40) == []
    state["plan_digest"] = "b" * 64
    assert any("plan_digest" in error for error in validate_plan_execution_state(state, plan, current_head="a" * 40))


def test_execution_state_blocks_stale_head_and_generation() -> None:
    plan = _plan()
    state = {
        "schema_version": 1,
        "plan_id": plan["plan_id"],
        "plan_digest": canonical_plan_digest(plan),
        "target_repo": plan["target_repo"],
        "state_generation": 0,
        "current_task_id": None,
        "task_statuses": {"TASK-001": "PENDING", "TASK-002": "PENDING"},
        "completed_evidence_refs": [],
        "observed_head_revision": "a" * 40,
        "blocked_reason": None,
        "updated_at": "2026-08-26T00:00:00Z",
    }
    errors = validate_plan_execution_state(state, plan, current_head="b" * 40, minimum_generation=1)
    assert any("generation" in error for error in errors)
    assert any("head" in error for error in errors)


def test_in_progress_task_without_matching_current_task_id_is_rejected() -> None:
    plan = _plan()
    state = {
        "schema_version": 1,
        "plan_id": plan["plan_id"],
        "plan_digest": canonical_plan_digest(plan),
        "target_repo": plan["target_repo"],
        "state_generation": 0,
        "current_task_id": None,
        "task_statuses": {"TASK-001": "IN_PROGRESS", "TASK-002": "PENDING"},
        "completed_evidence_refs": [],
        "observed_head_revision": "a" * 40,
        "blocked_reason": None,
        "updated_at": "2026-08-26T00:00:00Z",
    }
    errors = validate_plan_execution_state(state, plan, current_head="a" * 40)
    assert any("current_task_id must be the IN_PROGRESS task" in error for error in errors)


def test_malformed_execution_state_fails_closed_without_raising() -> None:
    plan = _plan()
    state = initial_plan_execution_state(plan, current_head="a" * 40, updated_at="2026-08-26T00:00:00Z")
    state["task_statuses"]["TASK-001"] = []
    errors = validate_plan_execution_state(state, plan, current_head="a" * 40)
    assert errors


def test_execution_state_reconciles_to_authoritative_task_statuses() -> None:
    plan = _plan()
    state = initial_plan_execution_state(plan, current_head="a" * 40, updated_at="2026-08-26T00:00:00Z")
    reconciled, errors = reconcile_plan_execution_state(
        state,
        plan,
        authoritative_task_statuses={"TASK-001": "COMPLETE", "TASK-002": "NOT_STARTED"},
        current_head="a" * 40,
        completed_evidence_refs=["ci:task-001", "ci:task-001"],
    )
    assert errors == []
    assert reconciled is not None
    assert reconciled["task_statuses"] == {"TASK-001": "COMPLETE", "TASK-002": "PENDING"}
    assert reconciled["completed_evidence_refs"] == ["ci:task-001"]


def test_execution_state_cannot_launder_caller_complete_status() -> None:
    plan = _plan()
    state = initial_plan_execution_state(plan, current_head="a" * 40, updated_at="2026-08-26T00:00:00Z")
    state["task_statuses"]["TASK-001"] = "COMPLETE"
    reconciled, errors = reconcile_plan_execution_state(
        state,
        plan,
        authoritative_task_statuses={"TASK-001": "NOT_STARTED", "TASK-002": "NOT_STARTED"},
        current_head="a" * 40,
    )
    assert errors == []
    assert reconciled is not None
    assert reconciled["task_statuses"]["TASK-001"] == "PENDING"


def test_execution_state_compare_and_swap_rejects_stale_writer() -> None:
    plan = _plan()
    state = initial_plan_execution_state(plan, current_head="a" * 40, updated_at="2026-08-26T00:00:00Z")
    advanced, errors = advance_plan_execution_state(
        state,
        plan,
        expected_generation=0,
        authoritative_task_statuses={"TASK-001": "BUILDING", "TASK-002": "NOT_STARTED"},
        current_head="a" * 40,
        updated_at="2026-08-26T00:01:00Z",
    )
    assert errors == []
    assert advanced is not None and advanced["state_generation"] == 1
    _, newer_errors = advance_plan_execution_state(
        advanced,
        plan,
        expected_generation=0,
        authoritative_task_statuses={"TASK-001": "COMPLETE", "TASK-002": "NOT_STARTED"},
        current_head="a" * 40,
        updated_at="2026-08-26T00:03:00Z",
    )
    assert any("compare-and-swap" in error for error in newer_errors)


def test_plan_digest_mismatch_blocks_resume() -> None:
    result = reconcile_plan_state(plan_digest="a" * 64, state={"plan_digest": "b" * 64})
    assert result["status"] == "BLOCKED"


def test_plan_digest_match_is_ready() -> None:
    result = reconcile_plan_state(plan_digest="a" * 64, state={"plan_digest": "a" * 64})
    assert result["status"] == "READY"


def test_stale_state_generation_cannot_overwrite_newer_state() -> None:
    current = {"state_generation": 4}
    incoming = {"state_generation": 3}
    assert merge_plan_state(current, incoming) == current


def test_newer_state_generation_replaces_current_state() -> None:
    current = {"state_generation": 1}
    incoming = {"state_generation": 2}
    assert merge_plan_state(current, incoming) == incoming


def test_head_drift_forces_revalidation() -> None:
    plan = _plan()
    state = initial_plan_execution_state(plan, current_head="a" * 40, updated_at="2026-08-26T00:00:00Z")
    errors = validate_plan_execution_state(state, plan, current_head="b" * 40)
    assert any("head" in error for error in errors)


# -- earliest-eligible-task selection (Task 6) -------------------------------------------------


def _official_state(**overrides: str) -> dict[str, str]:
    state = {task["task_id"]: "NOT_STARTED" for task in _plan()["tasks"]}
    state.update(overrides)
    return state


def test_earliest_dependency_satisfied_task_is_selected_by_id() -> None:
    plan = _plan()
    assert select_eligible_task(plan, _official_state()) == "TASK-001"
    assert select_eligible_task(plan, _official_state(**{"TASK-001": "COMPLETE"})) == "TASK-002"


def test_caller_claimed_complete_status_cannot_promote_selection_without_authority() -> None:
    plan = _plan()
    # No authoritative evidence at all: everything defaults to PENDING/NOT_STARTED, so the
    # earliest task is selected regardless of what a caller's own unverified state might claim.
    assert select_eligible_task(plan) == "TASK-001"
    # An authoritative map that omits a task, or names an invalid status, fails closed rather
    # than falling back to trusting whatever the caller separately asserted about that task.
    result = select_task(plan, authoritative_task_statuses={"TASK-001": "COMPLETE"})
    assert result["status"] == "BLOCKED"
    result = select_task(plan, authoritative_task_statuses=_official_state(**{"TASK-001": "not-a-real-status"}))
    assert result["status"] == "BLOCKED"


def test_existing_active_branch_or_pr_blocks_duplicate_dispatch() -> None:
    plan = _plan()
    result = select_task(
        plan,
        authoritative_task_statuses=_official_state(),
        scm_evidence={"TASK-001": {"active_pr": 42}},
    )
    assert result["status"] == "BLOCKED"
    assert result["task"] is None


def test_stale_remaining_task_blocks_and_requests_replan() -> None:
    plan = _plan()
    plan["tasks"][0]["target_paths"] = ["src/removed.py"]
    result = select_task(
        plan,
        authoritative_task_statuses=_official_state(),
        repository_snapshot={"paths": ["src/new.py"]},
    )
    assert result["status"] == "BLOCKED"
    assert "replan" in result["reason"].lower()


def test_select_task_returns_ready_task_when_ungated() -> None:
    plan = _plan()
    result = select_task(plan, authoritative_task_statuses=_official_state())
    assert result["status"] == "READY"
    assert result["task"]["task_id"] == "TASK-001"


# -- legacy/plan input normalization (Task 6) --------------------------------------------------


def test_legacy_task_normalization_is_unchanged() -> None:
    raw = {"implementation_task": {"scope": "fix the retry budget"}, "repo_root": "/repo"}
    assert normalize_input(raw) == raw


def test_non_ready_plan_input_blocks_before_normalization() -> None:
    plan = _plan()
    plan["readiness"] = "PARTIAL"
    result = normalize_input({"implementation_plan": plan})
    assert result["status"] == "BLOCKED"


def test_plan_input_normalizes_earliest_eligible_task_and_carries_plan_context() -> None:
    plan = _plan()
    result = normalize_input({"implementation_plan": plan})
    assert result["task_id"] == "TASK-001"
    assert result["plan_context"]["plan_id"] == plan["plan_id"]
    assert result["plan_context"]["plan_digest"] == canonical_plan_digest(plan)
    assert result["plan_context"]["source_plan_task_id"] == "TASK-001"


def test_plan_input_honors_authoritative_task_statuses_not_the_raw_checkpoint() -> None:
    plan = _plan()
    # A caller-asserted checkpoint claiming TASK-001 complete is not, by itself, authority: with
    # no authoritative_task_statuses supplied, TASK-001 is still selected.
    result = normalize_input({
        "implementation_plan": plan,
        "plan_execution_state": {"task_statuses": {"TASK-001": "COMPLETE", "TASK-002": "PENDING"}},
    })
    assert result["task_id"] == "TASK-001"

    result = normalize_input({
        "implementation_plan": plan,
        "authoritative_task_statuses": _official_state(**{"TASK-001": "COMPLETE"}),
    })
    assert result["task_id"] == "TASK-002"


def test_malformed_authoritative_task_statuses_fails_closed_not_silently_ignored() -> None:
    plan = _plan()
    result = normalize_input({
        "implementation_plan": plan,
        "authoritative_task_statuses": ["not", "a", "mapping"],
    })
    assert result["status"] == "BLOCKED"


def test_plan_cannot_grant_merge_or_other_authority() -> None:
    plan = _plan()
    plan["tasks"][0]["merge"] = True
    plan["tasks"][0]["allowed_actions"] = {"merge": True}
    result = normalize_input({"implementation_plan": plan})
    assert result["status"] == "BLOCKED"

    normalized = normalize_plan_task(plan["tasks"][0], target_repo=plan["target_repo"])
    assert "merge" not in normalized
    assert "allowed_actions" not in normalized


def test_plan_execution_state_never_appears_in_normalized_output() -> None:
    plan = _plan()
    result = normalize_input({"implementation_plan": plan})
    assert "plan_execution_state" not in result


# -- collision-safe remote reconciliation (Task 5.5) --------------------------------------------


def test_task_contract_digest_changes_only_when_binding_fields_change() -> None:
    task = _task("TASK-001")
    same_task = deepcopy(task)
    same_task["title"] = "a cosmetic rename does not change the contract"
    assert task_contract_digest(task) == task_contract_digest(same_task)

    changed_task = deepcopy(task)
    changed_task["required_tests"] = ["pytest -q tests/test_other.py"]
    assert task_contract_digest(task) != task_contract_digest(changed_task)


def test_execution_identity_is_stable_and_repo_bound() -> None:
    identity = execution_identity("a" * 64, "TASK-001", "b" * 64, "github.com/acme/payments", "c" * 40)
    assert identity == execution_identity(
        plan_digest="a" * 64,
        task_id="TASK-001",
        task_digest="b" * 64,
        target_repo="github.com/acme/payments",
        base_revision="c" * 40,
    )
    scheme_identity = execution_identity("a" * 64, "TASK-001", "b" * 64, "https://github.com/acme/payments.git", "c" * 40)
    assert scheme_identity == execution_identity("a" * 64, "TASK-001", "b" * 64, "https://github.com/acme/payments", "c" * 40)


def test_base_revision_change_invalidates_remote_claim() -> None:
    a = execution_identity("a" * 64, "TASK-001", "b" * 64, "github.com/acme/payments", "c" * 40)
    b = execution_identity("a" * 64, "TASK-001", "b" * 64, "github.com/acme/payments", "d" * 40)
    assert a != b


def test_execution_branch_name_requires_a_sha256_identity() -> None:
    identity = execution_identity("a" * 64, "TASK-001", "b" * 64, "github.com/acme/payments", "c" * 40)
    branch = execution_branch_name("PLANSET-abc-123", "TASK-001", identity)
    assert branch == f"loop-plan/PLANSET-abc-123/TASK-001-{identity[:12]}"
    try:
        execution_branch_name("PLANSET-abc-123", "TASK-001", "not-a-digest")
    except ValueError:
        pass
    else:
        raise AssertionError("execution_branch_name must reject a non-SHA-256 identity")


def test_existing_peer_branch_blocks_second_remote_dispatch() -> None:
    plan = _plan()
    result = prepare_remote_write(
        plan,
        "TASK-001",
        base_revision="c" * 40,
        actor="run-a",
        observed_branch_owner="peer-run",
    )
    assert result.status == "BLOCKED"
    assert result.create_fallback_branch is False


def test_owning_actor_may_advance_its_own_deterministic_branch() -> None:
    plan = _plan()
    result = prepare_remote_write(
        plan,
        "TASK-001",
        base_revision="c" * 40,
        actor="run-a",
        observed_branch_owner="run-a",
    )
    assert result.status == "READY"
    assert result.create_fallback_branch is False


def test_unclaimed_deterministic_branch_is_ready_for_first_writer() -> None:
    plan = _plan()
    result = prepare_remote_write(
        plan,
        "TASK-001",
        base_revision="c" * 40,
        actor="run-a",
        observed_branch_owner=None,
    )
    assert result.status == "READY"
    assert result.create_fallback_branch is False


def test_non_fast_forward_peer_update_is_never_force_pushed() -> None:
    result = handle_push_collision(expected_head="a" * 40, actual_head="b" * 40)
    assert result.status == "BLOCKED"
    assert result.force_push is False


def test_fast_forward_push_is_allowed() -> None:
    result = handle_push_collision(expected_head="a" * 40, actual_head="a" * 40)
    assert result.status == "READY"
    assert result.force_push is False


def test_same_identity_existing_pr_can_be_reconciled_without_new_pr() -> None:
    identity = execution_identity(
        plan_digest="a" * 64,
        task_id="TASK-001",
        task_digest="b" * 64,
        target_repo="github.com/acme/payments",
        base_revision="c" * 40,
    )
    result = reconcile_remote_claim(
        execution_identity=identity,
        existing_pr={"number": 7, "execution_identity": identity},
    )
    assert result.reuse_existing is True
    assert result.create_new_pr is False


def test_no_existing_pr_creates_a_new_pr() -> None:
    identity = execution_identity("a" * 64, "TASK-001", "b" * 64, "github.com/acme/payments", "c" * 40)
    result = reconcile_remote_claim(execution_identity=identity, existing_pr=None)
    assert result.reuse_existing is False
    assert result.create_new_pr is True
    assert result.status == "READY"


def test_reconcile_remote_claim_never_matches_two_missing_identities() -> None:
    result = reconcile_remote_claim(execution_identity=None, existing_pr={"execution_identity": None})
    assert result.reuse_existing is False
    assert result.status == "BLOCKED"

    result = reconcile_remote_claim(execution_identity="not-a-digest", existing_pr={"execution_identity": "not-a-digest"})
    assert result.reuse_existing is False
    assert result.status == "BLOCKED"


def test_same_plan_id_but_changed_task_contract_cannot_reuse_remote_claim() -> None:
    old_identity = execution_identity(
        plan_digest="a" * 64, task_id="TASK-001", task_digest="b" * 64,
        target_repo="github.com/acme/payments", base_revision="c" * 40,
    )
    new_identity = execution_identity(
        plan_digest="d" * 64, task_id="TASK-001", task_digest="e" * 64,
        target_repo="github.com/acme/payments", base_revision="c" * 40,
    )
    result = reconcile_remote_claim(
        execution_identity=new_identity,
        existing_pr={"number": 7, "execution_identity": old_identity},
    )
    assert result.reuse_existing is False
    assert result.status == "BLOCKED"
