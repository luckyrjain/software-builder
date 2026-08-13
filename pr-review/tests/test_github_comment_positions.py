"""Tests for GitHub RIGHT-side inline-comment anchors."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "github-comment-positions.py"
SPEC = importlib.util.spec_from_file_location("github_comment_positions", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate_github_anchor = MODULE.validate_github_anchor


def run_cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=input_text,
        capture_output=True,
        check=False,
        text=True,
    )

DIFF_WITH_ADDITION = """diff --git a/src/payments.py b/src/payments.py
--- a/src/payments.py
+++ b/src/payments.py
@@ -10,2 +10,3 @@
 one
+two
 three
"""
DIFF_WITH_REMOVAL = """diff --git a/src/payments.py b/src/payments.py
--- a/src/payments.py
+++ b/src/payments.py
@@ -10,2 +10,1 @@
 one
-two
"""
DIFF_WITH_REPLACEMENT = """diff --git a/src/payments.py b/src/payments.py
--- a/src/payments.py
+++ b/src/payments.py
@@ -10,2 +10,2 @@
 one
-old value
+new value
"""
DIFF_WITH_DELETION_THEN_CONTEXT = """diff --git a/src/payments.py b/src/payments.py
--- a/src/payments.py
+++ b/src/payments.py
@@ -10,3 +10,2 @@
 one
-deleted value
 trailing context
"""


def test_added_right_side_line_is_postable():
    assert validate_github_anchor(
        DIFF_WITH_ADDITION,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {
        "commit_id": "abc",
        "path": "src/payments.py",
        "line": 11,
        "side": "RIGHT",
    }


def test_removed_only_line_falls_back_to_summary():
    assert validate_github_anchor(
        DIFF_WITH_REMOVAL,
        path="src/payments.py",
        line=11,
        source_kind="removed",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "source_line_is_not_added",
    }


def test_unchanged_context_line_falls_back_to_summary():
    assert validate_github_anchor(
        DIFF_WITH_ADDITION,
        path="src/payments.py",
        line=10,
        source_kind="context",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "source_line_is_not_added",
    }


def test_removed_line_number_is_not_remapped_to_replacement_addition():
    assert validate_github_anchor(
        DIFF_WITH_REPLACEMENT,
        path="src/payments.py",
        line=11,
        source_kind="removed",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "source_line_is_not_added",
    }


def test_removed_line_number_is_not_remapped_to_following_context():
    assert validate_github_anchor(
        DIFF_WITH_DELETION_THEN_CONTEXT,
        path="src/payments.py",
        line=11,
        source_kind="removed",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "source_line_is_not_added",
    }


def test_absent_added_line_falls_back_to_summary():
    assert validate_github_anchor(
        DIFF_WITH_ADDITION,
        path="src/payments.py",
        line=99,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


def test_quoted_next_file_header_resets_file_state():
    diff = """diff --git a/src/payments.py b/src/payments.py
--- a/src/payments.py
+++ b/src/payments.py
@@ -1 +1 @@
 context only
diff --git \"a/src/other file.py\" \"b/src/other file.py\"
--- \"a/src/other file.py\"
+++ \"b/src/other file.py\"
@@ -11,0 +11,1 @@
+other file addition
"""
    assert validate_github_anchor(
        diff,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


def test_quoted_target_path_can_anchor_an_added_line():
    diff = """diff --git \"a/src/payment rules.py\" \"b/src/payment rules.py\"
--- \"a/src/payment rules.py\"
+++ \"b/src/payment rules.py\"
@@ -4,0 +5,1 @@
+new rule
"""
    assert validate_github_anchor(
        diff,
        path="src/payment rules.py",
        line=5,
        source_kind="added",
        head_sha="abc",
    ) == {
        "commit_id": "abc",
        "path": "src/payment rules.py",
        "line": 5,
        "side": "RIGHT",
    }


def test_deleted_file_header_resets_file_state():
    diff = """diff --git a/src/payments.py b/src/payments.py
--- a/src/payments.py
+++ b/src/payments.py
@@ -1 +1 @@
 context only
