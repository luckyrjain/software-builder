from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

from scripts.implementation_plan import (
    ELIGIBILITY_CATEGORIES,
    PLAN_FIELDS,
    canonical_plan_digest,
    derive_plan_id,
    derive_plan_ids,
    derive_plan_set_id,
    build_implementation_plan,
    finalize_plan,
    normalize_plan_task,
    plan_from_sources,
    select_next_task,
    source_digest_bundle,
    validate_external_dependency_cycles,
    validate_implementation_plan,
    validate_plan,
    validate_plan_set,
    _load_json,
)


ROOT = Path(__file__).resolve().parents[2]


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


def test_malformed_nested_values_and_keys_fail_closed_without_raising() -> None:
    plan = _plan()
    plan[123] = "unexpected"
    plan["tasks"][0]["dependencies"] = [[]]
    errors = validate_implementation_plan(plan)
    assert errors


def test_cli_json_loader_rejects_duplicate_and_nonfinite_values(tmp_path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"readiness":"READY","readiness":"BLOCKED"}', encoding="utf-8")
    try:
        _load_json(duplicate)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate JSON keys must fail closed")
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"value":NaN}', encoding="utf-8")
    try:
        _load_json(nonfinite)
    except ValueError as exc:
        assert "non-finite" in str(exc)
    else:
        raise AssertionError("non-finite JSON values must fail closed")


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


def test_finalize_plan_blocks_a_partial_plan_with_a_real_schema_defect() -> None:
    plan = _plan()
    plan["readiness"] = "PARTIAL"
    plan["tasks"][1]["dependencies"] = ["TASK-002"]
    result = finalize_plan(plan)
    assert result.skill_result.status == "BLOCKED"
    assert result.payload["readiness"] == "BLOCKED"


def test_builder_fails_closed_instead_of_crashing_on_a_non_finite_source_value() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}, "note": float("nan")}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 50, "confidence": "HIGH"}},
    )
    assert plan["readiness"] == "BLOCKED"


def test_task_dependency_cycle_detection_does_not_recurse_per_chain_link() -> None:
    depth = 500
    tasks = [_task(f"TASK-{i:04d}") for i in range(depth)]
    for i in range(1, depth):
        tasks[i]["dependencies"] = [tasks[i - 1]["task_id"]]
    plan = _plan()
    plan["tasks"] = tasks
    plan["execution_waves"] = [[task["task_id"]] for task in tasks]
    plan["traceability"] = {"condition_coverage": {}, "action_coverage": {}, "required_test_coverage": {}}
    original_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(150)
    try:
        errors = validate_implementation_plan(plan)
    finally:
        sys.setrecursionlimit(original_limit)
    assert isinstance(errors, list)


def test_builder_preserves_the_repo_contributing_sources_other_assessment_fields() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/svc", "component": "checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"notes": "unrelated"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 50, "confidence": "HIGH"}},
    )
    assert plan["assessment_target"] == {"repo": "github.com/acme/svc", "component": "checkout"}


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


def test_fabricated_plan_set_id_is_rejected_when_source_refs_are_canonical() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 50, "confidence": "HIGH"}},
    )
    assert validate_implementation_plan(plan) == []

    plan["plan_set_id"] = derive_plan_set_id("a" * 64, "b" * 64, "c" * 64)
    plan["plan_id"] = derive_plan_id(plan["plan_set_id"], plan["target_repo"])
    assert any("plan_set_id" in error and "source_refs" in error for error in validate_implementation_plan(plan))


def test_corrupting_a_single_canonical_source_ref_digest_cannot_bypass_the_check() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 50, "confidence": "HIGH"}},
    )
    # Corrupting just one of the three canonical digests must not let the consistency check skip
    # itself entirely -- only a plan_set_id/plan_id that also happen to still be consistent with
    # the (now unverifiable) declared source lineage would otherwise slip through.
    plan["source_refs"] = ["change_impact_report:not-a-real-digest", "system_design_spec:" + "a" * 64, "architecture_review_report:" + "b" * 64]
    assert any("source_refs" in error for error in validate_implementation_plan(plan))


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


