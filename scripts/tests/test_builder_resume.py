"""Tests for scripts/builder_resume.py: pure resume-decision logic driven by synthetic commit lists
(per the architecture review's own reasoning for why that is the right test shape here, rather than a
literal killed agent session)."""

from __future__ import annotations

from scripts.builder_resume import CommitInfo, decide, parse_checkpoint_marker


def _commit(sha: str, marker: str | None) -> CommitInfo:
    message = f"Do the thing for {sha}\n"
    if marker is not None:
        message += f"\nCheckpoint: {marker}\n"
    return CommitInfo.from_commit(sha, message)


def test_parse_checkpoint_marker_finds_the_last_trailer_and_ignores_absence() -> None:
    assert parse_checkpoint_marker("no trailer here") is None
    assert parse_checkpoint_marker("body\n\nCheckpoint: implementation-complete\n") == "implementation-complete"
    # A repeated trailer: the last occurrence governs, matching ordinary git-trailer convention.
    assert (
        parse_checkpoint_marker("Checkpoint: implementation-complete\nCheckpoint: tests-passing\n")
        == "tests-passing"
    )


def test_from_scratch_when_no_commits_exist() -> None:
    decision = decide([], base_revision="base-sha")
    assert decision.action == "FROM_SCRATCH"
    assert decision.last_marker is None
    assert decision.resume_head is None


def test_continue_from_a_single_valid_marker() -> None:
    commits = [_commit("sha1", "implementation-complete")]
    decision = decide(commits, base_revision="base-sha")
    assert decision.action == "CONTINUE_FROM"
    assert decision.last_marker == "implementation-complete"
    assert decision.resume_head == "sha1"


def test_continue_from_both_markers_present_and_correctly_ordered() -> None:
    commits = [
        _commit("sha1", "implementation-complete"),
        _commit("sha2", "tests-passing"),
    ]
    decision = decide(commits, base_revision="base-sha")
    assert decision.action == "CONTINUE_FROM"
    assert decision.last_marker == "tests-passing"
    assert decision.resume_head == "sha2"


def test_escalate_when_commits_exist_but_none_carry_a_recognized_marker() -> None:
    commits = [
        _commit("sha1", None),
        _commit("sha2", "some-unrelated-trailer"),
    ]
    decision = decide(commits, base_revision="base-sha")
    assert decision.action == "ESCALATE"
    assert decision.resume_head is None
    assert "recognized" in decision.reason.lower()


def test_escalate_when_tests_passing_appears_with_no_prior_implementation_complete() -> None:
    commits = [_commit("sha1", "tests-passing")]
    decision = decide(commits, base_revision="base-sha")
    assert decision.action == "ESCALATE"
    assert decision.resume_head is None
    assert "no earlier" in decision.reason.lower()


def test_escalate_when_tests_passing_precedes_implementation_complete_in_the_list() -> None:
    # Both markers present, but in the wrong chronological order -- still an ordering violation,
    # not a clean two-marker resume.
    commits = [
        _commit("sha1", "tests-passing"),
        _commit("sha2", "implementation-complete"),
    ]
    decision = decide(commits, base_revision="base-sha")
    assert decision.action == "ESCALATE"


def test_escalate_when_the_most_recent_commit_has_no_marker_even_though_an_earlier_one_did() -> None:
    commits = [
        _commit("sha1", "implementation-complete"),
        _commit("sha2", None),
    ]
    decision = decide(commits, base_revision="base-sha")
    assert decision.action == "ESCALATE"
    assert decision.resume_head is None


def test_decide_never_mutates_or_reorders_the_input_list() -> None:
    commits = [
        _commit("sha1", "implementation-complete"),
        _commit("sha2", "tests-passing"),
    ]
    original = list(commits)
    decide(commits, base_revision="base-sha")
    assert commits == original
