"""Tests for scripts/diff-to-positions.py (run with: python3 -m pytest pr-review/tests/).

These tests pin the GitLab position-object mapping: added lines must return
{new_line: N, old_line: None}, context lines must return both, removed lines must
return {new_line: None, old_line: N}, and the parser must handle GitLab MCP
headerless hunks, renamed files, --diff-text input, and JSON batch mode.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "diff-to-positions.py"

SHAS = ["--base-sha", "BASE", "--start-sha", "START", "--head-sha", "HEAD"]

# A standard unified diff with full `diff --git` / `+++ b/` headers.
DIFF_WITH_HEADERS = """diff --git a/src/foo.py b/src/foo.py
index 1111111..2222222 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,4 @@
 line_one
+added_two
 line_three
 line_four
"""

# Diff that removes a line (to test removed-line + old_line counting).
DIFF_WITH_REMOVAL = """diff --git a/src/foo.py b/src/foo.py
index 1111111..2222222 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,2 @@
 context_one
-removed_two
 context_three
"""

# GitLab get_merge_request_diffs returns per-file hunks WITHOUT file headers.
HEADERLESS_HUNK = """@@ -1,3 +1,4 @@
 line_one
+added_two
 line_three
 line_four
"""

# Two files in one diff (for multi-file --batch): each carries its own `+++ b/` header.
DIFF_MULTI_FILE = DIFF_WITH_HEADERS + """diff --git a/src/bar.py b/src/bar.py
index 3333333..4444444 100644
--- a/src/bar.py
+++ b/src/bar.py
@@ -1,2 +1,3 @@
 bar_one
+bar_added_two
 bar_three
"""

# Renamed file: old path differs from new path.
DIFF_RENAMED = """diff --git a/src/old_name.py b/src/new_name.py
similarity index 90%
rename from src/old_name.py
rename to src/new_name.py
--- a/src/old_name.py
+++ b/src/new_name.py
@@ -1,2 +1,3 @@
 keep_one
+added_two
 keep_three
"""


def run(args, stdin=None):
    """Invoke the script; return (returncode, parsed_stdout_or_raw, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
    )
    parsed = None
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError:
            parsed = proc.stdout
    return proc.returncode, parsed, proc.stderr


def test_added_line_returns_new_line_only():
    rc, out, err = run(
        ["--path", "src/foo.py", "--line", "2", *SHAS],
        stdin=DIFF_WITH_HEADERS,
    )
    assert rc == 0, err
    assert out["new_line"] == 2
    assert out["old_line"] is None
    assert out["new_path"] == "src/foo.py"
    assert out["old_path"] == "src/foo.py"
    assert out["position_type"] == "text"
    assert out["head_sha"] == "HEAD"


def test_first_line_of_hunk_is_matched():
    # Regression for the off-by-one: the first content line of a hunk
    # (a context line at new line 1) must be matched at --line 1, not --line 2.
    rc, out, err = run(["--path", "src/foo.py", "--line", "1"], stdin=DIFF_WITH_HEADERS)
    assert rc == 0, err
    assert out["new_line"] == 1
    assert out["old_line"] == 1  # context line: both set


def test_context_line_returns_both():
    rc, out, err = run(["--path", "src/foo.py", "--line", "3"], stdin=DIFF_WITH_HEADERS)
    assert rc == 0, err
    # new line 3 is "line_three", a context line after one addition.
    assert out["new_line"] == 3
    assert out["old_line"] == 2


def test_removed_line_returns_old_line_only():
    rc, out, err = run(
        ["--path", "src/foo.py", "--old-line", "2", *SHAS],
        stdin=DIFF_WITH_REMOVAL,
    )
    assert rc == 0, err
    assert out["new_line"] is None
    assert out["old_line"] == 2


def test_removed_line_advances_old_counter_for_following_context():
    # context_three is new line 2, old line 3 (the removed line consumed old line 2).
    rc, out, err = run(["--path", "src/foo.py", "--line", "2"], stdin=DIFF_WITH_REMOVAL)
    assert rc == 0, err
    assert out["new_line"] == 2
    assert out["old_line"] == 3


def test_renamed_file_uses_old_path():
    rc, out, err = run(
        ["--path", "src/new_name.py", "--old-path", "src/old_name.py", "--line", "2"],
        stdin=DIFF_RENAMED,
    )
    assert rc == 0, err
    assert out["new_path"] == "src/new_name.py"
    assert out["old_path"] == "src/old_name.py"
    assert out["new_line"] == 2
    assert out["old_line"] is None


def test_headerless_gitlab_hunk():
    rc, out, err = run(
        ["--path", "src/foo.py", "--line", "2", *SHAS],
        stdin=HEADERLESS_HUNK,
    )
    assert rc == 0, err
    assert out["new_line"] == 2
    assert out["old_line"] is None
    assert out["new_path"] == "src/foo.py"