def test_builder_blocks_when_a_source_ran_successfully_but_its_own_verdict_is_fail() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"normalized_decision": {"status": "FAIL"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 100, "confidence": "HIGH"}},
    )
    assert plan["readiness"] == "BLOCKED"


def test_builder_puts_each_chained_task_in_its_own_wave_for_three_or_more_targets() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/a.py", "src/b.py", "src/c.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 3, "changed_lines_upper_bound": 100, "confidence": "HIGH"}},
    )
    assert plan["readiness"] == "READY"
    assert validate_implementation_plan(plan) == []
    assert plan["execution_waves"] == [[task["task_id"]] for task in plan["tasks"]]


def test_builder_attaches_required_tests_to_the_last_chained_task_not_the_first() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/a.py", "src/b.py", "src/c.py"], "required_tests": ["pytest -q tests/test_integration.py"], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 3, "changed_lines_upper_bound": 100, "confidence": "HIGH"}},
    )
    assert plan["readiness"] == "READY"
    assert plan["tasks"][0]["required_tests"] == []
    assert plan["tasks"][1]["required_tests"] == []
    assert plan["tasks"][2]["required_tests"] == ["pytest -q tests/test_integration.py"]
    assert plan["traceability"]["required_test_coverage"]["pytest -q tests/test_integration.py"] == [plan["tasks"][2]["task_id"]]


def test_builder_recognizes_the_real_system_design_readiness_vocabulary() -> None:
    def _plan_with_design_readiness(readiness: str) -> dict[str, object]:
        return build_implementation_plan(
            {
                "system_design_spec": {"payload": {"title": "Checkout", "readiness": readiness, "assessment_target": {"repo": "github.com/acme/checkout"}}},
                "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
                "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
            },
            repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 100, "confidence": "HIGH"}},
        )

    assert _plan_with_design_readiness("Ready to implement")["readiness"] == "READY"
    assert _plan_with_design_readiness("Not ready")["readiness"] == "BLOCKED"
    # "Ready with open questions" maps to CONDITIONAL, which is not itself blocking.
    assert _plan_with_design_readiness("Ready with open questions")["readiness"] != "BLOCKED"


def test_builder_splits_the_aggregate_estimate_across_chained_tasks() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/a.py", "src/b.py", "src/c.py", "src/d.py", "src/e.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 40, "changed_lines_upper_bound": 1500, "confidence": "HIGH"}},
    )
    assert plan["readiness"] == "READY"
    assert sum(task["estimated_scope"]["files_upper_bound"] for task in plan["tasks"]) == 40
    assert sum(task["estimated_scope"]["changed_lines_upper_bound"] for task in plan["tasks"]) == 1500
    for task in plan["tasks"]:
        assert task["estimated_scope"]["files_upper_bound"] < 40


def test_builder_never_floors_a_known_per_task_estimate_to_zero() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/a.py", "src/b.py", "src/c.py", "src/d.py", "src/e.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 3, "changed_lines_upper_bound": 3, "confidence": "HIGH"}},
    )
    assert plan["readiness"] == "READY"
    for task in plan["tasks"]:
        assert task["estimated_scope"]["files_upper_bound"] >= 1
        assert task["estimated_scope"]["changed_lines_upper_bound"] >= 1


def test_builder_never_lets_assessment_target_repo_disagree_with_target_repo() -> None:
    # Neither system_design_spec nor change_impact_report declares an assessment_target.repo, so
    # target_repo can only resolve through the explicit sources["target_repo"] override -- the
    # emitted assessment_target.repo must still agree with it, not silently stay empty/absent.
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready"}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
            "target_repo": "github.com/acme/checkout",
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 50, "confidence": "HIGH"}},
    )
    assert plan["target_repo"] == "github.com/acme/checkout"
    assert plan["assessment_target"]["repo"] == plan["target_repo"]


def test_builder_ignores_an_undeclared_target_repo_field_inside_change_impact_report() -> None:
    # change_impact_report's registered schema has no top-level target_repo field, only
    # assessment_target.repo -- an unrelated field with that name inside the artifact must never
    # be picked up ahead of the schema-declared field or the explicit sources["target_repo"] override.
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "target_repo": "github.com/acme/unrelated-field-value", "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 50, "confidence": "HIGH"}},
    )
    assert plan["target_repo"] == "github.com/acme/checkout"


