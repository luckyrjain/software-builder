"""Tests for discovery-precedence shadow detection (Candidate 8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.registry.host_registry import parse_host_registry

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def host_registry():
    return parse_host_registry(ROOT / "agent-hosts.yaml")


def _write_install(dest: Path, *, files: dict[str, str] | None = None) -> None:
    dest.mkdir(parents=True)
    manifest = {"skill": dest.name, "files": files or {"SKILL.md": "abc123"}}
    (dest / ".software-builder-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_none_when_no_higher_precedence_root_has_the_skill(host_registry, tmp_path: Path) -> None:
    from scripts.registry.shadow_detector import SHADOW_NONE, detect_shadow

    home = tmp_path / "home"
    written = home / ".claude" / "skills" / "pr-review"
    _write_install(written)

    result = detect_shadow(
        host_registry, "claude", "claude-user", written, home=home, target_dir=None
    )
    assert result.status == SHADOW_NONE
    assert result.shadowing_path is None


def test_shadowed_when_higher_precedence_root_has_different_content(
    host_registry, tmp_path: Path
) -> None:
    from scripts.registry.shadow_detector import SHADOW_SHADOWED, detect_shadow

    home = tmp_path / "home"
    project = tmp_path / "project"
    written = home / ".claude" / "skills" / "pr-review"
    _write_install(written, files={"SKILL.md": "user-version-hash"})
    higher = project / ".claude" / "skills" / "pr-review"
    _write_install(higher, files={"SKILL.md": "project-version-hash"})

    result = detect_shadow(
        host_registry, "claude", "claude-user", written, home=home, target_dir=project
    )
    assert result.status == SHADOW_SHADOWED
    assert result.shadowing_path == higher


def test_duplicate_identical_when_higher_precedence_root_has_the_same_content(
    host_registry, tmp_path: Path
) -> None:
    from scripts.registry.shadow_detector import SHADOW_DUPLICATE_IDENTICAL, detect_shadow

    home = tmp_path / "home"
    project = tmp_path / "project"
    same_files = {"SKILL.md": "identical-hash"}
    written = home / ".claude" / "skills" / "pr-review"
    _write_install(written, files=same_files)
    higher = project / ".claude" / "skills" / "pr-review"
    _write_install(higher, files=same_files)

    result = detect_shadow(
        host_registry, "claude", "claude-user", written, home=home, target_dir=project
    )
    assert result.status == SHADOW_DUPLICATE_IDENTICAL
    assert result.shadowing_path == higher


def test_unknown_precedence_when_higher_precedence_root_has_unreadable_manifest(
    host_registry, tmp_path: Path
) -> None:
    from scripts.registry.shadow_detector import SHADOW_UNKNOWN_PRECEDENCE, detect_shadow

    home = tmp_path / "home"
    project = tmp_path / "project"
    written = home / ".claude" / "skills" / "pr-review"
    _write_install(written)
    higher = project / ".claude" / "skills" / "pr-review"
    higher.mkdir(parents=True)
    (higher / ".software-builder-manifest.json").write_text("{not valid json", encoding="utf-8")

    result = detect_shadow(
        host_registry, "claude", "claude-user", written, home=home, target_dir=project
    )
    assert result.status == SHADOW_UNKNOWN_PRECEDENCE
    assert result.shadowing_path == higher


def test_none_when_higher_precedence_root_directory_does_not_exist(
    host_registry, tmp_path: Path
) -> None:
    from scripts.registry.shadow_detector import SHADOW_NONE, detect_shadow

    home = tmp_path / "home"
    project = tmp_path / "project"
    written = home / ".claude" / "skills" / "pr-review"
    _write_install(written)

    result = detect_shadow(
        host_registry, "claude", "claude-user", written, home=home, target_dir=project
    )
    assert result.status == SHADOW_NONE


def test_none_when_written_target_is_already_the_highest_precedence(
    host_registry, tmp_path: Path
) -> None:
    """Writing to claude-project (precedence 10) has nothing higher above it to check."""
    from scripts.registry.shadow_detector import SHADOW_NONE, detect_shadow

    project = tmp_path / "project"
    written = project / ".claude" / "skills" / "pr-review"
    _write_install(written)

    result = detect_shadow(
        host_registry, "claude", "claude-project", written, home=tmp_path / "home", target_dir=project
    )
    assert result.status == SHADOW_NONE


def test_none_when_written_target_id_is_unknown_for_the_host(host_registry, tmp_path: Path) -> None:
    from scripts.registry.shadow_detector import SHADOW_NONE, detect_shadow

    written = tmp_path / "somewhere" / "pr-review"
    _write_install(written)

    result = detect_shadow(
        host_registry, "claude", "not-a-real-target", written, home=tmp_path, target_dir=None
    )
    assert result.status == SHADOW_NONE
