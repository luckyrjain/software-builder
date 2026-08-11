#!/usr/bin/env python3
"""Shared helpers for Markdown link extraction and framework path handling."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

MARKDOWN_LINK_RE = re.compile(r"\]\(([^)]+)\)")
FRAMEWORK_MARKER = "docs/skill-framework/"


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
    digest.update(path.read_bytes())
    return digest.hexdigest()
