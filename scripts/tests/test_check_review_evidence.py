"""Tests for scripts/check_review_evidence.py (review-evidence-check / review-evidence-analyze)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_review_evidence as cre  # noqa: E402
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


def review(login: str, state: str, commit_id: str, submitted_at: str) -> dict[str, Any]:
    return {
        "user": {"login": login},
        "state": state,
        "commit_id": commit_id,
        "submitted_at": submitted_at,
    }


# --- parse_paginated_json ------------------------------------------------------------------


def test_parse_paginated_json_single_page() -> None:
    # Each top-level decoded value is one page's own body (an array, for the reviews endpoint) --
    # parse_paginated_json doesn't flatten it itself; callers (fetch_pr_reviews) do that.
    assert cre.parse_paginated_json(json.dumps([{"a": 1}])) == [[{"a": 1}]]


def test_parse_paginated_json_empty_string() -> None:
    assert cre.parse_paginated_json("") == []


def test_parse_paginated_json_multiple_concatenated_pages() -> None:
    """`gh api ... --paginate` concatenates each page's JSON body with no separator."""
    text = json.dumps([{"a": 1}]) + json.dumps([{"b": 2}])
    assert cre.parse_paginated_json(text) == [[{"a": 1}], [{"b": 2}]]


def test_parse_paginated_json_malformed_raises() -> None:
    with pytest.raises(cre.GhApiError):
        cre.parse_paginated_json("{not json")


# --- most_recent_review_per_login: the round-3 same-commit staleness fix -------------------


def test_most_recent_review_per_login_picks_the_later_one() -> None:
    reviews = [
        review("alice", "APPROVED", "sha1", "2026-01-01T00:00:00Z"),
        review("alice", "CHANGES_REQUESTED", "sha1", "2026-01-02T00:00:00Z"),
    ]
    latest = cre.most_recent_review_per_login(reviews)
    assert latest["alice"]["state"] == "CHANGES_REQUESTED"


def test_most_recent_review_per_login_ignores_pending() -> None:
    reviews = [review("alice", "PENDING", "sha1", "")]
    assert cre.most_recent_review_per_login(reviews) == {}


def test_most_recent_review_per_login_independent_per_reviewer() -> None:
    reviews = [
        review("alice", "APPROVED", "sha1", "2026-01-01T00:00:00Z"),
        review("bob", "CHANGES_REQUESTED", "sha1", "2026-01-01T00:00:00Z"),
    ]
    latest = cre.most_recent_review_per_login(reviews)
    assert latest["alice"]["state"] == "APPROVED"
    assert latest["bob"]["state"] == "CHANGES_REQUESTED"


# --- has_valid_approval: SHA binding, author exclusion, stale-verdict rejection -------------


def test_has_valid_approval_true_for_clean_approval() -> None:
    reviews = [review("alice", "APPROVED", "sha_head", "2026-01-01T00:00:00Z")]
    assert cre.has_valid_approval(reviews, head_sha="sha_head", author_login="bob")


def test_has_valid_approval_false_when_only_author_approved() -> None:
    reviews = [review("bob", "APPROVED", "sha_head", "2026-01-01T00:00:00Z")]
    assert not cre.has_valid_approval(reviews, head_sha="sha_head", author_login="bob")


def test_has_valid_approval_is_case_insensitive_on_author_login() -> None:
    reviews = [review("Bob", "APPROVED", "sha_head", "2026-01-01T00:00:00Z")]
    assert not cre.has_valid_approval(reviews, head_sha="sha_head", author_login="bob")


def test_has_valid_approval_false_for_stale_commit() -> None:
    """A stale APPROVED from an earlier commit must not satisfy a newer head (round-1 fix)."""
    reviews = [review("alice", "APPROVED", "sha_old", "2026-01-01T00:00:00Z")]
    assert not cre.has_valid_approval(reviews, head_sha="sha_new", author_login="bob")


def test_has_valid_approval_false_when_latest_verdict_is_changes_requested() -> None:
    """A reviewer who approved and then later left CHANGES_REQUESTED at the *same* commit no
    longer counts (round-3 finding 8 -- same-commit staleness)."""
    reviews = [
        review("alice", "APPROVED", "sha_head", "2026-01-01T00:00:00Z"),
        review("alice", "CHANGES_REQUESTED", "sha_head", "2026-01-02T00:00:00Z"),
    ]
    assert not cre.has_valid_approval(reviews, head_sha="sha_head", author_login="bob")


def test_has_valid_approval_true_when_re_approved_after_changes_requested() -> None:
    reviews = [
        review("alice", "CHANGES_REQUESTED", "sha_head", "2026-01-01T00:00:00Z"),
        review("alice", "APPROVED", "sha_head", "2026-01-02T00:00:00Z"),
    ]
    assert cre.has_valid_approval(reviews, head_sha="sha_head", author_login="bob")


def test_has_valid_approval_false_with_no_reviews() -> None:
    assert not cre.has_valid_approval([], head_sha="sha_head", author_login="bob")


# --- run_check: the three exit codes --------------------------------------------------------


def test_run_check_exit_0_not_sensitive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")

    monkeypatch.setattr(cre, "fetch_pr_metadata", lambda repo, pr: ("sha_head", "author"))
    monkeypatch.setattr(cre, "fetch_pr_diff", lambda repo, pr: NON_SENSITIVE_DIFF)

    def _boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("fetch_pr_reviews must not be called for a non-sensitive PR")

    monkeypatch.setattr(cre, "fetch_pr_reviews", _boom)

    assert cre.run_check(repo="o/r", pr_number=1, sensitive_path_list=spec_path) == 0