def test_diff_text_argument_mode():
    rc, out, err = run(
        ["--path", "src/foo.py", "--line", "2", "--diff-text", HEADERLESS_HUNK]
    )
    assert rc == 0, err
    assert out["new_line"] == 2
    assert out["old_line"] is None


def test_batch_mode_emits_array():
    items = [
        {"path": "src/foo.py", "line": 2},
        {"path": "src/foo.py", "line": 3},
    ]
    rc, out, err = run(["--batch", "--diff-text", DIFF_WITH_HEADERS], stdin=json.dumps(items))
    assert rc == 0, err
    assert isinstance(out, list)
    assert len(out) == 2
    assert out[0]["new_line"] == 2 and out[0]["old_line"] is None
    assert out[1]["new_line"] == 3 and out[1]["old_line"] == 2


def test_line_not_found_errors():
    rc, out, err = run(["--path", "src/foo.py", "--line", "999"], stdin=DIFF_WITH_HEADERS)
    assert rc != 0
    assert "not found" in err


# Headerless hunks whose CONTENT lines look like file headers once prefixed:
# an added line whose text starts with "++ " becomes "+++ …"; a removed line whose
# text starts with "-- " becomes "--- …". These must be parsed as content, not headers.
HEADERLESS_ADDED_LOOKS_LIKE_HEADER = """@@ -1,2 +1,3 @@
 keep_one
+++ added line whose text begins with plus signs
 keep_tail
"""

HEADERLESS_REMOVED_LOOKS_LIKE_HEADER = """@@ -1,3 +1,2 @@
 keep_one
--- removed line whose text begins with minus signs
 keep_tail
"""


def test_headerless_added_line_starting_with_plus_is_content_not_header():
    rc, out, err = run(
        ["--path", "src/foo.py", "--line", "2"],
        stdin=HEADERLESS_ADDED_LOOKS_LIKE_HEADER,
    )
    assert rc == 0, err
    assert out["new_line"] == 2
    assert out["old_line"] is None


HEADERLESS_ADDED_LINE_MATCHES_HEADER_REGEX = """@@ -1,4 +1,5 @@
 context line 1
+real added line
+++ b/other.py
 context line 2
 context line 3
"""


def test_headerless_added_line_exactly_matching_header_regex_is_content_not_header():
    # The added line's own text is `++ b/other.py` — with the diff's `+` prefix
    # prepended it renders as `+++ b/other.py`, which is syntactically identical
    # to a real unified-diff file header. It must still be treated as content
    # since it falls inside the hunk's declared line budget (5 new lines).
    rc, out, err = run(
        ["--path", "src/foo.py", "--line", "5"],
        stdin=HEADERLESS_ADDED_LINE_MATCHES_HEADER_REGEX,
    )
    assert rc == 0, err
    assert out["new_line"] == 5
    assert out["old_line"] == 3


def test_headerless_removed_line_starting_with_minus_is_content_not_header():
    rc, out, err = run(
        ["--path", "src/foo.py", "--old-line", "2"],
        stdin=HEADERLESS_REMOVED_LOOKS_LIKE_HEADER,
    )
    assert rc == 0, err
    assert out["new_line"] is None
    assert out["old_line"] == 2


# New file: the OLD side is /dev/null, every line is an addition.
DIFF_NEW_FILE = """diff --git a/src/brand_new.py b/src/brand_new.py
new file mode 100644
index 0000000..2222222
--- /dev/null
+++ b/src/brand_new.py
@@ -0,0 +1,3 @@
+first_added
+second_added
+third_added
"""

# Deleted file (full unified diff): the NEW side is /dev/null, every line is a removal.
DIFF_DELETED_FILE = """diff --git a/src/gone.py b/src/gone.py
deleted file mode 100644
index 1111111..0000000
--- a/src/gone.py
+++ /dev/null
@@ -1,3 +0,0 @@
-removed_one
-removed_two
-removed_three
"""

# Deleted file as GitLab returns it: bare hunk, all removals, no headers.
HEADERLESS_DELETED_HUNK = """@@ -1,3 +0,0 @@
-removed_one
-removed_two
-removed_three
"""


def test_new_file_added_line_with_dev_null_old_header():
    # `--- /dev/null` must be treated as a file header, and the added line on the
    # new side resolves to new_line set / old_line None.
    rc, out, err = run(
        ["--path", "src/brand_new.py", "--line", "2", *SHAS],
        stdin=DIFF_NEW_FILE,
    )
    assert rc == 0, err
    assert out["new_line"] == 2
    assert out["old_line"] is None
    assert out["new_path"] == "src/brand_new.py"


def test_deleted_file_headerless_removed_line():
    # GitLab returns a deleted file's diff as a bare removal hunk; --old-line must map it.
    rc, out, err = run(
        ["--path", "src/gone.py", "--old-line", "2", *SHAS],
        stdin=HEADERLESS_DELETED_HUNK,
    )
    assert rc == 0, err
    assert out["new_line"] is None
    assert out["old_line"] == 2
    assert out["old_path"] == "src/gone.py"


