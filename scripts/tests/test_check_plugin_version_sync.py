"""Tests for scripts/check_plugin_version_sync.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.check_plugin_version_sync import drifted_plugin_versions, main


def _write_repo(tmp_path: Path, *, distribution_version: str, plugin_version: str) -> Path:
    (tmp_path / "VERSION").write_text(f"{distribution_version}\n", encoding="utf-8")
    plugin_dir = tmp_path / ".codex-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "software-builder", "version": plugin_version}),
        encoding="utf-8",
    )
    return tmp_path


def test_matching_versions_report_no_drift(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path, distribution_version="1.4.0", plugin_version="1.4.0")
    assert drifted_plugin_versions(repo) == []


def test_mismatched_versions_are_reported(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path, distribution_version="1.4.0", plugin_version="0.1.0")
    errors = drifted_plugin_versions(repo)
    assert len(errors) == 1
    assert ".codex-plugin/plugin.json" in errors[0]
    assert "0.1.0" in errors[0]
    assert "1.4.0" in errors[0]


def test_missing_plugin_manifest_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.4.0\n", encoding="utf-8")
    assert drifted_plugin_versions(tmp_path) == []


def test_main_exits_nonzero_on_drift(tmp_path: Path, capsys) -> None:
    repo = _write_repo(tmp_path, distribution_version="1.4.0", plugin_version="0.1.0")
    exit_code = main(["--repo-root", str(repo)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "0.1.0" in captured.err


def test_main_exits_zero_when_clean(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path, distribution_version="1.4.0", plugin_version="1.4.0")
    assert main(["--repo-root", str(repo)]) == 0