diff --git a/src/deleted.py b/src/deleted.py
--- a/src/deleted.py
+++ /dev/null
@@ -11 +0,0 @@
-deleted value
"""
    assert validate_github_anchor(
        diff,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


def test_marker_like_added_content_cannot_switch_files_in_combined_diff():
    diff = """diff --git a/src/payments.py b/src/payments.py
--- a/src/payments.py
+++ b/src/payments.py
@@ -10,0 +10,1 @@
+++ b/src/other.py
@@ -0,0 +50,1 @@
+forged cross-file addition
"""
    assert validate_github_anchor(
        diff,
        path="src/other.py",
        line=50,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


def test_marker_like_added_content_is_still_an_added_line_in_target_file():
    diff = """diff --git a/src/payments.py b/src/payments.py
--- a/src/payments.py
+++ b/src/payments.py
@@ -10,0 +10,1 @@
+++ b/src/other.py
"""
    assert validate_github_anchor(
        diff,
        path="src/payments.py",
        line=10,
        source_kind="added",
        head_sha="abc",
    ) == {
        "commit_id": "abc",
        "path": "src/payments.py",
        "line": 10,
        "side": "RIGHT",
    }


def test_headerless_per_file_patch_anchors_added_line_to_explicit_path():
    patch = """@@ -4,2 +4,3 @@
 context
+new rule
 trailing context
"""
    assert validate_github_anchor(
        patch,
        path="src/payment_rules.py",
        line=5,
        source_kind="added",
        head_sha="abc",
    ) == {
        "commit_id": "abc",
        "path": "src/payment_rules.py",
        "line": 5,
        "side": "RIGHT",
    }


def test_headerless_per_file_patch_rejects_context_and_absent_lines():
    patch = """@@ -4,2 +4,3 @@
 context
+new rule
 trailing context
"""
    assert validate_github_anchor(
        patch,
        path="src/payment_rules.py",
        line=4,
        source_kind="context",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "source_line_is_not_added",
    }
    assert validate_github_anchor(
        patch,
        path="src/payment_rules.py",
        line=99,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


def test_headerless_per_file_patch_rejects_removed_line():
    patch = """@@ -4,2 +4,1 @@
 context
-removed rule
"""
    assert validate_github_anchor(
        patch,
        path="src/payment_rules.py",
        line=5,
        source_kind="removed",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "source_line_is_not_added",
    }


def test_no_diff_git_concatenated_headers_do_not_cross_file_boundaries():
    patch = """--- a/src/payments.py
+++ b/src/payments.py
@@ -1 +1 @@
 context only
--- a/src/other.py
+++ b/src/other.py
@@ -10,0 +11,1 @@
+other file addition
"""
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


def test_no_diff_git_quoted_headers_bind_hunks_to_the_parsed_new_path():
    patch = """--- a/src/payments.py
+++ b/src/payments.py
@@ -1 +1 @@
 context only
--- "a/src/payment rules.py"
+++ "b/src/payment rules.py"
@@ -4,0 +5,1 @@
+new rule
"""
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=5,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }
    assert validate_github_anchor(
        patch,
        path="src/payment rules.py",
        line=5,
        source_kind="added",
        head_sha="abc",
    ) == {
        "commit_id": "abc",
        "path": "src/payment rules.py",
        "line": 5,
        "side": "RIGHT",
    }


def test_no_diff_git_deleted_and_created_files_reset_the_previous_path():
    patch = """--- a/src/payments.py
+++ b/src/payments.py
@@ -1 +1 @@
 context only
--- a/src/deleted.py
+++ /dev/null
@@ -11 +0,0 @@
-deleted value
--- /dev/null
+++ b/src/created.py
@@ -0,0 +11,1 @@
+created value
"""
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }
    assert validate_github_anchor(
        patch,
        path="src/created.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {
        "commit_id": "abc",
        "path": "src/created.py",
        "line": 11,
        "side": "RIGHT",
    }


def test_mixed_headerless_and_headerful_input_fails_closed():
    patch = """@@ -4,0 +5,1 @@
+candidate from an unbound hunk
--- a/src/other.py
+++ b/src/other.py
@@ -1,0 +1,1 @@
+other file addition
"""
    assert validate_github_anchor(
        patch,
        path="src/payment_rules.py",
        line=5,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


@pytest.mark.parametrize(
    "patch",
    [
        """diff --git a/src/payments.py b/src/payments.py
