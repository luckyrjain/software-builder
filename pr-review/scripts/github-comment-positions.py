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

INVALID_MARKER = object()

HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)


def _marker_path(raw: str) -> str | None | object:
    """Parse a ---/+++ marker path, including quoted paths and /dev/null."""
    try:
        fields = shlex.split(raw[4:])
    except ValueError:
        return INVALID_MARKER
    if not fields:
        return INVALID_MARKER
    if fields[0] == "/dev/null":
        return None
    marker_path = fields[0]
    return marker_path[2:] if marker_path.startswith(("a/", "b/")) else marker_path


def _hunk_range(raw: str) -> tuple[int, int, int, int] | None:
    """Return old/new starts and counts for a syntactically valid hunk header."""
    match = HUNK_HEADER.match(raw)
    if not match:
        return None
    numeric_fields = [group for group in match.groups() if group is not None]
    if any(len(group) > 12 for group in numeric_fields):
        return None
    try:
        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) is not None else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) is not None else 1
    except ValueError:
        return None
    # A non-empty range cannot begin at line zero. Zero-count ranges may use
    # zero (new/deleted files) or the insertion/deletion point used by git.
    if (old_count > 0 and old_start == 0) or (new_count > 0 and new_start == 0):
        return None
    if old_count == 0 and new_count == 0:
        return None
    return old_start, old_count, new_start, new_count


def _git_binary_patch_complete(body: list[str], binary_index: int) -> bool:
    """Validate canonical one-or-more git binary size/payload blocks."""
    prefix = body[:binary_index]
    index_pattern = r"index [0-9a-f]+\.\.[0-9a-f]+(?: [0-7]{6})?"
    prefix_ok = (
        len(prefix) == 1 and re.fullmatch(index_pattern, prefix[0]) is not None
    ) or (
        len(prefix) == 2
        and re.fullmatch(r"(?:new file mode|deleted file mode) [0-7]{6}", prefix[0])
        is not None
        and re.fullmatch(index_pattern, prefix[1]) is not None
    )
    if not prefix_ok:
        return False
    cursor = binary_index + 1
    blocks = 0
    while cursor < len(body):
        if re.fullmatch(r"(?:literal|delta) \d+", body[cursor]) is None:
            return False
        cursor += 1
        payload_lines = 0
        while cursor < len(body) and body[cursor] != "":
            if re.fullmatch(r"[A-Za-z][!-~]+", body[cursor]) is None:
                return False
            payload_lines += 1
            cursor += 1
        if payload_lines == 0:
            return False
        blocks += 1
        if cursor == len(body):
            break
        cursor += 1  # exactly one blank separator or trailing terminator
        if cursor == len(body):
            break
        if body[cursor] == "":
            return False
    return blocks == 2


def _combined_sections_complete(lines: list[str]) -> bool:
    """Reject truncated `diff --git` sections while allowing known metadata-only forms."""
    starts = [index for index, raw in enumerate(lines) if raw.startswith("diff --git ")]
    for offset, start in enumerate(starts):
        end = starts[offset + 1] if offset + 1 < len(starts) else len(lines)
        body = lines[start + 1 : end]
        if not body:
            return False
        try:
            diff_fields = shlex.split(lines[start])
        except ValueError:
            return False
        if len(diff_fields) != 4 or diff_fields[:2] != ["diff", "--git"]:
            return False
        old_diff_raw, new_diff_raw = diff_fields[2:]
        old_diff = old_diff_raw[2:] if old_diff_raw.startswith("a/") else old_diff_raw
        new_diff = new_diff_raw[2:] if new_diff_raw.startswith("b/") else new_diff_raw
        hunk_indexes = [index for index, raw in enumerate(body) if _hunk_range(raw) is not None]
        marker_indexes = [
            index
            for index, raw in enumerate(body[:-1])
            if raw.startswith("--- ") and body[index + 1].startswith("+++ ")
        ]
        if hunk_indexes:
            if len(marker_indexes) == 1 and marker_indexes[0] < hunk_indexes[0]:
                old_marker = _marker_path(body[marker_indexes[0]])
                new_marker = _marker_path(body[marker_indexes[0] + 1])
                if old_marker is INVALID_MARKER or new_marker is INVALID_MARKER:
                    return False
                if (old_marker is None or old_marker == old_diff) and (
                    new_marker is None or new_marker == new_diff
                ):
                    continue
            return False
        binary_summary = f"Binary files {old_diff_raw} and {new_diff_raw} differ"
        if body == [binary_summary] or (
            len(body) == 2
            and re.fullmatch(r"index [0-9a-f]+\.\.[0-9a-f]+(?: [0-7]{6})?", body[0])
            is not None
            and body[1] == binary_summary
        ):
            continue
        if "GIT binary patch" in body:
            binary_index = body.index("GIT binary patch")
            if _git_binary_patch_complete(body, binary_index):
                continue
            return False
        has_mode_pair = (
            len(body) == 2
            and re.fullmatch(r"old mode [0-7]{6}", body[0]) is not None
            and re.fullmatch(r"new mode [0-7]{6}", body[1]) is not None
        )
        similarity = r"similarity index (?:100|[0-9]{1,2})%"
        has_rename = (
            len(body) == 3
            and re.fullmatch(similarity, body[0]) is not None
            and body[1].startswith("rename from ")
            and body[1][len("rename from ") :] == old_diff
            and body[2].startswith("rename to ")
            and body[2][len("rename to ") :] == new_diff
        )
        has_copy = (
            len(body) == 3
            and re.fullmatch(similarity, body[0]) is not None
            and body[1].startswith("copy from ")
            and body[1][len("copy from ") :] == old_diff
            and body[2].startswith("copy to ")
            and body[2][len("copy to ") :] == new_diff
        )
        empty_blob = r"e69de29[0-9a-f]*"
        zero_blob = r"0+"
        has_new_empty_file = (
            len(body) == 2
            and re.fullmatch(r"new file mode [0-7]{6}", body[0]) is not None
            and re.fullmatch(rf"index {zero_blob}\.\.{empty_blob}", body[1]) is not None
        )
        has_deleted_empty_file = (
            len(body) == 2
            and re.fullmatch(r"deleted file mode [0-7]{6}", body[0]) is not None
            and re.fullmatch(rf"index {empty_blob}\.\.{zero_blob}", body[1]) is not None
        )
        if has_mode_pair or has_rename or has_copy or has_new_empty_file or has_deleted_empty_file:
            continue
        return False
    return True


