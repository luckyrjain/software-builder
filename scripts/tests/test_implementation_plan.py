from __future__ import annotations

from copy import deepcopy

from scripts.implementation_plan import (
    canonical_plan_digest,
    derive_plan_id,
    derive_plan_set_id,
    advance_plan_execution_state,
    build_implementation_plan,
    execution_branch_name,
    execution_identity,
    initial_plan_execution_state,
    normalize_plan_task,
    reconcile_plan_execution_state,
    select_next_task,
    validate_external_dependency_cycles,
    validate_implementation_plan,
    validate_plan_execution_state,
)


def _task(task_id: str, dependencies: list[str] | None = None) -> dict[str, object]:
    return {
        "task_id": task_id,
        "title": f"Implement {task_id}",
        "task_type": "code",
        "executor": "loop-task-implementer",
        "scope": "Implement the bounded task.",
        "target_paths": ["src/checkout.py"],
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


def test_identity_is_deterministic_and_repository_specific() -> None:
    plan_set_id = derive_plan_set_id("a" * 64, "b" * 64, "c" * 64)
    assert plan_set_id == "PLANSET-" + __import__("hashlib").sha256(
        b'{"architecture_review_digest":"' + b"c" * 64 + b'","change_impact_digest":"' + b"a" * 64 + b'","system_design_digest":"' + b"b" * 64 + b'"}'
    ).hexdigest()[:12]
    assert derive_plan_id(plan_set_id, "https://github.com/acme/checkout") != derive_plan_id(
        plan_set_id, "https://github.com/acme/other"
    )


def test_valid_plan_passes_and_digest_is_stable() -> None:
    plan = _plan()
    assert validate_implementation_plan(plan) == []
    assert canonical_plan_digest(plan) == canonical_plan_digest(deepcopy(plan))


def test_duplicate_task_and_unknown_dependency_fail_closed() -> None:
    plan = _plan()
    plan["tasks"] = [_task("TASK-001"), _task("TASK-001", ["MISSING"])]
    plan["execution_waves"] = [["TASK-001"], ["TASK-001"]]
    errors = validate_implementation_plan(plan)
    assert any("duplicate task_id" in error for error in errors)
    assert any("unknown dependency" in error for error in errors)
    assert any("exactly once" in error for error in errors)


def test_cycle_and_invalid_wave_order_are_rejected() -> None:
    plan = _plan()
    plan["tasks"] = [_task("TASK-001", ["TASK-002"]), _task("TASK-002", ["TASK-001"])]
    plan["execution_waves"] = [["TASK-001"], ["TASK-002"]]
    errors = validate_implementation_plan(plan)
    assert any("cycle" in error for error in errors)
    assert any("earlier wave" in error for error in errors)


def test_execution_waves_reject_unknown_task_ids() -> None:
    plan = _plan()
    plan["execution_waves"] = [["TASK-001", "UNKNOWN-TASK"], ["TASK-002"]]
    assert any("unknown task" in error for error in validate_implementation_plan(plan))


def test_ready_plan_requires_traceability_for_every_required_source_item() -> None:
    plan = _plan()
    plan["traceability"] = {
        "condition_coverage": {},
        "action_coverage": {},
        "required_test_coverage": {},
    }
    errors = validate_implementation_plan(
        plan,
        source_conditions=["condition:timeout-budget"],
        source_actions=["action:implement-timeout"],
        required_tests=["pytest -q tests/test_checkout.py"],
    )
    assert sum("traceability" in error for error in errors) == 3


def test_cli_style_validation_derives_traceability_obligations_from_tasks() -> None:
    plan = _plan()
    plan["traceability"] = {
        "condition_coverage": {},
        "action_coverage": {},
        "required_test_coverage": {},
    }
    errors = validate_implementation_plan(plan)
    assert any("condition_coverage" in error for error in errors)
    assert any("action_coverage" in error for error in errors)
    assert any("required_test_coverage" in error for error in errors)


def test_malformed_task_lists_fail_closed_without_raising() -> None:
    plan = _plan()
    plan["tasks"][0]["source_condition_refs"] = None
    plan["tasks"][0]["required_tests"] = None
    errors = validate_implementation_plan(plan)
    assert any("source_condition_refs" in error for error in errors)
    assert any("required_tests" in error for error in errors)


def test_unknown_estimate_cannot_make_a_ready_plan() -> None:
    plan = _plan()
    plan["tasks"][0]["estimated_scope"] = {
        "estimate_known": False,
        "files_upper_bound": 0,
        "changed_lines_upper_bound": 0,
        "confidence": "UNKNOWN",
    }
    errors = validate_implementation_plan(plan)
    assert any("READY" in error and "estimate" in error for error in errors)


def test_oversized_task_is_rejected_for_ready_plan() -> None:
    plan = _plan()
    plan["tasks"][0]["estimated_scope"]["files_upper_bound"] = 41
    errors = validate_implementation_plan(plan)
    assert any("hard stop" in error for error in errors)


def test_source_failure_blocks_ready_but_allows_partial() -> None:
    plan = _plan()
    plan["readiness"] = "PARTIAL"
    assert validate_implementation_plan(
        plan,
        source_statuses={"system_design": "READY", "architecture": "PASS", "specialist:resilience": "UNKNOWN"},
    ) == []
    plan["readiness"] = "READY"
    errors = validate_implementation_plan(
        plan,
        source_statuses={"system_design": "READY", "architecture": "PASS", "specialist:resilience": "UNKNOWN"},
    )
    assert any("blocking source status" in error for error in errors)


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


def test_execution_identity_and_branch_are_stable_and_repo_bound() -> None:
    identity = execution_identity("PLANSET-abc-123", "TASK-001", "https://github.com/acme/checkout.git")
    assert identity == "PLANSET-abc-123:TASK-001:https://github.com/acme/checkout"
    branch = execution_branch_name("PLANSET-abc-123", "TASK-001", "https://github.com/acme/checkout.git")
    assert branch == execution_branch_name("PLANSET-abc-123", "TASK-001", "https://github.com/acme/checkout")
    assert branch.startswith("loop-plan/PLANSET-abc-123/TASK-001-")


def test_builder_blocks_when_triggered_specialist_or_paths_are_missing() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "review_triggers": ["resilience"], "target_paths": []}},
        }
    )
    assert plan["readiness"] == "BLOCKED"
    assert plan["tasks"] == []


