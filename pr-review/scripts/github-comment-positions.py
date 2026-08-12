#!/usr/bin/env python3
"""Validate GitHub inline-review anchors against a unified diff."""
from __future__ import annotations

import re
import shlex
from typing import Literal


def _marker_path(raw: str) -> str | None:
    """Parse a ---/+++ marker path, including quoted paths and /dev/null."""
    try:
        fields = shlex.split(raw[4:])
    except ValueError:
        return None
    if not fields or fields[0] == "/dev/null":
        return None
    marker_path = fields[0]
    return marker_path[2:] if marker_path.startswith(("a/", "b/")) else marker_path


def validate_github_anchor(
    diff_text: str,
    *,
    path: str,
    line: int,
    source_kind: Literal["added", "context", "removed"],
    head_sha: str,
) -> dict[str, object]:
    """Return a RIGHT anchor only for a caller-identified added line in the matching file."""
    if not head_sha or line < 1:
        return {"unanchorable": True, "reason": "missing_head_sha_or_invalid_line"}
    if source_kind != "added":
        return {"unanchorable": True, "reason": "source_line_is_not_added"}

    current_path: str | None = None
    new_line: int | None = None
    wanted_in_file = False

    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            current_path = None
            new_line = None
            wanted_in_file = False
            continue
        if raw.startswith("--- "):
            current_path = None
            new_line = None
            wanted_in_file = False
            continue
        if raw.startswith("+++ "):
            current_path = _marker_path(raw)
            wanted_in_file = current_path == path
            continue
        if raw.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,\d+)?", raw)
            new_line = int(match.group(1)) if match and wanted_in_file else None
            continue
        if not wanted_in_file or new_line is None:
            continue
        if raw.startswith("-") and not raw.startswith("---"):
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            if new_line == line:
                return {"commit_id": head_sha, "path": path, "line": line, "side": "RIGHT"}
            new_line += 1
            continue
        if raw.startswith(" "):
            new_line += 1

    return {"unanchorable": True, "reason": "added_line_not_in_current_diff"}
