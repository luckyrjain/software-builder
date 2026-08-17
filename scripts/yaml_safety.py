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

# PyYAML has no public name for this; it's the literal tag flatten_mapping()
# matches on internally (see yaml.constructor.BaseConstructor.flatten_mapping).
_MERGE_TAG = "tag:yaml.org,2002:merge"


class DuplicateKeyError(yaml.YAMLError):
    """Raised when YAML would otherwise silently overwrite a mapping key."""


class DuplicateKeySafeLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects duplicate keys recursively."""


# Every function in this module raises from this set (or a subclass, e.g.
# DuplicateKeyError). Callers should catch this tuple, not just ValueError.
YAML_SAFETY_ERRORS = (ValueError, yaml.YAMLError)


def _construct_unique_mapping(
    loader: DuplicateKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    # flatten_mapping() resolves `<<:` merge keys by prepending the merged pairs
    # to node.value, relying on the *constructor* to let later (explicit) pairs
    # silently win over earlier (merged) ones -- standard YAML merge-key
    # semantics. Count explicit pairs before flattening so we know which tail
    # of the flattened node.value is this mapping's own explicit content: only
    # a key repeated within that explicit tail is a real accidental duplicate.
    # A key that merely overrides a merged key, or two merge sources that
    # collide with each other, resolve the same way plain yaml.safe_load does.
    explicit_count = sum(1 for key_node, _ in node.value if key_node.tag != _MERGE_TAG)
    loader.flatten_mapping(node)
    merge_count = len(node.value) - explicit_count
    mapping: dict[object, object] = {}
    explicit_keys: set[object] = set()
    for index, (key_node, value_node) in enumerate(node.value):
        # Fully construct keys so malformed collection keys have deterministic content
        # instead of PyYAML's still-empty deferred placeholder.
        key = loader.construct_object(key_node, deep=True)
        try:
            hash(key)
        except TypeError as exc:
            raise DuplicateKeyError(f"unhashable YAML mapping key {key!r}") from exc
        if index >= merge_count:
            if key in explicit_keys:
                raise DuplicateKeyError(f"duplicate YAML mapping key {key!r}")
            explicit_keys.add(key)
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

    Known limitation: self-referential anchors (a mapping that contains an
    alias to itself, e.g. ``a: &x\\n  b: *x``) raise ConstructorError here
    even though plain yaml.safe_load resolves them, because the duplicate-key
    check needs the mapping fully built before returning it. No file in this
    repo uses that pattern; supporting it would require the deferred,
    generator-based construction PyYAML's own constructors use.
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


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    """Return value if it's a mapping, else raise ValueError naming the offending field."""
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def read_schema_version(path: Path, *, raw: dict[str, Any] | None = None) -> int:
    """Read and validate the integer ``schema_version`` field of a YAML mapping file.

    Shared by release_contract.py and package_release.py, which both need the
    same schema_version a release's compatibility fields are checked against.

    Pass `raw` when the caller already parsed+shape-checked the file (e.g.
    package_release.py also reads host_contracts.yaml's ``hosts`` key for
    supported_hosts()) so this doesn't re-read and re-parse the same file a
    second time; omitted, it loads and validates `path` itself as before.
    """
    if raw is None:
        raw = require_mapping(load_unique_yaml_file(path), str(path))
    value = raw.get("schema_version")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{path}: schema_version must be an integer")
    return value


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
