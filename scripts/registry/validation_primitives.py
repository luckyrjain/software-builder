"""Shared primitives for the repo's `validate_X(data) -> list[str]` validators.

Every accumulating validator in this repository needs the same handful of building blocks:
coerce an untrusted top-level value to a mapping, test a non-empty string, check a list of
strings, check enum membership, and report undeclared fields. Each hand-rolled copy is another
chance for the degradation policy to differ, so this module owns them once.

Two degradation policies exist on purpose and are named at the interface rather than left to
each caller to re-derive:

* **Degrading** (`as_mapping(value)`) -- a malformed shape becomes `{}`. Used by the assessment
  modules, where one bad field from an untrusted child must fail that dimension closed rather
  than crash the whole aggregation.
* **Strict** (`as_mapping(value, strict=True, label=...)`) -- a malformed shape raises
  `TypeError`. Used where the input is repo-owned and a wrong shape is a bug, not evidence.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Collection, Iterable, Mapping
from pathlib import Path
from typing import Any


def as_mapping(value: Any, *, strict: bool = False, label: str = "value") -> Mapping[str, Any]:
    """Coerce any value to a mapping.

    By default a non-Mapping degrades to `{}` so a caller's unconditional `.get()` cannot raise
    `AttributeError`. With `strict=True` a non-Mapping raises `TypeError` naming `label`.
    """
    if isinstance(value, Mapping):
        return value
    if strict:
        raise TypeError(f"{label} must be a mapping")
    return {}


def non_empty_str(value: Any) -> bool:
    """True only for a string with at least one non-whitespace character."""
    return isinstance(value, str) and bool(value.strip())


def string_list(
    value: Any,
    label: str,
    *,
    allow_empty: bool = True,
    unique: bool = False,
) -> list[str]:
    """Validate a list of non-empty strings, returning accumulated error messages."""
    if not isinstance(value, list) or not all(non_empty_str(item) for item in value):
        return [f"error: {label} must be a list of non-empty strings"]
    errors: list[str] = []
    if not allow_empty and not value:
        errors.append(f"error: {label} must not be empty")
    if unique and len(value) != len(set(value)):
        errors.append(f"error: {label} must not contain duplicates")
    return errors


def enum_value(value: Any, allowed: Collection[str], label: str) -> list[str]:
    """Validate enum membership, returning accumulated error messages.

    An unhashable value (a list, a dict) degrades to "not a member" rather than raising the
    `TypeError` a bare `value in allowed` would produce against a set.
    """
    try:
        member = value in allowed
    except TypeError:
        member = False
    if isinstance(value, str) and member:
        return []
    return [f"error: {label} must be one of: {', '.join(sorted(allowed))}"]


def unknown_fields(value: Any, allowed: Iterable[str]) -> list[Any]:
    """Return the keys of `value` that are not in `allowed`, ordered by string form.

    Ordered by string form rather than by the keys themselves: YAML admits non-string keys, and
    an undeclared `1:` alongside an undeclared `a:` must be reported, not crash the validator on
    an unorderable comparison. Keys come back as written, so a caller can render them.
    """
    mapping = as_mapping(value)
    return sorted(set(mapping) - set(allowed), key=str)


def run_validator_cli(
    argv: list[str] | None,
    *,
    load: Callable[[Path], tuple[Any, str | None]],
    validate: Callable[[Any], list[str]],
    default_paths: Iterable[str] = (),
) -> int:
    """Run the repo's standard load -> validate -> report CLI over one or more paths.

    `load` returns `(data, load_error)`; a non-None `load_error` reports that path as failed
    without calling `validate`. Returns 0 when every path validates, 1 otherwise.
    """
    paths = (argv if argv is not None else sys.argv[1:]) or list(default_paths)
    exit_code = 0
    for path_str in paths:
        path = Path(path_str)
        data, load_error = load(path)
        if load_error:
            print(f"{path}: {load_error}", file=sys.stderr)
            exit_code = 1
            continue
        errors = validate(data)
        if errors:
            exit_code = 1
            print(f"{path}: validation failed", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"{path}: ok")
    return exit_code
