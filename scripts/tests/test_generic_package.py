"""Generic (host-neutral) package build: what it contains and what it refuses.

The host adapter interface that selects this bundle lives in
test_host_portability.py.
"""

from __future__ import annotations

import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pytest

from scripts.registry import cli as registry_cli
from scripts.registry.generic_package import (
    _is_safe_file,
    _markdown_targets,
    _packaged_bytes,
    _strip_non_runtime_links,
    _tracked_files,
    _validate_output_path,
    build_generic_package,
)
from scripts.registry.schema import parse_registry
from scripts.validate_references import validate_files

ROOT = Path(__file__).resolve().parents[2]


def test_registry_package_generic_command(tmp_path: Path) -> None:
    output = tmp_path / "generic.tar.gz"
    assert registry_cli.main(["package-generic", "--output", str(output)]) == 0
    assert output.is_file()


def test_generic_package_uses_only_git_tracked_files(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    tracked = tmp_path / "tracked.md"
    tracked.write_text("# Tracked\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.md"], check=True)
    untracked = tmp_path / "id_rsa"
    untracked.write_text("PRIVATE MATERIAL\n", encoding="utf-8")

    tracked_files = _tracked_files(tmp_path.resolve())
    assert tracked.resolve() in tracked_files
    assert untracked.resolve() not in tracked_files


def test_generic_package_rejects_untracked_markdown_targets_and_bad_anchors(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    target = tmp_path / "target.md"
    source.write_text("[target](target.md)\n", encoding="utf-8")
    target.write_text("# Valid heading\n", encoding="utf-8")
    with pytest.raises(ValueError, match="untracked file"):
        _markdown_targets(tmp_path, source, {source})

    source.write_text("[target](target.md#missing)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dangling markdown anchor"):
        _markdown_targets(tmp_path, source, {source, target})

    source.write_text("[target](target.md#valid-heading)\n", encoding="utf-8")
    assert _markdown_targets(tmp_path, source, {source, target}) == {target}


def test_generic_package_strips_only_non_runtime_changelog_links() -> None:
    source = ROOT / "release-readiness-checker" / "reference" / "gate-policy.md"
    packaged = _packaged_bytes(ROOT, source).decode("utf-8")
    assert "[CHANGELOG.md](../CHANGELOG.md)" not in packaged
    assert "CHANGELOG.md" in packaged
    assert "[phase-0.md](../../pr-review/workflow/phase-0.md)" in packaged

    sample = "[history](CHANGELOG.md)\n![image](CHANGELOG.md)\n```md\n[example](CHANGELOG.md)\n```\n"
    rewritten = _strip_non_runtime_links(sample)
    assert rewritten.startswith("history\n")
    assert "![image](CHANGELOG.md)" in rewritten
    assert "[example](CHANGELOG.md)" in rewritten


def test_generic_package_refuses_ci_sensitive_and_self_including_paths(tmp_path: Path) -> None:
    github_file = tmp_path / ".github" / "workflow.yml"
    github_file.parent.mkdir()
    github_file.write_text("name: test\n", encoding="utf-8")
    assert _is_safe_file(tmp_path, github_file) is False

    tests_file = tmp_path / "skill" / "tests" / "fixture.yaml"
    tests_file.parent.mkdir(parents=True)
    tests_file.write_text("payload: adversarial\n", encoding="utf-8")
    assert _is_safe_file(tmp_path, tests_file) is False

    secret = tmp_path / ".env.local"
    secret.write_text("TOKEN=example\n", encoding="utf-8")
    with pytest.raises(ValueError, match="potentially sensitive"):
        _is_safe_file(tmp_path, secret)

    mixed_case_secret = tmp_path / "Credentials.JSON"
    mixed_case_secret.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="potentially sensitive"):
        _is_safe_file(tmp_path, mixed_case_secret)

    mixed_case_env = tmp_path / ".ENV.production"
    mixed_case_env.write_text("TOKEN=example\n", encoding="utf-8")
    with pytest.raises(ValueError, match="potentially sensitive"):
        _is_safe_file(tmp_path, mixed_case_env)

    mixed_case_changelog = tmp_path / "Changelog.MD"
    mixed_case_changelog.write_text("history\n", encoding="utf-8")
    assert _is_safe_file(tmp_path, mixed_case_changelog) is False

    with pytest.raises(ValueError, match="output inside repository"):
        _validate_output_path(tmp_path, tmp_path / "skill" / "bundle.tar.gz")
    with pytest.raises(ValueError, match="output inside repository"):
        _validate_output_path(tmp_path, tmp_path / ".git" / "bundle.tar.gz")
    _validate_output_path(tmp_path, tmp_path / "dist" / "bundle.tar.gz")
    _validate_output_path(tmp_path, tmp_path.parent / "outside.tar.gz")


@dataclass(frozen=True)
class _BuiltGenericPackage:
    """One build of the generic package, shared by the assertions below."""

    first_bytes: bytes
    second_bytes: bytes
    member_names: frozenset[str]
    all_members_are_files: bool
    packaged_root: Path


@pytest.fixture(scope="module")
def generic_package(tmp_path_factory: pytest.TempPathFactory) -> _BuiltGenericPackage:
    """Build and extract the generic package once for the assertions that read it.

    Building costs ~2.5s, so the five independent properties below share one
    build rather than each paying for their own -- but they stay five separate
    tests, so a determinism regression is reported as a determinism failure
    instead of being hidden behind whichever assertion happens to run first.
    """
    tmp_path = tmp_path_factory.mktemp("generic-package")
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    build_generic_package(ROOT, first)
    build_generic_package(ROOT, second)

    extract_root = tmp_path / "extract"
    with tarfile.open(first, "r:gz") as archive:
        members = archive.getmembers()
        names = frozenset(member.name for member in members)
        all_files = all(member.isfile() for member in members)
        archive.extractall(extract_root, filter="data")

    return _BuiltGenericPackage(
        first_bytes=first.read_bytes(),
        second_bytes=second.read_bytes(),
        member_names=names,
        all_members_are_files=all_files,
        packaged_root=extract_root / "software-builder",
    )


def test_generic_package_build_is_byte_deterministic(generic_package: _BuiltGenericPackage) -> None:
    assert generic_package.first_bytes == generic_package.second_bytes


def test_generic_package_members_are_plain_relative_files(generic_package: _BuiltGenericPackage) -> None:
    assert generic_package.all_members_are_files
    assert all(
        not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
        for name in generic_package.member_names
    )


def test_generic_package_carries_every_registered_skill(generic_package: _BuiltGenericPackage) -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    names = generic_package.member_names
    for skill_id, entry in registry.skills.items():
        assert f"software-builder/{entry.path}/SKILL.md" in names, skill_id
    assert "software-builder/README.md" in names
    assert "software-builder/skills.yaml" in names
    assert "software-builder/docs/skill-framework/shared/skill-routing.md" in names
    assert "software-builder/docs/skill-framework/shared/runtime-contract.md" in names


def test_generic_package_excludes_non_runtime_paths(generic_package: _BuiltGenericPackage) -> None:
    names = generic_package.member_names
    assert not any("/.git/" in f"/{name}/" or "/.github/" in f"/{name}/" for name in names)
    assert not any("/dist/" in f"/{name}/" for name in names)
    assert not any("/tests/" in f"/{name}/" for name in names)
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
    assert not any(PurePosixPath(name).name.lower() == "changelog.md" for name in names)


def test_generic_package_markdown_links_resolve(generic_package: _BuiltGenericPackage) -> None:
    markdown_files = sorted(generic_package.packaged_root.rglob("*.md"))
    assert validate_files(markdown_files) == []
