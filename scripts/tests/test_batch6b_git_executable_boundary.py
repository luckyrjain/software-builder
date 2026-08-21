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
    bin_dir = repo / "tools"
    bin_dir.mkdir()
    shim = bin_dir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        f"printf executed > {str(marker)!r}\n"
        f"exec {real_git!r} \"$@\"\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    result = check_write_safety(nested, ["generated_test.py"])

    assert result.status == "ALLOWED"
    assert not marker.exists(), "guard executed git shim controlled by enclosing worktree"
