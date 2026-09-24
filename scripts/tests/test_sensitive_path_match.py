"""Tests for the shared sensitive-path matcher (scripts/sensitive_path_match.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from sensitive_path_match import (  # noqa: E402
    SensitivePathList,
    SensitivePathListError,
    classify,
    extract_changed_paths,
    load_sensitive_path_list,
    matched_content_patterns,
    matched_globs,
)


def make_spec(globs: list[str], content_patterns: list[str]) -> SensitivePathList:
    import re

    return SensitivePathList(
        globs=tuple(globs),
        content_patterns=tuple(re.compile(p) for p in content_patterns),
        content_pattern_sources=tuple(content_patterns),
    )


# --- The real seed list loads and is internally sane -----------------------------------------


def test_real_sensitive_path_list_loads_cleanly() -> None:
    spec = load_sensitive_path_list()
    assert "scripts/install_engine.py" in spec.globs
    assert "skills/loop-task-implementer/scripts/run_log.py" in spec.globs
    assert spec.content_patterns  # at least one content pattern


def test_real_sensitive_path_list_self_protects_its_own_enforcement_files() -> None:
    """The design's self-protection rule: the list's own file, and the enforcement mechanism's
    own files, must all be permanent members of `globs`."""
    spec = load_sensitive_path_list()
    for expected in (
        "docs/sensitive-paths.yaml",
        "scripts/sensitive_path_match.py",
        "scripts/check_review_evidence.py",
        ".github/workflows/review-evidence.yml",
    ):
        assert expected in spec.globs, f"{expected} must self-protect via globs"


# --- load_sensitive_path_list: fail-closed on malformed/empty input ----------------------------


def test_load_missing_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(SensitivePathListError):
        load_sensitive_path_list(tmp_path / "does-not-exist.yaml")


def test_load_invalid_yaml_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "sensitive-paths.yaml"
    path.write_text("globs: [\n", encoding="utf-8")
    with pytest.raises(SensitivePathListError):
        load_sensitive_path_list(path)


def test_load_non_mapping_top_level_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "sensitive-paths.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(SensitivePathListError):
        load_sensitive_path_list(path)


def test_load_missing_required_key_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "sensitive-paths.yaml"
    path.write_text("globs:\n  - foo.py\n", encoding="utf-8")
    with pytest.raises(SensitivePathListError):
        load_sensitive_path_list(path)


def test_load_unexpected_top_level_key_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "sensitive-paths.yaml"
    path.write_text("globs: [foo.py]\ncontent_patterns: [bar]\nextra: true\n", encoding="utf-8")
    with pytest.raises(SensitivePathListError):
        load_sensitive_path_list(path)


def test_load_both_lists_empty_fails_closed(tmp_path: Path) -> None:
    """Empty is malformed, never 'nothing is sensitive' (design doc, Failure strategy)."""
    path = tmp_path / "sensitive-paths.yaml"
    path.write_text("globs: []\ncontent_patterns: []\n", encoding="utf-8")
    with pytest.raises(SensitivePathListError):
        load_sensitive_path_list(path)


def test_load_non_string_list_item_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "sensitive-paths.yaml"
    path.write_text("globs: [foo.py, 5]\ncontent_patterns: [bar]\n", encoding="utf-8")
    with pytest.raises(SensitivePathListError):
        load_sensitive_path_list(path)


def test_load_invalid_regex_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "sensitive-paths.yaml"
    path.write_text("globs: [foo.py]\ncontent_patterns: ['(unterminated']\n", encoding="utf-8")
    with pytest.raises(SensitivePathListError):
        load_sensitive_path_list(path)


def test_load_one_list_empty_is_fine(tmp_path: Path) -> None:
    """Only *both* empty is malformed -- one empty list with the other populated is valid."""
    path = tmp_path / "sensitive-paths.yaml"
    path.write_text("globs: []\ncontent_patterns: ['\\\\bflock\\\\b']\n", encoding="utf-8")
    spec = load_sensitive_path_list(path)
    assert spec.globs == ()
    assert len(spec.content_patterns) == 1


# --- extract_changed_paths ----------------------------------------------------------------------


def test_extract_changed_paths_simple_edit() -> None:
    diff = "diff --git a/scripts/install_engine.py b/scripts/install_engine.py\n@@ -1,2 +1,2 @@\n"
    assert extract_changed_paths(diff) == {"scripts/install_engine.py"}


def test_extract_changed_paths_rename() -> None:
    diff = "diff --git a/scripts/old_name.py b/scripts/new_name.py\nsimilarity index 100%\n"
    assert extract_changed_paths(diff) == {"scripts/old_name.py", "scripts/new_name.py"}


def test_extract_changed_paths_multiple_files() -> None:
    diff = (
        "diff --git a/foo.py b/foo.py\n@@ -1 +1 @@\n"
        "diff --git a/bar.py b/bar.py\n@@ -1 +1 @@\n"
    )
    assert extract_changed_paths(diff) == {"foo.py", "bar.py"}


# --- matched_globs ---------------------------------------------------------------------------


def test_matched_globs_literal_path() -> None:
    hits = matched_globs(["scripts/install_engine.py"], ["scripts/install_engine.py", "docs/foo.md"])
    assert hits == ["scripts/install_engine.py"]


def test_matched_globs_wildcard_pattern() -> None:
    hits = matched_globs(
        ["skills/pr-gatekeeper/scripts/idempotency_store.py"],
        ["skills/*/scripts/*idempotency*"],
    )
    assert hits == ["skills/*/scripts/*idempotency*"]


def test_matched_globs_no_match() -> None:
    assert matched_globs(["docs/README.md"], ["scripts/install_engine.py"]) == []


def test_matched_globs_is_case_sensitive() -> None:
    assert matched_globs(["Scripts/Install_Engine.py"], ["scripts/install_engine.py"]) == []


# --- matched_content_patterns -----------------------------------------------------------------


def test_matched_content_patterns_hits_on_keyword_in_diff() -> None:
    spec = make_spec(globs=[], content_patterns=[r"\bflock\("])
    diff = "diff --git a/some/unrelated_file.py b/some/unrelated_file.py\n+    fcntl.flock(fd, LOCK_EX)\n"
    assert matched_content_patterns(diff, spec) == [r"\bflock\("]


def test_matched_content_patterns_no_hit() -> None:
    spec = make_spec(globs=[], content_patterns=[r"\bflock\("])
    diff = "diff --git a/docs/readme.md b/docs/readme.md\n+hello world\n"
    assert matched_content_patterns(diff, spec) == []


# --- classify: the rename/split-evasion case this mechanism exists to close --------------------


def test_classify_rename_out_of_glob_still_caught_by_content_pattern() -> None:
    """The evasion case the design's content-pattern supplement exists to close: renaming a
    lock-handling file out of every listed glob must still be caught, via the keyword grep over
    the full diff text -- independent of which file the matching text lands in."""
    spec = make_spec(globs=["scripts/install_engine.py"], content_patterns=[r"\bflock\("])
    diff = (
        "diff --git a/scripts/install_engine.py b/scripts/totally_renamed_innocuous.py\n"
        "similarity index 90%\n"
        "+    fcntl.flock(fd, fcntl.LOCK_EX)\n"
    )
    result = classify(diff, spec)
    assert result.sensitive
    # Renaming *out of* the glob still leaves the old path glob-matched too (both diff sides are
    # extracted), so both signals can fire together here -- the key assertion is the content
    # pattern alone is sufficient.
    assert result.matched_content_patterns == (r"\bflock\(",)


def test_classify_glob_match_alone_is_sensitive() -> None:
    spec = make_spec(globs=["scripts/install_engine.py"], content_patterns=[r"\bflock\("])
    diff = "diff --git a/scripts/install_engine.py b/scripts/install_engine.py\n+print('hello')\n"
    result = classify(diff, spec)
    assert result.sensitive
    assert result.matched_globs == ("scripts/install_engine.py",)
    assert result.matched_content_patterns == ()


def test_classify_not_sensitive() -> None:
    spec = make_spec(globs=["scripts/install_engine.py"], content_patterns=[r"\bflock\("])
    diff = "diff --git a/docs/readme.md b/docs/readme.md\n+hello\n"
    result = classify(diff, spec)
    assert not result.sensitive
    assert result.matched_globs == ()
    assert result.matched_content_patterns == ()


def test_classify_self_protecting_entries_match() -> None:
    """A PR editing the enforcement mechanism's own files must classify as sensitive."""
    spec = load_sensitive_path_list()
    diff = "diff --git a/scripts/check_review_evidence.py b/scripts/check_review_evidence.py\n+pass\n"
    result = classify(diff, spec)
    assert result.sensitive
    assert "scripts/check_review_evidence.py" in result.matched_globs


def test_classify_explicit_changed_paths_overrides_diff_parsing() -> None:
    spec = make_spec(globs=["scripts/install_engine.py"], content_patterns=[r"\bflock\("])
    # diff_text has no `diff --git` headers at all -- classify must still work off the explicit
    # changed_paths list rather than silently finding nothing.
    result = classify("no headers here", spec, changed_paths=["scripts/install_engine.py"])
    assert result.sensitive
    assert result.matched_globs == ("scripts/install_engine.py",)
