#!/usr/bin/env python3
"""Package a skill directory into a self-contained install bundle."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from test_creator_catalog import TEST_CREATOR_SKILL_SET

from reference_utils import (
    MANIFEST_NAME,
    MANIFEST_VERSION,
    copytree_ignore,
    extract_markdown_links,
    framework_relative_path,
    is_ignored_package_path,
    is_local_markdown_link,
    reject_symlinks,
    rewrite_framework_links,
    sha256_file,
    split_link_target,
)


from release_info import (
    RELEASE_MANIFEST_NAME,
    SEMVER_RE,
    SHA_RE,
    git_source_sha,
    read_distribution_version,
)


def collect_markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if path.is_file())


# Modules under docs/skill-framework/shared/ that a skill's own scripts may execute. A skill whose
# scripts name one of these needs the framework tree vendored regardless of what its markdown links
# say -- see skill_loads_shared_runtime().
SHARED_RUNTIME_DIR = "docs/skill-framework/shared"
SHARED_RUNTIME_LOADER = "shared_runtime_loader.py"
_SHARED_RUNTIME_MODULES = ("shared_runtime_loader", "review_contract_runtime")

# Skills whose scripts parse YAML written by the target workspace rather than by this repository.
# They get scripts/yaml_safety.py vendored so untrusted YAML goes through the same duplicate-key
# rejection and size/nesting caps as this repository's own registry files.
YAML_SAFETY_SKILL_SET = frozenset(
    {
        "domain-comprehension",
        "incident-rca",
        "k8s-overprovisioning-datadog",
        "migration-program-manager",
    }
)


def skill_references_framework(markdown_files: list[Path]) -> bool:
    for md_file in markdown_files:
        for link in extract_markdown_links(md_file.read_text(encoding="utf-8")):
            if framework_relative_path(link) is not None:
                return True
    return False


def skill_loads_shared_runtime(package_root: Path) -> bool:
    """Whether the skill's own scripts execute a module from the shared framework tree.

    skill_references_framework() answers whether the *documentation* links to the framework;
    this answers whether the *code* loads it, which is the fact that decides whether an installed
    package is self-contained. Inferring the second from the first is how trimming a SKILL.md link
    could silently stop vendoring a runtime the scripts still execute -- at which point the
    loader's containment check is all that stands between the package and a sibling path.
    """
    scripts_dir = package_root / "scripts"
    if not scripts_dir.is_dir():
        return False
    for path in sorted(scripts_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(module in text for module in _SHARED_RUNTIME_MODULES):
            return True
    return False


def vendor_readme_superpowers_specs(repo_root: Path, package_root: Path) -> None:
    readme = repo_root / "docs" / "skill-framework" / "README.md"
    if not readme.is_file():
        return

    for link in extract_markdown_links(readme.read_text(encoding="utf-8")):
        if not is_local_markdown_link(link):
            continue
        path_part, _ = split_link_target(link)
        resolved = (readme.parent / path_part).resolve()
        if not resolved.is_file():
            continue
        try:
            rel = resolved.relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            continue
        if not rel.startswith("docs/superpowers/specs/"):
            continue
        if is_ignored_package_path(rel):
            continue
        dest = package_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved, dest)


def vendor_framework_tree(repo_root: Path, package_root: Path) -> list[str]:
    framework_src = repo_root / "docs" / "skill-framework"
    reject_symlinks(framework_src, "vendored framework tree")
    framework_dest = package_root / "docs" / "skill-framework"
    if framework_dest.exists():
        shutil.rmtree(framework_dest)
    shutil.copytree(
        framework_src,
        framework_dest,
        ignore=copytree_ignore(framework_src),
    )

    vendor_readme_superpowers_specs(repo_root, package_root)

    return sorted(path.relative_to(framework_dest).as_posix() for path in framework_dest.rglob("*") if path.is_file())


def rewrite_package_links(package_root: Path) -> None:
    for md_file in collect_markdown_files(package_root):
        original = md_file.read_text(encoding="utf-8")
        rewritten = rewrite_framework_links(original, md_file, package_root)
        if rewritten != original:
            md_file.write_text(rewritten, encoding="utf-8")


def _release_provenance(repo_root: Path) -> tuple[str, str]:
    """Distribution version and source SHA to record in an install manifest.

    Prefers RELEASE-MANIFEST.json at repo_root (present when installing from
    an extracted release bundle -- .git is never a tracked file, so a bundle
    built by package_release.py never contains one) and falls back to live
    Git/VERSION metadata when installing directly from a Git checkout. Without
    this, every install from a downloaded-and-extracted release tarball -- the
    flow docs/RELEASE.md documents -- would hard-fail: git_source_sha() now
    raises instead of degrading to "unknown" when repo_root has no .git.

    Only trusts RELEASE-MANIFEST.json when repo_root has no .git: the two are
    meant to be mutually exclusive by construction (a tracked symlink/file
    named RELEASE-MANIFEST.json is rejected by package_release.py, and a bundle
    it builds never contains .git), but nothing stops a leftover
    RELEASE-MANIFEST.json -- e.g. docs/RELEASE.md's own "download and extract
    the newer bundle" upgrade path applied on top of an existing Git checkout,
    or any other stray copy -- from sitting next to a real .git. Without this
    guard, that leftover file would silently and permanently shadow the live
    checkout's actual HEAD in every subsequent install's manifest (with no
    error), which then makes doctor.py's installed-vs-running distribution_version
    comparison report a false VERSION_MISMATCH even though the skill content is
    current.
    """
    release_manifest_path = repo_root / RELEASE_MANIFEST_NAME
    if not (repo_root / ".git").exists() and release_manifest_path.is_file():
        try:
            release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{release_manifest_path}: invalid JSON: {exc}") from exc
        if not isinstance(release_manifest, dict):
            raise ValueError(f"{release_manifest_path}: must be a JSON object")
        version = release_manifest.get("distribution_version")
        sha = release_manifest.get("source_sha")
        # Enforce the same shape the live Git/VERSION fallback below already
        # guarantees (read_distribution_version/git_source_sha both validate
        # against these same patterns) -- otherwise a corrupted or tampered
        # RELEASE-MANIFEST.json could silently write a garbage-but-string
        # distribution_version/source_sha into every install's manifest.
        if (
            isinstance(version, str)
            and SEMVER_RE.fullmatch(version)
            and isinstance(sha, str)
            and SHA_RE.fullmatch(sha)
        ):
            return version, sha
        raise ValueError(f"{release_manifest_path}: distribution_version/source_sha are invalid")
    return read_distribution_version(repo_root), git_source_sha(repo_root)


def write_manifest(
    package_root: Path,
    *,
    skill: str,
    repo_root: Path,
    host: str,
    framework_files: list[str],
) -> None:
    files: dict[str, str] = {}
    for path in sorted(package_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(package_root).as_posix()
        if path.name == MANIFEST_NAME or is_ignored_package_path(rel):
            continue
        files[rel] = sha256_file(path)

    distribution_version, source_sha = _release_provenance(repo_root)
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "skill": skill,
        "distribution_version": distribution_version,
        "source_repo": repo_root.name,
        "source_sha": source_sha,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "host": host,
        "framework_files": framework_files,
        "files": files,
    }
    manifest_path = package_root / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _shared_script(repo_root: Path, filename: str, description: str, *, subdir: str = "scripts") -> Path:
    """Find a shared runtime script in the selected source repository."""

    selected_root = repo_root.resolve(strict=True)
    candidate = selected_root / subdir / filename
    if not candidate.is_file():
        raise FileNotFoundError(f"{description} missing: {candidate}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(selected_root)
    except ValueError as exc:
        raise ValueError(
            f"{description} resolves outside selected source repository: {candidate} -> {resolved}",
        ) from exc
    except (OSError, RuntimeError) as exc:
        raise FileNotFoundError(f"{description} cannot be resolved safely: {candidate}: {exc}") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"{description} is not a file: {candidate}")
    return candidate


def package_skill(
    *,
    skill: str,
    repo_root: Path,
    dest: Path,
    host: str,
) -> None:
    validate_skill_name(skill)
    validate_destination(dest)

    skill_src = repo_root / skill
    skill_md = skill_src / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"skill not found at {skill_md}")

    reject_symlinks(skill_src, f"skill source tree ({skill})")

    if dest.exists():
        shutil.rmtree(dest)

    # Selects from the working tree, not from Git's index -- deliberately, and unlike the
    # two archive builders (registry/generic_package.py and package_release.py) which both
    # source their inputs from `git ls-files`. install.sh supports two flows (docs/RELEASE.md):
    # a .git checkout, and an *extracted release bundle*, which carries RELEASE-MANIFEST.json
    # and no .git at all. An index-based selector here would package zero files in the second
    # flow, breaking the primary end-user install path. Containment is enforced instead by
    # reject_symlinks() above plus is_ignored_package_path() via copytree_ignore(), which is
    # the same exclusion decision `--verify` re-applies to the installed tree.
    shutil.copytree(
        skill_src,
        dest,
        ignore=copytree_ignore(skill_src),
    )

    # The five creators share one executable write guard. Keep its source
    # canonical in the repository and inject the exact same file into each
    # self-contained installed bundle; source-tree adapters are replaced here
    # so standalone installs never depend on this repository's Python package.
    if skill in TEST_CREATOR_SKILL_SET:
        guard_src = _shared_script(
            repo_root,
            "test_creator_write_guard.py",
            "shared test-creator write guard",
        )
        helper_src = _shared_script(repo_root, "git_paths.py", "shared Git path helper")
        guard_dest = dest / "scripts" / "test_creator_write_guard.py"
        guard_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(guard_src, guard_dest)
        shutil.copy2(helper_src, dest / "scripts" / "git_paths.py")

    if skill in YAML_SAFETY_SKILL_SET:
        yaml_safety_src = _shared_script(repo_root, "yaml_safety.py", "shared YAML safety loader")
        yaml_safety_dest = dest / "scripts" / "yaml_safety.py"
        yaml_safety_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(yaml_safety_src, yaml_safety_dest)

    seed_files = collect_markdown_files(dest)
    loads_shared_runtime = skill_loads_shared_runtime(dest)
    framework_files: list[str] = []
    if loads_shared_runtime or skill_references_framework(seed_files):
        framework_files = vendor_framework_tree(repo_root, dest)

    if loads_shared_runtime:
        # Vendored beside the skill's own scripts, so locating the loader itself never has to
        # search outside the package -- the loader then owns the containment policy for every
        # other module it loads out of the vendored framework tree.
        loader_src = _shared_script(
            repo_root,
            SHARED_RUNTIME_LOADER,
            "shared runtime loader",
            subdir=SHARED_RUNTIME_DIR,
        )
        loader_dest = dest / "scripts" / SHARED_RUNTIME_LOADER
        loader_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(loader_src, loader_dest)

    rewrite_package_links(dest)
    write_manifest(
        dest,
        skill=skill,
        repo_root=repo_root,
        host=host,
        framework_files=framework_files,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package a skill for installation.")
    parser.add_argument("--skill", required=True, help="Skill directory name")
    parser.add_argument("--dest", required=True, type=Path, help="Destination package path")
    parser.add_argument("--repo-root", required=True, type=Path, help="software-builder repo root")
    parser.add_argument("--host", default="unknown", help="Install host target label")
    return parser.parse_args(argv)


def validate_skill_name(skill: str) -> None:
    if "/" in skill or skill in {".", ".."}:
        raise ValueError(
            f"invalid skill name {skill!r} (must be a single directory name, no path separators)",
        )


def validate_destination(dest: Path) -> None:
    # Checks only the leaf, deliberately: is_symlink() uses lstat() and does
    # not require the link target to exist, so this also rejects a dangling
    # symlink, not just a live one. Checked on the raw, unresolved dest --
    # main() calls this before ever calling dest.resolve(), which is what
    # would otherwise follow straight through it and hand
    # shutil.rmtree()/copytree() a location the caller never actually named.
    #
    # An *ancestor* of dest being a symlink is not checked here, even though
    # a swapped ancestor could in principle redirect dest.resolve() the same
    # way: two earlier, more thorough versions of this check (rejecting any
    # symlinked ancestor outright, then rejecting one only when the resolved
    # destination already exists) both broke this tool's own real usage
    # rather than catching an attack. install.sh always calls this with
    # --dest set to a path mktemp -d has *already created* -- so "the
    # resolved destination already exists" is true on every ordinary
    # install, not a sign of anything wrong -- and on macOS that path is
    # always reached through /tmp or /var, which are themselves symlinks to
    # /private/tmp and /private/var by design. Every static, pre-operation
    # check tried here ended up rejecting that completely ordinary case
    # instead of an actual attack. Properly closing the ancestor-symlink gap
    # needs race-free, O_NOFOLLOW-based filesystem operations in place of
    # shutil.rmtree()/copytree(), not a heuristic here -- accepted as a
    # known limitation rather than another heuristic likely to trade one
    # false positive for another.
    if dest.is_symlink():
        raise ValueError(f"refusing to use destination under symlink: {dest}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()

    try:
        # Validate the raw --dest argument *before* resolving it: Path.resolve()
        # follows symlinks, so a symlinked dest would no longer look like a
        # symlink by the time it reached package_skill()'s own
        # validate_destination() call, letting a caller-supplied symlink slip
        # through and later get recursively deleted by shutil.rmtree() when it
        # "exists".
        validate_destination(args.dest)
        dest = args.dest.resolve()
        package_skill(
            skill=args.skill,
            repo_root=repo_root,
            dest=dest,
            host=args.host,
        )
    except (OSError, ValueError) as exc:
        # OSError (not just FileNotFoundError) so an I/O failure reading
        # RELEASE-MANIFEST.json in _release_provenance() -- e.g. a permission error on
        # an extracted bundle -- prints a clean error instead of a raw traceback.
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
