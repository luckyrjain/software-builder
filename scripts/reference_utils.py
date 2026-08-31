#!/usr/bin/env python3
"""Shared helpers for Markdown link extraction, framework path handling, and
the install-package manifest workflow (packaging, verification) per ADR 0002.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

# Allows exactly one level of nested parens in the target (e.g. a Wikipedia-style URL ending
# "_(bar)") so the match doesn't truncate at that inner ")" and silently corrupt the captured
# target -- a plain "[^)]+" class does exactly that. Same fix as
# scripts/registry/cross_skill_routing.py's _MARKDOWN_LINK, applied here independently since this
# regex's target class intentionally still allows whitespace (unlike that one).
MARKDOWN_LINK_RE = re.compile(r"\]\(((?:[^()]|\([^()]*\))*)\)")
FRAMEWORK_MARKER = "docs/skill-framework/"

MANIFEST_NAME = ".software-builder-manifest.json"


class ManifestError(ValueError):
    """Raised when a MANIFEST_NAME file is missing, unreadable, or malformed."""


def read_manifest_file(path: Path) -> dict[str, Any]:
    """Read and parse a MANIFEST_NAME file into its JSON object.

    Raises ManifestError with a specific, human-readable reason on any
    failure (missing file, invalid JSON, JSON root not an object) -- callers
    decide how to surface it.
    """
    if not path.is_file():
        raise ManifestError(f"missing manifest: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError (a corrupted or non-UTF-8 manifest on disk) is not an
        # OSError -- without catching it explicitly here too, it propagates past
        # callers that only catch ManifestError (e.g. doctor.py's
        # _installed_manifest, which treats a bad manifest as "can't determine
        # install status" for that one skill), crashing the whole command instead.
        raise ManifestError(f"cannot read manifest: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid manifest JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError("manifest is not a JSON object")
    return data


# Filesystem noise that can legitimately appear after a skill is packaged/installed and
# used (running a bundled script writes __pycache__, editors/OS write dotfiles) -- shared
# by package_skill.py (excluded when copying source into a package) and install_support.py
# (excluded when comparing an installed directory against its manifest) so the two agree
# on what counts as real package content.
IGNORED_DIR_NAMES = ("__pycache__", ".pytest_cache")
IGNORED_FILE_PATTERNS = ("*.pyc", ".DS_Store", "*.swp", "*~")


def is_ignored_package_path(rel_path: str) -> bool:
    """True if rel_path (posix-style, relative to a package/install root) is
    filesystem noise rather than real package content.

    Checks every path component against both IGNORED_DIR_NAMES and
    IGNORED_FILE_PATTERNS -- mirroring shutil.ignore_patterns()'s per-level
    matching (a noise-named directory anywhere in the path, not just the
    immediate parent, excludes everything under it) -- so copytree_ignore()
    and this function never disagree on what a nested path excludes.
    """
    for part in rel_path.split("/"):
        if part in IGNORED_DIR_NAMES:
            return True
        if any(fnmatch.fnmatch(part, pattern) for pattern in IGNORED_FILE_PATTERNS):
            return True
    return False


def find_symlinks(root: Path) -> list[str]:
    """List every symlink (file or directory, dangling or not) under root.

    Uses os.walk(followlinks=False) rather than Path.rglob(): rglob recurses
    through a symlinked subdirectory as if it were a plain one, so the
    symlinked directory's *contents* show up as ordinary paths while the
    symlink itself is never visited and never flagged. followlinks=False
    still reports a symlinked directory by name in dirnames without
    descending into it, so is_symlink() catches it like any other entry.
    Returned paths are posix-style, relative to root, sorted for stable
    error messages.
    """
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        for name in (*dirnames, *filenames):
            candidate = base / name
            if candidate.is_symlink():
                found.append(candidate.relative_to(root).as_posix())
    return sorted(found)


def reject_symlinks(root: Path, description: str) -> None:
    """Raise ValueError if root itself, or any symlink exists anywhere under it.

    find_symlinks() only reports symlinks os.walk() discovers *while walking
    beneath* root -- it never reports the walk's own starting argument, so a
    root that is itself a symlink (e.g. the top-level skill directory or the
    vendored framework directory having been replaced by one) would pass
    silently even though shutil.copytree(root, dest, symlinks=False) still
    follows it and vendors the symlink target's contents. Checking root
    directly here closes that gap.

    Packaging copies root's tree with shutil.copytree(symlinks=False), which
    silently dereferences symlinks and vendors whatever content they point
    at -- including content outside the intended source tree -- into the
    package. Rejecting symlinks up front closes that hole; by the time the
    package exists, the symlink is already gone (copied as real content), so
    checking the *installed* output afterward can no longer catch it.
    """
    if root.is_symlink():
        raise ValueError(f"{description} is itself a symlink, which is not allowed: {root}")
    symlinks = find_symlinks(root)
    if symlinks:
        raise ValueError(
            f"{description} contains symlink(s), which are not allowed: {', '.join(symlinks)}",
        )


def copytree_ignore(root: Path):
    """Build a shutil.copytree ignore() callback driven by is_ignored_package_path().

    shutil.ignore_patterns() and is_ignored_package_path() used to be two
    independently-maintained implementations that merely read from the same
    constants -- they diverged in practice (directory-vs-file matching
    granularity, and call sites like vendor_readme_superpowers_specs() that
    copy files without going through copytree's ignore= at all), so a file
    packaged under one path could be silently excluded when re-checked at
    verify time, or vice versa. Routing copytree itself through
    is_ignored_package_path() makes packaging and verification share the
    exact same decision function instead of just the same constants.

    Deliberately does not call .resolve() on `root` or on the `directory`
    shutil passes into ignore(): shutil.copytree builds every recursive
    `directory` argument by joining path components onto the exact `root`
    object passed to it, without ever resolving symlinks -- including when
    it follows a symlinked subdirectory (its default, since copytree() is
    called with symlinks=False at both call sites). Resolving here would
    make `directory` jump to the symlink's real target while `root` stays
    put, so relative_to(root) raises ValueError for any path reached through
    a symlinked subdirectory. Comparing both unresolved keeps them on the
    same textual prefix that shutil itself guarantees.
    """

    def ignore(directory: str, names: list[str]) -> set[str]:
        dir_path = Path(directory)
        return {
            name
            for name in names
            if is_ignored_package_path((dir_path / name).relative_to(root).as_posix())
        }

    return ignore


# CommonMark allows a fence delimiter to be indented up to 3 spaces (e.g. one nested inside
# a numbered-list item) before it stops being a fence and becomes an indented code block.
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,})(.*)$")
_FENCE_CLOSE_RE = re.compile(r"^ {0,3}(`+)$")


def _fence_open_length(line: str) -> int | None:
    """Return the opening fence's backtick-run length, or None if `line` isn't one.

    Per CommonMark, a backtick-fenced code block's info string (any text after the
    opening run on the same line) must not itself contain a backtick — otherwise the line
    isn't a fence opener at all. Without this check, ordinary prose demonstrating inline
    code spans with a triple-backtick example (e.g. "``` becomes ````, …") would be
    misread as opening a fence, silently swallowing everything after it — including real
    links and headings — as code-block content until an unrelated line happens to close
    it (or EOF, if none does).
    """
    match = _FENCE_OPEN_RE.match(line)
    if not match:
        return None
    if "`" in match.group(2):
        return None
    return len(match.group(1))


def strip_fenced_code_blocks(text: str) -> str:
    """Remove fenced code blocks, tracking each fence's own backtick-run length.

    A boolean toggle on any ```-prefixed line is wrong once fences of different lengths
    nest (e.g. a ```` block containing a literal ``` excerpt) — per CommonMark, only a
    line consisting of nothing but backticks, with a run at least as long as the opening
    fence, closes it. A shorter or unrelated backtick-prefixed line inside stays literal
    content, not a new delimiter.
    """
    lines: list[str] = []
    fence_len = 0
    for line in text.splitlines():
        if fence_len == 0:
            open_len = _fence_open_length(line)
            if open_len is not None:
                fence_len = open_len
                continue
            lines.append(line)
            continue
        stripped = line.rstrip()
        close_match = _FENCE_CLOSE_RE.match(stripped)
        if close_match and len(close_match.group(1)) >= fence_len:
            fence_len = 0
    return "\n".join(lines)


def has_unclosed_fenced_code_block(text: str) -> bool:
    """Return True if a fence opened in the file is never closed before EOF.

    A stray/orphaned fence marker (no real opening purpose, or an opener that's never
    closed) makes strip_fenced_code_blocks() treat everything after it — including real
    headings — as code-block content. That's only surfaced today as a downstream symptom
    (a dangling-anchor error, and only if something happens to link into the now-hidden
    heading) — this gives a direct, always-checked signal instead.
    """
    fence_len = 0
    for line in text.splitlines():
        if fence_len == 0:
            open_len = _fence_open_length(line)
            if open_len is not None:
                fence_len = open_len
            continue
        stripped = line.rstrip()
        close_match = _FENCE_CLOSE_RE.match(stripped)
        if close_match and len(close_match.group(1)) >= fence_len:
            fence_len = 0
    return fence_len != 0


def split_link_target(target: str) -> tuple[str, str]:
    if "#" in target:
        path_part, anchor = target.split("#", 1)
        return path_part, f"#{anchor}"
    return target, ""


def is_local_markdown_link(target: str) -> bool:
    if not target:
        return False
    path_part, _ = split_link_target(target)
    if path_part.startswith(("http://", "https://", "mailto:", "data:", "~")):
        return False
    if "*" in path_part:
        return False
    return path_part.endswith(".md")


def extract_markdown_links(text: str) -> list[str]:
    return MARKDOWN_LINK_RE.findall(strip_fenced_code_blocks(text))


def framework_relative_path(link_target: str) -> str | None:
    path_part, _ = split_link_target(link_target)
    if FRAMEWORK_MARKER not in path_part:
        return None
    idx = path_part.index(FRAMEWORK_MARKER)
    return path_part[idx + len(FRAMEWORK_MARKER) :]


def resolve_local_link(source_file: Path, link_target: str) -> Path:
    path_part, _ = split_link_target(link_target)
    return (source_file.parent / path_part).resolve()


def rewrite_framework_links(content: str, source_file: Path, package_root: Path) -> str:
    framework_root = package_root / "docs" / "skill-framework"

    def replace_link(match: re.Match[str]) -> str:
        target = match.group(1)
        framework_rel = framework_relative_path(target)
        if framework_rel is None:
            return match.group(0)

        _, anchor = split_link_target(target)
        target_path = framework_root / framework_rel
        rel_from_source = os.path.relpath(target_path, source_file.parent)
        return f"]({rel_from_source}{anchor})"

    return MARKDOWN_LINK_RE.sub(replace_link, content)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
