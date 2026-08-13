#!/usr/bin/env python3
"""Shared YAML-safety loader: rejects duplicate mapping keys and caps document
size/nesting so a malformed file fails loudly instead of silently overwriting
data (last-key-wins) or blowing the stack on deeply nested/recursive input.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

MAX_YAML_CHARS = 1_000_000
MAX_YAML_NESTING = 100

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


class DuplicateKeyError(yaml.YAMLError):
    """Raised when YAML would otherwise silently overwrite a mapping key."""


class DuplicateKeySafeLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects duplicate keys recursively."""


def _construct_unique_mapping(
    loader: DuplicateKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        # Fully construct keys so malformed collection keys have deterministic content
        # instead of PyYAML's still-empty deferred placeholder.
        key = loader.construct_object(key_node, deep=True)
        try:
            hash(key)
        except TypeError as exc:
            raise DuplicateKeyError(f"unhashable YAML mapping key {key!r}") from exc
        if key in mapping:
            raise DuplicateKeyError(f"duplicate YAML mapping key {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


DuplicateKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_unique_yaml(text: str) -> Any:
    """Parse YAML text, rejecting duplicate mapping keys and oversized/deeply
    nested input. Raises yaml.YAMLError (or a DuplicateKeyError subclass) on
    any violation.
    """
    if len(text) > MAX_YAML_CHARS:
        raise yaml.YAMLError(f"YAML input exceeds {MAX_YAML_CHARS} characters")
    # Parser events distinguish real YAML collections from brackets in quoted or
    # block scalars and comments, while still running before recursive construction.
    depth = 0
    for event in yaml.parse(text, Loader=yaml.SafeLoader):
        if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
            depth += 1
            if depth > MAX_YAML_NESTING:
                raise yaml.YAMLError(f"YAML nesting exceeds {MAX_YAML_NESTING} levels")
        elif isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
            depth -= 1
    try:
        return yaml.load(text, Loader=DuplicateKeySafeLoader)
    except RecursionError as exc:
        raise yaml.YAMLError("YAML nesting exceeds safe decoder limits") from exc


def load_unique_yaml_file(path: Path) -> Any:
    """Read and parse a YAML file via load_unique_yaml."""
    return load_unique_yaml(path.read_text(encoding="utf-8"))


def load_unique_frontmatter(path: Path) -> dict[str, Any]:
    """Extract and parse a Markdown file's leading ``---`` frontmatter block
    via load_unique_yaml. Raises ValueError if the block is missing or is not
    a mapping.
    """
    match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"missing YAML frontmatter: {path}")
    data = load_unique_yaml(match.group(1))
    if not isinstance(data, dict):
        raise ValueError(f"frontmatter must be a mapping: {path}")
    return data
