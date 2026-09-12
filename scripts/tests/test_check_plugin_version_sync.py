"""Tests for scripts.check_plugin_version_sync validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_plugin_version_sync import drifted_plugin_versions


def _write_repo(tmp_path: Path, *, version: str) -> None:
    """Write a minimal repo with VERSION and required directories."""
    (tmp_path / "VERSION").write_text(f"{version}\n", encoding="utf-8")


def _write_plugin_manifest(tmp_path: Path, *, version: str) -> None:
    """Write .codex-plugin/plugin.json with the given version."""
    plugin_dir = tmp_path / ".codex-plugin"
    plugin_dir.mkdir(exist_ok=True)
    (plugin_dir / "plugin.json").write_text(
        f'{{"name": "software-builder", "version": "{version}"}}\n',
        encoding="utf-8",
    )


def _write_cli_pyproject(tmp_path: Path, *, version: str) -> None:
    cli_dir = tmp_path / "cli"
    cli_dir.mkdir(exist_ok=True)
    (cli_dir / "pyproject.toml").write_text(
        f'[project]\nname = "software-builder-cli"\nversion = "{version}"\n',
        encoding="utf-8",
    )


def test_plugin_manifest_version_drift_is_reported(tmp_path: Path) -> None:
    _write_repo(tmp_path, version="1.4.0")
    _write_plugin_manifest(tmp_path, version="1.3.0")

    errors = drifted_plugin_versions(tmp_path)

    assert any(".codex-plugin/plugin.json" in error and "1.3.0" in error for error in errors)


def test_plugin_manifest_matching_version_reports_no_drift(tmp_path: Path) -> None:
    _write_repo(tmp_path, version="1.4.0")
    _write_plugin_manifest(tmp_path, version="1.4.0")

    assert drifted_plugin_versions(tmp_path) == []


def test_cli_pyproject_version_drift_is_reported(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.4.0\n", encoding="utf-8")
    _write_cli_pyproject(tmp_path, version="1.3.0")

    errors = drifted_plugin_versions(tmp_path)

    assert any("cli/pyproject.toml" in error and "1.3.0" in error for error in errors)


def test_cli_pyproject_matching_version_reports_no_drift(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.4.0\n", encoding="utf-8")
    _write_cli_pyproject(tmp_path, version="1.4.0")

    assert drifted_plugin_versions(tmp_path) == []