--- a/src/payments.py
+++ b/src/payments.py
@@ -10,3 +10,4 @@
 one
+target
""",
        """@@ -10,3 +10,4 @@
 one
+target
""",
    ],
)
def test_eof_before_declared_hunk_counts_rejects_a_candidate_anchor(patch):
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


def test_new_hunk_before_declared_counts_are_complete_rejects_the_candidate_anchor():
    patch = """@@ -10,3 +10,4 @@
 one
+target
@@ -20,0 +20,1 @@
+later
"""
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


def test_file_boundary_before_declared_counts_are_complete_never_satisfies_the_earlier_file():
    patch = """--- a/src/payments.py
+++ b/src/payments.py
@@ -10,2 +10,2 @@
 context
--- a/src/other.py
+++ b/src/other.py
@@ -20,0 +20,1 @@
+later
"""
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


def test_cli_reads_combined_diff_from_stdin_and_emits_json():
    result = run_cli(
        "--diff-stdin",
        "--path",
        "src/payments.py",
        "--line",
        "11",
        "--source-kind",
        "added",
        "--head-sha",
        "abc",
        input_text=DIFF_WITH_ADDITION,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "commit_id": "abc",
        "path": "src/payments.py",
        "line": 11,
        "side": "RIGHT",
    }
    assert result.stderr == ""


def test_cli_reads_headerless_diff_from_file_and_emits_json(tmp_path):
    diff_file = tmp_path / "change.diff"
    diff_file.write_text("@@ -4,0 +5,1 @@\n+new rule\n", encoding="utf-8")
    result = run_cli(
        "--diff-file",
        str(diff_file),
        "--path",
        "src/payment_rules.py",
        "--line",
        "5",
        "--source-kind",
        "added",
        "--head-sha",
        "abc",
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "commit_id": "abc",
        "path": "src/payment_rules.py",
        "line": 5,
        "side": "RIGHT",
    }


def test_cli_handles_concatenated_headerful_diff_without_diff_git():
    patch = """--- a/src/payments.py
+++ b/src/payments.py
@@ -1 +1 @@
 context
--- a/src/other.py
+++ b/src/other.py
@@ -10,0 +11,1 @@
+new rule
"""
    result = run_cli(
        "--diff-stdin",
        "--path",
        "src/other.py",
        "--line",
        "11",
        "--source-kind",
        "added",
        "--head-sha",
        "abc",
        input_text=patch,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "commit_id": "abc",
        "path": "src/other.py",
        "line": 11,
        "side": "RIGHT",
    }


def test_cli_reports_non_added_source_as_unanchorable():
    result = run_cli(
        "--diff-stdin",
        "--path",
        "src/payments.py",
        "--line",
        "11",
        "--source-kind",
        "removed",
        "--head-sha",
        "abc",
        input_text=DIFF_WITH_REMOVAL,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "unanchorable": True,
        "reason": "source_line_is_not_added",
    }


@pytest.mark.parametrize(
    "patch",
    [
        "@@ malformed @@\n+candidate\n",
        "@@ -10,3 +10,4 @@\n one\n+target\n",
    ],
)
def test_cli_reports_malformed_or_truncated_diff_as_unanchorable(patch):
    result = run_cli(
        "--diff-stdin",
        "--path",
        "src/payments.py",
        "--line",
        "11",
        "--source-kind",
        "added",
        "--head-sha",
        "abc",
        input_text=patch,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


def test_cli_missing_arguments_exits_with_usage_error():
    result = run_cli()
    assert result.returncode == 2
    assert result.stdout == ""
    assert "usage:" in result.stderr


def test_cli_help_describes_both_explicit_diff_input_modes():
    result = run_cli("--help")
    assert result.returncode == 0
    assert "--diff-file" in result.stdout
    assert "--diff-stdin" in result.stdout
    assert result.stderr == ""


def test_cli_unreadable_diff_file_exits_with_machine_readable_error(tmp_path):
    missing = tmp_path / "missing.diff"
    result = run_cli(
        "--diff-file",
        str(missing),
        "--path",
        "src/payments.py",
        "--line",
        "11",
        "--source-kind",
        "added",
        "--head-sha",
        "abc",
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert json.loads(result.stderr)["error"] == "diff_input_unavailable"
