"""Tests for scripts/check_sensitive_path_bypass.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_sensitive_path_bypass as csp  # noqa: E402
import sensitive_path_match  # noqa: E402


def make_spec(globs: list[str], content_patterns: list[str]) -> sensitive_path_match.SensitivePathList:
    import re

    return sensitive_path_match.SensitivePathList(
        globs=tuple(globs),
        content_patterns=tuple(re.compile(p) for p in content_patterns),
        content_pattern_sources=tuple(content_patterns),
    )


SENSITIVE_DIFF = "diff --git a/scripts/install_engine.py b/scripts/install_engine.py\n+flock(fd, LOCK_EX)\n"
NON_SENSITIVE_DIFF = "diff --git a/docs/readme.md b/docs/readme.md\n+hello\n"


def check_run(name: str, conclusion: str) -> dict[str, Any]:
    return {"name": name, "conclusion": conclusion}


# --- check_run_succeeded -----------------------------------------------------------------------


def test_check_run_succeeded_true() -> None:
    assert csp.check_run_succeeded([check_run("review-evidence-check", "success")], "review-evidence-check")


def test_check_run_succeeded_false_wrong_name() -> None:
    assert not csp.check_run_succeeded([check_run("lint-static", "success")], "review-evidence-check")


def test_check_run_succeeded_false_not_success() -> None:
    assert not csp.check_run_succeeded([check_run("review-evidence-check", "failure")], "review-evidence-check")


def test_check_run_succeeded_false_empty() -> None:
    assert not csp.check_run_succeeded([], "review-evidence-check")


# --- fetch_check_runs_for_merged_pr: the LENS-B-1 squash-merge-SHA regression ------------------


def test_fetch_check_runs_for_merged_pr_queries_head_sha_not_only_merge_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The core PR #298 remediation regression (LENS-B-1): this repo is squash-only, so a merged
    PR's `mergeCommit.oid` is a brand-new SHA distinct from `headRefOid`, the SHA
    `review-evidence-check`/`-post` actually ran against -- GitHub's Checks API never copies
    check-runs onto the new squash-merge commit. A fixture where check-runs exist *only* against
    `headRefOid`, and querying `mergeCommit.oid` returns nothing, must still be found -- the
    original implementation (querying `mergeCommit.oid` alone) would have returned `[]` here and
    silently reported a false bypass."""
    calls: list[str] = []

    def _fake_fetch_check_runs(repo: str, sha: str) -> list[dict[str, Any]]:
        calls.append(sha)
        if sha == "head_sha_only":
            return [check_run("review-evidence-check", "success")]
        return []  # the merge commit SHA has no check-runs recorded against it at all

    monkeypatch.setattr(csp, "fetch_check_runs", _fake_fetch_check_runs)

    check_runs = csp.fetch_check_runs_for_merged_pr(
        "o/r", head_sha="head_sha_only", merge_sha="merge_sha_distinct",
    )

    assert csp.check_run_succeeded(check_runs, "review-evidence-check")
    # Both SHAs were queried (defense-in-depth), not just the merge commit.
    assert set(calls) == {"head_sha_only", "merge_sha_distinct"}


def test_fetch_check_runs_for_merged_pr_skips_merge_sha_query_when_equal_to_head_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(csp, "fetch_check_runs", lambda repo, sha: calls.append(sha) or [])

    csp.fetch_check_runs_for_merged_pr("o/r", head_sha="same_sha", merge_sha="same_sha")

    assert calls == ["same_sha"]


def test_fetch_check_runs_for_merged_pr_handles_missing_merge_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(csp, "fetch_check_runs", lambda repo, sha: calls.append(sha) or [])

    csp.fetch_check_runs_for_merged_pr("o/r", head_sha="head_only", merge_sha=None)

    assert calls == ["head_only"]


