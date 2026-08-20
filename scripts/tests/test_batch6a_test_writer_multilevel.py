from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "test-writer"


def _read(path: str) -> str:
    return (SKILL / path).read_text(encoding="utf-8")


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


def test_plan_metadata_never_copies_raw_caller_signal():
    text = _read("workflow/classify.md").lower()
    assert "signal_source" in text
    assert "explicit_request | level_hint | clarification" in text
    assert "raw caller text" in text
    assert "test_plan" in text
    assert "rationale:" not in text
    assert "<caller signal>" not in text


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
