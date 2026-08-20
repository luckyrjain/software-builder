from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "test-writer"


def _read(path: str) -> str:
    return (SKILL / path).read_text(encoding="utf-8")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_skill_routes_one_or_more_complementary_test_levels():
    text = _read("SKILL.md").lower()
    assert "one or more complementary test levels" in text
    assert "test_plan" in text
    assert "single-level compatibility" in text


def test_contract_preserves_specialist_authority_in_multi_level_runs():
    text = _read("reference/skill-contract.md").lower()
    for token in (
        "ordered, de-duplicated",
        "each specialist",
        "verbatim",
        "fail closed",
        "single named level",
    ):
        assert token in text


def test_classification_distinguishes_complementary_levels_from_ambiguity():
    text = _read("workflow/classify.md").lower()
    for token in (
        "complementary",
        "levels",
        "ordered",
        "de-duplicated",
        "ambiguity is not breadth",
        "ask once",
    ):
        assert token in text


def test_level_hint_cannot_silently_collapse_explicit_multilevel_breadth():
    text = _read("workflow/classify.md").lower()
    assert "level_hint" in text
    assert "explicitly requested complementary levels" in text
    assert "keep unit + integration" in text
    assert "silently collapse caller-requested breadth" in text


def test_signal_source_precedence_is_deterministic():
    text = _read("workflow/classify.md").lower()
    assert "`explicit_request` > `clarification` > `level_hint`" in text
    assert "request explicitly names unit and `level_hint: unit`" in text
    assert "`signal_source.unit: explicit_request`" in text
    assert "without changing `test_plan.levels`" in text


def test_phase_index_matches_level_hint_precedence_and_status_contract():
    text = _read("reference/phase-index.md").lower()
    assert "generic/ambiguous request + `level_hint: integration`" in text
    assert "one-level integration plan" in text
    assert "explicit unit + integration request + `level_hint: unit`" in text
    assert "preserves both complementary levels" in text
    assert "`unfinished_levels`" in text
    for status in ("`complete`", "`partial`", "`blocked`", "`failed`", "`escalated`"):
        assert status in text


def test_smoke_test_exercises_multilevel_orchestration_not_legacy_single_dispatch():
    text = _read("reference/smoke-test.md").lower()
    assert "unit tests for the pricing rules and integration tests for the payments db seam" in text
    assert "one dispatch per planned level" in text
    assert "unit-test-creator and integration-test-creator" in text
    assert "unfinished_levels" in text
    assert "never more than one per request" not in text
    assert "exactly one dispatch" not in text


def test_plan_metadata_never_copies_raw_caller_signal():
    text = _read("workflow/classify.md").lower()
    assert "signal_source" in text
    assert "explicit_request | level_hint | clarification" in text
    assert "raw caller text" in text
    assert "test_plan" in text
    assert "rationale:" not in text
    assert "<caller signal>" not in text


def test_inputs_exempts_framework_execution_context_from_ordinary_pass_through():
    text = _read("workflow/inputs.md").lower()
    assert "ordinary specialist-owned fields" in text
    assert "`execution_context`" in text
    assert "framework-owned runtime context" in text
    assert "do not treat it as an ordinary caller field" in text
    assert "delegate advances it independently for each child" in text
    assert "| everything else |" not in text


def test_delegate_executes_each_planned_level_without_cross_level_mutation():
    text = _read("workflow/delegate.md").lower()
    for token in (
        "test_plan",
        "for each planned level",
        "fresh specialist context",
        "inputs unchanged",
        "do not feed one specialist's report",
        "level_reports",
    ):
        assert token in text


def test_delegate_advances_framework_execution_context_per_child():
    text = _read("workflow/delegate.md").lower()
    assert "execution_context" in text
    assert "required exception to unchanged pass-through" in text
    assert "runtime-contract.md#8-recursion-protection" in text
    assert "dispatch_status: blocked" in text
    assert "blocked_reason: recursion_guard_rejected" in text
    assert "same invocation id" in text
    assert "parent_skill" in text and "test-writer" in text
    assert "increment depth once" in text
    assert "same parent context" in text
    assert "one sibling's" in text
    assert "must not increase another sibling's depth" in text
    assert "sibling-specific visited state" in text


def test_delegate_preserves_all_portable_specialist_statuses():
    text = _read("workflow/delegate.md")
    for mapping in (
        "| `SUCCESS` | `COMPLETE` |",
        "| `PARTIAL` | `PARTIAL` |",
        "| `BLOCKED` | `BLOCKED` |",
        "| `FAILED` | `FAILED` |",
        "| `ESCALATED` | `ESCALATED` |",
    ):
        assert mapping in text
    assert "Never convert `FAILED` or `ESCALATED`" in text


def test_aggregate_preserves_raw_reports_and_blocks_incomplete_plan():
    text = _read("workflow/aggregate.md")
    for token in (
        "level_reports",
        "verbatim",
        "planned level",
        "BLOCKED",
        "PARTIAL",
        "COMPLETE",
        "must not report COMPLETE",
    ):
        assert token in text


def test_aggregate_declares_and_derives_unfinished_levels():
    text = _read("workflow/aggregate.md")
    assert "  - unfinished_levels" in text
    assert "same stable order as `test_plan.levels`" in text
    assert "`dispatch_status` is not `COMPLETE`" in text
    assert "missing a valid report/status" in text
    assert "pre-dispatch blocked reason" in text
    assert "`unfinished_levels: []`" in text
    skill = _read("SKILL.md")
    assert "unfinished_levels" in skill
    assert "unfinished_levels derived in test_plan order" in skill