def test_run_end_to_end_finds_check_run_on_head_sha_when_merge_sha_differs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """End-to-end version of the same regression through `_run`: a merged, sensitive PR whose
    `review-evidence-check` run only exists against its `headRefOid` (never its `mergeCommit.oid`,
    which is what a squash merge always produces) must NOT be reported as a bypass."""
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")

    prs = [
        {
            "number": 104,
            "mergedAt": "2026-01-01T00:00:00Z",
            "mergeCommit": {"oid": "squash_merge_sha_104"},
            "headRefOid": "pr_head_sha_104",
            "files": [{"path": "scripts/install_engine.py"}],
        },
    ]
    monkeypatch.setattr(csp, "fetch_merged_prs", lambda repo, since_days: prs)
    monkeypatch.setattr(csp.check_review_evidence, "fetch_pr_diff", lambda repo, pr: SENSITIVE_DIFF)

    def _fake_fetch_check_runs(repo: str, sha: str) -> list[dict[str, Any]]:
        # Check-runs exist only against the PR's head SHA -- never the squash-merge commit,
        # matching GitHub's real behavior for a squash-only repo.
        if sha == "pr_head_sha_104":
            return [check_run("review-evidence-check", "success"), check_run("review-evidence-post", "success")]
        return []

    monkeypatch.setattr(csp, "fetch_check_runs", _fake_fetch_check_runs)

    def _boom(*_a: Any, **_k: Any) -> None:
        raise AssertionError("must not report a bypass -- review-evidence-check passed on the head SHA")

    monkeypatch.setattr(csp, "ensure_bypass_issue", _boom)
    monkeypatch.setattr(csp, "ensure_bot_health_issue", _boom)

    rc = csp._run("o/r", since_days=8, sensitive_path_list=spec_path, dry_run=False)
    assert rc == 0


# --- classify_merged_pr: the core bypass decision -----------------------------------------------


def test_classify_merged_pr_not_sensitive_no_bypass() -> None:
    spec = make_spec(["scripts/install_engine.py"], [r"\bflock\("])
    pr = {"number": 1, "mergedAt": "2026-01-01T00:00:00Z", "files": [{"path": "docs/readme.md"}]}
    result, record = csp.classify_merged_pr(pr, spec=spec, diff_text=NON_SENSITIVE_DIFF, check_runs=[])
    assert not result.sensitive
    assert record is None


def test_classify_merged_pr_sensitive_with_passing_check_no_bypass() -> None:
    spec = make_spec(["scripts/install_engine.py"], [r"\bflock\("])
    pr = {"number": 2, "mergedAt": "2026-01-01T00:00:00Z", "files": [{"path": "scripts/install_engine.py"}]}
    check_runs = [check_run("review-evidence-check", "success")]
    result, record = csp.classify_merged_pr(pr, spec=spec, diff_text=SENSITIVE_DIFF, check_runs=check_runs)
    assert result.sensitive
    assert record is None


def test_classify_merged_pr_sensitive_without_passing_check_is_bypass() -> None:
    spec = make_spec(["scripts/install_engine.py"], [r"\bflock\("])
    pr = {"number": 3, "mergedAt": "2026-01-02T00:00:00Z", "files": [{"path": "scripts/install_engine.py"}]}
    result, record = csp.classify_merged_pr(pr, spec=spec, diff_text=SENSITIVE_DIFF, check_runs=[])
    assert result.sensitive
    assert record is not None
    assert record["number"] == 3
    assert record["merged_at"] == "2026-01-02T00:00:00Z"


def test_classify_merged_pr_sensitive_with_failing_check_is_bypass() -> None:
    spec = make_spec(["scripts/install_engine.py"], [r"\bflock\("])
    pr = {"number": 4, "mergedAt": "2026-01-02T00:00:00Z", "files": [{"path": "scripts/install_engine.py"}]}
    check_runs = [check_run("review-evidence-check", "failure")]
    result, record = csp.classify_merged_pr(pr, spec=spec, diff_text=SENSITIVE_DIFF, check_runs=check_runs)
    assert result.sensitive
    assert record is not None


# --- bot_credential_health: architecture review Condition 2 --------------------------------------


def test_bot_credential_health_none_when_no_sensitive_prs() -> None:
    assert csp.bot_credential_health([]) is None


def test_bot_credential_health_true_when_a_post_succeeded() -> None:
    runs = [[check_run("review-evidence-post", "success")], [check_run("review-evidence-post", "failure")]]
    assert csp.bot_credential_health(runs) is True


def test_bot_credential_health_false_when_none_succeeded() -> None:
    runs = [[check_run("review-evidence-post", "failure")], []]
    assert csp.bot_credential_health(runs) is False


# --- tracking_issue_exists / open_tracking_issue: dedup -------------------------------------------


def test_tracking_issue_exists_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        csp.check_review_evidence,
        "run_gh",
        lambda args: json.dumps(
            [{"number": 1, "title": "[sensitive-path-bypass] PR #9: merged without a passing review-evidence-check run"}],
        ),
    )
    assert csp.tracking_issue_exists("o/r", "[sensitive-path-bypass] PR #9")


