"""Tests for the shared YAML-safety loader (scripts/yaml_safety.py)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.yaml_safety import (
    DuplicateKeyError,
    load_unique_frontmatter,
    load_unique_yaml,
    load_unique_yaml_file,
)


def test_parses_ordinary_yaml_like_safe_load() -> None:
    text = "a: 1\nb:\n  - 2\n  - 3\n"
    assert load_unique_yaml(text) == yaml.safe_load(text)


def test_rejects_duplicate_top_level_key() -> None:
    with pytest.raises(DuplicateKeyError, match="duplicate YAML mapping key 'a'"):
        load_unique_yaml("a: 1\nb: 2\na: 3\n")


def test_rejects_duplicate_nested_key() -> None:
    with pytest.raises(DuplicateKeyError, match="duplicate YAML mapping key 'x'"):
        load_unique_yaml("root:\n  x: 1\n  x: 2\n")


def test_rejects_unhashable_key() -> None:
    with pytest.raises(DuplicateKeyError, match="unhashable YAML mapping key"):
        load_unique_yaml("? [1, 2]\n: value\n")


def test_rejects_oversized_document(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.yaml_safety as yaml_safety

    monkeypatch.setattr(yaml_safety, "MAX_YAML_CHARS", 10)
    with pytest.raises(yaml.YAMLError, match="exceeds 10 characters"):
        load_unique_yaml("a: " + "x" * 20)


def test_rejects_excessive_nesting(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.yaml_safety as yaml_safety

    monkeypatch.setattr(yaml_safety, "MAX_YAML_NESTING", 2)
    with pytest.raises(yaml.YAMLError, match="nesting exceeds 2 levels"):
        load_unique_yaml("a:\n  b:\n    c: 1\n")


def test_merge_key_explicit_override_is_allowed() -> None:
    # `<<:` (YAML merge key) followed by an explicit key of the same name is a
    # legal, common idiom -- the explicit value should win, matching
    # yaml.safe_load, not be rejected as an accidental duplicate.
    text = "base: &base\n  foo: 1\n  bar: 2\nchild:\n  <<: *base\n  bar: 3\n"
    result = load_unique_yaml(text)
    assert result == yaml.safe_load(text)
    assert result["child"] == {"foo": 1, "bar": 3}


def test_multiple_merge_sources_colliding_is_allowed() -> None:
    text = "a: &a\n  foo: 1\nb: &b\n  foo: 2\nchild:\n  <<: [*a, *b]\n"
    result = load_unique_yaml(text)
    assert result == yaml.safe_load(text)


def test_duplicate_explicit_key_alongside_merge_is_still_rejected() -> None:
    # A merge key doesn't grant amnesty to a genuine copy-paste duplicate
    # among the mapping's own explicit keys.
    text = "base: &base\n  foo: 1\nchild:\n  <<: *base\n  x: 1\n  x: 2\n"
    with pytest.raises(DuplicateKeyError, match="duplicate YAML mapping key 'x'"):
        load_unique_yaml(text)


def test_load_unique_yaml_file_reads_and_parses(tmp_path: Path) -> None:
    path = tmp_path / "doc.yaml"
    path.write_text("a: 1\n", encoding="utf-8")
    assert load_unique_yaml_file(path) == {"a": 1}


def test_load_unique_yaml_file_propagates_duplicate_key(tmp_path: Path) -> None:
    path = tmp_path / "doc.yaml"
    path.write_text("a: 1\na: 2\n", encoding="utf-8")
    with pytest.raises(DuplicateKeyError):
        load_unique_yaml_file(path)


def test_load_unique_yaml_file_names_the_file_in_duplicate_key_errors(tmp_path: Path) -> None:
    path = tmp_path / "fragment.yaml"
    path.write_text("a: 1\na: 2\n", encoding="utf-8")
    with pytest.raises(DuplicateKeyError) as excinfo:
        load_unique_yaml_file(path)
    assert str(path) in str(excinfo.value)
    assert "duplicate YAML mapping key" in str(excinfo.value)


def test_load_unique_yaml_file_names_the_file_in_syntax_errors(tmp_path: Path) -> None:
    path = tmp_path / "fragment.yaml"
    path.write_text("a: 1\n  b: [\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError) as excinfo:
        load_unique_yaml_file(path)
    assert str(path) in str(excinfo.value)


def test_load_unique_frontmatter_parses_valid_block(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
    assert load_unique_frontmatter(path) == {"name": "demo"}


def test_load_unique_frontmatter_missing_block_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text("no frontmatter here\n", encoding="utf-8")
    with pytest.raises(ValueError, match=f"missing YAML frontmatter: {path}"):
        load_unique_frontmatter(path)


def test_load_unique_frontmatter_non_mapping_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text("---\n- 1\n- 2\n---\nbody\n", encoding="utf-8")
    with pytest.raises(ValueError, match=f"frontmatter must be a mapping: {path}"):
        load_unique_frontmatter(path)


def test_load_unique_frontmatter_rejects_duplicate_key(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text("---\nname: demo\nname: other\n---\nbody\n", encoding="utf-8")
    with pytest.raises(DuplicateKeyError, match="duplicate YAML mapping key 'name'"):
        load_unique_frontmatter(path)
