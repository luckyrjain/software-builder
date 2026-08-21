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
