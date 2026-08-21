"""Packaging provenance regressions found during the PR 148 review."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.package_skill import _shared_script


def test_shared_runtime_script_must_come_from_packaged_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "other-checkout"
    (repo / "scripts").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="git_paths.py"):
        _shared_script(repo, "git_paths.py", "shared Git path helper")


def test_shared_runtime_script_rejects_symlink_outside_packaged_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "checkout"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    outside = tmp_path / "outside_git_paths.py"
    outside.write_text("# foreign helper\n", encoding="utf-8")
    (scripts / "git_paths.py").symlink_to(outside)

    with pytest.raises(ValueError, match="outside selected source repository"):
        _shared_script(repo, "git_paths.py", "shared Git path helper")
