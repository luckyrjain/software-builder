#!/usr/bin/env python3
"""Map a file:line finding to a GitLab create_merge_request_thread position object.

Usage (single finding, new-file line):
  python diff-to-positions.py --diff-file change.diff --path src/foo.py --line 42 \\
    --base-sha BASE --start-sha START --head-sha HEAD

Pipe a unified diff on stdin:
  git diff HEAD~1 -- src/foo.py | python diff-to-positions.py --path src/foo.py --line 42 ...

Pass the diff inline (e.g. a hunk from get_merge_request_diffs[].diff):
  python diff-to-positions.py --diff-text "$HUNK" --path src/foo.py --line 42 ...

Comment on a purely removed (-) line (no new_line):
  python diff-to-positions.py --diff-file change.diff --path src/foo.py --old-line 17 ...

Batch mode — read a JSON array of findings on stdin, emit a JSON array of positions:
  echo '[{"path":"src/foo.py","line":42},{"path":"src/bar.py","old_line":7}]' \\
    | python diff-to-positions.py --batch --diff-file change.diff ...

Input formats accepted:
  * Standard unified diff with `diff --git` / `+++ b/<path>` headers (one or many files).
  * GitLab MCP headerless hunks — `get_merge_request_diffs` returns each file's `diff`
    as bare `@@ ... @@` hunks with NO file header. When no header is present, the whole
    input is treated as the diff for `--path`. (See reference/gitlab-inline-comments.md
    "Preparing diff input" for wrapping multi-file GitLab diffs.)

Emits the `position` JSON (omits diff_refs SHA keys when the SHAs are not supplied).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Iterator, Optional, Tuple

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
# Real unified-diff file headers, not content lines that merely start with +++/---.
# A `+++ b/path` / `+++ /dev/null` line is a header; an added line whose text begins
# with `++ ` (rendered as `+++ …`) is content. Same for `--- a/path` / `--- /dev/null`.
FILE_HEADER_NEW_RE = re.compile(r"^\+\+\+ (b/|/dev/null)")
FILE_HEADER_OLD_RE = re.compile(r"^--- (a/|/dev/null)")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diff-file", help="Path to unified diff file (default: stdin)")
    p.add_argument("--diff-text", help="Raw diff/hunk text passed inline instead of a file/stdin")
    p.add_argument("--path", help="new_path of the file to comment on (required unless --batch)")
    p.add_argument("--line", type=int, help="1-based line number in the NEW file")
    p.add_argument("--old-line", type=int, help="1-based line number in the OLD file (for removed `-` lines)")
    p.add_argument("--old-path", help="old_path if renamed (default: same as --path)")
    p.add_argument("--base-sha")
    p.add_argument("--start-sha")
    p.add_argument("--head-sha")
    p.add_argument(
        "--batch",
        action="store_true",
        help="Read a JSON array of {path, line|old_line, old_path?} on stdin; emit a JSON array.",
    )
    return p.parse_args()


def _matches_target(path_token: str, target_path: str) -> bool:
    """Exact match on the diff's `a/<path>` or `b/<path>` token (prefix stripped)."""
    if path_token.startswith(("a/", "b/")):
        path_token = path_token[2:]
    return path_token == target_path


def _has_file_headers(diff_text: str) -> bool:
    """True if the diff carries `diff --git` or a real `+++ b/…`/`+++ /dev/null` header.

    GitLab `get_merge_request_diffs` returns bare hunks with neither; in that case the
    whole input belongs to the target path. Content lines that merely start with `+++`
    (an added line whose text begins with `++ `) do NOT count as headers.
    """
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git ") or FILE_HEADER_NEW_RE.match(raw):
            return True
    return False


def iter_diff_lines(
    diff_text: str, target_path: str
) -> Iterator[Tuple[str, Optional[int], Optional[int]]]:
    """Yield (kind, new_no, old_no) for each content line inside the target file's hunks.

    kind is "add", "del", or "context". Only the target file's hunks are walked
    (matched exactly on the `+++ b/<path>` token); the region resets at each new
    `diff --git` header so look-alike paths in other files can't be matched by
    accident. Headerless GitLab hunks are treated as belonging entirely to
    target_path.

    Line numbers point at the line being yielded (match-then-increment), so the
    first content line of a hunk carries the hunk's start line number.
    """
    in_file = not _has_file_headers(diff_text)
    cur_new = 0
    cur_old = 0
    last_old_token = None

    for raw in diff_text.splitlines():
        line = raw.rstrip("\n")
        if line.startswith("diff --git "):
            in_file = False
            last_old_token = None
            continue
        if FILE_HEADER_OLD_RE.match(line):
            # Remember the old path so a deleted file (new side `/dev/null`) can still
            # be matched by its old path for `--old-line` anchoring.
            last_old_token = line[4:].strip()
            continue
        if FILE_HEADER_NEW_RE.match(line):
            new_token = line[4:].strip()
            if new_token == "/dev/null":
                in_file = _matches_target(last_old_token or "", target_path)
            else:
                in_file = _matches_target(new_token, target_path)
            continue
        if not in_file:
            continue
        m = HUNK_RE.match(line)
        if m:
            cur_old = int(m.group(1))
            cur_new = int(m.group(3))
            continue
        if line.startswith("\\"):  # "\ No newline at end of file"
            continue
        prefix = line[0] if line else " "

        if prefix == "+":
            yield ("add", cur_new, None)
            cur_new += 1
        elif prefix == "-":
            yield ("del", None, cur_old)
            cur_old += 1
        else:
            yield ("context", cur_new, cur_old)
            cur_new += 1
            cur_old += 1


