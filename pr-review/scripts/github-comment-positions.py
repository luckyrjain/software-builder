#!/usr/bin/env python3
"""Validate GitHub inline-review anchors against a unified diff."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Literal
import zlib

INVALID_MARKER = object()
GIT_BASE85_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~"
GIT_BASE85_VALUES = {character: index for index, character in enumerate(GIT_BASE85_ALPHABET)}
MAX_BINARY_BLOCK_BYTES = 8 * 1024 * 1024

HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)


def _decode_git_path(raw: str) -> str | object:
    """Decode one Git path field, including C-quoted octal UTF-8 bytes."""
    if not raw.startswith('"'):
        return raw
    if len(raw) < 2 or not raw.endswith('"'):
        return INVALID_MARKER
    decoded = bytearray()
    cursor = 1
    escapes = {
        "a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13,
        '"': 34, "\\": 92,
    }
    while cursor < len(raw) - 1:
        character = raw[cursor]
        if character != "\\":
            decoded.extend(character.encode("utf-8"))
            cursor += 1
            continue
        cursor += 1
        if cursor >= len(raw) - 1:
            return INVALID_MARKER
        escaped = raw[cursor]
        if escaped in escapes:
            decoded.append(escapes[escaped])
            cursor += 1
            continue
        if escaped not in "01234567":
            return INVALID_MARKER
        end = cursor
        while end < min(cursor + 3, len(raw) - 1) and raw[end] in "01234567":
            end += 1
        value = int(raw[cursor:end], 8)
        if value > 255:
            return INVALID_MARKER
        decoded.append(value)
        cursor = end
    try:
        return decoded.decode("utf-8")
    except UnicodeDecodeError:
        return INVALID_MARKER


def _quoted_field_end(raw: str) -> int | None:
    escaped = False
    for index in range(1, len(raw)):
        if raw[index] == '"' and not escaped:
            return index + 1
        if raw[index] == "\\" and not escaped:
            escaped = True
        else:
            escaped = False
    return None


def _diff_paths(raw: str) -> tuple[str, str] | None:
    """Parse the two path fields from a canonical ``diff --git`` header."""
    prefix = "diff --git "
    if not raw.startswith(prefix):
        return None
    fields = raw[len(prefix):]
    if fields.startswith('"'):
        end = _quoted_field_end(fields)
        if end is None or end >= len(fields) or fields[end] != " ":
            return None
        old_raw, new_raw = fields[:end], fields[end + 1:]
    else:
        # Git does not quote spaces, so the (possibly quoted) b/ prefix is the
        # structural split. Each side is quoted independently.
        separator = max(fields.rfind(" b/"), fields.rfind(' "b/'))
        if separator < 0:
            return None
        old_raw, new_raw = fields[:separator], fields[separator + 1:]
    old_path, new_path = _decode_git_path(old_raw), _decode_git_path(new_raw)
    if old_path is INVALID_MARKER or new_path is INVALID_MARKER:
        return None
    if not old_path.startswith("a/") or not new_path.startswith("b/"):
        return None
    return old_path[2:], new_path[2:]


def _marker_path(raw: str) -> str | None | object:
    """Parse a ---/+++ marker path, including quoted paths and /dev/null."""
    field = raw[4:]
    if not field:
        return INVALID_MARKER
    if field.startswith('"'):
        end = _quoted_field_end(field)
        if end is None or (field[end:] and not field[end:].startswith("\t")):
            return INVALID_MARKER
        field = field[:end]
    else:
        field = field.split("\t", 1)[0]
    marker_path = _decode_git_path(field)
    if marker_path is INVALID_MARKER:
        return INVALID_MARKER
    if marker_path == "/dev/null":
        return None
    return marker_path[2:] if marker_path.startswith(("a/", "b/")) else marker_path


def _hunk_range(raw: str) -> tuple[int, int, int, int] | None:
    """Return old/new starts and counts for a syntactically valid hunk header."""
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


def _git_binary_patch_complete(body: list[str], binary_index: int) -> bool:
    """Validate canonical one-or-more git binary size/payload blocks."""
    prefix = body[:binary_index]
    index_pattern = r"index [0-9a-f]+\.\.[0-9a-f]+(?: [0-7]{6})?"
    prefix_ok = (
        len(prefix) == 1 and re.fullmatch(index_pattern, prefix[0]) is not None
    ) or (
        len(prefix) == 2
        and re.fullmatch(r"(?:new file mode|deleted file mode) [0-7]{6}", prefix[0])
        is not None
        and re.fullmatch(index_pattern, prefix[1]) is not None
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


VALID_FILE_MODE = r"(?:100644|100755|120000|160000)"
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
    elif (
        len(headers) == 2
        and re.fullmatch(rf"old mode {VALID_FILE_MODE}", headers[0])
        and re.fullmatch(rf"new mode {VALID_FILE_MODE}", headers[1])
    ):
        kind = "regular"
    elif len(headers) == 3 and re.fullmatch(
        r"similarity index (?:100|[0-9]{1,2})%", headers[0]
    ):
        if headers[1].startswith("rename from ") and headers[2].startswith("rename to "):
            source = _decode_git_path(headers[1][len("rename from "):])
            target = _decode_git_path(headers[2][len("rename to "):])
        elif headers[1].startswith("copy from ") and headers[2].startswith("copy to "):
            source = _decode_git_path(headers[1][len("copy from "):])
            target = _decode_git_path(headers[2][len("copy to "):])
        else:
            return None
        if source != old_path or target != new_path:
            return None
        kind = "regular"
    else:
        return None
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
        diff_paths = _diff_paths(lines[start])
        if diff_paths is None:
            return False
        old_diff, new_diff = diff_paths
        old_diff_raw, new_diff_raw = f"a/{old_diff}", f"b/{new_diff}"
        hunk_indexes = [index for index, raw in enumerate(body) if _hunk_range(raw) is not None]
        marker_indexes = [
            index
            for index, raw in enumerate(body[:-1])
            if raw.startswith("--- ") and body[index + 1].startswith("+++ ")
        ]
        if hunk_indexes:
            if len(marker_indexes) == 1 and marker_indexes[0] < hunk_indexes[0]:
                before_markers = body[: marker_indexes[0]]
                between_markers_and_hunk = body[marker_indexes[0] + 2 : hunk_indexes[0]]
                metadata = _content_metadata_kind(before_markers, old_diff, new_diff)
                if metadata is None:
                    return False
                if between_markers_and_hunk:
                    return False
                old_marker = _marker_path(body[marker_indexes[0]])
                new_marker = _marker_path(body[marker_indexes[0] + 1])
                if old_marker is INVALID_MARKER or new_marker is INVALID_MARKER:
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
        binary_summary = f"Binary files {old_diff_raw} and {new_diff_raw} differ"
        added_binary_summary = f"Binary files /dev/null and {new_diff_raw} differ"
        deleted_binary_summary = f"Binary files {old_diff_raw} and /dev/null differ"
        if body == [binary_summary] or (
            len(body) == 2
            and re.fullmatch(r"index [0-9a-f]+\.\.[0-9a-f]+(?: [0-7]{6})?", body[0])
            is not None
            and body[1] == binary_summary
        ) or (
            len(body) == 3
            and re.fullmatch(r"new file mode [0-7]{6}", body[0]) is not None
            and re.fullmatch(r"index 0+\.\.[0-9a-f]+", body[1]) is not None
            and body[2] == added_binary_summary
        ) or (
            len(body) == 3
            and re.fullmatch(r"deleted file mode [0-7]{6}", body[0]) is not None
            and re.fullmatch(r"index [0-9a-f]+\.\.0+", body[1]) is not None
            and body[2] == deleted_binary_summary
        ):
            continue
        if "GIT binary patch" in body:
            binary_index = body.index("GIT binary patch")
            if _git_binary_patch_complete(body, binary_index):
                continue
            return False
        has_mode_pair = (
            len(body) == 2
            and re.fullmatch(r"old mode [0-7]{6}", body[0]) is not None
            and re.fullmatch(r"new mode [0-7]{6}", body[1]) is not None
        )
        similarity = r"similarity index (?:100|[0-9]{1,2})%"
        has_rename = (
            len(body) == 3
            and re.fullmatch(similarity, body[0]) is not None
            and body[1].startswith("rename from ")
            and body[1][len("rename from ") :] == old_diff
            and body[2].startswith("rename to ")
            and body[2][len("rename to ") :] == new_diff
        )
        has_copy = (
            len(body) == 3
            and re.fullmatch(similarity, body[0]) is not None
            and body[1].startswith("copy from ")
            and body[1][len("copy from ") :] == old_diff
            and body[2].startswith("copy to ")
            and body[2][len("copy to ") :] == new_diff
        )
        empty_blob = r"e69de29[0-9a-f]*"
        zero_blob = r"0+"
        has_new_empty_file = (
            len(body) == 2
            and re.fullmatch(r"new file mode [0-7]{6}", body[0]) is not None
            and re.fullmatch(rf"index {zero_blob}\.\.{empty_blob}", body[1]) is not None
        )
        has_deleted_empty_file = (
            len(body) == 2
            and re.fullmatch(r"deleted file mode [0-7]{6}", body[0]) is not None
            and re.fullmatch(rf"index {empty_blob}\.\.{zero_blob}", body[1]) is not None
        )
        if has_mode_pair or has_rename or has_copy or has_new_empty_file or has_deleted_empty_file:
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
        hunk_indexes = [
            index for index, raw in enumerate(section_body) if _hunk_range(raw) is not None
        ]
        if not hunk_indexes or hunk_indexes[0] != 0:
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
