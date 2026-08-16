from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

from scripts.package_release import package_release
from scripts.release_info import read_distribution_version

ROOT = Path(__file__).resolve().parents[2]


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)


def _commit_all(root: Path) -> str:
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    # -c commit.gpgsign=false: don't inherit the invoking machine's global Git
    # signing config -- a contributor or CI runner with commit signing turned
    # on (common under org policy) would otherwise have every fixture commit
    # here block on a passphrase/hardware-key prompt or fail outright.
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=root, check=True
    )
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def _minimal_repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _init_repo(root)
    (root / "VERSION").write_text("2.3.4\n", encoding="utf-8")
    (root / "skills.yaml").write_text("schema_version: 1\nskills: {}\n", encoding="utf-8")
    (root / "scripts" / "registry").mkdir(parents=True)
    (root / "scripts" / "registry" / "host_contracts.yaml").write_text(
        "schema_version: 1\nhosts: {}\n", encoding="utf-8"
    )
    (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
    sha = _commit_all(root)
    return root, sha


def test_distribution_version_fails_closed_when_missing_or_invalid(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        read_distribution_version(tmp_path)

    (tmp_path / "VERSION").write_text("latest\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_distribution_version(tmp_path)


def test_release_contract_validates_repository() -> None:
    from scripts.release_contract import validate_release_contract

    assert validate_release_contract(ROOT) == []


def test_release_inputs_ignore_untracked_files_and_reject_tracked_symlinks(tmp_path: Path) -> None:
    root, _ = _minimal_repo(tmp_path)
    (root / "local-secret.txt").write_text("must-not-ship\n", encoding="utf-8")

    output = tmp_path / "out"
    output.mkdir()
    archive, _ = package_release(root, output)
    with tarfile.open(archive, "r:gz") as tar:
        names = set(tar.getnames())
    assert not any(name.endswith("local-secret.txt") for name in names)

    target = root / "README.md"
    link = root / "linked-readme.md"
    os.symlink(target.name, link)
    subprocess.run(["git", "add", "linked-readme.md"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "add symlink"], cwd=root, check=True
    )
    with pytest.raises(ValueError, match="symlink"):
        package_release(root, output)


def test_release_bundle_is_byte_reproducible_for_same_git_tree(tmp_path: Path) -> None:
    root, _ = _minimal_repo(tmp_path)
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    out_a.mkdir()
    out_b.mkdir()

    archive_a, _ = package_release(root, out_a)
    archive_b, _ = package_release(root, out_b)

    assert hashlib.sha256(archive_a.read_bytes()).hexdigest() == hashlib.sha256(
        archive_b.read_bytes()
    ).hexdigest()


def test_release_manifest_has_exact_provenance_and_file_hashes(tmp_path: Path) -> None:
    root, sha = _minimal_repo(tmp_path)
    output = tmp_path / "out"
    output.mkdir()
    archive, _ = package_release(root, output)

    with tarfile.open(archive, "r:gz") as tar:
        manifest_member = next(m for m in tar.getmembers() if m.name.endswith("/RELEASE-MANIFEST.json"))
        manifest = json.loads(tar.extractfile(manifest_member).read())

    assert manifest["schema_version"] == 1
    assert manifest["distribution_version"] == "2.3.4"
    assert manifest["source_sha"] == sha
    assert manifest["registry_schema_version"] == 1
    assert manifest["host_contract_schema_version"] == 1
    assert manifest["files"]
    assert all(len(digest) == 64 for digest in manifest["files"].values())


def test_release_bundle_verifier_accepts_clean_bundle_and_rejects_tampering(tmp_path: Path) -> None:
    from scripts.verify_release_bundle import verify_release_bundle

    root, _ = _minimal_repo(tmp_path)
    output = tmp_path / "out"
    output.mkdir()
    archive, _ = package_release(root, output)
    assert verify_release_bundle(archive) == []

    tampered = tmp_path / "tampered.tar.gz"
    extract = tmp_path / "extract"
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(extract)
    readme = next(extract.rglob("README.md"))
    readme.write_text("tampered\n", encoding="utf-8")
    root_dir = next(extract.iterdir())
    with tarfile.open(tampered, "w:gz") as tar:
        tar.add(root_dir, arcname=root_dir.name)

    errors = verify_release_bundle(tampered)
    assert any("hash mismatch" in error for error in errors)


def test_release_workflow_runs_contract_and_bundle_verification_before_upload() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    contract_at = workflow.index("release_contract")
    bundle_at = workflow.index("verify_release_bundle")
    upload_at = workflow.index("Upload release assets")
    assert contract_at < upload_at
    assert bundle_at < upload_at
