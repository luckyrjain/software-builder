"""Adversarial regressions for the Batch 6B test-creator write guard."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.test_creator_write_guard import check_write_safety

ROOT = Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(
        repo,
        "-c",
        "user.name=Batch 6B",
        "-c",
        "user.email=batch6b@example.invalid",
        "commit",
        "-qm",
        "initial",
    )
    return repo


def _commit_file(repo: Path, rel: str) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("committed\n", encoding="utf-8")
    _git(repo, "add", rel)
    _git(
        repo,
        "-c",
        "user.name=Batch 6B",
        "-c",
        "user.email=batch6b@example.invalid",
        "commit",
        "-qm",
        f"add {rel}",
    )
    return path


def test_guard_rejects_planned_git_metadata_path(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    result = check_write_safety(repo, [".git/hooks/generated-test-hook"])

    assert result.status == "BLOCKED"
    assert "git metadata" in result.reason.lower()


@pytest.mark.parametrize("index_flag", ["--assume-unchanged", "--skip-worktree"])
def test_guard_blocks_index_protected_planned_file(tmp_path: Path, index_flag: str) -> None:
    repo = _repo(tmp_path)
    planned = _commit_file(repo, "generated_test.py")
    _git(repo, "update-index", index_flag, "generated_test.py")
    planned.write_text("user change hidden from ordinary status\n", encoding="utf-8")

    result = check_write_safety(repo, ["generated_test.py"])

    assert result.status == "BLOCKED"
    assert result.conflicting_paths == ("generated_test.py",)
    assert "index-protected" in result.reason.lower()


def test_guard_ignores_ambient_git_repository_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _repo(tmp_path / "target")
    decoy = _repo(tmp_path / "decoy")
    target_file = _commit_file(target, "generated_test.py")
    _commit_file(decoy, "generated_test.py")
    target_file.write_text("user change\n", encoding="utf-8")

    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))
    result = check_write_safety(target, ["generated_test.py"])

    assert result.status == "BLOCKED"
    assert result.conflicting_paths == ("generated_test.py",)
    assert result.dirty_paths_before == ("generated_test.py",)


def test_packaged_guard_does_not_import_target_repo_git_helper(tmp_path: Path) -> None:
    bundle_scripts = tmp_path / "bundle" / "scripts"
    bundle_scripts.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "test_creator_write_guard.py", bundle_scripts)
    shutil.copy2(ROOT / "scripts" / "git_paths.py", bundle_scripts)

    repo = _repo(tmp_path / "target")
    target_scripts = repo / "scripts"
    target_scripts.mkdir()
    (target_scripts / "__init__.py").write_text("", encoding="utf-8")
    (target_scripts / "git_paths.py").write_text(
        'raise RuntimeError("target repository helper was imported")\n',
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(repo)

    completed = subprocess.run(
        [
            sys.executable,
            str(bundle_scripts / "test_creator_write_guard.py"),
            "--repo-root",
            str(repo),
            "--planned-file",
            "generated_test.py",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "ALLOWED"
