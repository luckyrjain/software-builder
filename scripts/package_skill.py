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

from reference_utils import (
    MANIFEST_NAME,
    copytree_ignore,
    extract_markdown_links,
    framework_relative_path,
    is_ignored_package_path,
    is_local_markdown_link,
    rewrite_framework_links,
    sha256_file,
    split_link_target,
)


from release_info import git_source_sha, read_distribution_version


def collect_markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def skill_references_framework(markdown_files: list[Path]) -> bool:
    for md_file in markdown_files:
        for link in extract_markdown_links(md_file.read_text(encoding="utf-8")):
            if framework_relative_path(link) is not None:
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
    """
    release_manifest_path = repo_root / "RELEASE-MANIFEST.json"
    if release_manifest_path.is_file():
        try:
            release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{release_manifest_path}: invalid JSON: {exc}") from exc
        if not isinstance(release_manifest, dict):
            raise ValueError(f"{release_manifest_path}: must be a JSON object")
        version = release_manifest.get("distribution_version")
        sha = release_manifest.get("source_sha")
        if isinstance(version, str) and isinstance(sha, str):
            return version, sha
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

    if dest.exists():
        shutil.rmtree(dest)

    shutil.copytree(
        skill_src,
        dest,
        ignore=copytree_ignore(skill_src),
    )

    seed_files = collect_markdown_files(dest)
    framework_files: list[str] = []
    if skill_references_framework(seed_files):
        framework_files = vendor_framework_tree(repo_root, dest)

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
    if dest.is_symlink():
        raise ValueError(f"refusing to replace symlink destination: {dest}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    dest = args.dest.resolve()

    try:
        package_skill(
            skill=args.skill,
            repo_root=repo_root,
            dest=dest,
            host=args.host,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
