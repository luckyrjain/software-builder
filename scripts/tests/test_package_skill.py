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

from package_skill import _release_provenance, main, package_skill  # noqa: E402
from reference_utils import copytree_ignore  # noqa: E402
from validate_references import validate_tree  # noqa: E402


def _init_fixture_repo(repo: Path) -> None:
    """Write a VERSION file and commit repo's current contents as a fresh Git repo.

    Shared by isolated_repo() and any standalone test building its own repo tree
    (rather than using that fixture), so this identical package_release.py-required
    setup (a real VERSION file plus a real, clean Git HEAD -- see release_info.py's
    fail-closed read_distribution_version()/git_source_sha()) isn't duplicated at
    every call site.
    """
    (repo / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    # -c commit.gpgsign=false: don't depend on the invoking machine's global
    # Git signing config (commit signing turned on would otherwise block this
    # fixture commit on a passphrase/hardware-key prompt or fail outright).
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=repo, check=True)


@pytest.fixture
def isolated_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "software-builder"
    shutil.copytree(ROOT / "unit-test-creator", repo / "unit-test-creator")
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "test_creator_write_guard.py", repo / "scripts" / "test_creator_write_guard.py")
    shutil.copy2(ROOT / "scripts" / "git_paths.py", repo / "scripts" / "git_paths.py")
    shutil.copytree(ROOT / "docs" / "skill-framework", repo / "docs" / "skill-framework")
    specs = ROOT / "docs" / "superpowers" / "specs"
    if specs.is_dir():
        shutil.copytree(specs, repo / "docs" / "superpowers" / "specs")
    _init_fixture_repo(repo)
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


def test_main_rejects_symlink_directory_destination(isolated_repo: Path, tmp_path: Path) -> None:
    # Regression test: main() used to resolve --dest (following symlinks)
    # before validate_destination() ran, so a symlinked dest looked like an
    # ordinary directory by validation time and got wiped out by
    # shutil.rmtree() once package_skill() saw it "exists".
    target = tmp_path / "target"
    target.mkdir()
    canary = target / "canary.txt"
    canary.write_text("do not delete me\n", encoding="utf-8")

    link = tmp_path / "link"
    link.symlink_to(target)

    rc = main(["--skill", "unit-test-creator", "--dest", str(link), "--repo-root", str(isolated_repo)])

    assert rc == 1
    assert link.is_symlink()
    assert target.is_dir()
    assert canary.read_text(encoding="utf-8") == "do not delete me\n"


def test_main_rejects_dangling_symlink_destination(isolated_repo: Path, tmp_path: Path) -> None:
    link = tmp_path / "dangling-link"
    link.symlink_to(tmp_path / "does-not-exist")

    rc = main(["--skill", "unit-test-creator", "--dest", str(link), "--repo-root", str(isolated_repo)])

    assert rc == 1
    assert link.is_symlink()
    assert not (tmp_path / "does-not-exist").exists()


def test_main_rejects_symlink_to_file_destination(isolated_repo: Path, tmp_path: Path) -> None:
    real_file = tmp_path / "real.txt"
    real_file.write_text("keep me\n", encoding="utf-8")
    link = tmp_path / "file-link"
    link.symlink_to(real_file)

    rc = main(["--skill", "unit-test-creator", "--dest", str(link), "--repo-root", str(isolated_repo)])

    assert rc == 1
    assert link.is_symlink()
    assert real_file.read_text(encoding="utf-8") == "keep me\n"


def test_main_accepts_ordinary_absolute_destination(isolated_repo: Path, tmp_path: Path) -> None:
    dest = tmp_path / "installed" / "unit-test-creator"

    rc = main(["--skill", "unit-test-creator", "--dest", str(dest), "--repo-root", str(isolated_repo)])

    assert rc == 0
    assert (dest / "SKILL.md").is_file()
    assert not dest.is_symlink()


