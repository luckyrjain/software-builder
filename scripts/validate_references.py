#!/usr/bin/env python3
"""Validate local Markdown links in a source tree or installed skill package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reference_utils import (
    extract_markdown_links,
    is_local_markdown_link,
    resolve_local_link,
    split_link_target,
)


def github_style_slug(heading: str) -> str:
    slug = heading.lstrip("#").strip().lower()
    cleaned = "".join(ch if ch.isalnum() or ch == " " else "" for ch in slug)
    return "-".join(cleaned.split())


def heading_slugs(markdown_path: Path) -> set[str]:
    slugs: set[str] = set()
    for line in markdown_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            slugs.add(github_style_slug(line))
    return slugs


def validate_markdown_file(
    source_file: Path,
    *,
    check_anchors: bool = True,
    package_root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    text = source_file.read_text(encoding="utf-8")
    for link in extract_markdown_links(text):
        if not is_local_markdown_link(link):
            continue

        path_part, anchor = split_link_target(link)
        target = resolve_local_link(source_file, path_part)
        if package_root is not None:
            try:
                rel_target = target.relative_to(package_root).as_posix()
            except ValueError:
                rel_target = None

            if not target.is_file():
                if rel_target is None or not rel_target.startswith("docs/skill-framework/"):
                    continue
                errors.append(f"{source_file}: dangling link {link!r} -> {target}")
                continue
        elif not target.is_file():
            errors.append(f"{source_file}: dangling link {link!r} -> {target}")
            continue

        if check_anchors and anchor:
            slug = anchor[1:]
            if slug not in heading_slugs(target):
                errors.append(
                    f"{source_file}: dangling anchor {link!r} in {target}",
                )
    return errors


def validate_tree(root: Path, *, check_anchors: bool = True, installed_package: bool = False) -> list[str]:
    errors: list[str] = []
    package_root = root if installed_package else None
    for md_file in sorted(root.rglob("*.md")):
        if not md_file.is_file():
            continue
        errors.extend(
            validate_markdown_file(
                md_file,
                check_anchors=check_anchors,
                package_root=package_root,
            ),
        )
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local Markdown references.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--source-tree",
        type=Path,
        help="Validate Markdown links under a repository checkout",
    )
    mode.add_argument(
        "--installed-package",
        type=Path,
        help="Validate an installed self-contained skill package",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = (args.source_tree or args.installed_package).resolve()
    if not root.is_dir():
        print(f"error: path not found: {root}", file=sys.stderr)
        return 2

    errors = validate_tree(
        root,
        check_anchors=args.source_tree is not None,
        installed_package=args.installed_package is not None,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"ok: {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