def test_builder_blocks_when_impacted_repositories_is_explicitly_empty() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "impacted_repositories": [], "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 100, "confidence": "HIGH"}},
    )
    assert plan["readiness"] == "BLOCKED"


def test_select_next_task_is_earliest_dependency_satisfied_and_non_mutating() -> None:
    plan = _plan()
    task = select_next_task(plan)
    assert task is not None and task["task_id"] == "TASK-001"
    task["title"] = "caller mutation"
    assert plan["tasks"][0]["title"] != "caller mutation"
    assert select_next_task(plan, {"TASK-001": "COMPLETE", "TASK-002": "PENDING"}, state_reconciled=True)["task_id"] == "TASK-002"
    assert select_next_task(plan, {"TASK-001": "IN_PROGRESS", "TASK-002": "PENDING"}, state_reconciled=True) is None
    assert select_next_task(plan, {"TASK-001": "COMPLETE", "TASK-002": "PENDING"}) is None


def test_builder_rejects_unknown_specialist_trigger_and_carries_specialist_traceability() -> None:
    sources = {
        "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
        "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
        "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {
            "assessment_target": {"repo": "github.com/acme/checkout"},
            "coverage_status": "COMPLETE",
            "target_paths": ["src/checkout.py"],
            "review_triggers": ["security", "future-specialist"],
        }},
        "specialist_reports": {
            "security": {"skill_result": {"status": "SUCCESS"}, "payload": {
                "conditions": [{"id": "security-condition"}],
                "required_actions": [{"id": "security-action"}],
            }},
        },
    }
    plan = build_implementation_plan(sources, repository_evidence={
        "estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 100, "confidence": "HIGH"},
    })
    assert plan["readiness"] == "BLOCKED"

    sources["change_impact_report"]["payload"]["review_triggers"] = ["security"]
    plan = build_implementation_plan(sources, repository_evidence={
        "estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 100, "confidence": "HIGH"},
    })
    assert "specialist:security-condition:security-condition" in plan["tasks"][0]["source_condition_refs"]
    assert "specialist:security-action:security-action" in plan["tasks"][0]["source_action_refs"]
    assert validate_implementation_plan(plan) == []


def test_builder_keeps_unresolved_external_dependencies_partial() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "review_triggers": []}},
        },
        repository_evidence={
            "external_dependencies": [{"repo": "https://github.com/acme/catalog", "required_state_or_artifact": "COMPLETE", "reason": "shared contract", "evidence_ref": "plan:catalog"}],
            "estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 100, "confidence": "HIGH"},
        },
    )
    assert plan["readiness"] == "PARTIAL"

    resolved_plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "review_triggers": []}},
        },
        repository_evidence={
            "external_dependencies": [{"repo": "https://github.com/acme/catalog", "required_state_or_artifact": "COMPLETE", "reason": "shared contract", "evidence_ref": "plan:catalog"}],
            "external_dependency_statuses": {"https://github.com/acme/catalog.git": "complete"},
            "estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 100, "confidence": "HIGH"},
        },
    )
    assert resolved_plan["readiness"] == "READY"


def test_path_traversal_and_mismatched_traceability_fail_closed() -> None:
    plan = _plan()
    plan["tasks"][0]["target_paths"] = ["C:\\repo\\..\\secrets.txt"]
    assert any("target_paths" in error for error in validate_implementation_plan(plan))
    plan = _plan()
    plan["tasks"][0]["target_paths"] = ["\\etc\\passwd"]
    assert any("target_paths" in error for error in validate_implementation_plan(plan))
    plan = _plan()
    plan["tasks"][0]["target_paths"] = [" /etc/passwd"]
    assert any("target_paths" in error for error in validate_implementation_plan(plan))
    plan = _plan()
    plan["tasks"][0]["target_paths"] = ["."]
    assert any("target_paths" in error for error in validate_implementation_plan(plan))
    plan = _plan()
    plan["tasks"][0]["target_paths"] = ["./."]
    assert any("target_paths" in error for error in validate_implementation_plan(plan))
    plan = _plan()
    plan["tasks"][0]["target_paths"] = ["././"]
    assert any("target_paths" in error for error in validate_implementation_plan(plan))
    plan = _plan()
    plan["tasks"][0]["target_paths"] = ["C:temp/secret.py"]
    assert any("target_paths" in error for error in validate_implementation_plan(plan))
    plan = _plan()
    plan["tasks"][1]["source_condition_refs"] = []
    plan["traceability"]["condition_coverage"]["condition:timeout-budget"] = ["TASK-002"]
    assert any("does not cite it" in error for error in validate_implementation_plan(plan))


