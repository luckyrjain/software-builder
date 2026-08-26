from __future__ import annotations

from copy import deepcopy

from scripts.implementation_plan import (
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

    failed = finalize_plan("not-a-plan")
    assert failed.skill_result.status == "FAILED"
