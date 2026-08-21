"""Regression for repository replace refs hiding staged write conflicts."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.test_creator_write_guard import check_write_safety


def _git(repo: Path, *args: str, input_text: str | None = None) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        input=input_text,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_guard_ignores_replace_refs_when_detecting_staged_target(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "review@example.invalid")
    _git(repo, "config", "user.name", "Final Review")
    target = repo / "generated_test.py"
    target.write_text("committed\n", encoding="utf-8")
    _git(repo, "add", "generated_test.py")
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")

    target.write_text("staged user change\n", encoding="utf-8")
    _git(repo, "add", "generated_test.py")
    head = _git(repo, "rev-parse", "HEAD")
    staged_tree = _git(repo, "write-tree")
    replacement = _git(repo, "commit-tree", staged_tree, input_text="replacement\n")
    _git(repo, "replace", head, replacement)
    assert _git(repo, "status", "--porcelain=v1") == ""

    result = check_write_safety(repo, ["generated_test.py"])

    assert result.status == "BLOCKED"
    assert result.conflicting_paths == ("generated_test.py",)
    assert result.dirty_paths_before == ("generated_test.py",)
