#!/usr/bin/env python3
"""Validate GitHub inline-review anchors against a unified diff."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Literal
import zlib

SKILL_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_DIR = Path(__file__).resolve().parent
_INSTALL_MANIFEST = ".software-builder-manifest.json"
_RUNTIME_DESCRIPTION = "shared unified-diff runtime"


def _shared_runtime_loader() -> ModuleType:
    """Import shared_runtime_loader, which owns the containment policy for every module this
    script executes out of docs/skill-framework/shared/.

    Only locating the loader itself is handled here, and it needs no policy of its own: an
    installed package carries the loader beside this script (package_skill.py vendors it), so the
    lookup never leaves the package, and the install manifest is what proves a missing vendored
    copy is a packaging fault rather than an invitation to read a sibling path.
    """
    beside = _SCRIPT_DIR / "shared_runtime_loader.py"
    if beside.is_file():
        path = beside
    elif (SKILL_ROOT / _INSTALL_MANIFEST).is_file():
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {beside}")
    else:
        path = SKILL_ROOT.parent / "docs/skill-framework/shared/shared_runtime_loader.py"
    if not path.is_file():
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    spec = importlib.util.spec_from_file_location("software_builder_shared_runtime_loader", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_unified_diff = _shared_runtime_loader().load_shared_runtime(
    SKILL_ROOT,
    "unified_diff",
    alias="shared_unified_diff",
    description=_RUNTIME_DESCRIPTION,
)

INVALID_MARKER = _unified_diff.INVALID_PATH
HUNK_HEADER = _unified_diff.HUNK_HEADER
GIT_BASE85_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~"
GIT_BASE85_VALUES = {character: index for index, character in enumerate(GIT_BASE85_ALPHABET)}
MAX_BINARY_BLOCK_BYTES = 8 * 1024 * 1024
# An anchor is validated against a whole PR patch, so records are capped generously; an
# unbound header is still only read as an unchanged path, which is the fail-closed reading.
MAX_DIFF_RECORD_CHARS = 64 * 1024
MAX_PATH_SEPARATORS = 64


def _diff_paths(
    raw: str,
    *,
    old_hint: str | None = None,
    new_hint: str | None = None,
    binary_summary: str | None = None,
) -> tuple[str, str] | None:
    """Parse a ``diff --git`` header, binding ambiguous spaces to section paths."""

    def binary_summary_binds(old_path: str, new_path: str) -> bool:
        return _binary_summary_matches(binary_summary, old_path, new_path)

    accept = None if binary_summary is None else binary_summary_binds
    return _unified_diff.parse_diff_git_header(
        raw,
        old_hint=old_hint,
        new_hint=new_hint,
        accept=accept,
        max_record_chars=MAX_DIFF_RECORD_CHARS,
        max_separators=MAX_PATH_SEPARATORS,
        require_identical_when_unbound=True,
    )


def _marker_operand(raw: str) -> str | object:
    """Decode a marker operand while retaining its a/ or b/ side prefix."""
    if len(raw) > MAX_DIFF_RECORD_CHARS:
        return INVALID_MARKER
    field = raw[4:]
    if not field:
        return INVALID_MARKER
    if field.startswith('"'):
        end = _unified_diff.quoted_field_end(field)
        if end is None or (field[end:] and not field[end:].startswith("\t")):
            return INVALID_MARKER
        field = field[:end]
    else:
        field = field.split("\t", 1)[0]
    return _unified_diff.decode_git_path(field)


def _marker_path(raw: str) -> str | None | object:
    """Parse a ---/+++ marker path, including quoted paths and /dev/null."""
    marker_path = _marker_operand(raw)
    if marker_path is INVALID_MARKER:
        return INVALID_MARKER
    if marker_path == "/dev/null":
        return None
    return marker_path[2:] if marker_path.startswith(("a/", "b/")) else marker_path


def _move_metadata_paths(records: list[str]) -> tuple[str, str] | None:
    """Decode one canonical similarity + rename/copy metadata triple."""
    if any(len(record) > MAX_DIFF_RECORD_CHARS for record in records):
        return None
    if len(records) != 3 or re.fullmatch(
        r"similarity index (?:100|[0-9]{1,2})%", records[0]
    ) is None:
        return None
    if records[1].startswith("rename from ") and records[2].startswith("rename to "):
        source_raw = records[1][len("rename from "):]
        target_raw = records[2][len("rename to "):]
    elif records[1].startswith("copy from ") and records[2].startswith("copy to "):
        source_raw = records[1][len("copy from "):]
        target_raw = records[2][len("copy to "):]
    else:
        return None
    source = _unified_diff.decode_git_path(source_raw)
    target = _unified_diff.decode_git_path(target_raw)
    if source is INVALID_MARKER or target is INVALID_MARKER:
        return None
    return source, target


def _binary_summary_matches(
    raw: str,
    old_path: str | None,
    new_path: str | None,
) -> bool:
    """Bind decoded operands from a canonical Git binary-summary record."""
    prefix, suffix = "Binary files ", " differ"
    if (
        len(raw) > MAX_DIFF_RECORD_CHARS
        or not raw.startswith(prefix)
        or not raw.endswith(suffix)
    ):
        return False
    fields = raw[len(prefix):-len(suffix)]
    separator_positions = _unified_diff.separator_positions_outside_quotes(
        fields, (" and ",), max_separators=MAX_PATH_SEPARATORS
    )
    if separator_positions is None:
        return False
    matches = 0
    for separator in separator_positions:
        old_raw = fields[:separator]
        new_raw = fields[separator + len(" and "):]
        old_operand = _unified_diff.decode_git_path(old_raw)
        new_operand = _unified_diff.decode_git_path(new_raw)
        if old_operand is INVALID_MARKER or new_operand is INVALID_MARKER:
            continue
        old_operand = None if old_operand == "/dev/null" else old_operand
        new_operand = None if new_operand == "/dev/null" else new_operand
        expected_old = None if old_path is None else f"a/{old_path}"
        expected_new = None if new_path is None else f"b/{new_path}"
        if old_operand == expected_old and new_operand == expected_new:
            matches += 1
    return matches == 1


def _binary_summary_null_hints(raw: str) -> tuple[str | None, str | None] | None:
    """Return the non-null path from a canonical new/deleted binary summary."""
    prefix, suffix = "Binary files ", " differ"
    if (
        len(raw) > MAX_DIFF_RECORD_CHARS
        or not raw.startswith(prefix)
        or not raw.endswith(suffix)
    ):
        return None
    fields = raw[len(prefix):-len(suffix)]
    if fields.startswith("/dev/null and "):
        new_operand = _unified_diff.decode_git_path(fields[len("/dev/null and "):])
        if new_operand is not INVALID_MARKER and new_operand.startswith("b/"):
            return None, new_operand[2:]
    if fields.endswith(" and /dev/null"):
        old_operand = _unified_diff.decode_git_path(fields[:-len(" and /dev/null")])
        if old_operand is not INVALID_MARKER and old_operand.startswith("a/"):
            return old_operand[2:], None
    return None


def _hunk_range(raw: str) -> tuple[int, int, int, int] | None:
    """Return old/new starts and counts for a syntactically valid hunk header."""
    return _unified_diff.hunk_range(raw)


def _delta_program_complete(program: bytes) -> bool:
    """Validate Git delta varints and the exact instruction/output grammar."""
    def read_varint(cursor: int) -> tuple[int, int] | None:
        value = 0
        shift = 0
        while cursor < len(program) and shift <= 63:
            byte = program[cursor]
            cursor += 1
            value |= (byte & 0x7f) << shift
            if not byte & 0x80:
                return value, cursor
            shift += 7
        return None

    source_field = read_varint(0)
    if source_field is None:
        return False
    source_size, cursor = source_field
    result_field = read_varint(cursor)
    if result_field is None:
        return False
    result_size, cursor = result_field
    if source_size > MAX_BINARY_BLOCK_BYTES or result_size > MAX_BINARY_BLOCK_BYTES:
        return False
    output_size = 0
    while cursor < len(program):
        opcode = program[cursor]
        cursor += 1
        if opcode == 0:
            return False
        if opcode & 0x80:
            copy_offset = 0
            copy_size = 0
            for bit, shift in zip((0x01, 0x02, 0x04, 0x08), (0, 8, 16, 24)):
                if opcode & bit:
                    if cursor >= len(program):
                        return False
                    copy_offset |= program[cursor] << shift
                    cursor += 1
            for bit, shift in zip((0x10, 0x20, 0x40), (0, 8, 16)):
                if opcode & bit:
                    if cursor >= len(program):
                        return False
                    copy_size |= program[cursor] << shift
                    cursor += 1
            if copy_size == 0:
                copy_size = 0x10000
            if copy_offset + copy_size > source_size:
                return False
            output_size += copy_size
        else:
            insert_size = opcode & 0x7f
            if cursor + insert_size > len(program):
                return False
            cursor += insert_size
            output_size += insert_size
        if output_size > result_size:
            return False
    return output_size == result_size


VALID_FILE_MODE = r"(?:100644|100755|120000|160000)"
MODE_PAIR = re.compile(r"old mode (100644|100755)\nnew mode (100644|100755)")
ABBREVIATED_INDEX_PARTS = re.compile(
    rf"index ([0-9a-f]+)\.\.([0-9a-f]+)(?: ({VALID_FILE_MODE}))?"
)
FULL_INDEX_PARTS = re.compile(
    rf"index ([0-9a-f]{{40}})\.\.([0-9a-f]{{40}})(?: ({VALID_FILE_MODE}))?"
    rf"|index ([0-9a-f]{{64}})\.\.([0-9a-f]{{64}})(?: ({VALID_FILE_MODE}))?"
)


def _mode_pair_matches(records: list[str]) -> bool:
    """Accept only Git's executable-bit transition for one retained path."""
    if len(records) != 2:
        return False
    match = MODE_PAIR.fullmatch("\n".join(records))
    return match is not None and match.group(1) != match.group(2)


