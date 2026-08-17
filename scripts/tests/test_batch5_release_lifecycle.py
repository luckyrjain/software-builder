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


# package_release()/verify_release_bundle() read a repo's/bundle's *own*
# scripts/release_contract.yaml (not this real repo's) for the manifest
# field-set and schema-version compatibility checks, so any fixture repo that
# calls package_release() needs one committed too -- mirrors this repo's own
# scripts/release_contract.yaml just enough to satisfy those checks against
# the minimal skills.yaml/host_contracts.yaml fixtures below.
_MINIMAL_RELEASE_CONTRACT = """\
schema_version: 1
tag_pattern: '^v\\d+\\.\\d+\\.\\d+$'
artifact_name_templates:
  - "software-builder-{version}.tar.gz"
compatibility:
  registry_schema_version: 1
  host_contract_schema_version: 1
provenance:
  required_fields:
    - schema_version
    - distribution_version
    - source_sha
    - registry_schema_version
    - host_contract_schema_version
    - supported_hosts
    - skill_versions
    - files
"""


def _write_minimal_release_contract(root: Path) -> None:
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "release_contract.yaml").write_text(_MINIMAL_RELEASE_CONTRACT, encoding="utf-8")


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
    _write_minimal_release_contract(root)
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


def test_release_inputs_reject_tracked_submodule(tmp_path: Path) -> None:
    # A submodule reference is a "gitlink" tree entry (mode 160000) -- neither a
    # symlink nor a regular file on disk. Without an explicit check it would
    # silently vanish from the release instead of erroring: abs_path.is_symlink()
    # and abs_path.is_file() are both False for a submodule path, so it would
    # just never be added to _tracked_files()'s output.
    root, _ = _minimal_repo(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()
    _init_repo(sub)
    (sub / "f.txt").write_text("hi\n", encoding="utf-8")
    _commit_all(sub)

    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "vendor/sub"],
        cwd=root,
        check=True,
    )
    _commit_all(root)

    output = tmp_path / "out"
    output.mkdir()
    with pytest.raises(ValueError, match="submodule"):
        package_release(root, output)


def test_release_inputs_exclude_tracked_repo_dev_tooling(tmp_path: Path) -> None:
    # git ls-files can't distinguish "untracked build noise" from "tracked
    # repo-development tooling" -- only the untracked half is naturally solved
    # by sourcing release inputs from Git. .cursor/.kiro/.agents/.claude-plugin/
    # .codex-plugin/.gitignore are all committed to *this* repo (generated
    # per-host IDE rules, plugin manifests, etc. for developing software-builder
    # itself) but must still never ship in a release bundle meant for someone
    # installing a skill via install.sh.
    root = tmp_path / "repo"
    root.mkdir()
    _init_repo(root)
    (root / "VERSION").write_text("2.3.4\n", encoding="utf-8")
    (root / "skills.yaml").write_text("schema_version: 1\nskills: {}\n", encoding="utf-8")
    (root / "scripts" / "registry").mkdir(parents=True)
    (root / "scripts" / "registry" / "host_contracts.yaml").write_text(
        "schema_version: 1\nhosts: {}\n", encoding="utf-8"
    )
    _write_minimal_release_contract(root)
    (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
    (root / ".gitignore").write_text("dist/\n", encoding="utf-8")
    (root / ".cursor" / "rules").mkdir(parents=True)
    (root / ".cursor" / "rules" / "example.mdc").write_text("rule\n", encoding="utf-8")
    (root / ".kiro").mkdir()
    (root / ".kiro" / "steering.md").write_text("steering\n", encoding="utf-8")
    (root / ".github").mkdir()
    (root / ".github" / "keep-me.txt").write_text("kept\n", encoding="utf-8")
    # Nested, not just top-level: a per-skill .cursor/.kiro/.gitignore buried
    # under another directory must be excluded too, not only one sitting at
    # the repo root -- the top-level-only dotdir catch-all
    # (parts[0].startswith(".")) wouldn't catch this since parts[0] here is
    # "some-skill", not ".cursor"/".gitignore", and (unlike .cursor/.kiro)
    # .gitignore isn't excluded at any depth unless _EXCLUDED_PATH_COMPONENTS
    # lists it explicitly.
    (root / "some-skill" / ".cursor" / "rules").mkdir(parents=True)
    (root / "some-skill" / ".cursor" / "rules" / "nested.mdc").write_text("rule\n", encoding="utf-8")
    (root / "some-skill" / ".gitignore").write_text("build/\n", encoding="utf-8")
    _commit_all(root)

    output = tmp_path / "out"
    output.mkdir()
    archive, _ = package_release(root, output)
    with tarfile.open(archive, "r:gz") as tar:
        names = set(tar.getnames())
    assert not any(".cursor/" in name for name in names)
    assert not any(".kiro/" in name for name in names)
    assert not any(name.endswith(".gitignore") for name in names)
    # .github is the one dotdir release bundles have always carried.
    assert any(name.endswith(".github/keep-me.txt") for name in names)
    # Nested repo-dev tooling (checked above at the top level) is excluded under
    # some-skill/ too, not only at the repo root.
    assert not any("some-skill/.cursor/" in name for name in names)
    assert not any(name.endswith("some-skill/.gitignore") for name in names)


def test_release_manifest_rejects_registered_but_untracked_skill(tmp_path: Path) -> None:
    # skill_versions() (scripts/registry/manifest.py) reads a registered skill's
    # SKILL.md straight off the working-tree filesystem, like read_schema_version()
    # does for skills.yaml/host_contracts.yaml -- none of them go through
    # _tracked_files()'s git-tracked-only filter. _ensure_clean_worktree() only
    # diffs already-tracked paths against HEAD, so it can't see a wholly new
    # untracked path either. Without _ensure_manifest_inputs_tracked(), committing
    # skills.yaml with a new skill entry before `git add`-ing that skill's own
    # directory would silently produce a RELEASE-MANIFEST.json whose
    # skill_versions names a skill with zero corresponding files in the archive.
    root, _ = _minimal_repo(tmp_path)
    skills_yaml = root / "skills.yaml"
    skills_yaml.write_text(
        "schema_version: 1\n"
        "skills:\n"
        "  ghost-skill:\n"
        "    path: ghost-skill\n"
        "    category: test\n"
        "    invocation: ambient\n"
        "    hosts:\n"
        "      cursor: {discovery: manual}\n"
        "      kiro: {discovery: manual}\n"
        "    install:\n"
        "      requires: []\n"
        "    lint: {}\n"
        "    risk_class: [read-only]\n",
        encoding="utf-8",
    )
    _commit_all(root)

    # ghost-skill/SKILL.md exists on disk but was never `git add`ed.
    (root / "ghost-skill").mkdir()
    (root / "ghost-skill" / "SKILL.md").write_text(
        "---\nskill_version: 1.0.0\ndescription: ghost\n---\n# Ghost\n",
        encoding="utf-8",
    )

    output = tmp_path / "out"
    output.mkdir()
    with pytest.raises(ValueError, match="ghost-skill/SKILL.md"):
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
    # _minimal_repo's host_contracts.yaml/skills.yaml declare no hosts/skills,
    # so these are present but empty -- this still pins the field's presence
    # and shape (list / mapping), which release_contract.yaml's
    # provenance.required_fields mandates every manifest carry.
    assert manifest["supported_hosts"] == []
    assert manifest["skill_versions"] == {}
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
