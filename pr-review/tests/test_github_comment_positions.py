"""Tests for GitHub RIGHT-side inline-comment anchors."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zlib

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "github-comment-positions.py"
SPEC = importlib.util.spec_from_file_location("github_comment_positions", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate_github_anchor = MODULE.validate_github_anchor
FULL_BINARY_INDEX = (
    "index 1111111111111111111111111111111111111111.."
    "2222222222222222222222222222222222222222 100644"
)


def git_base85_lines(data: bytes) -> list[str]:
    alphabet = MODULE.GIT_BASE85_ALPHABET
    lines: list[str] = []
    for start in range(0, len(data), 52):
        chunk = data[start : start + 52]
        length_code = chr(ord("A") + len(chunk) - 1) if len(chunk) <= 26 else chr(
            ord("a") + len(chunk) - 27
        )
        padded = chunk + b"\0" * ((4 - len(chunk) % 4) % 4)
        encoded = []
        for group_start in range(0, len(padded), 4):
            value = int.from_bytes(padded[group_start : group_start + 4], "big")
            digits = [""] * 5
            for index in range(4, -1, -1):
                value, remainder = divmod(value, 85)
                digits[index] = alphabet[remainder]
            encoded.extend(digits)
        lines.append(length_code + "".join(encoded))
    return lines


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
@@ -1 +0,0 @@
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
@@ -9,0 +10,1 @@
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
@@ -9,0 +10,1 @@
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
-old
+new
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
-old
+new
--- a/src/deleted.py
+++ /dev/null
@@ -1 +0,0 @@
-deleted value
--- /dev/null
+++ b/src/created.py
@@ -0,0 +1,1 @@
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
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {
        "commit_id": "abc",
        "path": "src/created.py",
        "line": 1,
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
-old
+new
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


def test_cli_invalid_utf8_diff_file_exits_with_machine_readable_error(tmp_path):
    invalid = tmp_path / "invalid.diff"
    invalid.write_bytes(b"\xff\xfe\x00")
    result = run_cli(
        "--diff-file",
        str(invalid),
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


def _strict_grammar_patch(mode: str, hunk_text: str) -> str:
    if mode == "headerless":
        return hunk_text
    target = (
        "diff --git a/src/payments.py b/src/payments.py\n"
        if mode == "combined"
        else "--- a/src/other.py\n+++ b/src/other.py\n@@ -1 +1 @@\n-old\n+new\n"
    )
    return target + "--- a/src/payments.py\n+++ b/src/payments.py\n" + hunk_text


@pytest.mark.parametrize("mode", ["combined", "headerless", "concatenated"])
@pytest.mark.parametrize(
    "hunk_text,target_line",
    [
        ("@@ -10,0 +10,2 @@\n impossible context\n+target\n", 11),
        ("@@ -10,2 +10,1 @@\n+target\n impossible\n impossible again\n", 10),
        ("@@ -10,0 +10,2 @@\n-impossible\n+target\n+other\n", 10),
        (
            "@@ -10,0 +10,1 @@\n+target\n"
            "@@ -20,1 +20,0 @@\n+impossible\n-deleted\n",
            10,
        ),
        (
            "@@ -10,0 +10,1 @@\n+target\n"
            "@@ -0,1 +20,1 @@\n invalid zero start\n",
            10,
        ),
        ("@@ -10,0 +10,1 @@\n+target\n+surplus body\n", 10),
        ("@@ -10,0 +10,1 @@\n+target\n@@ -5,0 +5,0 @@\n", 10),
        ("@@ -10,0 +10,1 @@\n+target\n@@ -20,1 +20,1 @@\n context only\n", 10),
    ],
    ids=[
        "context-without-old-range",
        "context-without-new-range",
        "deletion-without-old-range",
        "addition-without-new-range",
        "nonempty-range-with-zero-start",
        "surplus-body",
        "empty-hunk",
        "context-only-hunk",
    ],
)
def test_strict_hunk_grammar_rejects_malformed_body_in_every_input_mode(
    mode,
    hunk_text,
    target_line,
):
    assert validate_github_anchor(
        _strict_grammar_patch(mode, hunk_text),
        path="src/payments.py",
        line=target_line,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


@pytest.mark.parametrize("mode", ["combined", "headerless", "concatenated"])
def test_strict_hunk_grammar_retains_complete_valid_hunks(mode):
    patch = _strict_grammar_patch(
        mode,
        "@@ -10,2 +10,3 @@\n context\n+target\n trailing\n",
    )
    assert validate_github_anchor(
        patch,
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


@pytest.mark.parametrize("mode", ["combined", "headerless", "concatenated"])
@pytest.mark.parametrize(
    "hunk_text,target_line",
    [
        ("@@ -1,1 +1,2 @@\n\\ No newline at end of file\n context\n+target\n", 2),
        (
            (
                "@@ -1,1 +1,2 @@\n context\n\\ No newline at end of file\n"
                "\\ No newline at end of file\n+target\n"
            ),
            2,
        ),
        (
            (
                "@@ -1,1 +1,2 @@\n context\n+target\n"
                "@@ -4,1 +5,1 @@\n\\ No newline at end of file\n context\n"
            ),
            2,
        ),
        ("@@ -1,0 +1,2 @@\n+first\n\\ No newline at end of file\n+target\n", 2),
        (
            (
                "@@ -1,0 +1,1 @@\n+first\n\\ No newline at end of file\n"
                "@@ -4,0 +5,1 @@\n+target\n"
            ),
            5,
        ),
        (
            (
                "@@ -1,0 +1,1 @@\n+target\n\\ No newline at end of file\n"
                "@@ -4,1 +5,1 @@\n context\n"
            ),
            1,
        ),
        (
            (
                "@@ -1,1 +1,1 @@\n-removed\n\\ No newline at end of file\n+target\n"
                "@@ -4,1 +4,0 @@\n-later removal\n"
            ),
            1,
        ),
        (
            (
                "@@ -1,0 +1,1 @@\n+target\n\\ No newline at end of file\n"
                "@@ -4,1 +2,0 @@\n-later removal\n"
            ),
            1,
        ),
    ],
    ids=(
        "leading",
        "repeated",
        "next-hunk-leading",
        "before-new-side-eof",
        "later-hunk-after-new-side-eof",
        "later-context-after-new-side-eof",
        "later-removal-after-old-side-eof",
        "deletion-only-hunk-after-new-side-eof",
    ),
)
def test_no_newline_diagnostic_is_rejected_outside_legal_body_position(
    mode, hunk_text, target_line
):
    assert validate_github_anchor(
        _strict_grammar_patch(mode, hunk_text),
        path="src/payments.py",
        line=target_line,
        source_kind="added",
        head_sha="abc",
    ) == {
        "unanchorable": True,
        "reason": "added_line_not_in_current_diff",
    }


@pytest.mark.parametrize("mode", ["combined", "headerless", "concatenated"])
@pytest.mark.parametrize(
    "hunk_text,target_line",
    [
        ("@@ -0,0 +1,1 @@\n+target\n\\ No newline at end of file\n", 1),
        (
            "@@ -1,1 +1,1 @@\n-removed\n\\ No newline at end of file\n"
            "+target\n\\ No newline at end of file\n",
            1,
        ),
        ("@@ -1,1 +1,2 @@\n+target\n context\n\\ No newline at end of file\n", 1),
    ],
    ids=("after-addition", "after-removal-before-addition", "after-final-context"),
)
def test_no_newline_diagnostic_is_valid_once_after_a_body_record(mode, hunk_text, target_line):
    result = validate_github_anchor(
        _strict_grammar_patch(mode, hunk_text),
        path="src/payments.py",
        line=target_line,
        source_kind="added",
        head_sha="abc",
    )
    assert result == {
        "commit_id": "abc",
        "path": "src/payments.py",
        "line": target_line,
        "side": "RIGHT",
    }


@pytest.mark.parametrize(
    "trailing_section",
    [
        "diff --git a/src/next.py b/src/next.py\n",
        "diff --git a/src/next.py b/src/next.py\n--- a/src/next.py\n",
        "diff --git a/src/next.py b/src/next.py\nindex 1234567..89abcde 100644\n",
        "diff --git a/src/next.py b/src/next.py\n@@ -1,0 +1,1 @@\n+unmarked\n",
        "diff --git a/bin.dat b/bin.dat\nGIT binary patch\nliteral 4\n",
        (
            "diff --git a/not-empty b/not-empty\nnew file mode 100644\n"
            "index 0000000..1234567\n"
        ),
        "diff --git a/bin.dat b/bin.dat\nGIT binary patch\nliteral nope\nLgarbage\n",
        (
            "diff --git a/bin.dat b/bin.dat\nGIT binary patch\nliteral 4\n"
            "Lc$@<O00001\nliteral 4\n"
        ),
        "diff --git a/script.sh b/script.sh\nold mode nope\nnew mode nope\n",
        (
            "diff --git a/old b/new\nsimilarity index nope\n"
            "rename from old\nrename to new\ngarbage\n"
        ),
        (
            "diff --git a/old b/new\nsimilarity index 101%\n"
            "copy from old\ncopy to new\n"
        ),
        (
            "diff --git a/empty b/empty\nnew file mode 100644\n"
            "index 0000000..e69de29\ngarbage\n"
        ),
        (
            "diff --git a/x.dat b/x.dat\ngarbage\n"
            "Binary files a/x.dat and b/x.dat differ\nmore-garbage\n"
        ),
        (
            "diff --git a/old b/new\nsimilarity index 100%\n"
            "rename from unrelated-old\nrename to unrelated-new\n"
        ),
        (
            "diff --git a/bin.dat b/bin.dat\n"
            "index 1111111111111111111111111111111111111111.."
            "2222222222222222222222222222222222222222 100644\n"
            "GIT binary patch\nliteral 4\nLc$@<O00001\n\n"
        ),
        (
            "diff --git a/next.py b/next.py extra\n"
            "--- a/next.py\n+++ b/next.py\n@@ -0,0 +1,1 @@\n+new\n"
        ),
    ],
    ids=(
        "bare-header",
        "incomplete-marker-pair",
        "incomplete-index-header",
        "unmarked-hunk",
        "binary-size-without-payload",
        "nonempty-new-file-metadata",
        "nonnumeric-binary-size",
        "truncated-second-binary-block",
        "invalid-mode-syntax",
        "invalid-rename-metadata",
        "invalid-copy-percentage",
        "empty-file-trailing-record",
        "binary-summary-with-garbage",
        "rename-path-mismatch",
        "one-block-binary-patch",
        "extra-diff-header-token",
    ),
)
def test_truncated_trailing_combined_section_invalidates_prior_anchor(trailing_section):
    patch = (
        "diff --git a/src/payments.py b/src/payments.py\n"
        "--- a/src/payments.py\n+++ b/src/payments.py\n"
        "@@ -0,0 +1,1 @@\n+target\n"
        + trailing_section
    )
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize(
    "complete_section",
    [
        (
            "diff --git a/src/old.py b/src/new.py\n"
            "similarity index 100%\nrename from src/old.py\nrename to src/new.py\n"
        ),
        (
            "diff --git a/src/old.py b/src/new.py\n"
            "similarity index 75%\ncopy from src/old.py\ncopy to src/new.py\n"
        ),
        "diff --git a/bin.dat b/bin.dat\nBinary files a/bin.dat and b/bin.dat differ\n",
        "diff --git a/script.sh b/script.sh\nold mode 100644\nnew mode 100755\n",
        "diff --git a/empty b/empty\nnew file mode 100644\nindex 0000000..e69de29\n",
        (
            "diff --git a/bin.dat b/bin.dat\n"
            "index 1111111111111111111111111111111111111111.."
            "2222222222222222222222222222222222222222 100644\n"
            "GIT binary patch\nliteral 4\n"
            "LcmZQzWMT#Y01f~L\n\nliteral 0\nHcmV?d00001\n\n"
        ),
        (
            "diff --git a/new.bin b/new.bin\nnew file mode 100644\n"
            "index 0000000000000000000000000000000000000000.."
            "2222222222222222222222222222222222222222\n"
            "GIT binary patch\nliteral 4\n"
            "LcmZQzWMT#Y01f~L\n\nliteral 0\nHcmV?d00001\n\n"
        ),
        (
            "diff --git a/old.bin b/old.bin\ndeleted file mode 100644\n"
            "index 1111111111111111111111111111111111111111.."
            "0000000000000000000000000000000000000000\n"
            "GIT binary patch\nliteral 0\n"
            "HcmV?d00001\n\nliteral 4\nLcmZQzWMT#Y01f~L\n\n"
        ),
    ],
    ids=(
        "rename",
        "copy",
        "binary",
        "mode-only",
        "empty-file",
        "git-binary-payload",
        "new-binary-file",
        "deleted-binary-file",
    ),
)
def test_recognized_non_hunk_section_does_not_invalidate_prior_anchor(complete_section):
    patch = (
        "diff --git a/src/payments.py b/src/payments.py\n"
        "--- a/src/payments.py\n+++ b/src/payments.py\n"
        "@@ -0,0 +1,1 @@\n+target\n"
        + complete_section
    )
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"commit_id": "abc", "path": "src/payments.py", "line": 1, "side": "RIGHT"}


def test_combined_section_cannot_switch_files_without_another_diff_git_header():
    patch = (
        "diff --git a/one b/one\n--- a/one\n+++ b/one\n"
        "@@ -1 +1 @@\n context\n"
        "--- a/src/payments.py\n+++ b/src/payments.py\n"
        "@@ -0,0 +1,1 @@\n+target\n"
    )
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize(
    "old_marker,new_marker",
    [
        ('--- "unterminated', "+++ b/src/payments.py"),
        ("--- a/src/payments.py", '+++ "unterminated'),
        ("--- ", "+++ b/src/payments.py"),
    ],
    ids=("invalid-old-quote", "invalid-new-quote", "empty-old-marker"),
)
def test_invalid_file_markers_fail_closed(old_marker, new_marker):
    patch = (
        "diff --git a/src/payments.py b/src/payments.py\n"
        f"{old_marker}\n{new_marker}\n"
        "@@ -0,0 +1,1 @@\n+target\n"
    )
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


def test_concatenated_section_with_bare_trailing_marker_pair_invalidates_prior_anchor():
    patch = (
        "--- a/src/payments.py\n+++ b/src/payments.py\n"
        "@@ -0,0 +1,1 @@\n+target\n"
        "--- a/src/next.py\n+++ b/src/next.py\n"
    )
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize("mode", ["combined", "headerless", "concatenated"])
@pytest.mark.parametrize(
    "hunks,target_line",
    [
        ("@@ -10,0 +10,1 @@\n+target\n@@ -5,0 +5,1 @@\n+earlier\n", 10),
        (
            "@@ -10,2 +10,3 @@\n context\n+target\n trailing\n"
            "@@ -11,1 +13,1 @@\n overlapping\n",
            11,
        ),
        (
            "@@ -10,1 +10,2 @@\n context\n+target\n"
            "@@ -11,1 +11,1 @@\n reverse-new-side\n",
            11,
        ),
        (
            "@@ -1,1 +1,1 @@\n context\n"
            "@@ -10,1 +100,2 @@\n context\n+target\n",
            101,
        ),
    ],
    ids=("reverse-ordered", "old-range-overlap", "new-range-overlap", "unequal-gap"),
)
def test_hunk_ranges_must_be_monotonic_and_non_overlapping(mode, hunks, target_line):
    assert validate_github_anchor(
        _strict_grammar_patch(mode, hunks),
        path="src/payments.py",
        line=target_line,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize("mode", ["combined", "headerless", "concatenated"])
@pytest.mark.parametrize(
    "hunk,target_line",
    [
        ("@@ -1,0 +100,1 @@\n+target\n", 100),
        ("@@ -100,1 +1,2 @@\n context\n+target\n", 2),
    ],
    ids=("new-prefix-jump", "old-prefix-jump"),
)
def test_first_hunk_requires_equal_unchanged_prefixes(mode, hunk, target_line):
    assert validate_github_anchor(
        _strict_grammar_patch(mode, hunk),
        path="src/payments.py",
        line=target_line,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize("mode", ["combined", "headerless", "concatenated"])
def test_addition_before_removal_in_same_change_group_fails_closed(mode):
    assert validate_github_anchor(
        _strict_grammar_patch(mode, "@@ -1,1 +1,1 @@\n+target\n-old\n"),
        path="src/payments.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


def test_oversized_hunk_number_fails_closed_without_exception():
    huge = "9" * 5000
    assert validate_github_anchor(
        f"@@ -{huge},0 +1,1 @@\n+target\n",
        path="src/payments.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


def test_binary_patch_rejects_declared_size_above_resource_ceiling():
    assert not MODULE._git_binary_patch_complete(
        [
            FULL_BINARY_INDEX,
            "GIT binary patch",
            f"literal {MODULE.MAX_BINARY_BLOCK_BYTES + 1}",
            *git_base85_lines(zlib.compress(b"A")),
            "",
            "literal 0",
            *git_base85_lines(zlib.compress(b"")),
            "",
        ],
        1,
    )


def test_binary_patch_rejects_compressed_bomb_and_trailing_stream_data():
    bomb = zlib.compress(b"A" * (MODULE.MAX_BINARY_BLOCK_BYTES + 1))
    trailing = zlib.compress(b"data") + b"JUNK"
    for payload in (bomb, trailing):
        assert not MODULE._git_binary_patch_complete(
            [
                FULL_BINARY_INDEX,
                "GIT binary patch",
                "literal 4",
                *git_base85_lines(payload),
                "",
                "literal 4",
                *git_base85_lines(zlib.compress(b"data")),
                "",
            ],
            1,
        )


def test_binary_patch_rejects_arbitrary_bytes_labeled_as_delta_programs():
    payload = zlib.compress(b"not a git delta program")
    assert not MODULE._git_binary_patch_complete(
        [
            FULL_BINARY_INDEX,
            "GIT binary patch",
            "delta 123",
            *git_base85_lines(payload),
            "",
            "delta 456",
            *git_base85_lines(payload),
            "",
        ],
        1,
    )


def test_headerless_patch_rejects_unknown_text_before_first_hunk():
    assert validate_github_anchor(
        "garbage\n@@ -0,0 +1,1 @@\n+target\n",
        path="src/payments.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize(
    "patch",
    [
        (
            "diff --git a/src/payments.py b/src/payments.py\ngarbage\n"
            "--- a/src/payments.py\n+++ b/src/payments.py\n"
            "@@ -0,0 +1,1 @@\n+target\n"
        ),
        (
            "--- a/src/payments.py\n+++ b/src/payments.py\ngarbage\n"
            "@@ -0,0 +1,1 @@\n+target\n"
        ),
    ],
    ids=("combined", "sectioned"),
)
def test_text_sections_reject_unknown_records_outside_hunks(patch):
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize(
    "metadata",
    [
        "index 1234567..",
        "index garbage",
        "new file mode nope",
        "deleted file mode ",
        "new file mode 100644\nindex garbage",
    ],
)
def test_text_sections_reject_partial_pre_marker_metadata(metadata):
    patch = (
        "diff --git a/src/payments.py b/src/payments.py\n"
        f"{metadata}\n--- a/src/payments.py\n+++ b/src/payments.py\n"
        "@@ -0,0 +1,1 @@\n+target\n"
    )
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


def test_invalid_first_prefix_in_unrelated_file_invalidates_prior_anchor():
    patch = (
        "diff --git a/src/payments.py b/src/payments.py\n"
        "--- a/src/payments.py\n+++ b/src/payments.py\n"
        "@@ -0,0 +1,1 @@\n+target\n"
        "diff --git a/other b/other\n--- a/other\n+++ b/other\n"
        "@@ -1,0 +100,1 @@\n+other\n"
    )
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize("mode", ["combined", "headerless", "concatenated"])
@pytest.mark.parametrize(
    "hunks,target_line",
    [
        ("@@ -4,0 +5,1 @@\n+earlier\n@@ -9,0 +11,1 @@\n+target\n", 11),
        ("@@ -5,1 +4,0 @@\n-removed\n@@ -10,1 +8,2 @@\n context\n+target\n", 9),
    ],
    ids=("insertions", "deletion-then-addition"),
)
def test_non_overlapping_equal_gap_hunks_remain_anchorable(mode, hunks, target_line):
    patch = _strict_grammar_patch(mode, hunks)
    assert validate_github_anchor(
        patch,
        path="src/payments.py",
        line=target_line,
        source_kind="added",
        head_sha="abc",
    ) == {
        "commit_id": "abc",
        "path": "src/payments.py",
        "line": target_line,
        "side": "RIGHT",
    }


@pytest.mark.parametrize(
    "patch,path,line",
    [
        (
            "diff --git a/old name.txt b/new name.txt\n"
            "similarity index 65%\n"
            "rename from old name.txt\n"
            "rename to new name.txt\n"
            "index 85c3040..7048118 100644\n"
            "--- a/old name.txt\t\n"
            "+++ b/new name.txt\t\n"
            "@@ -1,3 +1,4 @@\n alpha\n beta\n+inserted\n gamma\n",
            "new name.txt",
            3,
        ),
        (
            "diff --git a/mode.txt b/mode.txt\n"
            "old mode 100644\n"
            "new mode 100755\n"
            "index 814f4a4..6d92e6a\n"
            "--- a/mode.txt\n"
            "+++ b/mode.txt\n"
            "@@ -1,2 +1,3 @@\n one\n+inserted\n two\n",
            "mode.txt",
            2,
        ),
    ],
    ids=("git-rename-and-content", "git-mode-and-content"),
)
def test_git_generated_extended_headers_with_content_are_anchorable(patch, path, line):
    assert validate_github_anchor(
        patch,
        path=path,
        line=line,
        source_kind="added",
        head_sha="abc",
    ) == {"commit_id": "abc", "path": path, "line": line, "side": "RIGHT"}


@pytest.mark.parametrize(
    "metadata,old_marker,new_marker,hunk",
    [
        (
            "new file mode 100644\nindex 1234567..89abcde 100644\n",
            "--- a/file.txt",
            "+++ b/file.txt",
            "@@ -1,1 +1,2 @@\n context\n+target\n",
        ),
        (
            "deleted file mode 100644\nindex 1234567..89abcde 100644\n",
            "--- a/file.txt",
            "+++ b/file.txt",
            "@@ -1,1 +1,2 @@\n context\n+target\n",
        ),
        (
            "new file mode 100644\nindex 0000000..89abcde\n",
            "--- /dev/null",
            "+++ b/file.txt",
            "@@ -1,1 +1,2 @@\n context\n+target\n",
        ),
        (
            "deleted file mode 100644\nindex 1234567..0000000\n",
            "--- a/file.txt",
            "+++ /dev/null",
            "@@ -0,0 +1,1 @@\n+target\n",
        ),
        (
            "old mode 10064x\nnew mode 100755\nindex 1234567..89abcde\n",
            "--- a/file.txt",
            "+++ b/file.txt",
            "@@ -1,1 +1,2 @@\n context\n+target\n",
        ),
    ],
    ids=(
        "new-mode-with-non-null-old",
        "deleted-mode-with-non-null-new",
        "new-file-hunk-has-old-lines",
        "deleted-file-has-added-lines",
        "invalid-old-mode",
    ),
)
def test_extended_headers_bind_modes_hashes_markers_and_hunk_kinds(
    metadata,
    old_marker,
    new_marker,
    hunk,
):
    patch = (
        "diff --git a/file.txt b/file.txt\n"
        f"{metadata}{old_marker}\n{new_marker}\n{hunk}"
    )
    assert validate_github_anchor(
        patch,
        path="file.txt",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


def test_git_c_quoted_octal_utf8_and_tab_path_is_decoded_for_headers_and_markers():
    patch = (
        'diff --git "a/caf\\303\\251\\tfile.txt" "b/caf\\303\\251\\tfile.txt"\n'
        "index e584f07..562bd90 100644\n"
        '--- "a/caf\\303\\251\\tfile.txt"\n'
        '+++ "b/caf\\303\\251\\tfile.txt"\n'
        "@@ -1,2 +1,3 @@\n alpha\n+inserted\n omega\n"
    )
    path = "café\tfile.txt"
    assert validate_github_anchor(
        patch,
        path=path,
        line=2,
        source_kind="added",
        head_sha="abc",
    ) == {"commit_id": "abc", "path": path, "line": 2, "side": "RIGHT"}


def test_git_header_decodes_independently_quoted_rename_paths():
    patch = (
        'diff --git a/plain.txt "b/caf\\303\\251\\tfile.txt"\n'
        "similarity index 50%\n"
        "rename from plain.txt\n"
        'rename to "caf\\303\\251\\tfile.txt"\n'
        "index e584f07..562bd90 100644\n"
        "--- a/plain.txt\n"
        '+++ "b/caf\\303\\251\\tfile.txt"\n'
        "@@ -1,2 +1,3 @@\n alpha\n+inserted\n omega\n"
    )
    path = "café\tfile.txt"
    assert validate_github_anchor(
        patch,
        path=path,
        line=2,
        source_kind="added",
        head_sha="abc",
    ) == {"commit_id": "abc", "path": path, "line": 2, "side": "RIGHT"}


def test_git_generated_unquoted_paths_containing_b_prefix_are_bound_to_markers():
    patch = (
        "diff --git a/dir b/file.txt b/dir b/file.txt\n"
        "index 814f4a4..6d92e6a 100644\n"
        "--- a/dir b/file.txt\n"
        "+++ b/dir b/file.txt\n"
        "@@ -1,2 +1,3 @@\n one\n+inserted\n two\n"
    )
    path = "dir b/file.txt"
    assert validate_github_anchor(
        patch,
        path=path,
        line=2,
        source_kind="added",
        head_sha="abc",
    ) == {"commit_id": "abc", "path": path, "line": 2, "side": "RIGHT"}


def test_git_generated_rename_mode_and_content_headers_are_anchorable():
    patch = (
        "diff --git a/old.sh b/new.sh\n"
        "old mode 100644\n"
        "new mode 100755\n"
        "similarity index 66%\n"
        "rename from old.sh\n"
        "rename to new.sh\n"
        "index 814f4a4..6d92e6a\n"
        "--- a/old.sh\n"
        "+++ b/new.sh\n"
        "@@ -1,2 +1,3 @@\n one\n+inserted\n two\n"
    )
    assert validate_github_anchor(
        patch,
        path="new.sh",
        line=2,
        source_kind="added",
        head_sha="abc",
    ) == {"commit_id": "abc", "path": "new.sh", "line": 2, "side": "RIGHT"}


def test_git_generated_c_quoted_metadata_only_rename_keeps_prior_anchor_valid():
    rename = (
        'diff --git "a/caf\\303\\251.txt" "b/r\\303\\251sum\\303\\251.txt"\n'
        "similarity index 100%\n"
        'rename from "caf\\303\\251.txt"\n'
        'rename to "r\\303\\251sum\\303\\251.txt"\n'
    )
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + rename,
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


def test_git_generated_c_quoted_binary_summary_keeps_prior_anchor_valid():
    binary = (
        'diff --git "a/caf\\303\\251.bin" "b/caf\\303\\251.bin"\n'
        "index 1234567..89abcde 100644\n"
        'Binary files "a/caf\\303\\251.bin" and "b/caf\\303\\251.bin" differ\n'
    )
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + binary,
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


@pytest.mark.parametrize(
    "old_marker,new_marker,hunk",
    [
        ("--- /dev/null", "+++ b/other.py", "@@ -1,1 +1,1 @@\n-old\n+new\n"),
        ("--- a/other.py", "+++ /dev/null", "@@ -1,1 +1,1 @@\n-old\n+new\n"),
    ],
    ids=("old-dev-null-has-lines", "new-dev-null-has-lines"),
)
def test_sectioned_dev_null_markers_are_bound_to_empty_hunk_sides(
    old_marker,
    new_marker,
    hunk,
):
    patch = (
        "--- /dev/null\n"
        "+++ b/target.py\n"
        "@@ -0,0 +1,1 @@\n+target\n"
        f"{old_marker}\n{new_marker}\n{hunk}"
    )
    assert validate_github_anchor(
        patch,
        path="target.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


def test_direct_sectioned_dev_null_marker_is_bound_to_empty_old_hunk_side():
    patch = (
        "--- /dev/null\n"
        "+++ b/other.py\n"
        "@@ -1,1 +1,1 @@\n-old\n+new\n"
    )
    assert validate_github_anchor(
        patch,
        path="other.py",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


def test_sectioned_marker_side_prefixes_cannot_be_swapped():
    patch = (
        "--- b/old.py\n"
        "+++ a/new.py\n"
        "@@ -1,1 +1,2 @@\n old\n+new\n"
    )
    assert validate_github_anchor(
        patch,
        path="new.py",
        line=2,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


def test_combined_marker_side_prefixes_cannot_be_swapped():
    patch = (
        "diff --git a/old.py b/new.py\n"
        "index 1234567..89abcde 100644\n"
        "--- b/old.py\n"
        "+++ a/new.py\n"
        "@@ -1,1 +1,2 @@\n old\n+new\n"
    )
    assert validate_github_anchor(
        patch,
        path="new.py",
        line=2,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize(
    "invalid_section",
    [
        (
            "diff --git a/script.sh b/script.sh\n"
            "old mode 777777\n"
            "new mode 777776\n"
        ),
        (
            "diff --git a/empty b/empty\n"
            "new file mode 777777\n"
            "index 0000000..e69de29\n"
        ),
    ],
    ids=("mode-only", "new-empty-file"),
)
def test_non_hunk_sections_reject_unsupported_git_file_modes(invalid_section):
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + invalid_section,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


def test_binary_prefix_rejects_unsupported_git_file_mode():
    body = [
        "new file mode 777777",
        "index 0000000..89abcde",
        "GIT binary patch",
        "literal 4",
        *git_base85_lines(zlib.compress(b"data")),
        "",
        "literal 0",
        *git_base85_lines(zlib.compress(b"")),
        "",
    ]
    assert not MODULE._git_binary_patch_complete(body, 2)


def test_ambiguous_unquoted_diff_header_without_matching_markers_fails_closed():
    patch = (
        "diff --git a/dir b/file.txt b/dir b/file.txt\n"
        "--- a/unrelated.txt\n"
        "+++ b/unrelated.txt\n"
        "@@ -1,1 +1,2 @@\n one\n+inserted\n"
    )
    assert validate_github_anchor(
        patch,
        path="unrelated.txt",
        line=2,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize(
    "section",
    [
        (
            "diff --git a/dir b/file.bin b/dir b/file.bin\n"
            "index 1234567..89abcde 100644\n"
            "Binary files a/dir b/file.bin and b/dir b/file.bin differ\n"
        ),
        (
            "diff --git a/dir b/file.bin b/dir b/file.bin\n"
            "index c5ebe4a6bed51d0508de6a090d5cdba194db16de.."
            "4d42bb23d89d7b39e906c9da5fad38ef60888ce5 100755\n"
            "GIT binary patch\n"
            "delta 26\n"
            "icmaEHo#VxIjtz_glXo)lHwy@~3kWc77Z6~&Aq@bJxCq1m\n\n"
            "delta 38\n"
            "ucmaEHo#VxIjtz_g{PFQQnMuj<#U+VFCGok5%>n}L0s@TN1q7IGNCN;Z;|+)a\n"
        ),
        (
            "diff --git a/dir b/file.bin b/dir b/file.bin\n"
            "old mode 100644\nnew mode 100755\n"
        ),
        (
            "diff --git a/dir b/file.bin b/dir b/file.bin\n"
            "new file mode 100644\nindex 0000000..e69de29\n"
        ),
    ],
    ids=("binary-summary", "binary-delta", "mode-only", "empty-file"),
)
def test_git_no_marker_sections_bind_unquoted_internal_b_prefix_paths(section):
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + section,
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


def test_git_generated_pure_rename_with_mode_change_keeps_prior_anchor_valid():
    section = (
        "diff --git a/old.sh b/new.sh\n"
        "old mode 100644\n"
        "new mode 100755\n"
        "similarity index 100%\n"
        "rename from old.sh\n"
        "rename to new.sh\n"
    )
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + section,
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


def test_git_generated_binary_content_and_mode_change_keeps_prior_anchor_valid():
    section = (
        "diff --git a/payload.bin b/payload.bin\n"
        "old mode 100644\n"
        "new mode 100755\n"
        "index 1234567..89abcde\n"
        "Binary files a/payload.bin and b/payload.bin differ\n"
    )
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + section,
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


def test_separator_heavy_oversized_binary_summary_fails_closed_with_bounded_decode_work(
    monkeypatch,
):
    decode_calls = 0
    original_decode = MODULE._decode_git_path

    def counting_decode(raw):
        nonlocal decode_calls
        decode_calls += 1
        return original_decode(raw)

    monkeypatch.setattr(MODULE, "_decode_git_path", counting_decode)
    summary = "Binary files a/x" + " and a/x" * 20_000 + " differ"
    assert not MODULE._binary_summary_matches(summary, "x", "x")
    assert decode_calls <= 2


def test_separator_heavy_oversized_diff_header_is_rejected_before_candidates_materialize():
    header = "diff --git a/x" + " b/x" * 20_000
    assert len(header) > MODULE.MAX_DIFF_RECORD_CHARS
    assert MODULE._diff_paths(header) is None


def test_under_limit_path_records_remain_accepted():
    path = "segment/" + "x" * 4_096
    header = f"diff --git a/{path} b/{path}"
    summary = f"Binary files a/{path} and b/{path} differ"
    assert len(header) < MODULE.MAX_DIFF_RECORD_CHARS
    assert MODULE._diff_paths(header) == (path, path)
    assert MODULE._binary_summary_matches(summary, path, path)


def test_under_limit_separator_heavy_records_reject_before_path_decoding(monkeypatch):
    decode_calls = 0
    original_decode = MODULE._decode_git_path

    def counting_decode(raw):
        nonlocal decode_calls
        decode_calls += 1
        return original_decode(raw)

    monkeypatch.setattr(MODULE, "_decode_git_path", counting_decode)
    header = "diff --git a/x" + " b/" * 15_000
    summary = "Binary files a/x" + " and " * 12_000 + " differ"
    assert len(header) < MODULE.MAX_DIFF_RECORD_CHARS
    assert len(summary) < MODULE.MAX_DIFF_RECORD_CHARS
    assert MODULE._diff_paths(header) is None
    assert not MODULE._binary_summary_matches(summary, "x", "x")
    assert decode_calls == 0


def test_diff_header_rejects_sixty_five_structural_path_separators():
    header = "diff --git a/x" + " b/x" * (MODULE.MAX_PATH_SEPARATORS + 1)
    assert len(header) < MODULE.MAX_DIFF_RECORD_CHARS
    assert MODULE._diff_paths(header) is None


@pytest.mark.parametrize("oid_length", [40, 64], ids=("sha1", "sha256"))
def test_git_binary_patch_requires_full_equal_length_object_ids(oid_length):
    old_oid = "1" * oid_length
    new_oid = "2" * oid_length
    body = [
        f"index {old_oid}..{new_oid} 100644",
        "GIT binary patch",
        "literal 4",
        *git_base85_lines(zlib.compress(b"data")),
        "",
        "literal 0",
        *git_base85_lines(zlib.compress(b"")),
        "",
    ]
    assert MODULE._git_binary_patch_complete(body, 1)


def test_git_binary_patch_rejects_abbreviated_object_ids():
    body = [
        "index 1234567..89abcde 100644",
        "GIT binary patch",
        "literal 4",
        *git_base85_lines(zlib.compress(b"data")),
        "",
        "literal 0",
        *git_base85_lines(zlib.compress(b"")),
        "",
    ]
    assert not MODULE._git_binary_patch_complete(body, 1)


@pytest.mark.parametrize(
    "old_mode,new_mode",
    [("120000", "160000"), ("120000", "100644")],
    ids=("symlink-to-gitlink", "symlink-to-regular"),
)
@pytest.mark.parametrize("form", ["content", "metadata-only", "binary"])
def test_git_mode_pairs_reject_file_type_transitions(old_mode, new_mode, form):
    prefix = (
        "diff --git a/file b/file\n"
        f"old mode {old_mode}\nnew mode {new_mode}\n"
    )
    if form == "content":
        section = (
            prefix
            + "index 1234567..89abcde\n"
            "--- a/file\n+++ b/file\n"
            "@@ -1,1 +1,2 @@\n old\n+new\n"
        )
    elif form == "metadata-only":
        section = prefix
    else:
        section = (
            prefix
            + "index 1234567..89abcde\n"
            "Binary files a/file and b/file differ\n"
        )
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + section,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize(
    "metadata",
    [
        "dissimilarity index 100%\nindex 1234567..89abcde 100644\n",
        "dissimilarity index 0%\nindex 1234567..89abcde 100644\n",
        "index 1234567..89abcde 100644\ndissimilarity index 100%\n",
    ],
    ids=("canonical", "invalid-percentage", "invalid-order"),
)
def test_git_dissimilarity_content_metadata_is_strict(metadata):
    patch = (
        "diff --git a/rewrite.txt b/rewrite.txt\n"
        f"{metadata}"
        "--- a/rewrite.txt\n"
        "+++ b/rewrite.txt\n"
        "@@ -1,1 +1,1 @@\n-old\n+new\n"
    )
    expected = (
        {"commit_id": "abc", "path": "rewrite.txt", "line": 1, "side": "RIGHT"}
        if metadata.startswith((
            "dissimilarity index 100%\nindex ",
            "dissimilarity index 0%\nindex ",
        ))
        else {"unanchorable": True, "reason": "added_line_not_in_current_diff"}
    )
    assert validate_github_anchor(
        patch,
        path="rewrite.txt",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == expected


@pytest.mark.parametrize("with_mode", [False, True], ids=("same-mode", "mode-change"))
@pytest.mark.parametrize("binary_kind", ["summary", "git-binary"])
def test_git_generated_binary_rename_with_content_keeps_prior_anchor_valid(
    binary_kind,
    with_mode,
):
    prefix = (
        "diff --git a/old.bin b/new.bin\n"
        + ("old mode 100644\nnew mode 100755\n" if with_mode else "")
        + "similarity index 75%\n"
        "rename from old.bin\n"
        "rename to new.bin\n"
        "index c5ebe4a6bed51d0508de6a090d5cdba194db16de.."
        "4d42bb23d89d7b39e906c9da5fad38ef60888ce5 100644\n"
    )
    if binary_kind == "summary":
        section = prefix + "Binary files a/old.bin and b/new.bin differ\n"
    else:
        section = prefix + GIT_GENERATED_DELTA_PATCH.split("GIT binary patch\n", 1)[1]
        section = prefix + "GIT binary patch\n" + section[len(prefix):]
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + section,
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


def test_git_generated_c_quoted_binary_summary_path_may_contain_and_separator():
    section = (
        'diff --git "a/caf\\303\\251 and x.dat" "b/caf\\303\\251 and x.dat"\n'
        "index 1234567..89abcde 100644\n"
        'Binary files "a/caf\\303\\251 and x.dat" and '
        '"b/caf\\303\\251 and x.dat" differ\n'
    )
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + section,
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


@pytest.mark.parametrize("change_kind", ["new", "deleted"])
def test_git_binary_summary_with_internal_b_prefix_binds_non_null_side(change_kind):
    if change_kind == "new":
        metadata = "new file mode 100644\nindex 0000000..89abcde\n"
        summary = "Binary files /dev/null and b/dir b/file.dat differ\n"
    else:
        metadata = "deleted file mode 100644\nindex 1234567..0000000\n"
        summary = "Binary files a/dir b/file.dat and /dev/null differ\n"
    section = (
        "diff --git a/dir b/file.dat b/dir b/file.dat\n"
        f"{metadata}{summary}"
    )
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + section,
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


@pytest.mark.parametrize(
    "metadata,summary",
    [
        (
            "new file mode 100644\nindex 0000000..89abcde\n",
            "Binary files /dev/null and b/unrelated.dat differ\n",
        ),
        (
            "deleted file mode 100644\nindex 1234567..0000000\n",
            "Binary files a/unrelated.dat and /dev/null differ\n",
        ),
    ],
)
def test_binary_summary_null_side_path_hint_mismatch_fails_closed(metadata, summary):
    section = (
        "diff --git a/dir b/file.dat b/dir b/file.dat\n"
        f"{metadata}{summary}"
    )
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + section,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize(
    "summary",
    [
        'Binary files "a/caf\\303\\251 and x.dat and "b/x.dat" differ',
        'Binary files "a/x.dat" and garbage and "b/x.dat" differ',
    ],
    ids=("unterminated-quote", "extra-outside-separator"),
)
def test_c_quoted_binary_summary_separator_grammar_fails_closed(summary):
    section = (
        'diff --git "a/caf\\303\\251 and x.dat" "b/x.dat"\n'
        "index 1234567..89abcde 100644\n"
        f"{summary}\n"
    )
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + section,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize(
    "metadata",
    [
        "rename from old.bin\nrename to new.bin\nsimilarity index 75%\n",
        "similarity index 75%\nrename from unrelated.bin\nrename to new.bin\n",
    ],
    ids=("wrong-order", "wrong-identity"),
)
@pytest.mark.parametrize("binary_kind", ["summary", "git-binary"])
def test_binary_rename_content_metadata_is_strict(metadata, binary_kind):
    prefix = (
        "diff --git a/old.bin b/new.bin\n"
        f"{metadata}"
        "index c5ebe4a6bed51d0508de6a090d5cdba194db16de.."
        "4d42bb23d89d7b39e906c9da5fad38ef60888ce5 100644\n"
    )
    tail = (
        "Binary files a/old.bin and b/new.bin differ\n"
        if binary_kind == "summary"
        else "GIT binary patch\n"
        + GIT_GENERATED_DELTA_PATCH.split("GIT binary patch\n", 1)[1]
    )
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + prefix + tail,
        path="src/payments.py",
        line=11,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


@pytest.mark.parametrize(
    "percentage,anchor_expected",
    [("87", True), ("0", True), ("100", True), ("101", False), ("x", False)],
)
def test_git_dissimilarity_accepts_only_canonical_percentages(percentage, anchor_expected):
    patch = (
        "diff --git a/rewrite.txt b/rewrite.txt\n"
        f"dissimilarity index {percentage}%\n"
        "index 1234567..89abcde 100644\n"
        "--- a/rewrite.txt\n+++ b/rewrite.txt\n"
        "@@ -1,1 +1,1 @@\n-old\n+new\n"
    )
    result = validate_github_anchor(
        patch,
        path="rewrite.txt",
        line=1,
        source_kind="added",
        head_sha="abc",
    )
    assert ("commit_id" in result) is anchor_expected


def test_invalid_git_c_quoted_filename_escape_fails_closed():
    patch = (
        'diff --git "a/bad\\q.txt" "b/bad\\q.txt"\n'
        '--- "a/bad\\q.txt"\n+++ "b/bad\\q.txt"\n'
        "@@ -0,0 +1,1 @@\n+target\n"
    )
    assert validate_github_anchor(
        patch,
        path="badq.txt",
        line=1,
        source_kind="added",
        head_sha="abc",
    ) == {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


GIT_GENERATED_DELTA_PATCH = """diff --git a/payload.bin b/payload.bin
index c5ebe4a6bed51d0508de6a090d5cdba194db16de..4d42bb23d89d7b39e906c9da5fad38ef60888ce5 100755
GIT binary patch
delta 26
icmaEHo#VxIjtz_glXo)lHwy@~3kWc77Z6~&Aq@bJxCq1m