def test_builder_uses_repository_estimate_to_produce_a_ready_plan() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"title": "Impact", "assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "required_tests": ["pytest -q tests/test_checkout.py"], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 100, "confidence": "HIGH"}},
    )
    assert plan["readiness"] == "READY"
    assert validate_implementation_plan(plan) == []


def test_select_next_task_is_earliest_dependency_satisfied_and_non_mutating() -> None:
    plan = _plan()
    task = select_next_task(plan)
    assert task is not None and task["task_id"] == "TASK-001"
    task["title"] = "caller mutation"
    assert plan["tasks"][0]["title"] != "caller mutation"
    assert select_next_task(plan, {"TASK-001": "COMPLETE", "TASK-002": "PENDING"})["task_id"] == "TASK-002"
    assert select_next_task(plan, {"TASK-001": "IN_PROGRESS", "TASK-002": "PENDING"}) is None


def test_plan_task_normalization_preserves_legacy_task_inputs() -> None:
    normalized = normalize_plan_task(_task("TASK-001"))
    assert normalized["task_id"] == "TASK-001"
    assert normalized["description"] == "Implement the bounded task."
    assert normalized["target_paths"] == ["src/checkout.py"]
    assert normalized["estimated_scope"]["estimate_known"] is True


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


def test_external_dependency_cycles_are_only_rejected_when_provable() -> None:
    plan = _plan()
    plan["target_repo"] = "github.com/acme/one"
    plan["plan_id"] = derive_plan_id(plan["plan_set_id"], plan["target_repo"])
    plan["external_dependencies"] = [{
        "repo": "github.com/acme/two",
        "required_state_or_artifact": "plan complete",
        "reason": "shared contract",
        "evidence_ref": "plan:two",
    }]
    assert validate_external_dependency_cycles(plan) == []
    sibling = deepcopy(plan)
    sibling["target_repo"] = "github.com/acme/two"
    sibling["plan_id"] = derive_plan_id(sibling["plan_set_id"], sibling["target_repo"])
    sibling["external_dependencies"] = [{
        "repo": "github.com/acme/one",
        "required_state_or_artifact": "plan complete",
        "reason": "shared contract",
        "evidence_ref": "plan:one",
    }]
    assert any("provable cycle" in error for error in validate_external_dependency_cycles(plan, {"github.com/acme/two": sibling}))


def test_builder_uses_repository_target_paths_when_impact_has_no_path_field() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"title": "Impact", "assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={
            "target_paths": ["src/checkout.py"],
            "estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 100, "confidence": "HIGH"},
        },
    )
    assert plan["readiness"] == "READY"
    assert plan["tasks"][0]["target_paths"] == ["src/checkout.py"]


def test_builder_blocks_incomplete_or_multi_repository_impact() -> None:
    sources = {
        "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
        "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
        "change_impact_report": {"payload": {
            "assessment_target": {"repo": "github.com/acme/checkout"},
            "coverage_status": "COMPLETE",
            "impacted_repositories": ["github.com/acme/checkout", "github.com/acme/catalog"],
            "target_paths": ["src/checkout.py"],
            "review_triggers": [],
        }},
    }
    plan = build_implementation_plan(sources, repository_evidence={
        "estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 100, "confidence": "HIGH"},
    })
    assert plan["readiness"] == "BLOCKED"


def test_builder_preserves_explicit_external_dependencies() -> None:
    dependency = {
        "repo": "github.com/acme/catalog",
        "required_state_or_artifact": "catalog schema plan COMPLETE",
        "reason": "checkout consumes the catalog contract",
        "evidence_ref": "architecture:catalog-contract",
    }
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "review_triggers": []}},
        },
        repository_evidence={
            "external_dependencies": [dependency],
            "estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 100, "confidence": "HIGH"},
        },
    )
    assert plan["external_dependencies"] == [dependency]
    assert validate_implementation_plan(plan) == []
