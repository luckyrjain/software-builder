"""Regressions for test-creator writes crossing nested Git boundaries."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.test_creator_write_guard import check_write_safety


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "review@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Final Review"], cwd=path, check=True)
    (path / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=path, check=True)
    return path


def _repo_with_submodule(tmp_path: Path) -> Path:
    source = _init_repo(tmp_path / "source")
    repo = _init_repo(tmp_path / "repo")
    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "submodule", "add", str(source), "modules/child"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", ".gitmodules", "modules/child"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "submodule"], cwd=repo, check=True)
    return repo


def _assert_nested_repo_block(repo: Path, planned: str = "modules/child/generated_test.py") -> None:
    result = check_write_safety(repo, [planned])

    assert result.status == "BLOCKED"
    assert "nested git repository" in result.reason.lower()


def test_guard_rejects_new_file_inside_initialized_submodule(tmp_path: Path) -> None:
    _assert_nested_repo_block(_repo_with_submodule(tmp_path))


def test_guard_rejects_new_file_inside_deinitialized_submodule(tmp_path: Path) -> None:
    repo = _repo_with_submodule(tmp_path)
    subprocess.run(
        ["git", "submodule", "deinit", "-f", "--", "modules/child"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )

    _assert_nested_repo_block(repo)


def test_guard_rejects_new_file_inside_unregistered_nested_repo(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _init_repo(repo / "vendor" / "nested")

    _assert_nested_repo_block(repo, "vendor/nested/generated_test.py")
