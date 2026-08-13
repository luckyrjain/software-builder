#!/usr/bin/env python3
"""Validate GitHub inline-review anchors against a unified diff."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shlex
import sys
from typing import Literal

HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)


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


def _hunk_range(raw: str) -> tuple[int, int, int, int] | None:
    """Return old/new starts and counts for a syntactically valid hunk header."""
    match = HUNK_HEADER.match(raw)
    if not match:
        return None
    old_start = int(match.group(1))
    old_count = int(match.group(2)) if match.group(2) is not None else 1
    new_start = int(match.group(3))
    new_count = int(match.group(4)) if match.group(4) is not None else 1
    # A non-empty range cannot begin at line zero. Zero-count ranges may use
    # zero (new/deleted files) or the insertion/deletion point used by git.
    if (old_count > 0 and old_start == 0) or (new_count > 0 and new_start == 0):
        return None
    return old_start, old_count, new_start, new_count


def _combined_sections_complete(lines: list[str]) -> bool:
    """Reject truncated `diff --git` sections while allowing known metadata-only forms."""
    starts = [index for index, raw in enumerate(lines) if raw.startswith("diff --git ")]
    for offset, start in enumerate(starts):
        end = starts[offset + 1] if offset + 1 < len(starts) else len(lines)
        body = lines[start + 1 : end]
        if not body:
            return False
        hunk_indexes = [index for index, raw in enumerate(body) if _hunk_range(raw) is not None]
        marker_indexes = [
            index
            for index, raw in enumerate(body[:-1])
            if raw.startswith("--- ") and body[index + 1].startswith("+++ ")
        ]
        if hunk_indexes:
            if marker_indexes and marker_indexes[0] < hunk_indexes[0]:
                continue
            return False
        if any(raw.startswith("Binary files ") and raw.endswith(" differ") for raw in body):
            continue
        if "GIT binary patch" in body:
            binary_index = body.index("GIT binary patch")
            size_indexes = [
                index
                for index in range(binary_index + 1, len(body))
                if body[index].startswith(("literal ", "delta "))
            ]
            if size_indexes and any(
                re.fullmatch(r"[A-Za-z][!-~]+", raw) is not None
                for raw in body[size_indexes[0] + 1 :]
            ):
                continue
            return False
        has_mode_pair = any(raw.startswith("old mode ") for raw in body) and any(
            raw.startswith("new mode ") for raw in body
        )
        has_rename = (
            any(raw.startswith(("similarity index ", "dissimilarity index ")) for raw in body)
            and any(raw.startswith("rename from ") for raw in body)
            and any(raw.startswith("rename to ") for raw in body)
        )
        has_copy = (
            any(raw.startswith(("similarity index ", "dissimilarity index ")) for raw in body)
            and any(raw.startswith("copy from ") for raw in body)
            and any(raw.startswith("copy to ") for raw in body)
        )
        empty_blob = r"e69de29[0-9a-f]*"
        zero_blob = r"0+"
        has_new_empty_file = any(raw.startswith("new file mode ") for raw in body) and any(
            re.fullmatch(rf"index {zero_blob}\.\.{empty_blob}(?: \d+)?", raw) is not None
            for raw in body
        )
        has_deleted_empty_file = any(
            raw.startswith("deleted file mode ") for raw in body
        ) and any(
            re.fullmatch(rf"index {empty_blob}\.\.{zero_blob}(?: \d+)?", raw) is not None
            for raw in body
        )
        if has_mode_pair or has_rename or has_copy or has_new_empty_file or has_deleted_empty_file:
            continue
        return False
    return True


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

    lines = diff_text.splitlines()
    has_diff_headers = any(raw.startswith("diff --git ") for raw in lines)
    first_patch_token: Literal["markers", "hunk"] | None = None
    if not has_diff_headers:
        for index, raw in enumerate(lines):
            if raw.startswith("--- ") and index + 1 < len(lines) and lines[index + 1].startswith("+++ "):
                first_patch_token = "markers"
                break
            if raw.startswith("@@"):
                first_patch_token = "hunk"
                break

    parser_mode: Literal["combined", "sectioned", "headerless"]
    if has_diff_headers:
        parser_mode = "combined"
    elif first_patch_token == "markers":
        parser_mode = "sectioned"
    else:
        parser_mode = "headerless"

    parser_state: Literal["outside", "file_header", "file_body", "hunk"] = "outside"
    current_path: str | None = path if parser_mode == "headerless" else None
    new_line: int | None = None
    old_remaining = 0
    new_remaining = 0
    wanted_in_file = parser_mode == "headerless"
    found_anchor = False
    ambiguous_headerless_input = False
    malformed_hunk = has_diff_headers and not _combined_sections_complete(lines)
    previous_hunk_record: Literal["added", "removed", "context"] | None = None
    old_side_eof = False
    new_side_eof = False
    last_old_end: int | None = None
    last_new_end: int | None = None

    index = 0
    while index < len(lines):
        raw = lines[index]
        hunk_complete = parser_state == "hunk" and old_remaining == 0 and new_remaining == 0

        if raw.startswith("diff --git "):
            if parser_state == "hunk" and not hunk_complete:
                malformed_hunk = True
            parser_state = "file_header"
            current_path = None
            new_line = None
            old_remaining = 0
            new_remaining = 0
            previous_hunk_record = None
            old_side_eof = False
            new_side_eof = False
            last_old_end = None
            last_new_end = None
            wanted_in_file = False
            index += 1
            continue

        marker_pair = (
            raw.startswith("--- ")
            and index + 1 < len(lines)
            and lines[index + 1].startswith("+++ ")
        )
        if marker_pair:
            # A ---/+++ pair is indistinguishable from marker-shaped hunk
            # content when a capture is truncated at a file boundary. Treat
            # that ambiguity as malformed instead of consuming the pair as
            # deletion/addition records for the preceding file.
            if parser_state == "hunk" and not hunk_complete:
                malformed_hunk = True
            if parser_mode == "headerless":
                ambiguous_headerless_input = True
            current_path = _marker_path(lines[index + 1])
            wanted_in_file = current_path == path
            parser_state = "file_body"
            new_line = None
            old_remaining = 0
            new_remaining = 0
            previous_hunk_record = None
            old_side_eof = False
            new_side_eof = False
            last_old_end = None
            last_new_end = None
            index += 2
            continue

        if raw.startswith("@@"):
            if parser_state == "hunk" and not hunk_complete:
                malformed_hunk = True
            hunk_range = _hunk_range(raw)
            if not hunk_range:
                malformed_hunk = True
                parser_state = "outside"
                new_line = None
                wanted_in_file = False
                index += 1
                continue
            parser_state = "hunk"
            old_start, old_remaining, hunk_start, new_remaining = hunk_range
            if (old_side_eof and old_remaining > 0) or (new_side_eof and new_remaining > 0):
                malformed_hunk = True
            if (
                (last_old_end is not None and old_start < last_old_end)
                or (last_new_end is not None and hunk_start < last_new_end)
            ):
                malformed_hunk = True
            last_old_end = old_start + old_remaining
            last_new_end = hunk_start + new_remaining
            new_line = hunk_start if wanted_in_file else None
            previous_hunk_record = None
            index += 1
            continue

        if parser_state != "hunk":
            if raw.startswith(("--- ", "+++ ")):
                current_path = None
                wanted_in_file = False
                parser_state = "file_header"
            index += 1
            continue

        if raw == r"\ No newline at end of file":
            marker_is_valid = (
                (previous_hunk_record == "added" and new_remaining == 0)
                or (previous_hunk_record == "removed" and old_remaining == 0)
                or (
                    previous_hunk_record == "context"
                    and old_remaining == 0
                    and new_remaining == 0
                )
            )
            if not marker_is_valid:
                malformed_hunk = True
            elif previous_hunk_record == "added":
                new_side_eof = True
            elif previous_hunk_record == "removed":
                old_side_eof = True
            else:
                old_side_eof = True
                new_side_eof = True
            previous_hunk_record = None
            index += 1
            continue
        if hunk_complete:
            # Once the declared body is exhausted, only a recognized next
            # hunk/file boundary or the no-newline marker is legal.
            malformed_hunk = True
            parser_state = "file_body"
            index += 1
            continue
        if raw.startswith("-"):
            if old_remaining <= 0:
                malformed_hunk = True
            else:
                old_remaining -= 1
            previous_hunk_record = "removed"
            index += 1
            continue
        if raw.startswith("+"):
            if new_remaining <= 0:
                malformed_hunk = True
            else:
                if wanted_in_file and new_line == line:
                    found_anchor = True
                if new_line is not None:
                    new_line += 1
                new_remaining -= 1
            previous_hunk_record = "added"
            index += 1
            continue
        if raw.startswith(" "):
            if old_remaining <= 0 or new_remaining <= 0:
                malformed_hunk = True
            else:
                old_remaining -= 1
                if new_line is not None:
                    new_line += 1
                new_remaining -= 1
            previous_hunk_record = "context"
            index += 1
            continue
        malformed_hunk = True
        previous_hunk_record = None
        index += 1

    if parser_state == "hunk" and (old_remaining != 0 or new_remaining != 0):
        malformed_hunk = True

    if found_anchor and not ambiguous_headerless_input and not malformed_hunk:
        return {"commit_id": head_sha, "path": path, "line": line, "side": "RIGHT"}

    return {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a GitHub RIGHT-side inline-comment anchor against a unified diff."
    )
    diff_input = parser.add_mutually_exclusive_group(required=True)
    diff_input.add_argument("--diff-file", type=Path, help="read the unified diff from this file")
    diff_input.add_argument(
        "--diff-stdin",
        action="store_true",
        help="read the unified diff from standard input",
    )
    parser.add_argument("--path", required=True, help="repository-relative target path")
    parser.add_argument("--line", required=True, type=int, help="new-file line number")
    parser.add_argument(
        "--source-kind",
        required=True,
        choices=("added", "context", "removed"),
        help="diff source kind assigned by the review workflow",
    )
    parser.add_argument("--head-sha", required=True, help="current pull-request head SHA")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    if args.diff_stdin:
        diff_text = sys.stdin.read()
    else:
        try:
            diff_text = args.diff_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(
                json.dumps({"error": "diff_input_unavailable", "detail": str(exc)}),
                file=sys.stderr,
            )
            return 1

    result = validate_github_anchor(
        diff_text,
        path=args.path,
        line=args.line,
        source_kind=args.source_kind,
        head_sha=args.head_sha,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