def test_main_rejects_symlinked_ancestor_directory_when_target_preexists(
    isolated_repo: Path, tmp_path: Path,
) -> None:
    # Regression test: validate_destination() used to check only the leaf
    # component of --dest for is_symlink(). A symlinked *ancestor* directory
    # slipped past that check, then main()'s dest.resolve() followed it
    # anyway -- so a --dest reached through a symlinked parent directory
    # could still land package_skill()'s shutil.rmtree() outside the tree
    # the caller intended, even though the leaf itself was never a symlink.
    # This is only actually dangerous once something already exists at the
    # resolved location for shutil.rmtree()/copytree() to clobber -- see
    # test_main_allows_symlinked_ancestor_when_resolved_target_is_fresh for
    # the (allowed) case where nothing does.
    outside = tmp_path / "outside"
    target_dir = outside / "some-skill"
    target_dir.mkdir(parents=True)
    canary = target_dir / "canary.txt"
    canary.write_text("do not delete me\n", encoding="utf-8")

    link_parent = tmp_path / "link-parent"
    link_parent.symlink_to(outside)
    dest = link_parent / "some-skill"

    rc = main(["--skill", "unit-test-creator", "--dest", str(dest), "--repo-root", str(isolated_repo)])

    assert rc == 1
    assert link_parent.is_symlink()
    assert target_dir.is_dir()
    assert canary.read_text(encoding="utf-8") == "do not delete me\n"


def test_main_allows_symlinked_ancestor_when_resolved_target_is_fresh(
    isolated_repo: Path, tmp_path: Path,
) -> None:
    # A *plain* symlinked ancestor with nothing already at the resolved
    # destination must be allowed, not rejected: macOS's /tmp and /var are
    # themselves symlinks to /private/tmp and /private/var, so any --dest
    # built from mktemp -- exactly what this project's own install tests do
    # -- routes through a symlinked ancestor on every macOS CI run. Rejecting
    # that outright (as an earlier version of this check did) broke every
    # install on macOS even though nothing unsafe was happening: there is
    # nothing pre-existing at the resolved location for shutil.rmtree()/
    # copytree() to clobber, so package_skill() just creates a fresh
    # directory there, exactly as if no symlink had been involved at all.
    real_dir = tmp_path / "private-var"
    real_dir.mkdir()
    ancestor_link = tmp_path / "var"
    ancestor_link.symlink_to(real_dir)
    dest = ancestor_link / "folders" / "some-skill"

    rc = main(["--skill", "unit-test-creator", "--dest", str(dest), "--repo-root", str(isolated_repo)])

    assert rc == 0
    assert (real_dir / "folders" / "some-skill" / "SKILL.md").is_file()


def test_main_rejects_symlinked_ancestor_with_trailing_dotdot_escape_when_target_preexists(
    isolated_repo: Path, tmp_path: Path,
) -> None:
    # Regression test: validate_destination() used to collapse ".." purely
    # lexically (os.path.abspath()) before checking for symlinks. A --dest
    # of the shape "<symlink>/../evil" lexically collapses to the symlink's
    # own *literal* parent + "evil" -- a path containing no symlink, so the
    # old check passed -- while dest.resolve() actually follows the symlink
    # first and applies ".." against its *target*, landing somewhere else
    # entirely that was never validated. As with a plain symlinked ancestor,
    # this only matters once something already exists at the real resolved
    # location.
    x = tmp_path / "x"
    (x / "a" / "b").mkdir(parents=True)
    elsewhere = x / "elsewhere"
    elsewhere.mkdir()
    evil = x / "evil"
    evil.mkdir()
    canary = evil / "canary.txt"
    canary.write_text("do not touch\n", encoding="utf-8")
    linkdir = x / "a" / "b" / "linkdir"
    linkdir.symlink_to(elsewhere)

    dest_arg = f"{linkdir}/../evil"
    assert Path(dest_arg).resolve() == evil  # confirms the exploit's real target

    rc = main(["--skill", "unit-test-creator", "--dest", dest_arg, "--repo-root", str(isolated_repo)])

    assert rc == 1
    assert canary.read_text(encoding="utf-8") == "do not touch\n"