def test_tracking_issue_exists_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(csp.check_review_evidence, "run_gh", lambda args: json.dumps([]))
    assert not csp.tracking_issue_exists("o/r", "[sensitive-path-bypass] PR #9")


def test_open_tracking_issue_dry_run_does_not_call_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(args: list[str]) -> str:
        raise AssertionError("gh must not be called in --dry-run mode")

    monkeypatch.setattr(csp.check_review_evidence, "run_gh", _boom)
    csp.open_tracking_issue("o/r", "title", "body", dry_run=True)


def test_open_tracking_issue_calls_gh_issue_create(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def _fake_run_gh(args: list[str]) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(csp.check_review_evidence, "run_gh", _fake_run_gh)
    csp.open_tracking_issue("o/r", "title", "body", dry_run=False)
    assert calls[0][:2] == ["issue", "create"]


def test_ensure_bypass_issue_skips_when_already_tracked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(csp, "tracking_issue_exists", lambda repo, marker: True)

    def _boom(*_a: Any, **_k: Any) -> None:
        raise AssertionError("must not open a duplicate tracking issue")

    monkeypatch.setattr(csp, "open_tracking_issue", _boom)
    record = {"number": 9, "merged_at": "2026-01-01", "matched_globs": [], "matched_content_patterns": []}
    csp.ensure_bypass_issue("o/r", record, dry_run=False)


def test_ensure_bypass_issue_opens_when_not_tracked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(csp, "tracking_issue_exists", lambda repo, marker: False)
    opened: list[tuple[str, str]] = []
    monkeypatch.setattr(csp, "open_tracking_issue", lambda repo, title, body, dry_run: opened.append((title, body)))
    record = {
        "number": 9,
        "merged_at": "2026-01-01",
        "matched_globs": ["scripts/install_engine.py"],
        "matched_content_patterns": [],
    }
    csp.ensure_bypass_issue("o/r", record, dry_run=False)
    assert len(opened) == 1
    assert "PR #9" in opened[0][0]


# --- report_own_failure: the self-alerting-on-its-own-failure property, tested directly -----------


def test_report_own_failure_opens_a_distinct_marker_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(csp, "tracking_issue_exists", lambda repo, marker: False)
    opened: list[tuple[str, str]] = []
    monkeypatch.setattr(csp, "open_tracking_issue", lambda repo, title, body, dry_run: opened.append((title, body)))

    csp.report_own_failure("o/r", RuntimeError("boom"), dry_run=False)

    assert len(opened) == 1
    title, body = opened[0]
    assert csp.ALERTER_FAILURE_MARKER in title
    assert "boom" in body


def test_report_own_failure_dedupes_when_already_tracked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(csp, "tracking_issue_exists", lambda repo, marker: True)

    def _boom(*_a: Any, **_k: Any) -> None:
        raise AssertionError("must not open a second alerter-failure issue")

    monkeypatch.setattr(csp, "open_tracking_issue", _boom)

    csp.report_own_failure("o/r", RuntimeError("boom again"), dry_run=False)
    assert "boom again" in capsys.readouterr().err


def test_report_own_failure_survives_its_own_issue_creation_failing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Last-resort: even if opening the failure-tracking issue itself fails,
    report_own_failure must not raise past main() uncaught -- it degrades to stderr."""
    monkeypatch.setattr(csp, "tracking_issue_exists", lambda repo, marker: False)

    def _boom(*_a: Any, **_k: Any) -> None:
        raise csp.check_review_evidence.GhApiError("gh issue create failed too")

    monkeypatch.setattr(csp, "open_tracking_issue", _boom)

    csp.report_own_failure("o/r", RuntimeError("original failure"), dry_run=False)
    err = capsys.readouterr().err
    assert "gh issue create failed too" in err
    assert "original failure" in err


# --- main(): the alerter path end to end ---------------------------------------------------------


def test_main_returns_2_and_alerts_on_unhandled_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: Any, **_k: Any) -> int:
        raise RuntimeError("scan blew up")

    monkeypatch.setattr(csp, "_run", _boom)

    reported: list[BaseException] = []
    monkeypatch.setattr(csp, "report_own_failure", lambda repo, exc, dry_run: reported.append(exc))

    rc = csp.main(["--repo", "o/r"])
    assert rc == 2
    assert len(reported) == 1
    assert "scan blew up" in str(reported[0])


def test_main_exit_2_on_malformed_sensitive_path_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: []\ncontent_patterns: []\n")

    reported: list[BaseException] = []
    monkeypatch.setattr(csp, "report_own_failure", lambda repo, exc, dry_run: reported.append(exc))

    rc = csp.main(["--repo", "o/r", "--sensitive-path-list", str(spec_path)])
    assert rc == 2
    assert reported


# --- _run: end-to-end orchestration with fully mocked I/O -----------------------------------------


def test_run_end_to_end_detects_bypass_and_files_issue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")

    prs = [
        {
            "number": 100,
            "mergedAt": "2026-01-01T00:00:00Z",
            "mergeCommit": {"oid": "sha100"},
            "files": [{"path": "scripts/install_engine.py"}],
        },
    ]
    monkeypatch.setattr(csp, "fetch_merged_prs", lambda repo, since_days: prs)
    monkeypatch.setattr(csp.check_review_evidence, "fetch_pr_diff", lambda repo, pr: SENSITIVE_DIFF)
    monkeypatch.setattr(csp, "fetch_check_runs", lambda repo, sha: [])  # no passing check-run: a bypass

    opened: list[tuple[str, str]] = []
    monkeypatch.setattr(csp, "tracking_issue_exists", lambda repo, marker: False)
    monkeypatch.setattr(csp, "open_tracking_issue", lambda repo, title, body, dry_run: opened.append((title, body)))

    rc = csp._run("o/r", since_days=8, sensitive_path_list=spec_path, dry_run=False)
    assert rc == 0
    titles = [title for title, _ in opened]
    assert any("PR #100" in title for title in titles)


def test_run_end_to_end_no_bypass_when_check_passed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")

    prs = [
        {
            "number": 101,
            "mergedAt": "2026-01-01T00:00:00Z",
            "mergeCommit": {"oid": "sha101"},
            "files": [{"path": "scripts/install_engine.py"}],
        },
    ]
    monkeypatch.setattr(csp, "fetch_merged_prs", lambda repo, since_days: prs)
    monkeypatch.setattr(csp.check_review_evidence, "fetch_pr_diff", lambda repo, pr: SENSITIVE_DIFF)
    monkeypatch.setattr(
        csp,
        "fetch_check_runs",
        lambda repo, sha: [check_run("review-evidence-check", "success"), check_run("review-evidence-post", "success")],
    )

    def _boom(*_a: Any, **_k: Any) -> None:
        raise AssertionError("must not open any tracking issue when the check passed and the bot is healthy")

    monkeypatch.setattr(csp, "ensure_bypass_issue", _boom)
    monkeypatch.setattr(csp, "ensure_bot_health_issue", _boom)

    rc = csp._run("o/r", since_days=8, sensitive_path_list=spec_path, dry_run=False)
    assert rc == 0


def test_run_end_to_end_flags_unhealthy_bot_credential(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")

    prs = [
        {
            "number": 102,
            "mergedAt": "2026-01-01T00:00:00Z",
            "mergeCommit": {"oid": "sha102"},
            "files": [{"path": "scripts/install_engine.py"}],
        },
    ]
    monkeypatch.setattr(csp, "fetch_merged_prs", lambda repo, since_days: prs)
    monkeypatch.setattr(csp.check_review_evidence, "fetch_pr_diff", lambda repo, pr: SENSITIVE_DIFF)
    # review-evidence-check passed (e.g. a genuine human approval) but review-evidence-post never
    # ran successfully anywhere in the scan window.
    monkeypatch.setattr(csp, "fetch_check_runs", lambda repo, sha: [check_run("review-evidence-check", "success")])

    bot_health_titles: list[str] = []
    monkeypatch.setattr(csp, "tracking_issue_exists", lambda repo, marker: False)
    monkeypatch.setattr(csp, "open_tracking_issue", lambda repo, title, body, dry_run: bot_health_titles.append(title))

    rc = csp._run("o/r", since_days=8, sensitive_path_list=spec_path, dry_run=False)
    assert rc == 0
    assert any(csp.BOT_HEALTH_MARKER in title for title in bot_health_titles)


def test_run_skips_pr_without_merge_commit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")

    prs = [{"number": 103, "mergedAt": "2026-01-01T00:00:00Z", "mergeCommit": None, "files": []}]
    monkeypatch.setattr(csp, "fetch_merged_prs", lambda repo, since_days: prs)

    def _boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("must not fetch a diff for a PR with no merge commit")

    monkeypatch.setattr(csp.check_review_evidence, "fetch_pr_diff", _boom)

    rc = csp._run("o/r", since_days=8, sensitive_path_list=spec_path, dry_run=False)
    assert rc == 0
