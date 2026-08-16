"""Tests for self-contained skill packaging."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from package_skill import package_skill  # noqa: E402
from reference_utils import copytree_ignore  # noqa: E402
from validate_references import validate_tree  # noqa: E402


@pytest.fixture
def isolated_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "software-builder"
    shutil.copytree(ROOT / "unit-test-creator", repo / "unit-test-creator")
    shutil.copytree(ROOT / "docs" / "skill-framework", repo / "docs" / "skill-framework")
    specs = ROOT / "docs" / "superpowers" / "specs"
    if specs.is_dir():
        shutil.copytree(specs, repo / "docs" / "superpowers" / "specs")
    (repo / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    # -c commit.gpgsign=false: don't depend on the invoking machine's global
    # Git signing config (commit signing turned on would otherwise block this
    # fixture commit on a passphrase/hardware-key prompt or fail outright).
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=repo, check=True)
    return repo


def test_package_skill_vendors_framework_and_validates(isolated_repo: Path, tmp_path: Path) -> None:
    dest = tmp_path / "installed" / "unit-test-creator"
    package_skill(
        skill="unit-test-creator",
        repo_root=isolated_repo,
        dest=dest,
        host="cursor",
    )

    framework_readme = dest / "docs" / "skill-framework" / "README.md"
    assert framework_readme.is_file()

    skill_md = dest / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    assert "../docs/skill-framework/" not in text
    assert "docs/skill-framework/shared/test-creation-principles.md" in text

    manifest = json.loads((dest / ".software-builder-manifest.json").read_text(encoding="utf-8"))
    assert manifest["skill"] == "unit-test-creator"
    assert manifest["host"] == "cursor"
    assert "shared/test-creation-principles.md" in manifest["framework_files"]

    errors = validate_tree(dest, check_anchors=False, installed_package=True)
    assert errors == []


def test_copytree_ignore_handles_symlinked_subdirectory(tmp_path: Path) -> None:
    # copytree_ignore() used to .resolve() both `root` and the `directory`
    # shutil passes into ignore() -- fine for a plain tree, but
    # shutil.copytree (called with the default symlinks=False) follows a
    # symlinked subdirectory by recursing into it without ever resolving
    # paths itself, so a symlink pointing outside `root` made `directory`
    # jump to its real target on resolve while `root` stayed put, and
    # relative_to(root) raised ValueError instead of shutil.copytree ever
    # completing.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real.md").write_text("vendored content\n", encoding="utf-8")

    src = tmp_path / "src"
    src.mkdir()
    (src / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    (src / "linked").symlink_to(outside)

    dst = tmp_path / "dst"
    shutil.copytree(src, dst, ignore=copytree_ignore(src))

    assert (dst / "SKILL.md").is_file()
    assert (dst / "linked" / "real.md").read_text(encoding="utf-8") == "vendored content\n"


def test_package_and_verify_agree_on_ignored_source_files(isolated_repo: Path, tmp_path: Path) -> None:
    # Packaging (copytree_ignore) and the manifest verify walks in
    # install_support.py used to apply the ignore patterns via two
    # independently-maintained mechanisms that could disagree -- a source
    # file matching one of the shared noise patterns (an editor backup file,
    # say) would be silently dropped by copytree at packaging time in some
    # cases and not others depending on which code path touched it, and a
    # nested noise directory wasn't excluded consistently either. This
    # exercises the full package -> verify round trip end to end, the one
    # check that would have caught every divergence found in review.
    (isolated_repo / "unit-test-creator" / "notes~").write_text("scratch\n", encoding="utf-8")

    dest = tmp_path / "installed" / "unit-test-creator"
    package_skill(skill="unit-test-creator", repo_root=isolated_repo, dest=dest, host="cursor")

    assert not (dest / "notes~").exists()
    manifest = json.loads((dest / ".software-builder-manifest.json").read_text(encoding="utf-8"))
    assert "notes~" not in manifest["files"]

    from scripts.install_support import cmd_verify

    assert cmd_verify(dest) == 0


def test_prd_architect_package_contains_executable_safe_output_renderer(tmp_path: Path) -> None:
    repo = tmp_path / "software-builder"
    shutil.copytree(ROOT / "prd-architect", repo / "prd-architect")
    shutil.copytree(ROOT / "docs" / "skill-framework", repo / "docs" / "skill-framework")
    (repo / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    # -c commit.gpgsign=false: don't depend on the invoking machine's global
    # Git signing config (commit signing turned on would otherwise block this
    # fixture commit on a passphrase/hardware-key prompt or fail outright).
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=repo, check=True)
    dest = tmp_path / "installed" / "prd-architect"
    package_skill(skill="prd-architect", repo_root=repo, dest=dest, host="test")

    renderer = dest / "scripts" / "prd_safe_output.py"
    assert renderer.is_file()
    spec = importlib.util.spec_from_file_location("installed_prd_safe_output", renderer)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rendered = module.render_gate_output(
        "# forged\napi_key=hostile.secret-value-12345",
        "Not Ready",
        "[forged](javascript:alert(1))",
    )
    assert "hostile.secret-value-12345" not in rendered
    assert len([line for line in rendered.splitlines() if line == "## Build Readiness"]) == 1
    assert validate_tree(dest, check_anchors=False, installed_package=True) == []

    renderer.unlink()
    errors = validate_tree(dest, check_anchors=False, installed_package=True)
    assert len(errors) == 1
    assert "scripts/prd_safe_output.py" in errors[0]