def test_main_allows_dotdot_escape_through_symlink_when_resolved_target_is_fresh(
    isolated_repo: Path, tmp_path: Path,
) -> None:
    # Companion to the "preexists" case above: with nothing at the real
    # resolved location, a symlink-then-".." --dest is allowed for the same
    # reason a plain symlinked ancestor is -- nothing exists yet for
    # shutil.rmtree()/copytree() to clobber, so this just creates a fresh
    # directory at the real resolved location.
    x = tmp_path / "x"
    (x / "a" / "b").mkdir(parents=True)
    elsewhere = x / "elsewhere"
    elsewhere.mkdir()
    linkdir = x / "a" / "b" / "linkdir"
    linkdir.symlink_to(elsewhere)

    dest_arg = f"{linkdir}/../fresh-skill"
    assert Path(dest_arg).resolve() == x / "fresh-skill"

    rc = main(["--skill", "unit-test-creator", "--dest", dest_arg, "--repo-root", str(isolated_repo)])

    assert rc == 0
    assert (x / "fresh-skill" / "SKILL.md").is_file()


def test_package_skill_rejects_symlinked_source_root(isolated_repo: Path, tmp_path: Path) -> None:
    # Regression test: find_symlinks()/reject_symlinks() only reported
    # symlinks os.walk() discovered *beneath* root, never root itself, so a
    # skill whose own top-level directory was a symlink passed the guard
    # silently while shutil.copytree() still followed it and vendored the
    # target's contents.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    (outside / "secret.md").write_text("secret-data\n", encoding="utf-8")

    real_skill_dir = isolated_repo / "unit-test-creator"
    shutil.rmtree(real_skill_dir)
    real_skill_dir.symlink_to(outside)

    dest = tmp_path / "installed" / "unit-test-creator"
    with pytest.raises(ValueError, match="symlink"):
        package_skill(skill="unit-test-creator", repo_root=isolated_repo, dest=dest, host="test")

    assert not dest.exists()


