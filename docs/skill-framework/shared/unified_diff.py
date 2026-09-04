#!/usr/bin/env python3
"""One grammar for the parts of a unified diff that three consumers had each re-derived.

`scripts/change_impact.py` wanted the paths a diff touches. `pr-review`'s
`github-comment-positions.py` wanted to validate that a GitHub anchor's diff record is complete.
`pr-review`'s `diff-to-positions.py` wanted line numbers inside a hunk. Each grew its own copy of
the same two grammars -- how Git writes a path in a `diff --git` header, and how a hunk header
reads -- and the copies had already drifted: two different octal-escape decoders, two different
record-size caps, two `@@` regexes.

What lives here is the grammar, not the policy. A `diff --git` header is genuinely ambiguous --
Git does not quote a path merely because it contains a space, so `diff --git a/my file.py b/my
file.py` has several readings until the record's own rename/copy/`---`/`+++` metadata binds it --
and the two callers resolve that ambiguity differently on purpose:

* the anchor validator fails closed, accepting an unbound header only when both sides are the same
  path (`require_identical_when_unbound=True`);
* the impact analyser prefers an identical split when one exists but will still take a single
  unambiguous rename split, because dropping a renamed path silently understates blast radius.

That difference is a parameter, not a reason for two parsers. The size caps are parameters for the
same reason: an anchor validator reads whole PR patches, an impact analyser reads a header.

Details one consumer needs and the others merely tolerate live here too, so no consumer grows a
private fork of the grammar to hold them: C-quoted paths with octal escapes, `/dev/null` sides,
rename/copy metadata, `\\ No newline at end of file` (a content line, never a header -- see
`FILE_MARKER_OLD`/`FILE_MARKER_NEW`, which match only real markers), and mode-only records, which
name no hunk at all and so simply yield a header with equal sides.
"""

from __future__ import annotations

import re
from typing import Callable, Iterator, NamedTuple

#: Returned by `decode_git_path` for a field that is not a well-formed Git path.
INVALID_PATH = object()

DIFF_HEADER_PREFIX = "diff --git "

# Caps that keep header disambiguation linear in the record length: a pathological header full of
# " b/" tokens is discarded, not searched. Callers pick the bound their input size warrants.
DEFAULT_MAX_RECORD_CHARS = 64 * 1024
DEFAULT_MAX_PATH_SEPARATORS = 64

GIT_QUOTE_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}

#: `@@ -old[,count] +new[,count] @@` -- the one hunk header grammar.
HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

# Real file-boundary markers, not content lines that merely start with `+++`/`---`. An added line
# whose own text begins with `++ b/x` renders as `+++ b/x`; only the side prefix or /dev/null
# distinguishes the two, and only position (between hunks) settles the rest.
FILE_MARKER_OLD = re.compile(r"^--- (a/|/dev/null)")
FILE_MARKER_NEW = re.compile(r"^\+\+\+ (b/|/dev/null)")

# Within one diff record these lines name a path unambiguously and so bind an otherwise ambiguous
# header. A rename/copy operand carries no side prefix; a --- / +++ marker does.
OLD_PATH_HINTS: tuple[tuple[str, bool], ...] = (
    ("rename from ", False),
    ("copy from ", False),
    ("--- ", True),
)
NEW_PATH_HINTS: tuple[tuple[str, bool], ...] = (
    ("rename to ", False),
    ("copy to ", False),
    ("+++ ", True),
)


class DiffFileHeader(NamedTuple):
    """One resolved `diff --git` record: the paths it names and whether the sides differ."""

    old_path: str
    new_path: str
    is_rename: bool


def decode_git_path(raw: str) -> str | object:
    """Decode one Git path field, including C-quoted octal UTF-8 bytes.

    Returns `INVALID_PATH` when the field is malformed, so a caller can tell "not a path" from a
    path that happens to be empty.
    """
    if not raw.startswith('"'):
        return raw
    if len(raw) < 2 or not raw.endswith('"'):
        return INVALID_PATH
    decoded = bytearray()
    cursor = 1
    while cursor < len(raw) - 1:
        character = raw[cursor]
        if character != "\\":
            decoded.extend(character.encode("utf-8"))
            cursor += 1
            continue
        cursor += 1
        if cursor >= len(raw) - 1:
            return INVALID_PATH
        escaped = raw[cursor]
        if escaped in GIT_QUOTE_ESCAPES:
            decoded.append(GIT_QUOTE_ESCAPES[escaped])
            cursor += 1
            continue
        if escaped not in "01234567":
            return INVALID_PATH
        end = cursor
        while end < min(cursor + 3, len(raw) - 1) and raw[end] in "01234567":
            end += 1
        value = int(raw[cursor:end], 8)
        if value > 255:
            return INVALID_PATH
        decoded.append(value)
        cursor = end
    try:
        return decoded.decode("utf-8")
    except UnicodeDecodeError:
        return INVALID_PATH


def quoted_field_end(raw: str) -> int | None:
    """Index just past the closing quote of a C-quoted field starting at index 0."""
    escaped = False
    for index in range(1, len(raw)):
        if raw[index] == '"' and not escaped:
            return index + 1
        escaped = raw[index] == "\\" and not escaped
    return None


def separator_positions_outside_quotes(
    raw: str,
    tokens: tuple[str, ...],
    *,
    max_separators: int = DEFAULT_MAX_PATH_SEPARATORS,
) -> list[int] | None:
    """Candidate field-separator offsets that fall outside C quotes, or None when unbounded."""
    positions: list[int] = []
    quoted = False
    escaped = False
    for index, character in enumerate(raw):
        if character == '"' and not escaped:
            quoted = not quoted
        if not quoted and any(raw.startswith(token, index) for token in tokens):
            positions.append(index)
            if len(positions) > max_separators:
                return None
        escaped = quoted and character == "\\" and not escaped
    return None if quoted else positions