delta 38
ucmaEHo#VxIjtz_g{PFQQnMuj<#U+VFCGok5%>n}L0s@TN1q7IGNCN;Z;|+)a
"""


def test_real_git_generated_delta_section_does_not_invalidate_other_file_anchor():
    patch = DIFF_WITH_ADDITION + GIT_GENERATED_DELTA_PATCH
    assert validate_github_anchor(
        patch,
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


def test_git_generated_mode_change_with_binary_delta_keeps_prior_anchor_valid():
    binary = GIT_GENERATED_DELTA_PATCH.replace(
        "index c5ebe4a6bed51d0508de6a090d5cdba194db16de",
        "old mode 100644\nnew mode 100755\n"
        "index c5ebe4a6bed51d0508de6a090d5cdba194db16de",
        1,
    )
    assert validate_github_anchor(
        DIFF_WITH_ADDITION + binary,
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


def encode_delta_block(delta_program: bytes) -> list[str]:
    return git_base85_lines(zlib.compress(delta_program))


@pytest.mark.parametrize(
    "delta_program,declared_size",
    [
        (b"\x80", 1),
        (b"\x01\x80", 2),
        (b"\x01\x01\x00", 3),
        (b"\x01\x01\x91\x02\x01", 5),
        (b"\x01\x02\x01A", 4),
        (b"\x01\x01\x02A", 4),
        (b"\x01\x02\x01A", 3),
    ],
    ids=(
        "truncated-source-varint",
        "truncated-result-varint",
        "opcode-zero",
        "copy-out-of-bounds",
        "accumulated-output-mismatch",
        "truncated-insert",
        "declaration-program-size-mismatch",
    ),
)
def test_binary_delta_structure_rejects_malformed_programs(delta_program, declared_size):
    body = [
        FULL_BINARY_INDEX,
        "GIT binary patch",
        f"delta {declared_size}",
        *encode_delta_block(delta_program),
        "",
        "literal 0",
        *git_base85_lines(zlib.compress(b"")),
        "",
    ]
    assert not MODULE._git_binary_patch_complete(body, 1)
