#!/usr/bin/env python3
"""Package a skill directory into a self-contained install bundle."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from reference_utils import (
    extract_markdown_links,
    framework_relative_path,
    is_local_markdown_link,
    rewrite_framework_links,
    sha256_file,
    split_link_target,
)


def git_source_sha(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


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
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )

    vendor_readme_superpowers_specs(repo_root, package_root)

    return sorted(path.relative_to(framework_dest).as_posix() for path in framework_dest.rglob("*") if path.is_file())


def rewrite_package_links(package_root: Path) -> None:
    for md_file in collect_markdown_files(package_root):
        original = md_file.read_text(encoding="utf-8")
        rewritten = rewrite_framework_links(original, md_file, package_root)
        if rewritten != original:
            md_file.write_text(rewritten, encoding="utf-8")


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
        if path.is_file() and path.name != ".software-builder-manifest.json":
            rel = path.relative_to(package_root).as_posix()
            files[rel] = sha256_file(path)

    manifest = {
        "skill": skill,
        "source_repo": repo_root.name,
        "source_sha": git_source_sha(repo_root),
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "host": host,
        "framework_files": framework_files,
        "files": files,
    }
    manifest_path = package_root / ".software-builder-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def package_skill(
    *,
    skill: str,
    repo_root: Path,
    dest: Path,
    host: str,
) -> None:
    skill_src = repo_root / skill
    skill_md = skill_src / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"skill not found at {skill_md}")

    if dest.exists():
        shutil.rmtree(dest)

    shutil.copytree(
        skill_src,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    dest = args.dest.resolve()

    package_skill(
        skill=args.skill,
        repo_root=repo_root,
        dest=dest,
        host=args.host,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
