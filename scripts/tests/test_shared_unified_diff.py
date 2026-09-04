"""The one unified-diff grammar three consumers used to re-derive.

`scripts/change_impact.py`, `pr-review/scripts/github-comment-positions.py` and
`pr-review/scripts/diff-to-positions.py` each had their own path decoder and hunk-header regex.
These tests pin the grammar itself -- quoted paths, `/dev/null` sides, rename metadata, mode-only
records, `\\ No newline at end of file` -- and the one place the two callers legitimately differ:
how an unbound, ambiguous header is read.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def grammar():
    return _load(ROOT / "docs/skill-framework/shared/unified_diff.py", "shared_unified_diff_test")


@pytest.fixture(scope="module")
def positions():
    return _load(
        ROOT / "pr-review/scripts/github-comment-positions.py",
        "github_comment_positions_under_test",
    )


@pytest.fixture(scope="module")
def to_positions():
    return _load(
        ROOT / "pr-review/scripts/diff-to-positions.py", "diff_to_positions_under_test"
    )


def test_every_consumer_reads_the_same_hunk_header(grammar, positions, to_positions) -> None:
    assert positions.HUNK_HEADER is grammar.HUNK_HEADER or (
        positions.HUNK_HEADER.pattern == grammar.HUNK_HEADER.pattern
    )
    assert to_positions.HUNK_RE.pattern == grammar.HUNK_HEADER.pattern


def test_decodes_a_c_quoted_path_with_octal_and_escape_sequences(grammar) -> None:
    assert grammar.decode_git_path(r'"src/caf\303\251.py"') == "src/café.py"
    assert grammar.decode_git_path(r'"src/a\tb.py"') == "src/a\tb.py"
    assert grammar.decode_git_path(r'"src/say \"hi\".py"') == 'src/say "hi".py'


@pytest.mark.parametrize(
    "field",
    ['"unterminated', r'"bad\9escape"', r'"\400"', '"' + "\\" + '"'],
)
def test_rejects_a_malformed_quoted_path(grammar, field) -> None:
    assert grammar.decode_git_path(field) is grammar.INVALID_PATH


def test_resolves_a_header_whose_paths_contain_spaces_using_rename_metadata(grammar) -> None:
    diff = (
        "diff --git a/docs/old name.md b/docs/new name.md\n"
        "similarity index 95%\n"
        "rename from docs/old name.md\n"
        "rename to docs/new name.md\n"
    )
    assert list(grammar.iter_file_headers(diff, require_identical_when_unbound=False)) == [
        grammar.DiffFileHeader("docs/old name.md", "docs/new name.md", True)
    ]


def test_a_mode_only_record_still_names_its_file(grammar) -> None:
    diff = "diff --git a/run.sh b/run.sh\nold mode 100644\nnew mode 100755\n"
    assert [header.new_path for header in grammar.iter_file_headers(diff)] == ["run.sh"]


def test_a_dev_null_side_binds_the_surviving_path(grammar) -> None:
    diff = (
        "diff --git a/src/gone.py b/src/gone.py\n"
        "deleted file mode 100644\n"
        "--- a/src/gone.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-one\n"
        "-two\n"
        "\\ No newline at end of file\n"
    )
    assert [header.new_path for header in grammar.iter_file_headers(diff)] == ["src/gone.py"]


def test_no_newline_marker_is_never_read_as_a_file_header(grammar) -> None:
    assert not grammar.FILE_MARKER_OLD.match("\\ No newline at end of file")
    assert not grammar.FILE_MARKER_NEW.match("\\ No newline at end of file")
    # An added line whose own text begins with "++ b/x" renders as "+++ b/x" and is content.
    assert grammar.FILE_MARKER_NEW.match("+++ b/src/x.py")
    assert grammar.FILE_MARKER_OLD.match("--- a/src/x.py")


def test_the_two_unbound_readings_are_the_documented_difference(grammar) -> None:
    """`diff --git a/x b/y` with no metadata: fail closed, or take the single candidate."""
    header = "diff --git a/x b/y"
    assert grammar.parse_diff_git_header(header, require_identical_when_unbound=True) is None
    assert grammar.parse_diff_git_header(header, require_identical_when_unbound=False) == ("x", "y")


def test_an_ambiguous_unbound_header_is_still_refused_by_both_readings(grammar) -> None:
    header = "diff --git a/one b/two b/three"
    assert grammar.parse_diff_git_header(header, require_identical_when_unbound=True) is None
    assert grammar.parse_diff_git_header(header, require_identical_when_unbound=False) is None


def test_separator_and_record_caps_reject_before_any_path_is_decoded(grammar, monkeypatch) -> None:
    decode_calls = 0
    original = grammar.decode_git_path

    def counting(raw):
        nonlocal decode_calls
        decode_calls += 1
        return original(raw)

    monkeypatch.setattr(grammar, "decode_git_path", counting)
    assert grammar.parse_diff_git_header("diff --git a/x" + " b/x" * 200, max_separators=32) is None
    assert grammar.parse_diff_git_header("diff --git a/x b/x", max_record_chars=4) is None
    assert decode_calls == 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("@@ -10,2 +10,3 @@", (10, 2, 10, 3)),
        ("@@ -1 +1 @@ def f():", (1, 1, 1, 1)),
        ("@@ -0,0 +1,4 @@", (0, 0, 1, 4)),
        ("@@ -1,0 +1,0 @@", None),
        ("@@ -0,1 +1,1 @@", None),
        ("@@ nonsense @@", None),
    ],
)
def test_hunk_range_reads_the_one_hunk_grammar(grammar, raw, expected) -> None:
    assert grammar.hunk_range(raw) == expected


def test_consumers_agree_with_the_shared_grammar_on_the_same_header(
    grammar, positions
) -> None:
    header = "diff --git a/src/payments.py b/src/payments.py"
    assert positions._diff_paths(header) == grammar.parse_diff_git_header(header)