def _change_prefix_move(
    records: list[str], *, require_full_index: bool
) -> tuple[str, str] | None | object:
    """Validate optional mode/move metadata followed by one bound index."""
    if not records:
        return INVALID_MARKER
    index_pattern = FULL_INDEX_PARTS if require_full_index else ABBREVIATED_INDEX_PARTS
    index_match = index_pattern.fullmatch(records[-1])
    if index_match is None:
        return INVALID_MARKER
    if require_full_index:
        old_oid = index_match.group(1) or index_match.group(4)
        new_oid = index_match.group(2) or index_match.group(5)
        index_mode = index_match.group(3) or index_match.group(6)
    else:
        old_oid, new_oid, index_mode = index_match.groups()
    headers = records[:-1]
    consumed_mode_pair = False
    if len(headers) >= 2 and _mode_pair_matches(headers[:2]):
        consumed_mode_pair = True
        headers = headers[2:]
    elif headers and headers[0].startswith("old mode "):
        return INVALID_MARKER
    if consumed_mode_pair and index_mode is not None:
        return INVALID_MARKER
    if set(old_oid) == {"0"} or set(new_oid) == {"0"}:
        return INVALID_MARKER
    if not headers:
        return None
    move = _move_metadata_paths(headers)
    return move if move is not None else INVALID_MARKER