def strip_side_prefix(path: str | object | None, side: str) -> str | None:
    """Drop a leading `a/` or `b/`, or None when `path` does not carry that side's prefix."""
    return path[2:] if isinstance(path, str) and path.startswith(f"{side}/") else None


def hunk_range(raw: str) -> tuple[int, int, int, int] | None:
    """Old/new starts and counts for a syntactically valid hunk header, else None."""
    match = HUNK_HEADER.match(raw)
    if not match:
        return None
    numeric_fields = [group for group in match.groups() if group is not None]
    if any(len(group) > 12 for group in numeric_fields):
        return None
    try:
        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) is not None else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) is not None else 1
    except ValueError:
        return None
    # A non-empty range cannot begin at line zero. Zero-count ranges may use
    # zero (new/deleted files) or the insertion/deletion point used by git.
    if (old_count > 0 and old_start == 0) or (new_count > 0 and new_start == 0):
        return None
    if old_count == 0 and new_count == 0:
        return None
    return old_start, old_count, new_start, new_count


def record_path_hint(line: str, hints: tuple[tuple[str, bool], ...], side: str) -> str | None:
    """The path a rename/copy/marker line names, or None when the line names no path."""
    for prefix, side_prefixed in hints:
        if not line.startswith(prefix):
            continue
        operand = line[len(prefix):].strip()
        if operand == "/dev/null":
            return None
        decoded = decode_git_path(operand)
        if side_prefixed:
            return strip_side_prefix(decoded, side)
        return decoded if isinstance(decoded, str) else None
    return None


def parse_diff_git_header(
    raw: str,
    *,
    old_hint: str | None = None,
    new_hint: str | None = None,
    accept: Callable[[str, str], bool] | None = None,
    max_record_chars: int = DEFAULT_MAX_RECORD_CHARS,
    max_separators: int = DEFAULT_MAX_PATH_SEPARATORS,
    require_identical_when_unbound: bool = True,
) -> tuple[str, str] | None:
    """Resolve one `diff --git` header to its (old, new) paths, or None when still ambiguous.

    `old_hint`/`new_hint`/`accept` are the record's own binding evidence. With none of them,
    `require_identical_when_unbound` decides the reading: True accepts only a split whose sides
    are the same path (fail closed), False prefers such a split but falls back to a single
    unambiguous candidate.
    """
    if len(raw) > max_record_chars or not raw.startswith(DIFF_HEADER_PREFIX):
        return None
    fields = raw[len(DIFF_HEADER_PREFIX):]
    if fields.startswith('"'):
        end = quoted_field_end(fields)
        if end is None or end >= len(fields) or fields[end] != " ":
            return None
        splits = [(fields[:end], fields[end + 1:])]
    else:
        separators = separator_positions_outside_quotes(
            fields, (" b/", ' "b/'), max_separators=max_separators
        )
        if separators is None:
            return None
        splits = [(fields[:index], fields[index + 1:]) for index in separators]

    candidates: list[tuple[str, str]] = []
    for old_raw, new_raw in splits:
        old_path = strip_side_prefix(decode_git_path(old_raw), "a")
        new_path = strip_side_prefix(decode_git_path(new_raw), "b")
        if old_path is None or new_path is None:
            continue
        if old_hint is not None and old_path != old_hint:
            continue
        if new_hint is not None and new_path != new_hint:
            continue
        if accept is not None and not accept(old_path, new_path):
            continue
        candidates.append((old_path, new_path))

    if old_hint is None and new_hint is None and accept is None:
        identical = [candidate for candidate in candidates if candidate[0] == candidate[1]]
        if require_identical_when_unbound or identical:
            candidates = identical
    return candidates[0] if len(candidates) == 1 else None


def iter_file_headers(
    text: str,
    *,
    max_record_chars: int = DEFAULT_MAX_RECORD_CHARS,
    max_separators: int = DEFAULT_MAX_PATH_SEPARATORS,
    require_identical_when_unbound: bool = True,
) -> Iterator[DiffFileHeader]:
    """Every `diff --git` record in a unified diff, resolved against its own metadata.

    A record that stays ambiguous after its metadata is consulted yields nothing, rather than
    yielding a truncated path.
    """
    records: list[tuple[str, str | None, str | None]] = []
    header: str | None = None
    old_hint: str | None = None
    new_hint: str | None = None
    for line in text.splitlines():
        if line.startswith(DIFF_HEADER_PREFIX):
            if header is not None:
                records.append((header, old_hint, new_hint))
            header, old_hint, new_hint = line, None, None
            continue
        if header is None:
            continue
        old_hint = record_path_hint(line, OLD_PATH_HINTS, "a") or old_hint
        new_hint = record_path_hint(line, NEW_PATH_HINTS, "b") or new_hint
    if header is not None:
        records.append((header, old_hint, new_hint))

    for raw_header, old, new in records:
        resolved = parse_diff_git_header(
            raw_header,
            old_hint=old,
            new_hint=new,
            max_record_chars=max_record_chars,
            max_separators=max_separators,
            require_identical_when_unbound=require_identical_when_unbound,
        )
        if resolved is None:
            continue
        left, right = resolved
        yield DiffFileHeader(old_path=left, new_path=right, is_rename=left != right)