def line_type_and_position(
    diff_text: str, target_path: str, new_line: int
) -> Optional[dict]:
    """Return {new_line, old_line} for a NEW-file line (added or context), or None."""
    for kind, new_no, old_no in iter_diff_lines(diff_text, target_path):
        if new_no != new_line:
            continue
        if kind == "add":
            return {"new_line": new_line, "old_line": None}
        if kind == "context":
            return {"new_line": new_line, "old_line": old_no}
    return None


def removed_line_position(
    diff_text: str, target_path: str, old_line: int
) -> Optional[dict]:
    """Return {new_line: None, old_line} for a removed (`-`) line, or None."""
    for kind, _new_no, old_no in iter_diff_lines(diff_text, target_path):
        if kind == "del" and old_no == old_line:
            return {"new_line": None, "old_line": old_line}
    return None


def build_position(
    diff_text: str,
    path: str,
    *,
    line: Optional[int],
    old_line: Optional[int],
    old_path: Optional[str],
    base_sha: Optional[str],
    start_sha: Optional[str],
    head_sha: Optional[str],
) -> dict:
    """Resolve one finding to a GitLab position dict; raise ValueError if not found."""
    if (line is None) == (old_line is None):
        raise ValueError("provide exactly one of line / old_line")

    if line is not None:
        coords = line_type_and_position(diff_text, path, line)
        if coords is None:
            raise ValueError(f"line {line} not found in diff for {path}")
    else:
        coords = removed_line_position(diff_text, path, old_line)
        if coords is None:
            raise ValueError(f"old line {old_line} not found in diff for {path}")

    position = {
        "position_type": "text",
        "old_path": old_path or path,
        "new_path": path,
        **coords,
    }
    if base_sha:
        position["base_sha"] = base_sha
    if start_sha:
        position["start_sha"] = start_sha
    if head_sha:
        position["head_sha"] = head_sha
    return position


def read_diff_text(args: argparse.Namespace) -> str:
    if args.diff_text is not None:
        return args.diff_text
    if args.diff_file:
        with open(args.diff_file, encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def main() -> None:
    args = parse_args()

    if args.batch:
        # Diff comes from --diff-text/--diff-file; findings come from stdin JSON.
        if args.diff_text is None and not args.diff_file:
            print(
                json.dumps({"error": "--batch requires --diff-text or --diff-file"}),
                file=sys.stderr,
            )
            sys.exit(2)
        diff_text = read_diff_text(args)
        try:
            items = json.loads(sys.stdin.read())
        except json.JSONDecodeError as exc:
            print(json.dumps({"error": f"invalid batch JSON: {exc}"}), file=sys.stderr)
            sys.exit(2)

        positions = []
        had_error = False
        for item in items:
            # A single unresolvable/failed finding must NOT abort the batch:
            # collect a per-item error entry and keep going so the good items still
            # produce valid positions.
            try:
                positions.append(
                    build_position(
                        diff_text,
                        item["path"],
                        line=item.get("line"),
                        old_line=item.get("old_line"),
                        old_path=item.get("old_path"),
                        base_sha=args.base_sha,
                        start_sha=args.start_sha,
                        head_sha=args.head_sha,
                    )
                )
            except (ValueError, KeyError) as exc:
                had_error = True
                error_entry = {
                    "path": item.get("path"),
                    "error": str(exc) if isinstance(exc, ValueError) else f"missing key: {exc}",
                }
                if "line" in item:
                    error_entry["line"] = item["line"]
                if "old_line" in item:
                    error_entry["old_line"] = item["old_line"]
                positions.append(error_entry)
        print(json.dumps(positions, indent=2))
        # Always emit results for all items; signal partial failure via exit code.
        sys.exit(1 if had_error else 0)

    if not args.path:
        print(json.dumps({"error": "--path is required"}), file=sys.stderr)
        sys.exit(2)

    diff_text = read_diff_text(args)
    try:
        position = build_position(
            diff_text,
            args.path,
            line=args.line,
            old_line=args.old_line,
            old_path=args.old_path,
            base_sha=args.base_sha,
            start_sha=args.start_sha,
            head_sha=args.head_sha,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(position, indent=2))


if __name__ == "__main__":
    main()
