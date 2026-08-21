"""Executable-resolution regressions for the test-creator write guard."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.test_creator_write_guard import check_write_safety


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "review@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Final Review"], cwd=repo, check=True)
    (repo / "project").mkdir()
    (repo / "project" / "tracked.py").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=repo, check=True)
    return repo


def _submodule_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "review@example.invalid"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "Final Review"], cwd=source, check=True)
    (source / "tracked.py").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=source, check=True)
    return source


def _install_git_shim(repo: Path, marker: Path, real_git: str) -> Path:
    bin_dir = repo / "tools"
    bin_dir.mkdir(exist_ok=True)
    shim = bin_dir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        f"printf executed > {str(marker)!r}\n"
        f"exec {real_git!r} \"$@\"\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return bin_dir


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable shim regression")
def test_nested_repo_root_rejects_git_shim_from_enclosing_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path)
    nested = repo / "project"
    real_git = shutil.which("git")
    assert real_git is not None
    marker = tmp_path / "enclosing-git-executed"
    bin_dir = _install_git_shim(repo, marker, real_git)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    result = check_write_safety(nested, ["generated_test.py"])

    assert result.status == "ALLOWED"
    assert not marker.exists(), "guard executed git shim controlled by enclosing worktree"


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable shim regression")
def test_selected_submodule_rejects_git_shim_from_superproject(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path)
    source = _submodule_source(tmp_path)
    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "submodule", "add", str(source), "modules/child"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", ".gitmodules", "modules/child"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "submodule"], cwd=repo, check=True)

    real_git = shutil.which("git")
    assert real_git is not None
    marker = tmp_path / "superproject-git-executed"
    bin_dir = _install_git_shim(repo, marker, real_git)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    result = check_write_safety(repo / "modules" / "child", ["generated_test.py"])

    assert result.status == "ALLOWED"
    assert not marker.exists(), "guard executed git shim controlled by enclosing superproject"


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable shim regression")
def test_linked_worktree_rejects_git_shim_from_original_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path)
    linked = tmp_path / "linked-worktree"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "review-linked", str(linked)],
        cwd=repo,
        check=True,
    )

    real_git = shutil.which("git")
    assert real_git is not None
    marker = tmp_path / "original-checkout-git-executed"
    bin_dir = _install_git_shim(repo, marker, real_git)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    result = check_write_safety(linked, ["generated_test.py"])

    assert result.status == "ALLOWED"
    assert not marker.exists(), "guard executed git shim controlled by original checkout"
