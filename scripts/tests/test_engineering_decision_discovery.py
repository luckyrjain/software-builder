"""RED baseline for the engineering-decision-discovery skill (Child Plan B, Task 1),
plus Task 2's package-level assertions.

The routing/registry/eval-admission tests below (Task 1) stay RED until Task 3
wires the skill into skills.yaml -- registry wiring is explicitly out of
scope for Task 2. Every test in the original RED baseline is expected to
fail until then; the exact failure messages recorded at that commit live in
docs/superpowers/specs/2026-09-05-engineering-decision-discovery-red-baseline.md.

The `TestSkillPackageContract` tests below were added by Task 2. They check
the skill package's own text and workflow invariants directly against the
files on disk -- not through the registry or dispatcher -- so they do not
depend on Task 3's registry wiring and are expected to pass now.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evals.__main__ import run_all
from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


@pytest.mark.parametrize(
    "prompt",
    [
        "Grill me on this architecture decision.",
        "Challenge my plan and question my assumptions.",
        "Stress-test this engineering decision.",
        "What decisions are missing before we implement this design?",
        "Help me decide between these module designs.",
    ],
)
def test_decision_discovery_has_a_dedicated_owner(prompt: str) -> None:
    result = _dispatch(prompt)
    assert result.status == "selected", result
    assert result.owner == "engineering-decision-discovery"


def test_challenge_proposed_architecture_still_routes_to_architecture_review() -> None:
    """Task 4 review, Finding 4: the brief's Step 4 names "challenge this proposed
    architecture" as a collision check -- it must still route to architecture-review,
    not get stolen by engineering-decision-discovery's own "challenge my plan" trigger.
    evals/negative/cases.yaml carries the same prompt as its one permitted
    engineering-decision-discovery row (the negative dimension allows exactly one
    scenario per skill); this test is the same check run directly against the
    dispatcher as committed evidence, independent of the cases.yaml scenario harness."""
    result = _dispatch("Challenge this proposed architecture before we start building.")
    assert result.status == "selected", result
    assert result.owner == "architecture-review"
    assert "engineering-decision-discovery" not in result.candidates


def test_concrete_module_design_still_routes_to_module_design() -> None:
    """Task 4 review, Finding 4: the brief's Step 4 names "a concrete module design" as
    the second collision check -- it must still route to module-design, not get stolen
    by engineering-decision-discovery. evals/negative/cases.yaml already has one
    permitted row per skill (module-design's own row covers a different collision), so
    this check is committed here as a direct dispatcher assertion instead of a second
    cases.yaml row for the same skill."""
    result = _dispatch("Design the concrete module boundary for the new charge module.")
    assert result.status == "selected", result
    assert result.owner == "module-design"
    assert "engineering-decision-discovery" not in result.candidates


def test_decision_discovery_skill_is_not_yet_registered() -> None:
    """Documents the RED reason every other test in this module fails on: there is
    no `engineering-decision-discovery` entry in skills.yaml yet (Task 3 adds it)."""
    registry = load_registry(ROOT)
    assert "engineering-decision-discovery" in registry.skills


def test_decision_frontier_transcript_fixture_is_admitted_and_passes() -> None:
    """evals/transcripts/engineering-decision-discovery/decision-frontier.yaml requires:
    repository is read before the frontier is computed; a recommendation is recorded
    separately from -- and initially unapproved by -- the human; a human decision
    resolves D1 before D2/D3 enter the frontier; and the repository and an ADR are
    never written. The fixture's events/assertions are already self-consistent, so
    the only reason this currently fails is admission: the skill it names is not yet
    registered (scripts/evals/__main__.py's admit_case gates every case on
    `case.skill in registry.skills`)."""
    results = run_all(ROOT, skill_filter="engineering-decision-discovery")
    by_case_id = {result.case_id: result for result in results}
    assert "decision-frontier" in by_case_id, by_case_id
    result = by_case_id["decision-frontier"]
    assert result.passed, result.messages


def test_decision_record_golden_fixture_is_admitted_and_passes() -> None:
    """evals/golden/engineering-decision-discovery/decision-record.yaml requires the
    typed engineering_decision_record to keep repository/ADR writes at "none", never
    synthesize a human decision, and hold D2/D3 behind the frontier until D1 is
    resolved. Same RED reason as the transcript case above: admission, not the
    recorded content, fails until the skill is registered."""
    results = run_all(ROOT, skill_filter="engineering-decision-discovery")
    by_case_id = {result.case_id: result for result in results}
    assert "decision-record" in by_case_id, by_case_id
    result = by_case_id["decision-record"]
    assert result.passed, result.messages


def test_independent_frontier_transcript_fixture_is_admitted_and_passes() -> None:
    """Task 4 review, Finding 1:
    evals/transcripts/engineering-decision-discovery/independent-frontier.yaml covers
    reference/pressure-tests.md's "Two independent nodes are both askable | Both appear
    on the same frontier round" row -- two nodes with no dependency on each other
    (D1, D4) are computed onto one frontier round and both get a recommendation before
    the round ends. decision-frontier.yaml's own D2/D3 pairing only tests the different
    "shared prerequisite resolves, dependents join the next round together" case."""
    results = run_all(ROOT, skill_filter="engineering-decision-discovery")
    by_case_id = {result.case_id: result for result in results}
    assert "independent-frontier" in by_case_id, by_case_id
    result = by_case_id["independent-frontier"]
    assert result.passed, result.messages


def test_decision_record_complete_golden_fixture_is_admitted_and_passes() -> None:
    """Task 4 review, Finding 2:
    evals/golden/engineering-decision-discovery/decision-record-complete.yaml is the
    "complete resolved decision record" scenario named by the plan's Step 3 -- every
    node resolved, frontier and unresolved_decisions both empty, status SUCCESS --
    distinct from decision-record.yaml's still-partial snapshot."""
    results = run_all(ROOT, skill_filter="engineering-decision-discovery")
    by_case_id = {result.case_id: result for result in results}
    assert "decision-record-complete" in by_case_id, by_case_id
    result = by_case_id["decision-record-complete"]
    assert result.passed, result.messages


def test_unattended_block_transcript_fixture_is_admitted_and_passes() -> None:
    """evals/transcripts/engineering-decision-discovery/unattended-block.yaml requires an
    unattended composition run to return BLOCKED with the frontier left explicit, instead
    of synthesizing a human decision to clear the unresolved, prerequisite-dependent D1. No
    human_decision event is present in the fixture at all -- BLOCKED must not depend on one
    being synthesized to reach that outcome -- and the fixture's own event_order assertion
    requires decision_frontier to be found, in order, before the BLOCKED outcome, so the
    frontier's presence is enforced by a real, symmetric fixture-level assertion rather than
    an eyeballed raw events list (Task 1's carried-forward Minor on the in-memory version of
    this scenario). Task 4 formally admits this fixture into the eval suite now that
    engineering-decision-discovery is a registered skill."""
    results = run_all(ROOT, skill_filter="engineering-decision-discovery")
    by_case_id = {result.case_id: result for result in results}
    assert "unattended-block" in by_case_id, by_case_id
    result = by_case_id["unattended-block"]
    assert result.passed, result.messages

    fixture_path = ROOT / "evals" / "transcripts" / "engineering-decision-discovery" / "unattended-block.yaml"
    raw_events = load_unique_yaml_file(fixture_path).get("events", [])
    assert not any(event.get("type") == "human_decision" for event in raw_events)


class TestSkillPackageContract:
    """Task 2 package-level assertions: skill text and workflow invariants,
    checked directly against engineering-decision-discovery/ on disk. These do
    not go through load_registry()/dispatch_prompt(), so they do not depend on
    Task 3's registry wiring and are expected to pass now."""

    SKILL_DIR = ROOT / "engineering-decision-discovery"

    EXPECTED_ROUTING_FRONTMATTER = (
        "---\n"
        "name: engineering-decision-discovery\n"
        "description: >-\n"
        "  Use when engineering decisions remain unresolved and need an interactive,\n"
        "  evidence-backed challenge before design or implementation. Keywords: grill\n"
        "  me, challenge my plan, stress-test this decision, question my assumptions,\n"
        "  help me decide, what decisions are missing, interrogate this architecture.\n"
        "  Not for reconstructing current domain behavior, reviewing a proposed\n"
        "  architecture, or implementing an already-settled task.\n"
        "---"
    )

    REQUIRED_FILES = [
        "SKILL.md",
        "README.md",
        "SETUP.md",
        "CHANGELOG.md",
        "examples.md",
        "workflow/inputs.md",
        "workflow/tree.md",
        "workflow/frontier.md",
        "workflow/interaction.md",
        "workflow/report.md",
        "reference/phase-index.md",
        "reference/lazy-load-index.md",
        "reference/pressure-tests.md",
        "reference/report-format.md",
        "reference/smoke-test.md",
    ]

    def test_package_files_exist(self) -> None:
        for rel_path in self.REQUIRED_FILES:
            assert (self.SKILL_DIR / rel_path).is_file(), rel_path

    def test_skill_md_uses_the_exact_routing_frontmatter(self) -> None:
        text = (self.SKILL_DIR / "SKILL.md").read_text()
        assert text.startswith(self.EXPECTED_ROUTING_FRONTMATTER)

    def test_skill_md_states_facts_vs_decisions_ownership(self) -> None:
        text = (self.SKILL_DIR / "SKILL.md").read_text()
        assert "belong" in text.lower()
        assert "decisions belong to the user" in text.lower()
        assert "recommendation" in text.lower()

    def test_inputs_workflow_requires_bounded_decision_scope(self) -> None:
        text = (self.SKILL_DIR / "workflow" / "inputs.md").read_text()
        assert "decision_scope" in text
        assert "BLOCKED" in text
        assert "interaction_policy" in text
        assert "human_available" in text
        assert "unattended" in text
        # Missing repository evidence is a gap, not a request for the user to
        # fetch facts the host can already read.
        assert "gap" in text.lower()

    def test_tree_workflow_defines_the_node_schema(self) -> None:
        text = (self.SKILL_DIR / "workflow" / "tree.md").read_text()
        for required_field in (
            "id:",
            "question:",
            "depends_on:",
            "options:",
            "status:",
            "selected_option:",
            "evidence_refs:",
        ):
            assert required_field in text, required_field
        assert "unresolved" in text and "resolved" in text and "not_applicable" in text

    def test_frontier_workflow_defines_the_dependency_gate(self) -> None:
        text = (self.SKILL_DIR / "workflow" / "frontier.md").read_text()
        assert "depends_on" in text
        assert "frontier" in text.lower()
        assert "BLOCKED" in text
        assert "unattended" in text.lower()

    def test_interaction_workflow_states_ownership_rules(self) -> None:
        text = (self.SKILL_DIR / "workflow" / "interaction.md").read_text()
        lowered = text.lower()
        assert "recommend" in lowered
        assert "a recommendation is never a decision" in lowered
        assert "record the decision and recompute" in lowered or "record" in lowered
        assert "explicitly deferred" in lowered

    def test_report_workflow_forbids_source_and_adr_writes(self) -> None:
        text = (self.SKILL_DIR / "workflow" / "report.md").read_text()
        assert "ENGINEERING_DECISION_RECORD.md" in text
        assert "engineering_decision_record" in text
        assert "ADR" in text
        assert "do not write" in text.lower() or "never write" in text.lower()

    def test_report_format_documents_the_nine_artifact_fields(self) -> None:
        text = (self.SKILL_DIR / "reference" / "report-format.md").read_text()
        for field in (
            "title",
            "decision_scope",
            "decision_tree",
            "frontier",
            "recommendations",
            "resolved_decisions",
            "unresolved_decisions",
            "alternatives_rejected",
            "limitations",
        ):
            assert field in text, field

    def test_smoke_test_documents_blocked_on_missing_scope(self) -> None:
        text = (self.SKILL_DIR / "reference" / "smoke-test.md").read_text()
        assert "BLOCKED" in text
        assert "decision_scope" in text
