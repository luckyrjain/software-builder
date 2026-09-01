"""Tests for scripts/reference_utils.py: the shared MANIFEST_NAME reader and markdown-link regex."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from scripts.reference_utils import (
    MANIFEST_NAME,
    OWNERSHIP_ABSENT,
    OWNERSHIP_CORRUPT_OWNERSHIP,
    OWNERSHIP_SOFTWARE_BUILDER_OWNED,
    OWNERSHIP_SYMLINK,
    OWNERSHIP_UNOWNED,
    ManifestError,
    classify_install_destination,
    extract_markdown_links,
    read_manifest_file,
    rewrite_framework_links,
)


def test_read_manifest_file_parses_valid_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.write_text('{"skill": "demo", "source_sha": "abc123"}', encoding="utf-8")

    manifest = read_manifest_file(manifest_path)

    assert manifest == {"skill": "demo", "source_sha": "abc123"}


def test_read_manifest_file_missing_raises_with_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / MANIFEST_NAME

    with pytest.raises(ManifestError, match=f"missing manifest: {manifest_path}"):
        read_manifest_file(manifest_path)


def test_read_manifest_file_invalid_json_raises(tmp_path: Path) -> None:
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ManifestError, match="invalid manifest JSON"):
        read_manifest_file(manifest_path)


def test_read_manifest_file_non_object_root_raises(tmp_path: Path) -> None:
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ManifestError, match="manifest is not a JSON object"):
        read_manifest_file(manifest_path)


def test_read_manifest_file_directory_at_path_raises_missing(tmp_path: Path) -> None:
    # Path.is_file() returns False for a directory too, so a directory
    # sitting at the manifest path (e.g. from some other tooling bug) falls
    # into the same "missing manifest" branch as a genuinely absent path --
    # confirm that degrades the same way rather than raising something else.
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.mkdir()

    with pytest.raises(ManifestError, match=f"missing manifest: {manifest_path}"):
        read_manifest_file(manifest_path)


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="chmod 0o000 doesn't block reads for root or on Windows",
)
def test_read_manifest_file_unreadable_raises_manifest_error(tmp_path: Path) -> None:
    # A manifest that exists but can't be read (permissions, a transient FS
    # error) used to escape as a raw OSError/PermissionError -- neither
    # caller catches anything but ManifestError, so doctor.py would crash
    # its whole run instead of degrading that one skill, and install_support
    # verify would crash instead of its clean "error: ..." + exit 1.
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.write_text("{}", encoding="utf-8")
    manifest_path.chmod(0o000)
    try:
        with pytest.raises(ManifestError, match="cannot read manifest"):
            read_manifest_file(manifest_path)
    finally:
        manifest_path.chmod(0o644)


def test_manifest_error_is_a_value_error(tmp_path: Path) -> None:
    # doctor.py's _installed_manifest catches ManifestError specifically and
    # degrades to None; confirm it also satisfies any broader `except
    # ValueError` a caller might use.
    assert issubclass(ManifestError, ValueError)


def test_classify_install_destination_absent_when_path_does_not_exist(tmp_path: Path) -> None:
    dest = tmp_path / "does-not-exist"
    assert classify_install_destination(dest, skill_id="demo") == OWNERSHIP_ABSENT


def test_classify_install_destination_symlink_before_checking_existence(tmp_path: Path) -> None:
    # A broken symlink (target doesn't exist) must still classify as SYMLINK, not ABSENT --
    # Path.exists() follows symlinks and would report False for a broken one.
    dest = tmp_path / "broken-link"
    dest.symlink_to(tmp_path / "nonexistent-target")
    assert classify_install_destination(dest, skill_id="demo") == OWNERSHIP_SYMLINK


def test_classify_install_destination_symlink_to_real_directory(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    dest = tmp_path / "link"
    dest.symlink_to(real_dir)
    assert classify_install_destination(dest, skill_id="demo") == OWNERSHIP_SYMLINK


def test_classify_install_destination_unowned_when_a_plain_file(tmp_path: Path) -> None:
    dest = tmp_path / "not-a-directory"
    dest.write_text("surprise", encoding="utf-8")
    assert classify_install_destination(dest, skill_id="demo") == OWNERSHIP_UNOWNED


def test_classify_install_destination_unowned_when_directory_has_no_manifest(tmp_path: Path) -> None:
    dest = tmp_path / "third-party"
    dest.mkdir()
    (dest / "README.md").write_text("not ours", encoding="utf-8")
    assert classify_install_destination(dest, skill_id="demo") == OWNERSHIP_UNOWNED


def test_classify_install_destination_corrupt_when_manifest_is_invalid_json(tmp_path: Path) -> None:
    dest = tmp_path / "corrupt"
    dest.mkdir()
    (dest / MANIFEST_NAME).write_text("{not valid json", encoding="utf-8")
    assert classify_install_destination(dest, skill_id="demo") == OWNERSHIP_CORRUPT_OWNERSHIP


def test_classify_install_destination_corrupt_when_manifest_names_a_different_skill(tmp_path: Path) -> None:
    dest = tmp_path / "wrong-skill"
    dest.mkdir()
    (dest / MANIFEST_NAME).write_text('{"skill": "other-skill"}', encoding="utf-8")
    assert classify_install_destination(dest, skill_id="demo") == OWNERSHIP_CORRUPT_OWNERSHIP


def test_classify_install_destination_owned_when_manifest_names_this_skill(tmp_path: Path) -> None:
    dest = tmp_path / "demo"
    dest.mkdir()
    (dest / MANIFEST_NAME).write_text('{"skill": "demo"}', encoding="utf-8")
    assert classify_install_destination(dest, skill_id="demo") == OWNERSHIP_SOFTWARE_BUILDER_OWNED


def test_extract_markdown_links_preserves_parens_in_target() -> None:
    # Regression test: a plain "[^)]+" target class truncates at the FIRST ")", corrupting any
    # link whose target legitimately contains one (e.g. a Wikipedia-style URL ending "_(bar)").
    # This is the same bug class fixed in scripts/registry/cross_skill_routing.py's own markdown
    # link regex, found live here too during a full-system review.
    text = "See [wiki](https://en.wikipedia.org/wiki/Foo_(bar)) for detail"

    links = extract_markdown_links(text)

    assert links == ["https://en.wikipedia.org/wiki/Foo_(bar)"]


def test_rewrite_framework_links_preserves_parens_in_untouched_target(tmp_path: Path) -> None:
    # A link the rewriter doesn't touch (no docs/skill-framework/ marker) must still round-trip
    # intact. Note: replace_link() returns match.group(0) verbatim on this early-return path, so
    # this specific case can't discriminate old vs. new regex behavior on its own (a truncated
    # match's leftover text recombines into the same original string either way) -- it guards
    # against a *different* mutation (e.g. .sub() dropping/mangling untouched text), not the
    # paren-truncation bug. See the sibling test below for the discriminating case.
    content = "See [wiki](https://en.wikipedia.org/wiki/Foo_(bar)) for detail"
    source_file = tmp_path / "SKILL.md"
    package_root = tmp_path / "package"

    result = rewrite_framework_links(content, source_file, package_root)

    assert result == content


def test_rewrite_framework_links_preserves_parens_in_rewritten_target(tmp_path: Path) -> None:
    # Discriminating version: a framework-marked link actually gets rewritten (goes through
    # framework_relative_path + os.path.relpath), so a truncated target here produces a visibly
    # different (unresolved "/../") result versus the correctly-collapsed path -- same technique
    # as test_reanchor_relative_links_preserves_parens_in_relative_link_target in test_registry.py.
    content = "[x](docs/skill-framework/shared/foo_(bar)/../other.md)"
    source_file = tmp_path / "sub" / "SKILL.md"
    package_root = tmp_path

    result = rewrite_framework_links(content, source_file, package_root)

    assert result == "[x](../docs/skill-framework/shared/other.md)"