def test_plan_task_normalization_preserves_legacy_task_inputs() -> None:
    normalized = normalize_plan_task(_task("TASK-001"), target_repo="github.com/acme/checkout")
    assert normalized["task_id"] == "TASK-001"
    assert normalized["request"] == "Implement TASK-001"
    assert normalized["target"] == ["src/checkout.py"]
    assert normalized["repo_root"] == "github.com/acme/checkout"
    assert normalized["max_files_per_run"] == 1
    assert set(normalized) == {
        "task_id", "scope", "acceptance_criteria", "request", "repo_root", "target", "level_hint",
        "specialist_inputs", "test_framework_hint", "run_tests", "max_files_per_run", "deadline",
        "session_token_budget", "output_dir",
    }


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
    assert any("cross-repository cycle" in error for error in validate_external_dependency_cycles(plan, {"github.com/acme/two": sibling}))


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


def test_builder_blocks_target_repo_absent_from_impacted_repositories() -> None:
    sources = {
        "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
        "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
        "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {
            "assessment_target": {"repo": "github.com/acme/checkout"},
            "coverage_status": "COMPLETE",
            "impacted_repositories": ["github.com/acme/other-repo"],
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


def test_source_digest_bundle_and_derive_plan_ids_are_deterministic_and_repo_specific() -> None:
    bundle = source_digest_bundle("design-a")
    assert derive_plan_ids(bundle, "github.com/acme/payments") == derive_plan_ids(bundle, "github.com/acme/payments")
    plan_set_id, plan_id = derive_plan_ids(bundle, "github.com/acme/payments")
    assert plan_id == derive_plan_id(plan_set_id, "github.com/acme/payments")
    other_bundle_plan_set_id, _ = derive_plan_ids(source_digest_bundle("design-b"), "github.com/acme/payments")
    assert other_bundle_plan_set_id != plan_set_id


def test_validate_plan_and_plan_from_sources_are_the_canonical_aliases() -> None:
    assert validate_plan is validate_implementation_plan
    assert plan_from_sources is build_implementation_plan
    assert validate_plan(_plan()) == []


def test_validate_plan_set_rejects_cross_repo_cycle_and_keeps_missing_sibling_unresolved() -> None:
    plan_a = _plan()
    plan_a["target_repo"] = "github.com/acme/one"
    plan_a["plan_id"] = derive_plan_id(plan_a["plan_set_id"], plan_a["target_repo"])
    plan_a["external_dependencies"] = [{
        "repo": "github.com/acme/two",
        "required_state_or_artifact": "plan complete",
        "reason": "shared contract",
        "evidence_ref": "plan:two",
    }]
    plan_b = deepcopy(plan_a)
    plan_b["target_repo"] = "github.com/acme/two"
    plan_b["plan_id"] = derive_plan_id(plan_b["plan_set_id"], plan_b["target_repo"])
    plan_b["external_dependencies"] = [{
        "repo": "github.com/acme/one",
        "required_state_or_artifact": "plan complete",
        "reason": "shared contract",
        "evidence_ref": "plan:one",
    }]
    assert any("cross-repository cycle" in error for error in validate_plan_set([plan_a, plan_b]))
    assert not any("cross-repository cycle" in error for error in validate_plan_set([plan_a]))

    mismatched_plan_set = deepcopy(plan_b)
    mismatched_plan_set["plan_set_id"] = "PLANSET-different0000"
    assert any("plan_set_id" in error for error in validate_plan_set([plan_a, mismatched_plan_set]))

    duplicate_repo_plan = deepcopy(plan_b)
    duplicate_repo_plan["target_repo"] = plan_a["target_repo"]
    duplicate_repo_plan["plan_id"] = derive_plan_id(duplicate_repo_plan["plan_set_id"], duplicate_repo_plan["target_repo"])
    assert any("distinct repository" in error for error in validate_plan_set([plan_a, duplicate_repo_plan]))


def test_sibling_sharing_the_primary_plans_own_repo_is_never_substituted_for_it() -> None:
    plan = _plan()
    plan["target_repo"] = "github.com/acme/one"
    plan["plan_id"] = derive_plan_id(plan["plan_set_id"], plan["target_repo"])
    plan["external_dependencies"] = [{
        "repo": "github.com/acme/two",
        "required_state_or_artifact": "plan complete",
        "reason": "shared contract",
        "evidence_ref": "plan:two",
    }]
    # A malformed sibling_plans entry keyed to the plan's own repo must never replace the plan
    # itself in the analysis graph -- its real external_dependencies edge to "two" must still be
    # visible, and it must not be reported as a (nonexistent) self-cycle.
    imposter_sibling = {"target_repo": "github.com/acme/one", "external_dependencies": []}
    errors = validate_external_dependency_cycles(plan, {"github.com/acme/one": imposter_sibling})
    assert not any("cycle" in error for error in errors)


def test_finalize_plan_maps_readiness_to_execution_status() -> None:
    ready = finalize_plan(_plan())
    assert ready.payload["readiness"] == "READY"
    assert ready.skill_result.status == "SUCCESS"

    partial_plan = _plan()
    partial_plan["readiness"] = "PARTIAL"
    partial = finalize_plan(partial_plan)
    assert partial.payload["readiness"] == "PARTIAL"
    assert partial.skill_result.status == "PARTIAL"

    broken_plan = _plan()
    broken_plan["tasks"] = [_task("A", ["B"]), _task("B", ["A"])]
    blocked = finalize_plan(broken_plan)
    assert blocked.skill_result.status == "BLOCKED"
    assert any("cycle" in blocker for blocker in blocked.skill_result.blockers)
    assert ready.skill_result.blockers == ()

    failed = finalize_plan("not-a-plan")
    assert failed.skill_result.status == "FAILED"
    assert failed.skill_result.blockers != ()


def test_builder_downgrading_for_incomplete_coverage_never_overwrites_a_worse_status() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"normalized_decision": {"status": "FAIL"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "PARTIAL", "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 50, "confidence": "HIGH"}},
    )
    assert plan["readiness"] == "BLOCKED"


def test_builder_blocks_when_an_upstream_source_escalated() -> None:
    plan = build_implementation_plan(
        {
            "system_design_spec": {"skill_result": {"status": "ESCALATED"}, "payload": {"title": "Checkout", "readiness": "Ready to implement", "assessment_target": {"repo": "github.com/acme/checkout"}}},
            "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
            "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
        },
        repository_evidence={"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 50, "confidence": "HIGH"}},
    )
    assert plan["readiness"] == "BLOCKED"


# --- B2: lightweight ticket -> plan path for small tasks ------------------------------------------------


def _single_task_plan(target_paths: list[str], planning_path: dict[str, object] | None = None) -> dict[str, object]:
    """A minimal single-task variant of `_plan()` for exercising `_validate_planning_path` directly."""
    plan = _plan()
    task = _task("TASK-001")
    task["target_paths"] = target_paths
    plan["tasks"] = [task]
    plan["execution_waves"] = [["TASK-001"]]
    plan["traceability"] = {
        "condition_coverage": {"condition:timeout-budget": ["TASK-001"]},
        "action_coverage": {"action:implement-timeout": ["TASK-001"]},
        "required_test_coverage": {"pytest -q tests/test_checkout.py": ["TASK-001"]},
    }
    if planning_path is not None:
        plan["planning_path"] = planning_path
    return plan


def _lw(category: str = "CONFIG_VALUE_ONLY", asserted_by: str = "Bump the pinned value in src/checkout.py per CONFIG_VALUE_ONLY.") -> dict[str, object]:
    return {"mode": "LIGHTWEIGHT", "eligibility_category": category, "asserted_by": asserted_by}


def _lightweight_stub_sources(title: str, target_paths: list[str], category: str, *, repo: str = "github.com/acme/checkout") -> dict[str, object]:
    evidence_refs = ["lightweight-plan-path:v1", f"eligibility:{category}"]
    return {
        "system_design_spec": {
            "skill_result": {"status": "SUCCESS"},
            "payload": {
                "title": title,
                "readiness": "ready",
                "assessment_target": {"repo": repo, "target_paths": target_paths},
                "normalized_decision": {"status": "READY"},
                "findings": [], "conditions": [], "required_actions": [],
                "evidence_refs": evidence_refs,
            },
        },
        "architecture_review_report": {
            "skill_result": {"status": "SUCCESS"},
            "payload": {
                "title": title,
                "decision": "Approved",
                "assessment_target": {"repo": repo, "target_paths": target_paths},
                "normalized_decision": {"status": "READY"},
                "findings": [], "conditions": [], "required_actions": [],
                "evidence_refs": evidence_refs,
            },
        },
        "change_impact_report": {
            "skill_result": {"status": "SUCCESS"},
            "payload": {
                "title": title,
                "assessment_target": {"repo": repo},
                "coverage_status": "COMPLETE",
                "material_unknowns": [],
                "impacted_repositories": [repo],
                "criticality": "Low",
                "change_classes": [category],
                "impacted_services": [], "impacted_contracts": [], "impacted_data": [],
                "impacted_dependencies": [], "impacted_owners": [],
                "target_paths": target_paths,
                "required_tests": [],
                "operational_impacts": [],
                "review_triggers": [],
                "unknowns": [],
                "evidence_refs": evidence_refs,
            },
        },
    }


def _lightweight_evidence(category: str, target_paths: list[str], asserted_by: str) -> dict[str, object]:
    return {
        "estimated_scope": {
            "estimate_known": True,
            "files_upper_bound": len(target_paths),
            "changed_lines_upper_bound": 20,
            "confidence": "HIGH",
        },
        "planning_path": {"mode": "LIGHTWEIGHT", "eligibility_category": category, "asserted_by": asserted_by},
    }


def test_full_mode_plan_gains_only_the_new_planning_path_key() -> None:
    # Required test 1 (change-impact report): a FULL-mode plan built through the unmodified default
    # path is unchanged except for the addition of the new planning_path key.
    sources = {
        "system_design_spec": {"payload": {"title": "Checkout", "readiness": "Ready", "assessment_target": {"repo": "github.com/acme/checkout"}}},
        "architecture_review_report": {"payload": {"normalized_decision": {"status": "PASS"}}},
        "change_impact_report": {"skill_result": {"status": "SUCCESS"}, "payload": {"title": "Impact", "assessment_target": {"repo": "github.com/acme/checkout"}, "coverage_status": "COMPLETE", "target_paths": ["src/checkout.py"], "required_tests": [], "review_triggers": []}},
    }
    evidence = {"estimated_scope": {"estimate_known": True, "files_upper_bound": 1, "changed_lines_upper_bound": 50, "confidence": "HIGH"}}
    plan = build_implementation_plan(sources, repository_evidence=evidence)
    assert plan["readiness"] == "READY"
    assert set(plan) == PLAN_FIELDS
    assert plan["planning_path"] == {"mode": "FULL", "eligibility_category": None, "asserted_by": None}
    assert validate_implementation_plan(plan) == []


def test_resume_compatibility_accepts_a_real_historical_plan_without_planning_path() -> None:
    # Required test 2: a real, already-committed plan built before planning_path existed still
    # validates cleanly (implicit FULL via the backward-compat carve-out).
    historical_plan = _load_json(ROOT / "docs/superpowers/specs/2026-09-28-b1-clarify-step-implementation-plan.json")
    assert isinstance(historical_plan, dict)
    assert "planning_path" not in historical_plan
    assert validate_implementation_plan(historical_plan) == []


def test_lightweight_plan_with_valid_category_and_asserted_by_passes() -> None:
    plan = _single_task_plan(["src/checkout.py"], _lw())
    assert validate_implementation_plan(plan) == []


def test_lightweight_plan_rejects_invalid_category() -> None:
    plan = _single_task_plan(["src/checkout.py"], _lw(category="NOT_A_REAL_CATEGORY"))
    errors = validate_implementation_plan(plan)
    assert any("eligibility_category" in error for error in errors)


def test_lightweight_plan_rejects_missing_asserted_by() -> None:
    plan = _single_task_plan(["src/checkout.py"], _lw(asserted_by=""))
    errors = validate_implementation_plan(plan)
    assert any("asserted_by" in error for error in errors)


def test_lightweight_plan_rejects_more_than_three_target_paths() -> None:
    plan = _single_task_plan(["a.md", "b.md", "c.md", "d.md"], _lw(category="DOC_ONLY"))
    errors = validate_implementation_plan(plan)
    assert any("at most 3 target_paths" in error for error in errors)


def test_lightweight_plan_denylist_rejects_dotslash_prefixed_ci_path() -> None:
    plan = _single_task_plan(["./.github/workflows/ci.yml"], _lw())
    errors = validate_implementation_plan(plan)
    assert any("never eligible" in error for error in errors)


def test_lightweight_plan_denylist_rejects_backslash_separated_ci_path() -> None:
    plan = _single_task_plan([".github\\workflows\\ci.yml"], _lw())
    errors = validate_implementation_plan(plan)
    assert any("never eligible" in error for error in errors)


def test_lightweight_plan_denylist_rejects_dependency_manifest_basename() -> None:
    plan = _single_task_plan(["requirements.txt"], _lw())
    errors = validate_implementation_plan(plan)
    assert any("never eligible" in error for error in errors)


def test_lightweight_plan_denylist_rejects_case_varied_dependency_manifest_basename() -> None:
    plan = _single_task_plan(["Requirements.txt"], _lw())
    errors = validate_implementation_plan(plan)
    assert any("never eligible" in error for error in errors)


def test_lightweight_plan_denylist_rejects_case_varied_ci_workflow_path() -> None:
    # Round 4, Lens A (Safety and State): a case-varied spelling of the CI workflow prefix must
    # not evade the denylist -- mirrors the case-insensitivity already required of the
    # dependency-manifest basename check above.
    plan = _single_task_plan([".GitHub/Workflows/ci.yml"], _lw())
    errors = validate_implementation_plan(plan)
    assert any("never eligible" in error for error in errors)


def test_lightweight_plan_denylist_rejects_case_varied_governance_file() -> None:
    # Round 4, Lens A (Safety and State): a case-varied spelling of an exact-match governance file
    # (e.g. CODEOWNERS) must not evade the denylist either.
    plan = _single_task_plan(["Codeowners"], _lw())
    errors = validate_implementation_plan(plan)
    assert any("never eligible" in error for error in errors)


def test_lightweight_plan_denylist_exempts_manifest_basename_under_tests_fixtures() -> None:
    plan = _single_task_plan(["tests/fixtures/requirements.txt"], _lw(category="ADDITIVE_TEST_ONLY"))
    assert validate_implementation_plan(plan) == []


def test_full_mode_plan_rejects_non_null_eligibility_category_or_asserted_by() -> None:
    plan = _single_task_plan(["src/checkout.py"], {"mode": "FULL", "eligibility_category": "DOC_ONLY", "asserted_by": "reason"})
    errors = validate_implementation_plan(plan)
    assert any("FULL planning_path must have null" in error for error in errors)


def test_lightweight_build_produces_a_ready_plan_with_planning_path_recorded() -> None:
    target_paths = ["src/checkout.py"]
    title = "Bump the pinned timeout value in src/checkout.py"
    asserted_by = "Bump the pinned timeout value in src/checkout.py per CONFIG_VALUE_ONLY."
    plan = build_implementation_plan(
        _lightweight_stub_sources(title, target_paths, "CONFIG_VALUE_ONLY"),
        repository_evidence=_lightweight_evidence("CONFIG_VALUE_ONLY", target_paths, asserted_by),
    )
    assert plan["readiness"] == "READY"
    assert plan["planning_path"] == {
        "mode": "LIGHTWEIGHT",
        "eligibility_category": "CONFIG_VALUE_ONLY",
        "asserted_by": asserted_by,
    }
    assert validate_implementation_plan(plan) == []


def test_two_lightweight_builds_with_different_titles_produce_different_plan_ids() -> None:
    # Required test 4 (plan-identity uniqueness): different, genuinely task-specific title text
    # must not collide even when category and target_paths match.
    target_paths = ["src/checkout.py"]
    plan_a = build_implementation_plan(
        _lightweight_stub_sources("Bump numpy to 1.26.4 in src/checkout.py", target_paths, "CONFIG_VALUE_ONLY"),
        repository_evidence=_lightweight_evidence("CONFIG_VALUE_ONLY", target_paths, "Bump numpy to 1.26.4 per CONFIG_VALUE_ONLY."),
    )
    plan_b = build_implementation_plan(
        _lightweight_stub_sources("Bump requests to 2.32.0 in src/checkout.py", target_paths, "CONFIG_VALUE_ONLY"),
        repository_evidence=_lightweight_evidence("CONFIG_VALUE_ONLY", target_paths, "Bump requests to 2.32.0 per CONFIG_VALUE_ONLY."),
    )
    assert plan_a["plan_id"] != plan_b["plan_id"]


def test_two_lightweight_builds_with_identical_stub_content_produce_the_same_plan_id() -> None:
    # Required test 4 (plan-identity uniqueness), idempotent-retry half: identical stub content
    # (the natural shape of a legitimate retry of the same logical task) must produce the same
    # plan_id.
    target_paths = ["src/checkout.py"]
    title = "Bump numpy to 1.26.4 in src/checkout.py"
    asserted_by = "Bump numpy to 1.26.4 per CONFIG_VALUE_ONLY."
    plan_a = build_implementation_plan(
        _lightweight_stub_sources(title, target_paths, "CONFIG_VALUE_ONLY"),
        repository_evidence=_lightweight_evidence("CONFIG_VALUE_ONLY", target_paths, asserted_by),
    )
    plan_b = build_implementation_plan(
        _lightweight_stub_sources(title, target_paths, "CONFIG_VALUE_ONLY"),
        repository_evidence=_lightweight_evidence("CONFIG_VALUE_ONLY", target_paths, asserted_by),
    )
    assert plan_a["plan_id"] == plan_b["plan_id"]


def test_identical_lightweight_stub_content_yields_stable_canonical_plan_digest_across_builds() -> None:
    # Required test 5 (resume-digest stability): byte-identical title/target_paths/asserted_by/
    # eligibility_category across two builds must produce the same canonical_plan_digest -- the
    # direct regression test for the round-4/5 bug class (run-scoped content silently entering the
    # resume digest via planning_path/asserted_by).
    target_paths = ["src/checkout.py"]
    title = "Bump numpy to 1.26.4 in src/checkout.py"
    asserted_by = "Bump numpy to 1.26.4 per CONFIG_VALUE_ONLY."
    plan_a = build_implementation_plan(
        _lightweight_stub_sources(title, target_paths, "CONFIG_VALUE_ONLY"),
        repository_evidence=_lightweight_evidence("CONFIG_VALUE_ONLY", target_paths, asserted_by),
    )
    plan_b = build_implementation_plan(
        _lightweight_stub_sources(title, target_paths, "CONFIG_VALUE_ONLY"),
        repository_evidence=_lightweight_evidence("CONFIG_VALUE_ONLY", target_paths, asserted_by),
    )
    assert canonical_plan_digest(plan_a) == canonical_plan_digest(plan_b)


def test_reference_documents_every_eligibility_category() -> None:
    # Required test 6 (design Fix 10): every ELIGIBILITY_CATEGORIES value appears backtick-wrapped
    # in reference/lightweight-path.md, matching test_run_log.py's
    # test_reference_documents_every_event_actor_outcome_reason_and_exit_code convention exactly
    # (literal-text containment), not test_plan_execution_state.py's structured YAML-equality
    # convention.
    text = (ROOT / "skills/implementation-planner/reference/lightweight-path.md").read_text(encoding="utf-8")
    for category in ELIGIBILITY_CATEGORIES:
        assert f"`{category}`" in text, category
