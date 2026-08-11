#!/usr/bin/env python3
"""Validate local Markdown links in a source tree or installed skill package."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from reference_utils import (
    extract_markdown_links,
    is_local_markdown_link,
    resolve_local_link,
    split_link_target,
    strip_fenced_code_blocks,
)

_SLUG_SPACE_RUN_RE = re.compile(r" +")


def github_style_slug(heading: str) -> str:
    # Keep letters/digits/space/hyphen, collapse runs of whitespace to one
    # space, THEN replace every remaining space with a hyphen — matching both
    # GitHub's real anchor algorithm and scripts/lint-dangling-md-links.sh's
    # sed pipeline (`s/[^a-z0-9 -]//g; s/ +/ /g; s/ /-/g`), which the repo's
    # whole existing anchor corpus is already written against.
    #
    # The keep step uses Unicode-aware `str.isalnum()` rather than an
    # ASCII-only `[a-z0-9 -]` regex class: GitHub's renderer preserves
    # non-ASCII letters in anchors (e.g. "Café Menu" -> "café-menu"), and an
    # ASCII-only class would silently strip them (verified: it produced
    # "caf-menu", dropping the accented "é" that even the prior, differently
    # buggy implementation preserved).
    #
    # The collapse-and-join step is NOT the prior implementation's
    # strip()+split()+join(), which silently discards a leading/trailing
    # single space — real headings that end in a stripped character (e.g. an
    # emoji) leave a real trailing space behind after the keep step, e.g.
    # "5. Slack — PR review 🔴" must slugify to "5-slack-pr-review-" (trailing
    # hyphen), matching the already-verified link in pr-review/examples.md and
    # confirmed by directly running lint-dangling-md-links.sh's sed pipeline
    # on that exact heading. The prior implementation also dropped hyphen from
    # its keep-set entirely, mangling compound-word headings like "Test-first
    # evidence" into "testfirst-evidence" instead of "test-first-evidence".
    slug = heading.lstrip("#").strip().lower()
    cleaned = "".join(ch for ch in slug if ch.isalnum() or ch in " -")
    cleaned = _SLUG_SPACE_RUN_RE.sub(" ", cleaned)
    return cleaned.replace(" ", "-")


def heading_slugs(markdown_path: Path) -> set[str]:
    slugs: set[str] = set()
    text = strip_fenced_code_blocks(markdown_path.read_text(encoding="utf-8"))
    for line in text.splitlines():
        if line.startswith("#"):
            slugs.add(github_style_slug(line))
    return slugs


def is_within_package(path: Path, package_root: Path) -> bool:
    try:
        path.resolve().relative_to(package_root.resolve())
    except ValueError:
        return False
    return True


def is_skippable_installed_link(source_file: Path, target: Path, package_root: Path) -> bool:
    """Return True when a missing link is optional in an installed skill bundle.

    Normative runtime content lives under docs/skill-framework/ and skill-local
    paths. Historical design docs (docs/superpowers/) and cross-skill corpus
    references outside the bundle are tolerated when absent.
    """
    if target.is_file():
        return False

    try:
        source_rel = source_file.resolve().relative_to(package_root.resolve()).as_posix()
    except ValueError:
        return True

    try:
        target_rel = target.resolve().relative_to(package_root.resolve()).as_posix()
    except ValueError:
        return True

    if not source_rel.startswith("docs/"):
        return False

    if source_rel.startswith("docs/superpowers/") or target_rel.startswith("docs/superpowers/"):
        return True

    if source_rel.startswith("docs/skill-framework/") and not target_rel.startswith("docs/skill-framework/"):
        return True

    return False


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
            if is_skippable_installed_link(source_file, target, package_root):
                continue
            if not is_within_package(target, package_root):
                continue

        if not target.is_file():
            errors.append(f"{source_file}: dangling link {link!r} -> {target}")
            continue

        if check_anchors and anchor:
            slug = anchor[1:]
            if slug not in heading_slugs(target):
                errors.append(
                    f"{source_file}: dangling anchor {link!r} in {target}",
                )
    return errors


def validate_tree(
    root: Path,
    *,
    check_anchors: bool = True,
    installed_package: bool = False,
    exclude: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    package_root = root.resolve() if installed_package else None
    # The PRD safe-output contract names an executable rather than Markdown, so
    # the normal Markdown-link pass cannot enforce this installed runtime asset.
    if installed_package and (root / "reference" / "safe-output-contract.md").is_file():
        renderer = root / "scripts" / "prd_safe_output.py"
        if not renderer.is_file():
            errors.append(f"{renderer}: required safe-output renderer is missing")
    exclude_roots = [(root / rel).resolve() for rel in (exclude or [])]
    for md_file in sorted(root.rglob("*.md")):
        if not md_file.is_file():
            continue
        resolved_md_file = md_file.resolve()
        if any(resolved_md_file.is_relative_to(excluded) for excluded in exclude_roots):
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
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="RELATIVE_DIR",
        help=(
            "Directory (relative to the validated root) whose Markdown files are skipped as "
            "link sources. Repeatable. Two independent reasons to exclude a directory: (1) "
            "historical/superseded doc trees exempt from active reference upkeep (see "
            "docs/history/README.md), or (2) actively-maintained trees already covered by "
            "another checker whose anchor algorithm may disagree with this one (e.g. an "
            "ASCII-only sed script) — excluding avoids contradictory results, not upkeep."
        ),
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
        exclude=args.exclude,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"ok: {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
