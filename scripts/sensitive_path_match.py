#!/usr/bin/env python3
"""Shared sensitive-path matcher for the F1 review-evidence gate (Track B).

The one place `docs/sensitive-paths.yaml` (globs + content-pattern supplement) is matched
against a PR's changed files and diff text. `scripts/check_review_evidence.py` imports this
module for both its `check` (review-evidence-check CI job) and `analyze` (invoked directly by
the review-evidence-post CI job -- see `.github/workflows/review-evidence-post.yml`) subcommands,
so "is this PR sensitive" is never independently re-derived in two places and cannot drift out of
sync -- see the design doc's Components table, `sensitive_path_match` row.

Fail-closed by construction: `load_sensitive_path_list` raises `SensitivePathListError` (a
`ValueError` subclass) on anything missing, malformed, or empty, rather than returning a spec
that would silently treat every PR as "not sensitive". Callers must catch this and fail closed
(exit 2, "cannot determine" -- never "nothing is sensitive"), per the design's Failure-strategy
table.
"""

from __future__ import annotations

import fnmatch
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file  # noqa: E402

DEFAULT_SENSITIVE_PATH_LIST = ROOT / "docs" / "sensitive-paths.yaml"

# `diff --git a/<path> b/<path>` is the one line `gh pr diff`'s unified-diff output always
# emits for every changed file -- added, deleted, edited in place, or renamed/copied (where
# `a/<old path>` and `b/<new path>` differ). Extracting both sides means a rename *out of* a
# still-glob-matching path stays visible to path-based matching; the content-pattern supplement
# below is the primary defense against a rename that also escapes every glob.
_DIFF_GIT_LINE_RE = re.compile(r'^diff --git "?a/(?P<old>.+?)"? "?b/(?P<new>.+?)"?$', re.MULTILINE)

_REQUIRED_KEYS = {"globs", "content_patterns"}


class SensitivePathListError(ValueError):
    """Raised when docs/sensitive-paths.yaml is missing, malformed, or empty.

    Callers MUST treat this as "cannot determine" (fail closed), never as "nothing is
    sensitive" -- see the design doc's Failure-strategy table.
    """


@dataclass(frozen=True)
class SensitivePathList:
    """A loaded, validated `docs/sensitive-paths.yaml`."""

    globs: tuple[str, ...]
    content_patterns: tuple[re.Pattern[str], ...]
    content_pattern_sources: tuple[str, ...]


@dataclass(frozen=True)
class SensitivityResult:
    """The one sensitivity verdict both consumers act on."""

    sensitive: bool
    matched_globs: tuple[str, ...]
    matched_content_patterns: tuple[str, ...]


def _require_string_list(value: object, key: str, path: Path) -> list[str]:
    if value is None:
        raise SensitivePathListError(f"{path}: missing required key {key!r}")
    if not isinstance(value, list):
        raise SensitivePathListError(f"{path}: {key!r} must be a list, got {type(value).__name__}")
    strings: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise SensitivePathListError(f"{path}: {key}[{index}] must be a non-empty string")
        strings.append(item)
    return strings


def load_sensitive_path_list(path: Path = DEFAULT_SENSITIVE_PATH_LIST) -> SensitivePathList:
    """Load and validate `path` as a two-key `{globs, content_patterns}` mapping.

    Raises `SensitivePathListError` on anything missing, malformed, or empty -- including a
    file with both lists empty, which is treated as broken configuration, not as "protect
    nothing" (design doc, Failure strategy: "Malformed or empty docs/sensitive-paths.yaml ...
    never silently 'nothing is sensitive'").
    """
    if not path.is_file():
        raise SensitivePathListError(f"cannot read sensitive-path list at {path}: no such file")

    try:
        data = load_unique_yaml_file(path)
    except YAML_SAFETY_ERRORS as exc:
        raise SensitivePathListError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise SensitivePathListError(
            f"{path}: top level must be a mapping with 'globs' and 'content_patterns' keys",
        )

    extra_keys = set(data) - _REQUIRED_KEYS
    if extra_keys:
        raise SensitivePathListError(f"{path}: unexpected top-level key(s): {sorted(extra_keys)}")

    globs = _require_string_list(data.get("globs"), "globs", path)
    pattern_sources = _require_string_list(data.get("content_patterns"), "content_patterns", path)

    if not globs and not pattern_sources:
        raise SensitivePathListError(
            f"{path}: 'globs' and 'content_patterns' are both empty -- a sensitive-path list "
            "that could never match anything is treated as malformed, not as 'nothing is "
            "sensitive'",
        )

    compiled: list[re.Pattern[str]] = []
    for source in pattern_sources:
        try:
            compiled.append(re.compile(source))
        except re.error as exc:
            raise SensitivePathListError(f"{path}: invalid content_patterns regex {source!r}: {exc}") from exc

    return SensitivePathList(
        globs=tuple(globs),
        content_patterns=tuple(compiled),
        content_pattern_sources=tuple(pattern_sources),
    )


def extract_changed_paths(diff_text: str) -> set[str]:
    """Return every path (old and new side) named by a `diff --git` header in `diff_text`.

    Covers ordinary adds/edits/deletes (old path == new path) and renames/copies (old path !=
    new path) alike.
    """
    paths: set[str] = set()
    for match in _DIFF_GIT_LINE_RE.finditer(diff_text):
        paths.add(match.group("old"))
        paths.add(match.group("new"))
    return paths


def matched_globs(paths: Iterable[str], globs: Iterable[str]) -> list[str]:
    """Return the subset of `globs` that match at least one of `paths`.

    Uses `fnmatch` semantics case-sensitively (`fnmatchcase`): `*` matches across path
    separators too, so a broader-than-literal pattern like `skills/*/scripts/*lock*` matches
    by design. Overmatching only ever widens the gate's scope, never narrows it -- the safe
    direction for a fail-closed mechanism.
    """
    path_list = list(paths)
    return [glob for glob in globs if any(fnmatch.fnmatchcase(candidate, glob) for candidate in path_list)]


def matched_content_patterns(diff_text: str, spec: SensitivePathList) -> list[str]:
    """Return the `content_patterns` (as originally authored strings) whose regex matches
    somewhere in `diff_text` -- the rename/split-evasion supplement, independent of which
    file(s) the matching text lands in.
    """
    return [
        source
        for source, pattern in zip(spec.content_pattern_sources, spec.content_patterns)
        if pattern.search(diff_text)
    ]


def classify(
    diff_text: str,
    spec: SensitivePathList,
    *,
    changed_paths: Iterable[str] | None = None,
) -> SensitivityResult:
    """The one sensitivity decision every consumer calls.

    Combines glob matching against changed paths (parsed from `diff_text` itself unless
    `changed_paths` is supplied explicitly) with the content-pattern supplement over the full
    diff text.
    """
    paths = list(changed_paths) if changed_paths is not None else sorted(extract_changed_paths(diff_text))
    globs_hit = matched_globs(paths, spec.globs)
    patterns_hit = matched_content_patterns(diff_text, spec)
    return SensitivityResult(
        sensitive=bool(globs_hit or patterns_hit),
        matched_globs=tuple(globs_hit),
        matched_content_patterns=tuple(patterns_hit),
    )