def test_deleted_file_full_diff_removed_line_matches_by_old_path():
    # Full unified diff for a deleted file has `+++ /dev/null` on the new side; the
    # region must still be matchable by its old path so --old-line resolves.
    rc, out, err = run(
        ["--path", "src/gone.py", "--old-line", "2", *SHAS],
        stdin=DIFF_DELETED_FILE,
    )
    assert rc == 0, err
    assert out["new_line"] is None
    assert out["old_line"] == 2


def test_diff_file_mode(tmp_path):
    diff_path = tmp_path / "change.diff"
    diff_path.write_text(DIFF_WITH_HEADERS, encoding="utf-8")
    rc, out, err = run(
        ["--path", "src/foo.py", "--line", "2", "--diff-file", str(diff_path), *SHAS]
    )
    assert rc == 0, err
    assert out["new_line"] == 2
    assert out["old_line"] is None


def test_neither_line_nor_old_line_is_error():
    rc, out, err = run(["--path", "src/foo.py", *SHAS], stdin=DIFF_WITH_HEADERS)
    assert rc != 0
    assert "exactly one" in err


def test_both_line_and_old_line_is_error():
    rc, out, err = run(
        ["--path", "src/foo.py", "--line", "2", "--old-line", "1", *SHAS],
        stdin=DIFF_WITH_HEADERS,
    )
    assert rc != 0
    assert "exactly one" in err


def test_batch_one_failure_does_not_abort_rest():
    # Item 1 is valid, item 2 is unresolvable, item 3 is valid: all three must come back,
    # the bad one carrying an `error` field and the good ones carrying valid positions.
    items = [
        {"path": "src/foo.py", "line": 2},
        {"path": "src/foo.py", "line": 999},
        {"path": "src/foo.py", "line": 3},
    ]
    rc, out, err = run(["--batch", "--diff-text", DIFF_WITH_HEADERS], stdin=json.dumps(items))
    assert rc == 1, err  # partial failure exits 1 (a clean batch exits 0, see test_batch_mode_emits_array)
    assert isinstance(out, list), err
    assert len(out) == 3
    # Good items keep valid positions.
    assert out[0]["new_line"] == 2 and out[0]["old_line"] is None
    assert "error" not in out[0]
    assert out[2]["new_line"] == 3 and out[2]["old_line"] == 2
    assert "error" not in out[2]
    # Bad item carries an error and echoes its input.
    assert "error" in out[1]
    assert "not found" in out[1]["error"]
    assert out[1]["path"] == "src/foo.py"
    assert out[1]["line"] == 999


def test_batch_multi_file_resolves_each_to_its_own_file():
    # Two items targeting two different files in one multi-file diff: each must
    # resolve against its own `+++ b/<path>` header, and the batch exits 0.
    items = [
        {"path": "src/foo.py", "line": 2},
        {"path": "src/bar.py", "line": 2},
    ]
    rc, out, err = run(["--batch", "--diff-text", DIFF_MULTI_FILE], stdin=json.dumps(items))
    assert rc == 0, err
    assert isinstance(out, list)
    assert len(out) == 2
    assert out[0]["new_path"] == "src/foo.py" and out[0]["new_line"] == 2
    assert "error" not in out[0]
    assert out[1]["new_path"] == "src/bar.py" and out[1]["new_line"] == 2
    assert "error" not in out[1]


def test_batch_headerless_multiple_paths_raises():
    # A headerless diff (GitLab MCP per-file hunk) belongs to exactly one file. If a
    # caller mistakenly batches items for two different paths against one headerless
    # blob, iter_diff_lines() would treat the whole blob as belonging to whichever path
    # it's asked about — silently resolving item B's line against item A's hunk content.
    # This must fail loudly instead of guessing.
    items = [
        {"path": "src/foo.py", "line": 2},
        {"path": "src/bar.py", "line": 2},
    ]
    rc, out, err = run(["--batch", "--diff-text", HEADERLESS_HUNK], stdin=json.dumps(items))
    assert rc == 2, err
    assert "headerless" in err
    assert "src/foo.py" in err and "src/bar.py" in err


def test_batch_headerless_single_path_still_works():
    # Sanity check: headerless + --batch is fine as long as every item shares one path
    # (the documented per-file GitLab MCP use case) — must not be broken by the new guard.
    items = [
        {"path": "src/foo.py", "line": 2},
        {"path": "src/foo.py", "line": 3},
    ]
    rc, out, err = run(["--batch", "--diff-text", HEADERLESS_HUNK], stdin=json.dumps(items))
    assert rc == 0, err
    assert isinstance(out, list)
    assert len(out) == 2
    assert out[0]["new_line"] == 2 and "error" not in out[0]
