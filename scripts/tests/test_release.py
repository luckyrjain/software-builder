"""Tests for release packaging."""

from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _minimal_release_repo(tmp_path: Path) -> Path:
    # package_release() requires a clean Git worktree (_ensure_clean_worktree)
    # and reads inputs from `git ls-files`, so this builds a small isolated Git
    # repo rather than pointing at ROOT -- pointing at ROOT made this test fail
    # on any uncommitted edit to a tracked file anywhere in the real repo, even
    # one with nothing to do with release packaging.
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    (root / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    (root / "skills.yaml").write_text("schema_version: 1\nskills: {}\n", encoding="utf-8")
    (root / "scripts" / "registry").mkdir(parents=True)
    (root / "scripts" / "registry" / "host_contracts.yaml").write_text(
        "schema_version: 1\nhosts: {}\n", encoding="utf-8"
    )
    # package_release() validates its manifest's field set against root's own
    # scripts/release_contract.yaml (not this real repo's), so this fixture needs
    # a minimal one of its own too.
    (root / "scripts" / "release_contract.yaml").write_text(
        "schema_version: 1\n"
        "tag_pattern: '^v\\d+\\.\\d+\\.\\d+$'\n"
        "artifact_name_templates:\n"
        '  - "software-builder-{version}.tar.gz"\n'
        "compatibility:\n"
        "  registry_schema_version: 1\n"
        "  host_contract_schema_version: 1\n"
        "provenance:\n"
        "  required_fields:\n"
        "    - schema_version\n"
        "    - distribution_version\n"
        "    - source_sha\n"
        "    - registry_schema_version\n"
        "    - host_contract_schema_version\n"
        "    - supported_hosts\n"
        "    - skill_versions\n"
        "    - executable_files\n"
        "    - files\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    # -c commit.gpgsign=false: don't depend on the invoking machine's global
    # Git signing config (commit signing turned on would otherwise block this
    # fixture commit on a passphrase/hardware-key prompt or fail outright).
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=root, check=True
    )
    return root


def test_package_release_writes_checksums(tmp_path: Path) -> None:
    from scripts.package_release import package_release

    repo = _minimal_release_repo(tmp_path)
    output = tmp_path / "out"
    output.mkdir()
    archive_path, checksum_path = package_release(repo, output)
    assert archive_path.is_file()
    assert checksum_path.is_file()
    assert "software-builder-" in archive_path.name

    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
    assert any(name.endswith("VERSION") for name in names)
    assert any(name.endswith("skills.yaml") for name in names)
