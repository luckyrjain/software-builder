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
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,})")
_FENCE_CLOSE_RE = re.compile(r"^ {0,3}(`+)$")


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
            match = _FENCE_OPEN_RE.match(line)
            if match:
                fence_len = len(match.group(1))
                continue
            lines.append(line)
            continue
        stripped = line.rstrip()
        close_match = _FENCE_CLOSE_RE.match(stripped)
        if close_match and len(close_match.group(1)) >= fence_len:
            fence_len = 0
    return "\n".join(lines)


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