def test_package_skill_rejects_existing_file_destination(isolated_repo: Path, tmp_path: Path) -> None:
    # A plain (non-symlink) file sitting at --dest is not a package directory;
    # shutil.rmtree() must refuse to touch it rather than silently deleting an
    # unrelated file that happens to occupy that path.
    dest = tmp_path / "not-a-directory"
    dest.write_text("unrelated file\n", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        package_skill(skill="unit-test-creator", repo_root=isolated_repo, dest=dest, host="test")

    assert dest.read_text(encoding="utf-8") == "unrelated file\n"


def test_package_skill_rejects_directory_symlink_in_skill_source(isolated_repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("outside content\n", encoding="utf-8")
    (isolated_repo / "unit-test-creator" / "linked-dir").symlink_to(outside)

    dest = tmp_path / "installed" / "unit-test-creator"
    with pytest.raises(ValueError, match="symlink"):
        package_skill(skill="unit-test-creator", repo_root=isolated_repo, dest=dest, host="test")

    assert not dest.exists()


def test_package_skill_rejects_file_symlink_in_skill_source(isolated_repo: Path, tmp_path: Path) -> None:
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside content\n", encoding="utf-8")
    (isolated_repo / "unit-test-creator" / "linked-file.md").symlink_to(outside_file)

    dest = tmp_path / "installed" / "unit-test-creator"
    with pytest.raises(ValueError, match="symlink"):
        package_skill(skill="unit-test-creator", repo_root=isolated_repo, dest=dest, host="test")


def test_package_skill_rejects_dangling_symlink_in_skill_source(isolated_repo: Path, tmp_path: Path) -> None:
    (isolated_repo / "unit-test-creator" / "dangling").symlink_to(isolated_repo / "does-not-exist")

    dest = tmp_path / "installed" / "unit-test-creator"
    with pytest.raises(ValueError, match="symlink"):
        package_skill(skill="unit-test-creator", repo_root=isolated_repo, dest=dest, host="test")


def test_package_skill_rejects_symlink_pointing_inside_repo(isolated_repo: Path, tmp_path: Path) -> None:
    # A symlink that resolves to somewhere *inside* the repo is still a
    # symlink -- it can be swapped to point elsewhere later (TOCTOU) and it
    # still bypasses is_ignored_package_path()'s directory-boundary
    # assumptions, so it must be rejected the same as a link pointing outside.
    (isolated_repo / "unit-test-creator" / "linked-framework").symlink_to(
        isolated_repo / "docs" / "skill-framework",
    )

    dest = tmp_path / "installed" / "unit-test-creator"
    with pytest.raises(ValueError, match="symlink"):
        package_skill(skill="unit-test-creator", repo_root=isolated_repo, dest=dest, host="test")


def test_package_skill_rejects_symlink_in_vendored_framework_tree(isolated_repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "extra.md").write_text("outside content\n", encoding="utf-8")
    (isolated_repo / "docs" / "skill-framework" / "linked-dir").symlink_to(outside)

    dest = tmp_path / "installed" / "unit-test-creator"
    with pytest.raises(ValueError, match="symlink"):
        package_skill(skill="unit-test-creator", repo_root=isolated_repo, dest=dest, host="test")


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
    _init_fixture_repo(repo)
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


def test_release_provenance_reads_extracted_bundle_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "extracted"
    repo.mkdir()
    (repo / "RELEASE-MANIFEST.json").write_text(
        json.dumps({"distribution_version": "1.2.3", "source_sha": "a" * 40}),
        encoding="utf-8",
    )
    assert _release_provenance(repo) == ("1.2.3", "a" * 40)


def test_release_provenance_rejects_invalid_json(tmp_path: Path) -> None:
    repo = tmp_path / "extracted"
    repo.mkdir()
    (repo / "RELEASE-MANIFEST.json").write_text("not json{", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        _release_provenance(repo)


def test_release_provenance_rejects_non_object_json(tmp_path: Path) -> None:
    repo = tmp_path / "extracted"
    repo.mkdir()
    (repo / "RELEASE-MANIFEST.json").write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        _release_provenance(repo)


def test_release_provenance_rejects_invalid_version_or_sha_shape(tmp_path: Path) -> None:
    repo = tmp_path / "extracted"
    repo.mkdir()
    (repo / "RELEASE-MANIFEST.json").write_text(
        json.dumps({"distribution_version": "not-a-semver", "source_sha": "a" * 40}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="distribution_version/source_sha are invalid"):
        _release_provenance(repo)


def test_release_provenance_prefers_live_git_over_stray_manifest(tmp_path: Path) -> None:
    # A RELEASE-MANIFEST.json sitting next to a real .git (e.g. a stale bundle
    # extracted on top of an existing checkout) must never shadow the checkout's
    # real, live HEAD -- see the .git-presence guard's own docstring.
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / "RELEASE-MANIFEST.json").write_text(
        json.dumps({"distribution_version": "9.9.9", "source_sha": "f" * 40}),
        encoding="utf-8",
    )
    _init_fixture_repo(repo)  # writes VERSION="0.0.0" and commits a real Git HEAD
    version, sha = _release_provenance(repo)
    assert version == "0.0.0"
    assert sha != "f" * 40


def test_release_provenance_fails_closed_with_neither_git_nor_manifest(tmp_path: Path) -> None:
    # docs/RELEASE.md promises install.sh needs either a Git checkout or an extracted
    # package_release.py bundle -- there is no third, degraded path. A plain copy of the
    # tree with neither .git nor RELEASE-MANIFEST.json (e.g. GitHub's auto-generated
    # "Source code (zip/tar.gz)" download) must fail closed, not silently degrade.
    repo = tmp_path / "bare"
    repo.mkdir()
    (repo / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing distribution VERSION file"):
        _release_provenance(repo)