def _sectioned_sections_complete(lines: list[str]) -> bool:
    """Require every concatenated ---/+++ file section to contain a valid hunk."""
    starts = [
        index
        for index, raw in enumerate(lines[:-1])
        if raw.startswith("--- ") and lines[index + 1].startswith("+++ ")
    ]
    if not starts:
        return False
    for offset, start in enumerate(starts):
        end = starts[offset + 1] if offset + 1 < len(starts) else len(lines)
        if not any(_hunk_range(raw) is not None for raw in lines[start + 2 : end]):
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
    malformed_hunk = (
        (parser_mode == "combined" and not _combined_sections_complete(lines))
        or (parser_mode == "sectioned" and not _sectioned_sections_complete(lines))
        or (parser_mode == "headerless" and (not lines or not lines[0].startswith("@@")))
    )
    previous_hunk_record: Literal["added", "removed", "context"] | None = None
    old_side_eof = False
    new_side_eof = False
    last_old_end: int | None = None
    last_new_end: int | None = None
    hunk_has_change = False

    index = 0
    while index < len(lines):
        raw = lines[index]
        hunk_complete = parser_state == "hunk" and old_remaining == 0 and new_remaining == 0

        if raw.startswith("diff --git "):
            if parser_state == "hunk" and not hunk_complete:
                malformed_hunk = True
            if parser_state == "hunk" and not hunk_has_change:
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
            hunk_has_change = False
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
            if parser_state == "hunk" and not hunk_has_change:
                malformed_hunk = True
            if parser_mode == "headerless":
                ambiguous_headerless_input = True
            current_path = _marker_path(lines[index + 1])
            if current_path is INVALID_MARKER or _marker_path(raw) is INVALID_MARKER:
                malformed_hunk = True
                current_path = None
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
            hunk_has_change = False
            index += 2
            continue

        if raw.startswith("@@"):
            if parser_state == "hunk" and not hunk_complete:
                malformed_hunk = True
            if parser_state == "hunk" and not hunk_has_change:
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
            if old_side_eof or new_side_eof:
                malformed_hunk = True
            if (
                (last_old_end is not None and old_start < last_old_end)
                or (last_new_end is not None and hunk_start < last_new_end)
            ):
                malformed_hunk = True
            if last_old_end is not None and last_new_end is not None:
                old_gap = old_start - last_old_end
                new_gap = hunk_start - last_new_end
                if old_gap != new_gap:
                    malformed_hunk = True
            elif parser_mode == "headerless" or wanted_in_file:
                old_prefix = old_start if old_remaining == 0 else old_start - 1
                new_prefix = hunk_start if new_remaining == 0 else hunk_start - 1
                if old_prefix != new_prefix:
                    malformed_hunk = True
            last_old_end = old_start + old_remaining
            last_new_end = hunk_start + new_remaining
            new_line = hunk_start if wanted_in_file else None
            previous_hunk_record = None
            hunk_has_change = False
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
            if previous_hunk_record == "added":
                malformed_hunk = True
            if old_remaining <= 0:
                malformed_hunk = True
            else:
                old_remaining -= 1
            previous_hunk_record = "removed"
            hunk_has_change = True
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
            hunk_has_change = True
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
    if parser_state == "hunk" and not hunk_has_change:
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
