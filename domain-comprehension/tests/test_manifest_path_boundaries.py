"""Path-boundary regression tests for validate_manifest_yaml.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_manifest_yaml import validate_manifest  # noqa: E402

pytest.importorskip("yaml")


def _manifest() -> dict:
    import yaml

    return yaml.safe_load((ROOT / "templates" / "manifest.yaml").read_text(encoding="utf-8"))


def test_rejects_absolute_artifact_path() -> None:
    data = _manifest()
    data["artifacts"][0]["path"] = "/tmp/domain-config.yaml"
    errors = validate_manifest(data)
    assert any("artifacts[0].path must be a relative path" in error for error in errors)


def test_rejects_parent_traversal_artifact_path() -> None:
    data = _manifest()
    data["artifacts"][0]["path"] = "../domain-config.yaml"
    errors = validate_manifest(data)
    assert any("artifacts[0].path must be a relative path" in error for error in errors)


def test_rejects_windows_parent_traversal_artifact_path() -> None:
    data = _manifest()
    data["artifacts"][0]["path"] = "..\\domain-config.yaml"
    errors = validate_manifest(data)
    assert any("artifacts[0].path must be a relative path" in error for error in errors)


def test_rejects_absolute_map_file() -> None:
    data = _manifest()
    data["engagement"]["map_file"] = "/tmp/DOMAIN_MAP.md"
    errors = validate_manifest(data)
    assert any("engagement.map_file must be a relative path" in error for error in errors)


def test_rejects_windows_absolute_artifact_root() -> None:
    data = _manifest()
    data["engagement"]["artifact_root"] = "C:\\temp\\domain"
    errors = validate_manifest(data)
    assert any("engagement.artifact_root must be a relative path" in error for error in errors)


def test_valid_nested_artifact_root_resolves_under_workspace(tmp_path: Path) -> None:
    data = _manifest()
    data["engagement"]["artifact_root"] = "docs/domain-comprehension/repayment"
    data["artifacts"][0]["status"] = "stub"
    target = tmp_path / "docs" / "domain-comprehension" / "repayment"
    target.mkdir(parents=True)
    (target / "domain-config.yaml").write_text("domain: {}\n", encoding="utf-8")

    errors = validate_manifest(data, workspace_root=tmp_path)
    assert not any("domain-config.yaml" in error for error in errors)