def test_aggregate_preserves_full_fixed_vocabulary_test_plan():
    text = _read("workflow/aggregate.md")
    assert "signal_source:" in text
    assert "unit: explicit_request" in text
    assert "integration: explicit_request" in text
    assert "must not drop or rewrite" in text
    assert "fixed-vocabulary `signal_source` provenance" in text


def test_aggregate_maps_internal_statuses_to_portable_runtime_statuses():
    text = _read("workflow/aggregate.md")
    assert "Portable `skill_result` mapping" in text
    for mapping in (
        "| `COMPLETE` | `SUCCESS` |",
        "| `PARTIAL` | `PARTIAL` |",
        "| `BLOCKED` | `BLOCKED` |",
        "| `FAILED` | `FAILED` |",
        "| `ESCALATED` | `ESCALATED` |",
    ):
        assert mapping in text
    assert "Never emit `COMPLETE` as `skill_result.status`" in text


def test_aggregate_defines_precedence_for_mixed_specialist_outcomes():
    text = _read("workflow/aggregate.md")
    assert text.index("1. `FAILED`") < text.index("2. `BLOCKED`")
    assert text.index("2. `BLOCKED`") < text.index("3. `ESCALATED`")
    assert text.index("3. `ESCALATED`") < text.index("4. `PARTIAL`")
    assert text.index("4. `PARTIAL`") < text.index("5. `COMPLETE`")


def test_phase_and_lazy_load_indexes_include_multilevel_aggregate_phase():
    phase = _read("reference/phase-index.md")
    lazy = _read("reference/lazy-load-index.md")
    assert "workflow/aggregate.md" in phase
    assert "workflow/aggregate.md" in lazy
    assert phase.index("Classify") < phase.index("Delegate") < phase.index("Aggregate")


def test_shared_router_sends_complementary_levels_to_test_writer_but_one_level_direct():
    routing = (ROOT / "docs/skill-framework/shared/skill-routing.md").read_text(encoding="utf-8").lower()
    for token in (
        "two or more complementary test levels explicitly requested",
        "two or more explicitly named complementary levels",
        "one explicitly named level",
        "that matching `*-test-creator` directly",
        "test-writer to build and execute the multi-level plan",
    ):
        assert token in routing


def test_registry_declares_a_distinct_orchestration_result_contract():
    contracts = _load_yaml(ROOT / "scripts" / "registry" / "composition_contracts.yaml")
    runtime = _load_yaml(ROOT / "scripts" / "registry" / "composition_runtime.yaml")
    assert "test_orchestration_result" in contracts["artifact_types"]
    assert contracts["artifact_schemas"]["test_orchestration_result"]["fields"] == [
        "test_plan",
        "orchestration_status",
        "unfinished_levels",
        "level_reports",
    ]
    test_writer = contracts["skills"]["test-writer"]
    assert test_writer["produces"] == ["test_orchestration_result"]
    assert test_writer["produce_fields"]["test_orchestration_result"] == [
        "test_plan",
        "orchestration_status",
        "unfinished_levels",
        "level_reports",
    ]
    assert "test-writer" not in runtime["artifact_ownership"]["test_suite"]["owners"]
    assert runtime["artifact_ownership"]["test_orchestration_result"] == {
        "mode": "canonical",
        "owners": ["test-writer"],
    }


def test_typed_implementation_task_carries_the_child_invocation_fields():
    contracts = _load_yaml(ROOT / "scripts" / "registry" / "composition_contracts.yaml")
    fields = contracts["artifact_schemas"]["implementation_task"]["fields"]
    for field in ("request", "repo_root", "target", "level_hint", "specialist_inputs"):
        assert field in fields
    for skill in (
        "test-writer",
        "unit-test-creator",
        "integration-test-creator",
        "contract-test-creator",
        "e2e-test-creator",
        "api-test-creator",
    ):
        assert contracts["skills"][skill]["consumes"] == ["implementation_task"]
        required = contracts["skills"][skill]["consume_fields"]["implementation_task"]
        for field in ("task_id", "scope", "acceptance_criteria", "request", "repo_root", "target"):
            assert field in required


def test_delegate_documents_a_canonical_child_handoff_and_child_context_history():
    text = _read("workflow/delegate.md").lower()
    for token in (
        "canonical handoff envelope",
        "target_skill",
        "evidence_refs",
        "assumptions",
        "unresolved",
        "implementation_task",
        "visited_skills",
        "parent.depth + 1",
        "check-handoff",
    ):
        assert token in text


def test_definition_of_done_matches_blocked_pre_dispatch_artifacts():
    skill = _read("SKILL.md").lower()
    aggregate = _read("workflow/aggregate.md").lower()
    assert "one level_reports entry per planned level" in skill
    assert "report or blocked_reason" in skill
    assert "blocked_reason" in aggregate
    assert "must not contain both" in aggregate


def test_changelog_versions_match_the_workflow_frontmatter():
    changelog = _read("CHANGELOG.md")
    assert "`workflow/inputs.md` → 2.4" in changelog
    assert "`workflow/delegate.md` → 2.5" in changelog
    assert "`workflow/aggregate.md` → 1.5" in changelog


def test_multilevel_lifecycle_golden_cases_cover_completion_failure_and_ambiguity():
    from scripts.evals.golden import load_golden_fixtures

    cases = {case.case_id: case for case in load_golden_fixtures(ROOT / "evals" / "golden")}
    for case_id in (
        "golden-test-writer-multilevel-complete",
        "golden-test-writer-multilevel-failed",
        "golden-test-writer-ambiguous-no-dispatch",
    ):
        assert case_id in cases