def _binary_file_kind_prefix_matches(prefix: list[str]) -> bool:
    """Bind a full zero OID to its canonical new/deleted file-mode record."""
    if len(prefix) != 2:
        return False
    kind_match = re.fullmatch(
        rf"(new file mode|deleted file mode) {VALID_FILE_MODE}", prefix[0]
    )
    index_match = FULL_INDEX_PARTS.fullmatch(prefix[1])
    if kind_match is None or index_match is None:
        return False
    old_oid = index_match.group(1) or index_match.group(4)
    new_oid = index_match.group(2) or index_match.group(5)
    index_mode = index_match.group(3) or index_match.group(6)
    old_zero = set(old_oid) == {"0"}
    new_zero = set(new_oid) == {"0"}
    return index_mode is None and (
        (kind_match.group(1) == "new file mode" and old_zero and not new_zero)
        or (kind_match.group(1) == "deleted file mode" and not old_zero and new_zero)
    )


def _git_binary_patch_complete(body: list[str], binary_index: int) -> bool:
    """Validate canonical one-or-more git binary size/payload blocks."""
    prefix = body[:binary_index]
    change_prefix = _change_prefix_move(prefix, require_full_index=True)
    prefix_ok = (
        change_prefix is not INVALID_MARKER
        or _binary_file_kind_prefix_matches(prefix)
    )
    if not prefix_ok:
        return False
    cursor = binary_index + 1
    blocks = 0
    while cursor < len(body):
        size_match = re.fullmatch(r"(literal|delta) (\d+)", body[cursor])
        if size_match is None or len(size_match.group(2)) > 12:
            return False
        kind, declared_size = size_match.group(1), int(size_match.group(2))
        if declared_size > MAX_BINARY_BLOCK_BYTES:
            return False
        cursor += 1
        compressed = bytearray()
        while cursor < len(body) and body[cursor] != "":
            raw = body[cursor]
            if not raw:
                return False
            length_code = raw[0]
            if "A" <= length_code <= "Z":
                decoded_length = ord(length_code) - ord("A") + 1
            elif "a" <= length_code <= "z":
                decoded_length = ord(length_code) - ord("a") + 27
            else:
                return False
            encoded = raw[1:]
            if len(encoded) != ((decoded_length + 3) // 4) * 5:
                return False
            decoded = bytearray()
            try:
                for group_start in range(0, len(encoded), 5):
                    value = 0
                    for character in encoded[group_start : group_start + 5]:
                        value = value * 85 + GIT_BASE85_VALUES[character]
                    decoded.extend(value.to_bytes(4, "big"))
            except (KeyError, OverflowError):
                return False
            compressed.extend(decoded[:decoded_length])
            cursor += 1
        if not compressed:
            return False
        try:
            inflater = zlib.decompressobj()
            inflated = inflater.decompress(bytes(compressed), MAX_BINARY_BLOCK_BYTES + 1)
            if len(inflated) <= MAX_BINARY_BLOCK_BYTES:
                inflated += inflater.flush(MAX_BINARY_BLOCK_BYTES + 1 - len(inflated))
        except zlib.error:
            return False
        if (
            len(inflated) > MAX_BINARY_BLOCK_BYTES
            or not inflater.eof
            or inflater.unused_data
            or inflater.unconsumed_tail
        ):
            return False
        if len(inflated) != declared_size:
            return False
        if kind == "delta" and not _delta_program_complete(inflated):
            return False
        blocks += 1
        if cursor == len(body):
            break
        cursor += 1  # exactly one blank separator or trailing terminator
        if cursor == len(body):
            break
        if body[cursor] == "":
            return False
    return blocks == 2


INDEX_METADATA = re.compile(
    rf"index ([0-9a-f]+)\.\.([0-9a-f]+)(?: ({VALID_FILE_MODE}))?"
)


def _content_metadata_kind(
    metadata: list[str], old_path: str, new_path: str
) -> tuple[str, str, str] | None:
    """Validate extended headers and return kind plus bound old/new hashes."""
    if not metadata:
        return "regular", "unknown", "unknown"
    index_match = INDEX_METADATA.fullmatch(metadata[-1])
    if index_match is None:
        return None
    old_hash, new_hash = index_match.group(1), index_match.group(2)
    headers = metadata[:-1]
    if not headers:
        kind = "regular"
    elif len(headers) == 1 and re.fullmatch(
        rf"new file mode {VALID_FILE_MODE}", headers[0]
    ):
        kind = "new"
    elif len(headers) == 1 and re.fullmatch(
        rf"deleted file mode {VALID_FILE_MODE}", headers[0]
    ):
        kind = "deleted"
    else:
        consumed_mode_pair = False
        if len(headers) >= 2 and _mode_pair_matches(headers[:2]):
            consumed_mode_pair = True
            headers = headers[2:]
        elif headers and headers[0].startswith("old mode "):
            return None
        if consumed_mode_pair and index_match.group(3) is not None:
            return None
        move_paths = _move_metadata_paths(headers) if headers else None
        has_dissimilarity = (
            len(headers) == 1
            and re.fullmatch(
                r"dissimilarity index (?:100|[0-9]{1,2})%", headers[0]
            ) is not None
        )
        if headers and move_paths is None and not has_dissimilarity:
            return None
        if move_paths is not None:
            source, target = move_paths
            if source != old_path or target != new_path:
                return None
        kind = "regular"
    old_zero = set(old_hash) == {"0"}
    new_zero = set(new_hash) == {"0"}
    if (
        (kind == "new" and (not old_zero or new_zero))
        or (kind == "deleted" and (old_zero or not new_zero))
        or (kind == "regular" and (old_zero or new_zero))
    ):
        return None
    return kind, old_hash, new_hash


def _combined_sections_complete(lines: list[str]) -> bool:
    """Reject truncated `diff --git` sections while allowing known metadata-only forms."""
    starts = [index for index, raw in enumerate(lines) if raw.startswith("diff --git ")]
    for offset, start in enumerate(starts):
        end = starts[offset + 1] if offset + 1 < len(starts) else len(lines)
        body = lines[start + 1 : end]
        if not body:
            return False
        hunk_indexes = [index for index, raw in enumerate(body) if _hunk_range(raw) is not None]
        marker_indexes = [
            index
            for index, raw in enumerate(body[:-1])
            if raw.startswith("--- ") and body[index + 1].startswith("+++ ")
        ]
        old_hint: str | None = None
        new_hint: str | None = None
        if len(marker_indexes) == 1:
            old_operand = _marker_operand(body[marker_indexes[0]])
            new_operand = _marker_operand(body[marker_indexes[0] + 1])
            old_marker = _marker_path(body[marker_indexes[0]])
            new_marker = _marker_path(body[marker_indexes[0] + 1])
            if (
                old_operand is INVALID_MARKER
                or new_operand is INVALID_MARKER
                or old_marker is INVALID_MARKER
                or new_marker is INVALID_MARKER
                or (old_marker is not None and not old_operand.startswith("a/"))
                or (new_marker is not None and not new_operand.startswith("b/"))
            ):
                return False
            old_hint, new_hint = old_marker, new_marker
        else:
            moves = [
                move
                for index in range(len(body) - 2)
                if (move := _move_metadata_paths(body[index:index + 3])) is not None
            ]
            if len(moves) == 1:
                old_hint, new_hint = moves[0]
        binary_summary = next(
            (record for record in body if record.startswith("Binary files ")),
            None,
        )
        null_hints = (
            _binary_summary_null_hints(binary_summary)
            if binary_summary is not None
            else None
        )
        if null_hints is not None:
            old_hint, new_hint = null_hints
        diff_paths = _diff_paths(
            lines[start],
            old_hint=old_hint,
            new_hint=new_hint,
            binary_summary=binary_summary if null_hints is None else None,
        )
        if diff_paths is None:
            return False
        old_diff, new_diff = diff_paths
        if hunk_indexes:
            if len(marker_indexes) == 1 and marker_indexes[0] < hunk_indexes[0]:
                before_markers = body[: marker_indexes[0]]
                between_markers_and_hunk = body[marker_indexes[0] + 2 : hunk_indexes[0]]
                metadata = _content_metadata_kind(before_markers, old_diff, new_diff)
                if metadata is None:
                    return False
                if between_markers_and_hunk:
                    return False
                kind = metadata[0]
                ranges = [_hunk_range(body[index]) for index in hunk_indexes]
                markers_valid = (
                    (kind == "new" and old_marker is None and new_marker == new_diff)
                    or (kind == "deleted" and old_marker == old_diff and new_marker is None)
                    or (
                        kind == "regular"
                        and old_marker == old_diff
                        and new_marker == new_diff
                    )
                )
                hunks_valid = all(
                    item is not None
                    and (kind != "new" or item[1] == 0)
                    and (kind != "deleted" or item[3] == 0)
                    for item in ranges
                )
                if markers_valid and hunks_valid:
                    continue
            return False
        summary_move = (
            _change_prefix_move(body[:-1], require_full_index=False)
            if body and body[-1].startswith("Binary files ")
            else INVALID_MARKER
        )
        if (
            len(body) == 1
            and _binary_summary_matches(body[0], old_diff, new_diff)
        ) or (
            summary_move is not INVALID_MARKER
            and (summary_move is None or summary_move == (old_diff, new_diff))
            and _binary_summary_matches(body[-1], old_diff, new_diff)
        ) or (
            len(body) == 3
            and re.fullmatch(rf"new file mode {VALID_FILE_MODE}", body[0]) is not None
            and re.fullmatch(r"index 0+\.\.[0-9a-f]+", body[1]) is not None
            and _binary_summary_matches(body[2], None, new_diff)
        ) or (
            len(body) == 3
            and re.fullmatch(rf"deleted file mode {VALID_FILE_MODE}", body[0]) is not None
            and re.fullmatch(r"index [0-9a-f]+\.\.0+", body[1]) is not None
            and _binary_summary_matches(body[2], old_diff, None)
        ) or (
            len(body) == 4
            and _mode_pair_matches(body[:2])
            and re.fullmatch(r"index [0-9a-f]+\.\.[0-9a-f]+", body[2]) is not None
            and _binary_summary_matches(body[3], old_diff, new_diff)
        ):
            continue
        if "GIT binary patch" in body:
            binary_index = body.index("GIT binary patch")
            if _git_binary_patch_complete(body, binary_index):
                continue
            return False
        has_mode_pair = _mode_pair_matches(body)
        move_records = body[2:] if len(body) == 5 and _mode_pair_matches(body[:2]) else body
        move_paths = _move_metadata_paths(move_records)
        has_move = move_paths == (old_diff, new_diff)
        empty_blob = r"e69de29[0-9a-f]*"
        zero_blob = r"0+"
        has_new_empty_file = (
            len(body) == 2
            and re.fullmatch(rf"new file mode {VALID_FILE_MODE}", body[0]) is not None
            and re.fullmatch(rf"index {zero_blob}\.\.{empty_blob}", body[1]) is not None
        )
        has_deleted_empty_file = (
            len(body) == 2
            and re.fullmatch(rf"deleted file mode {VALID_FILE_MODE}", body[0]) is not None
            and re.fullmatch(rf"index {empty_blob}\.\.{zero_blob}", body[1]) is not None
        )
        if has_mode_pair or has_move or has_new_empty_file or has_deleted_empty_file:
            continue
        return False
    return True


def _sectioned_sections_complete(lines: list[str]) -> bool:
    """Require every concatenated ---/+++ file section to contain a valid hunk."""
    starts = [
        index
        for index, raw in enumerate(lines[:-1])
        if raw.startswith("--- ") and lines[index + 1].startswith("+++ ")
    ]
    if not starts:
        return False
    for offset, start in enumerate(starts):
        end = starts[offset + 1] if offset + 1 < len(starts) else len(lines)
        section_body = lines[start + 2 : end]
        old_operand = _marker_operand(lines[start])
        new_operand = _marker_operand(lines[start + 1])
        old_marker = _marker_path(lines[start])
        new_marker = _marker_path(lines[start + 1])
        if (
            old_operand is INVALID_MARKER
            or new_operand is INVALID_MARKER
            or old_marker is INVALID_MARKER
            or new_marker is INVALID_MARKER
            or (old_marker is None and new_marker is None)
            or (old_marker is not None and not old_operand.startswith("a/"))
            or (new_marker is not None and not new_operand.startswith("b/"))
        ):
            return False
        hunk_indexes = [
            index for index, raw in enumerate(section_body) if _hunk_range(raw) is not None
        ]
        if not hunk_indexes or hunk_indexes[0] != 0:
            return False
        for hunk_index in hunk_indexes:
            hunk_range = _hunk_range(section_body[hunk_index])
            if hunk_range is None:
                return False
            if (old_marker is None and hunk_range[1] != 0) or (
                new_marker is None and hunk_range[3] != 0
            ):
                return False
    return True


def validate_github_anchor(
    diff_text: str,
    *,
    path: str,
    line: int,
    source_kind: Literal["added", "context", "removed"],
    head_sha: str,
) -> dict[str, object]:
    """Return a RIGHT anchor only for a caller-identified added line in the matching file."""
    if not head_sha or line < 1:
        return {"unanchorable": True, "reason": "missing_head_sha_or_invalid_line"}
    if source_kind != "added":
        return {"unanchorable": True, "reason": "source_line_is_not_added"}

    lines = diff_text.splitlines()
    has_diff_headers = any(raw.startswith("diff --git ") for raw in lines)
    first_patch_token: Literal["markers", "hunk"] | None = None
    if not has_diff_headers:
        for index, raw in enumerate(lines):
            if raw.startswith("--- ") and index + 1 < len(lines) and lines[index + 1].startswith("+++ "):
                first_patch_token = "markers"
                break
            if raw.startswith("@@"):
                first_patch_token = "hunk"
                break

    parser_mode: Literal["combined", "sectioned", "headerless"]
    if has_diff_headers:
        parser_mode = "combined"
    elif first_patch_token == "markers":
        parser_mode = "sectioned"
    else:
        parser_mode = "headerless"

    parser_state: Literal["outside", "file_header", "file_body", "hunk"] = "outside"
    current_path: str | None = path if parser_mode == "headerless" else None
    new_line: int | None = None
    old_remaining = 0
    new_remaining = 0
    wanted_in_file = parser_mode == "headerless"
    found_anchor = False
    ambiguous_headerless_input = False
    malformed_hunk = (
        (parser_mode == "combined" and not _combined_sections_complete(lines))
        or (parser_mode == "sectioned" and not _sectioned_sections_complete(lines))
        or (parser_mode == "headerless" and (not lines or not lines[0].startswith("@@")))
    )
    previous_hunk_record: Literal["added", "removed", "context"] | None = None
    old_side_eof = False
    new_side_eof = False
    last_old_end: int | None = None
    last_new_end: int | None = None
    hunk_has_change = False

    index = 0
    while index < len(lines):
        raw = lines[index]
        hunk_complete = parser_state == "hunk" and old_remaining == 0 and new_remaining == 0

        if raw.startswith("diff --git "):
            if parser_state == "hunk" and not hunk_complete:
                malformed_hunk = True
            if parser_state == "hunk" and not hunk_has_change:
                malformed_hunk = True
            parser_state = "file_header"
            current_path = None
            new_line = None
            old_remaining = 0
            new_remaining = 0
            previous_hunk_record = None
            old_side_eof = False
            new_side_eof = False
            last_old_end = None
            last_new_end = None
            hunk_has_change = False
            wanted_in_file = False
            index += 1
            continue

        marker_pair = (
            raw.startswith("--- ")
            and index + 1 < len(lines)
            and lines[index + 1].startswith("+++ ")
        )
        if marker_pair:
            # A ---/+++ pair is indistinguishable from marker-shaped hunk
            # content when a capture is truncated at a file boundary. Treat
            # that ambiguity as malformed instead of consuming the pair as
            # deletion/addition records for the preceding file.
            if parser_state == "hunk" and not hunk_complete:
                malformed_hunk = True
            if parser_state == "hunk" and not hunk_has_change:
                malformed_hunk = True
            if parser_mode == "headerless":
                ambiguous_headerless_input = True
            current_path = _marker_path(lines[index + 1])
            if current_path is INVALID_MARKER or _marker_path(raw) is INVALID_MARKER:
                malformed_hunk = True
                current_path = None
            wanted_in_file = current_path == path
            parser_state = "file_body"
            new_line = None
            old_remaining = 0
            new_remaining = 0
            previous_hunk_record = None
            old_side_eof = False
            new_side_eof = False
            last_old_end = None
            last_new_end = None
            hunk_has_change = False
            index += 2
            continue

        if raw.startswith("@@"):
            if parser_state == "hunk" and not hunk_complete:
                malformed_hunk = True
            if parser_state == "hunk" and not hunk_has_change:
                malformed_hunk = True
            hunk_range = _hunk_range(raw)
            if not hunk_range:
                malformed_hunk = True
                parser_state = "outside"
                new_line = None
                wanted_in_file = False
                index += 1
                continue
            parser_state = "hunk"
            old_start, old_remaining, hunk_start, new_remaining = hunk_range
            if old_side_eof or new_side_eof:
                malformed_hunk = True
            if (
                (last_old_end is not None and old_start < last_old_end)
                or (last_new_end is not None and hunk_start < last_new_end)
            ):
                malformed_hunk = True
            if last_old_end is not None and last_new_end is not None:
                old_gap = old_start - last_old_end
                new_gap = hunk_start - last_new_end
                if old_gap != new_gap:
                    malformed_hunk = True
            else:
                old_prefix = old_start if old_remaining == 0 else old_start - 1
                new_prefix = hunk_start if new_remaining == 0 else hunk_start - 1
                if old_prefix != new_prefix:
                    malformed_hunk = True
            last_old_end = old_start + old_remaining
            last_new_end = hunk_start + new_remaining
            new_line = hunk_start if wanted_in_file else None
            previous_hunk_record = None
            hunk_has_change = False
            index += 1
            continue

        if parser_state != "hunk":
            if raw.startswith(("--- ", "+++ ")):
                current_path = None
                wanted_in_file = False
                parser_state = "file_header"
            index += 1
            continue

        if raw == r"\ No newline at end of file":
            marker_is_valid = (
                (previous_hunk_record == "added" and new_remaining == 0)
                or (previous_hunk_record == "removed" and old_remaining == 0)
                or (
                    previous_hunk_record == "context"
                    and old_remaining == 0
                    and new_remaining == 0
                )
            )
            if not marker_is_valid:
                malformed_hunk = True
            elif previous_hunk_record == "added":
                new_side_eof = True
            elif previous_hunk_record == "removed":
                old_side_eof = True
            else:
                old_side_eof = True
                new_side_eof = True
            previous_hunk_record = None
            index += 1
            continue
        if hunk_complete:
            # Once the declared body is exhausted, only a recognized next
            # hunk/file boundary or the no-newline marker is legal.
            malformed_hunk = True
            parser_state = "file_body"
            index += 1
            continue
        if raw.startswith("-"):
            if previous_hunk_record == "added":
                malformed_hunk = True
            if old_remaining <= 0:
                malformed_hunk = True
            else:
                old_remaining -= 1
            previous_hunk_record = "removed"
            hunk_has_change = True
            index += 1
            continue
        if raw.startswith("+"):
            if new_remaining <= 0:
                malformed_hunk = True
            else:
                if wanted_in_file and new_line == line:
                    found_anchor = True
                if new_line is not None:
                    new_line += 1
                new_remaining -= 1
            previous_hunk_record = "added"
            hunk_has_change = True
            index += 1
            continue
        if raw.startswith(" "):
            if old_remaining <= 0 or new_remaining <= 0:
                malformed_hunk = True
            else:
                old_remaining -= 1
                if new_line is not None:
                    new_line += 1
                new_remaining -= 1
            previous_hunk_record = "context"
            index += 1
            continue
        malformed_hunk = True
        previous_hunk_record = None
        index += 1

    if parser_state == "hunk" and (old_remaining != 0 or new_remaining != 0):
        malformed_hunk = True
    if parser_state == "hunk" and not hunk_has_change:
        malformed_hunk = True

    if found_anchor and not ambiguous_headerless_input and not malformed_hunk:
        return {"commit_id": head_sha, "path": path, "line": line, "side": "RIGHT"}

    return {"unanchorable": True, "reason": "added_line_not_in_current_diff"}


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a GitHub RIGHT-side inline-comment anchor against a unified diff."
    )
    diff_input = parser.add_mutually_exclusive_group(required=True)
    diff_input.add_argument("--diff-file", type=Path, help="read the unified diff from this file")
    diff_input.add_argument(
        "--diff-stdin",
        action="store_true",
        help="read the unified diff from standard input",
    )
    parser.add_argument("--path", required=True, help="repository-relative target path")
    parser.add_argument("--line", required=True, type=int, help="new-file line number")
    parser.add_argument(
        "--source-kind",
        required=True,
        choices=("added", "context", "removed"),
        help="diff source kind assigned by the review workflow",
    )
    parser.add_argument("--head-sha", required=True, help="current pull-request head SHA")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    if args.diff_stdin:
        diff_text = sys.stdin.read()
    else:
        try:
            diff_text = args.diff_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(
                json.dumps({"error": "diff_input_unavailable", "detail": str(exc)}),
                file=sys.stderr,
            )
            return 1

    result = validate_github_anchor(
        diff_text,
        path=args.path,
        line=args.line,
        source_kind=args.source_kind,
        head_sha=args.head_sha,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
