"""Plugin bundle build: the generic bundle's file set plus .claude-plugin/.codex-plugin.

Security/symlink/sensitive-file rejection is not re-tested here -- the plugin bundle reuses
_is_safe_file/_tracked_files unchanged, and that logic already has dedicated coverage in
test_generic_package_security.py.
"""

from __future__ import annotations

import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pytest

from scripts.registry import cli as registry_cli
from scripts.registry.generic_package import build_generic_package, build_plugin_package

ROOT = Path(__file__).resolve().parents[2]


def test_registry_package_plugin_command(tmp_path: Path) -> None:
    output = tmp_path / "plugin.tar.gz"
    assert registry_cli.main(["package-plugin", "--output", str(output)]) == 0
    assert output.is_file()


@dataclass(frozen=True)
class _BuiltPluginPackage:
    member_names: frozenset[str]
    packaged_root: Path


@pytest.fixture(scope="module")
def plugin_package(tmp_path_factory: pytest.TempPathFactory) -> _BuiltPluginPackage:
    tmp_path = tmp_path_factory.mktemp("plugin-package")
    output = tmp_path / "plugin.tar.gz"
    build_plugin_package(ROOT, output)

    extract_root = tmp_path / "extract"
    with tarfile.open(output, "r:gz") as archive:
        names = frozenset(member.name for member in archive.getmembers())
        archive.extractall(extract_root, filter="data")

    return _BuiltPluginPackage(
        member_names=names,
        packaged_root=extract_root / "software-builder",
    )


def test_plugin_package_is_a_strict_superset_of_the_generic_package(
    tmp_path_factory: pytest.TempPathFactory,
    plugin_package: _BuiltPluginPackage,
) -> None:
    generic_tmp = tmp_path_factory.mktemp("generic-for-comparison")
    generic_output = generic_tmp / "generic.tar.gz"
    build_generic_package(ROOT, generic_output)
    with tarfile.open(generic_output, "r:gz") as archive:
        generic_names = frozenset(member.name for member in archive.getmembers())

    assert generic_names <= plugin_package.member_names


def test_plugin_package_carries_both_plugin_manifests(plugin_package: _BuiltPluginPackage) -> None:
    names = plugin_package.member_names
    assert "software-builder/.claude-plugin/plugin.json" in names
    assert "software-builder/.claude-plugin/marketplace.json" in names
    assert "software-builder/.codex-plugin/plugin.json" in names


def test_plugin_package_manifests_resolve_to_a_real_populated_skills_dir(
    plugin_package: _BuiltPluginPackage,
) -> None:
    import json

    claude_plugin = json.loads(
        (plugin_package.packaged_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"),
    )
    codex_plugin = json.loads(
        (plugin_package.packaged_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"),
    )
    assert claude_plugin["skills"] == "./skills"
    assert codex_plugin["skills"] == "./skills"

    skills_dir = plugin_package.packaged_root / "skills"
    assert skills_dir.is_dir()
    assert any(skills_dir.rglob("SKILL.md"))


def test_plugin_package_members_are_plain_relative_files(plugin_package: _BuiltPluginPackage) -> None:
    assert all(
        not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
        for name in plugin_package.member_names
    )
