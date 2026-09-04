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
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterator, Optional, Tuple

SKILL_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_DIR = Path(__file__).resolve().parent
_INSTALL_MANIFEST = ".software-builder-manifest.json"
_RUNTIME_DESCRIPTION = "shared unified-diff runtime"


def _shared_runtime_loader() -> ModuleType:
    """Import shared_runtime_loader, which owns the containment policy for every module this
    script executes out of docs/skill-framework/shared/.

    Only locating the loader itself is handled here, and it needs no policy of its own: an
    installed package carries the loader beside this script (package_skill.py vendors it), so the
    lookup never leaves the package, and the install manifest is what proves a missing vendored
    copy is a packaging fault rather than an invitation to read a sibling path.
    """
    beside = _SCRIPT_DIR / "shared_runtime_loader.py"
    if beside.is_file():
        path = beside
    elif (SKILL_ROOT / _INSTALL_MANIFEST).is_file():
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {beside}")
    else:
        path = SKILL_ROOT.parent / "docs/skill-framework/shared/shared_runtime_loader.py"
    if not path.is_file():
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    spec = importlib.util.spec_from_file_location("software_builder_shared_runtime_loader", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_unified_diff = _shared_runtime_loader().load_shared_runtime(
    SKILL_ROOT,
    "unified_diff",
    alias="shared_unified_diff",
    description=_RUNTIME_DESCRIPTION,
)

HUNK_RE = _unified_diff.HUNK_HEADER
# Real unified-diff file headers, not content lines that merely start with +++/---.
# A `+++ b/path` / `+++ /dev/null` line is a header; an added line whose text begins
# with `++ ` (rendered as `+++ …`) is content. Same for `--- a/path` / `--- /dev/null`.
# Position (between hunks, never inside one) settles the rest -- see _classify_diff_lines.
FILE_HEADER_NEW_RE = _unified_diff.FILE_MARKER_NEW
FILE_HEADER_OLD_RE = _unified_diff.FILE_MARKER_OLD


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
    for side in ("a", "b"):
        stripped = _unified_diff.strip_side_prefix(path_token, side)
        if stripped is not None:
            return stripped == target_path
    return path_token == target_path


def _classify_diff_lines(diff_text: str) -> Iterator[Tuple[str, str]]:
    """Yield (line, role) for each line, where role is one of:
    "diff_git", "header_old", "header_new", "hunk", "content".

    A line that syntactically matches a header pattern (`+++ b/…`, `--- a/…`) is
    still classified as "content" when it falls inside an active hunk's declared
    line budget (tracked from the hunk's `@@ -old,count +new,count @@` header) —
    this is how a genuine added/removed line whose *text* happens to render as
    `+++ b/path` (i.e. the line's own content begins with `++ b/path`) is told
    apart from a real unified-diff file-boundary header. Real file headers only
    ever appear between hunks, never inside one.
    """
    hunk_old_end: Optional[int] = None
    hunk_new_end: Optional[int] = None
    cur_old = 0
    cur_new = 0

    for raw in diff_text.splitlines():
        line = raw.rstrip("\n")
        in_hunk_body = hunk_old_end is not None and (
            cur_old < hunk_old_end or cur_new < hunk_new_end
        )

        if line.startswith("diff --git "):
            hunk_old_end = hunk_new_end = None
            yield line, "diff_git"
            continue
        if not in_hunk_body and FILE_HEADER_OLD_RE.match(line):
            yield line, "header_old"
            continue
        if not in_hunk_body and FILE_HEADER_NEW_RE.match(line):
            yield line, "header_new"
            continue

        m = HUNK_RE.match(line)
        if m:
            cur_old = int(m.group(1))
            cur_new = int(m.group(3))
            old_count = int(m.group(2)) if m.group(2) else 1
            new_count = int(m.group(4)) if m.group(4) else 1
            hunk_old_end = cur_old + old_count
            hunk_new_end = cur_new + new_count
            yield line, "hunk"
            continue

        yield line, "content"
        if in_hunk_body and not line.startswith("\\"):
            prefix = line[0] if line else " "
            if prefix == "+":
                cur_new += 1
            elif prefix == "-":
                cur_old += 1
            else:
                cur_new += 1
                cur_old += 1


def _has_file_headers(diff_text: str) -> bool:
    """True if the diff carries `diff --git` or a real `+++ b/…`/`+++ /dev/null` header.

    GitLab `get_merge_request_diffs` returns bare hunks with neither; in that case the
    whole input belongs to the target path. Content lines that merely start with `+++`
    (an added line whose text begins with `++ `) do NOT count as headers — including
    when that content line occurs mid-hunk, which a naive per-line regex scan would
    misclassify (see `_classify_diff_lines`).
    """
    for _line, role in _classify_diff_lines(diff_text):
        if role in ("diff_git", "header_new"):
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

    for line, role in _classify_diff_lines(diff_text):
        if role == "diff_git":
            in_file = False
            last_old_token = None
            continue
        if role == "header_old":
            # Remember the old path so a deleted file (new side `/dev/null`) can still
            # be matched by its old path for `--old-line` anchoring.
            last_old_token = line[4:].strip()
            continue
        if role == "header_new":
            new_token = line[4:].strip()
            if new_token == "/dev/null":
                in_file = _matches_target(last_old_token or "", target_path)
            else:
                in_file = _matches_target(new_token, target_path)
            continue
        if not in_file:
            continue
        if role == "hunk":
            m = HUNK_RE.match(line)
            cur_old = int(m.group(1))
            cur_new = int(m.group(3))
            continue
        # role == "content"
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

        if not _has_file_headers(diff_text):
            # A headerless diff (GitLab MCP per-file hunk) belongs entirely to ONE file.
            # Batching items for more than one distinct path against it is ambiguous:
            # iter_diff_lines() would silently treat the whole blob as every path's
            # file, matching by line number alone and mis-anchoring findings onto the
            # wrong file's diff content. Fail loudly instead of guessing.
            distinct_paths = sorted(
                {item.get("path") for item in items if isinstance(item, dict) and item.get("path")}
            )
            if len(distinct_paths) > 1:
                print(
                    json.dumps(
                        {
                            "error": (
                                "headerless diff (--diff-text/--diff-file with no file headers) "
                                "can only resolve findings for one file, but batch items reference "
                                f"{len(distinct_paths)} distinct paths: {distinct_paths}. Invoke "
                                "--batch once per file with that file's own headerless hunk, or "
                                "wrap multi-file GitLab diffs with proper `+++ b/<path>` headers "
                                "first (see reference/gitlab-inline-comments.md)."
                            )
                        }
                    ),
                    file=sys.stderr,
                )
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