def test_run_check_exit_0_sensitive_with_approval(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")

    monkeypatch.setattr(cre, "fetch_pr_metadata", lambda repo, pr: ("sha_head", "author"))
    monkeypatch.setattr(cre, "fetch_pr_diff", lambda repo, pr: SENSITIVE_DIFF)
    monkeypatch.setattr(
        cre,
        "fetch_pr_reviews",
        lambda repo, pr: [review("reviewer", "APPROVED", "sha_head", "2026-01-01T00:00:00Z")],
    )

    assert cre.run_check(repo="o/r", pr_number=1, sensitive_path_list=spec_path) == 0


def test_run_check_exit_1_sensitive_evidence_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")

    monkeypatch.setattr(cre, "fetch_pr_metadata", lambda repo, pr: ("sha_head", "author"))
    monkeypatch.setattr(cre, "fetch_pr_diff", lambda repo, pr: SENSITIVE_DIFF)
    monkeypatch.setattr(cre, "fetch_pr_reviews", lambda repo, pr: [])

    assert cre.run_check(repo="o/r", pr_number=1, sensitive_path_list=spec_path) == 1


def test_run_check_exit_2_malformed_sensitive_path_list(tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: []\ncontent_patterns: []\n")
    assert cre.run_check(repo="o/r", pr_number=1, sensitive_path_list=spec_path) == 2


def test_run_check_exit_2_gh_api_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")

    def _boom(repo: str, pr: int) -> Any:
        raise cre.GhApiError("network is down")

    monkeypatch.setattr(cre, "fetch_pr_metadata", _boom)

    assert cre.run_check(repo="o/r", pr_number=1, sensitive_path_list=spec_path) == 2


def test_run_check_exit_2_reviews_api_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")

    monkeypatch.setattr(cre, "fetch_pr_metadata", lambda repo, pr: ("sha_head", "author"))
    monkeypatch.setattr(cre, "fetch_pr_diff", lambda repo, pr: SENSITIVE_DIFF)

    def _boom(repo: str, pr: int) -> Any:
        raise cre.GhApiError("reviews API down")

    monkeypatch.setattr(cre, "fetch_pr_reviews", _boom)

    assert cre.run_check(repo="o/r", pr_number=1, sensitive_path_list=spec_path) == 2


# --- build_verdict / run_analyze (review-evidence-analyze) ---------------------------------


def test_build_verdict_none_for_non_sensitive() -> None:
    spec = make_spec(["scripts/install_engine.py"], [r"\bflock\("])
    assert cre.build_verdict(spec, NON_SENSITIVE_DIFF, pr_number=1) is None


def test_build_verdict_blocks_for_sensitive_phase_0() -> None:
    """Phase 0 has no real review pass wired up (architecture review Condition 1 still open) --
    every sensitive PR must get a fail-closed 'block' verdict, never an invented 'approve'."""
    spec = make_spec(["scripts/install_engine.py"], [r"\bflock\("])
    verdict = cre.build_verdict(spec, SENSITIVE_DIFF, pr_number=42)
    assert verdict is not None
    assert verdict["verdict"] == "block"
    assert verdict["pr_number"] == 42


def test_run_analyze_writes_no_artifact_for_non_sensitive_pr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")
    out_path = tmp_path / "verdict.json"

    monkeypatch.setattr(cre, "fetch_pr_diff", lambda repo, pr: NON_SENSITIVE_DIFF)

    rc = cre.run_analyze(repo="o/r", pr_number=1, sensitive_path_list=spec_path, out_path=out_path)
    assert rc == 0
    assert not out_path.exists()


def test_run_analyze_writes_block_artifact_for_sensitive_pr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")
    out_path = tmp_path / "verdict.json"

    monkeypatch.setattr(cre, "fetch_pr_diff", lambda repo, pr: SENSITIVE_DIFF)

    rc = cre.run_analyze(repo="o/r", pr_number=7, sensitive_path_list=spec_path, out_path=out_path)
    assert rc == 0
    written = json.loads(out_path.read_text())
    assert written["verdict"] == "block"
    assert written["pr_number"] == 7


def test_run_analyze_exit_2_on_malformed_list(tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: []\ncontent_patterns: []\n")
    out_path = tmp_path / "verdict.json"
    assert cre.run_analyze(repo="o/r", pr_number=1, sensitive_path_list=spec_path, out_path=out_path) == 2


# --- CLI routing: bare `--pr N` means `check --pr N` -----------------------------------------


def test_main_bare_pr_flag_routes_to_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")

    monkeypatch.setattr(cre, "fetch_pr_metadata", lambda repo, pr: ("sha_head", "author"))
    monkeypatch.setattr(cre, "fetch_pr_diff", lambda repo, pr: NON_SENSITIVE_DIFF)

    rc = cre.main(["--pr", "5", "--repo", "o/r", "--sensitive-path-list", str(spec_path)])
    assert rc == 0


def test_main_analyze_subcommand_routes_to_run_analyze(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec_path = tmp_path / "sensitive-paths.yaml"
    spec_path.write_text("globs: [scripts/install_engine.py]\ncontent_patterns: ['\\\\bflock\\\\b']\n")
    out_path = tmp_path / "verdict.json"

    monkeypatch.setattr(cre, "fetch_pr_diff", lambda repo, pr: NON_SENSITIVE_DIFF)

    rc = cre.main(
        ["analyze", "--pr", "5", "--repo", "o/r", "--sensitive-path-list", str(spec_path), "--out", str(out_path)],
    )
    assert rc == 0
    assert not out_path.exists()
