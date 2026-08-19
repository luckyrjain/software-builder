#!/usr/bin/env python3
"""Portable runtime validation for shared review identity/evidence contracts."""
from __future__ import annotations

import json
import math
import re
from pathlib import PurePosixPath

_SHA_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_FP_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_MAX_NESTING_DEPTH = 32
_REQUIRED_IDENTITY = {
    "schema_version", "base_sha", "head_sha", "merge_base_sha",
    "normalized_diff_fingerprint", "changed_paths", "generated_paths",
    "dependency_changes", "config_changes",
}
_REQUIRED_EVIDENCE = {
    "schema_version", "change_identity", "requirements_ref", "review_mode",
    "inspection_status", "inspected_surfaces", "unable_to_inspect", "findings",
    "generated_at",
}
_FINDING_BUCKETS = {"defect", "suggestion", "question"}
_UNABLE_FIELDS = {"surface", "reason", "mandatory"}
_FINDING_FIELDS = {"id", "category", "summary", "evidence"}
_EFFECTIVE_PATCH_FIELDS = (
    "changed_paths", "generated_paths", "dependency_changes", "config_changes",
)
_UNSET = object()


def _portable_scalar(value: object) -> bool:
    if value is None or type(value) in (str, bool, int):
        return True
    return type(value) is float and math.isfinite(value)


def _portable_value(value: object, *, depth: int = 0, seen: set[int] | None = None) -> bool:
    if depth > _MAX_NESTING_DEPTH:
        return False
    if not isinstance(value, (dict, list)):
        return _portable_scalar(value)
    active = set() if seen is None else seen
    marker = id(value)
    if marker in active:
        return False
    active.add(marker)
    try:
        if isinstance(value, dict):
            return all(
                isinstance(key, str) and _portable_value(item, depth=depth + 1, seen=active)
                for key, item in value.items()
            )
        return all(_portable_value(item, depth=depth + 1, seen=active) for item in value)
    finally:
        active.remove(marker)


def _canonical_json(value: object) -> str | None:
    if not _portable_value(value):
        return None
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError):
        return None


def _json_equivalent(left: object, right: object) -> bool:
    left_json = _canonical_json(left)
    right_json = _canonical_json(right)
    return left_json is not None and right_json is not None and left_json == right_json


def _same_hex(left: object, right: object) -> bool:
    return isinstance(left, str) and isinstance(right, str) and left.lower() == right.lower()


def _valid_repo_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and path != PurePosixPath(".")
        and ".." not in path.parts
        and str(path) == value
    )


def _canonical_mapping_value(value: object, *, depth: int = 0, seen: set[int] | None = None) -> bool:
    if depth > _MAX_NESTING_DEPTH:
        return False
    if not isinstance(value, (dict, list)):
        return _portable_scalar(value)
    active = set() if seen is None else seen
    marker = id(value)
    if marker in active:
        return False
    active.add(marker)
    try:
        if isinstance(value, dict):
            keys = list(value)
            return (
                all(isinstance(key, str) for key in keys)
                and keys == sorted(keys)
                and all(
                    _canonical_mapping_value(item, depth=depth + 1, seen=active)
                    for item in value.values()
                )
            )
        return all(
            _canonical_mapping_value(item, depth=depth + 1, seen=active)
            for item in value
        )
    finally:
        active.remove(marker)


def _effective_patch_unchanged(stored: object, current: object) -> bool:
    return (
        isinstance(stored, dict)
        and isinstance(current, dict)
        and _same_hex(
            stored.get("normalized_diff_fingerprint"),
            current.get("normalized_diff_fingerprint"),
        )
        and all(
            _json_equivalent(stored.get(field), current.get(field))
            for field in _EFFECTIVE_PATCH_FIELDS
        )
    )


def _identity_fresh(
    stored: object,
    current: object,
    *,
    conflict_resolution_occurred: bool,
) -> bool:
    if conflict_resolution_occurred or not _effective_patch_unchanged(stored, current):
        return False
    assert isinstance(stored, dict) and isinstance(current, dict)
    sha_fields = ("base_sha", "head_sha", "merge_base_sha")
    if all(_same_hex(stored.get(field), current.get(field)) for field in sha_fields):
        return True
    return (
        _same_hex(stored.get("base_sha"), stored.get("merge_base_sha"))
        and _same_hex(current.get("base_sha"), current.get("merge_base_sha"))
        and not _same_hex(stored.get("base_sha"), current.get("base_sha"))
    )


def validate_change_identity(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["change_identity must be an object"]
    errors: list[str] = []
    missing = sorted(_REQUIRED_IDENTITY - set(payload))
    if missing:
        errors.append(f"change_identity missing required fields: {', '.join(missing)}")
    unknown = sorted(repr(key) for key in payload if not isinstance(key, str) or key not in _REQUIRED_IDENTITY)
    if unknown:
        errors.append(f"change_identity contains unknown v1 fields: {', '.join(unknown)}")
    if "schema_version" in payload and type(payload.get("schema_version")) is not int:
        errors.append("change_identity schema_version must be integer 1")
    elif payload.get("schema_version") != 1:
        errors.append("change_identity schema_version must be integer 1")
    for field in ("base_sha", "head_sha", "merge_base_sha"):
        value = payload.get(field)
        if field in payload and (not isinstance(value, str) or not _SHA_RE.fullmatch(value)):
            errors.append(f"{field} must be a 40- or 64-character Git SHA")
    fingerprint = payload.get("normalized_diff_fingerprint")
    if "normalized_diff_fingerprint" in payload and (
        not isinstance(fingerprint, str) or not _FP_RE.fullmatch(fingerprint)
    ):
        errors.append("normalized_diff_fingerprint must be a 64-character SHA-256 hex value")
    for field in ("changed_paths", "generated_paths"):
        value = payload.get(field)
        if field in payload:
            if not isinstance(value, list) or not all(_valid_repo_path(item) for item in value):
                errors.append(f"{field} must be a list of canonical repository-relative POSIX paths")
            elif value != sorted(value) or len(value) != len(set(value)):
                errors.append(f"{field} must be sorted and contain no duplicates")
    changed = payload.get("changed_paths")
    generated = payload.get("generated_paths")
    if isinstance(changed, list) and isinstance(generated, list):
        if all(_valid_repo_path(item) for item in changed + generated) and not set(generated).issubset(changed):
            errors.append("generated_paths must be a subset of changed_paths")
    for field in ("dependency_changes", "config_changes"):
        value = payload.get(field)
        if field not in payload:
            continue
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            errors.append(f"{field} must be a list of objects")
            continue
        if not all(_canonical_mapping_value(item) for item in value):
            errors.append(
                f"{field} objects must use recursively sorted string keys, JSON-portable finite scalar values, and at most {_MAX_NESTING_DEPTH} nested levels"
            )
            continue
        canonical = [_canonical_json(item) for item in value]
        if canonical != sorted(canonical) or len(canonical) != len(set(canonical)):
            errors.append(f"{field} must use canonical object ordering and contain no duplicate objects")
    return errors


def validate_review_evidence(
    payload: object,
    *,
    current_identity: object | None = None,
    current_requirements_ref: object = _UNSET,
    conflict_resolution_occurred: bool = False,
) -> list[str]:
    if not isinstance(payload, dict):
        return ["review_evidence must be an object"]
    errors: list[str] = []
    missing = sorted(_REQUIRED_EVIDENCE - set(payload))
    if missing:
        errors.append(f"review_evidence missing required fields: {', '.join(missing)}")
    unknown = sorted(repr(key) for key in payload if not isinstance(key, str) or key not in _REQUIRED_EVIDENCE)
    if unknown:
        errors.append(f"review_evidence contains unknown v1 fields: {', '.join(unknown)}")
    if payload.get("schema_version") != 1 or type(payload.get("schema_version")) is not int:
        errors.append("review_evidence schema_version must be integer 1")

    identity = payload.get("change_identity")
    errors.extend(validate_change_identity(identity))
    if current_identity is not None:
        current_errors = validate_change_identity(current_identity)
        errors.extend(f"current {error}" for error in current_errors)
        if not current_errors and not _identity_fresh(
            identity,
            current_identity,
            conflict_resolution_occurred=conflict_resolution_occurred,
        ):
            errors.append("stale change_identity: review evidence does not match the current change/base state")

    requirements_ref = payload.get("requirements_ref")
    if "requirements_ref" in payload and requirements_ref is not None:
        if not isinstance(requirements_ref, dict):
            errors.append("requirements_ref must be an object or null")
        elif not _portable_value(requirements_ref):
            errors.append(
                f"requirements_ref must contain only JSON-portable finite values with string object keys and at most {_MAX_NESTING_DEPTH} nested levels"
            )
    if current_requirements_ref is not _UNSET:
        if current_requirements_ref is not None and (
            not isinstance(current_requirements_ref, dict) or not _portable_value(current_requirements_ref)
        ):
            errors.append(
                f"current requirements_ref must be a JSON-portable object or null with at most {_MAX_NESTING_DEPTH} nested levels"
            )
        elif not _json_equivalent(requirements_ref, current_requirements_ref):
            errors.append("stale requirements_ref: review evidence does not match current requirements surface")

    mode = payload.get("review_mode")
    if mode not in {"normal", "exhaustive"}:
        errors.append("review_mode must be normal or exhaustive")
    status = payload.get("inspection_status")
    if status not in {"complete", "partial", "unable"}:
        errors.append("inspection_status must be complete, partial, or unable")
    inspected = payload.get("inspected_surfaces")
    if not isinstance(inspected, list) or not all(isinstance(item, str) and item for item in inspected):
        errors.append("inspected_surfaces must be a list of non-empty strings")

    unavailable = payload.get("unable_to_inspect")
    if not isinstance(unavailable, list):
        errors.append("unable_to_inspect must be a list")
    else:
        for item in unavailable:
            if not isinstance(item, dict) or set(item) != _UNABLE_FIELDS:
                errors.append("unable_to_inspect entries must contain exactly surface, reason, and mandatory")
                continue
            if (
                not isinstance(item.get("surface"), str)
                or not item.get("surface")
                or not isinstance(item.get("reason"), str)
                or not item.get("reason")
                or type(item.get("mandatory")) is not bool
            ):
                errors.append("unable_to_inspect entries require non-empty surface/reason strings and boolean mandatory")
        if status == "unable" and not unavailable:
            errors.append("inspection_status unable requires at least one unable_to_inspect entry")
        if status == "complete" and any(
            isinstance(item, dict) and item.get("mandatory") is True for item in unavailable
        ):
            errors.append("inspection_status complete is invalid with a mandatory unable-to-inspect surface")

    findings = payload.get("findings")
    if not isinstance(findings, dict) or set(findings) != _FINDING_BUCKETS:
        errors.append("finding buckets must be exactly defect, suggestion, and question")
    else:
        ids: set[str] = set()
        for bucket, items in findings.items():
            if not isinstance(items, list):
                errors.append(f"findings.{bucket} must be a list")
                continue
            for item in items:
                if not isinstance(item, dict):
                    errors.append(f"findings.{bucket} entries must be objects")
                    continue
                if set(item) != _FINDING_FIELDS:
                    errors.append(
                        f"findings.{bucket} entries must contain exactly id, category, summary, and evidence"
                    )
                if item.get("category") != bucket:
                    errors.append(f"findings.{bucket} entry category must equal {bucket}")
                for field in ("id", "summary", "evidence"):
                    if not isinstance(item.get(field), str) or not item.get(field):
                        errors.append(f"findings.{bucket} entry {field} must be a non-empty string")
                finding_id = item.get("id")
                if isinstance(finding_id, str) and finding_id:
                    if finding_id in ids:
                        errors.append(f"finding id {finding_id} must be unique across all categories")
                    ids.add(finding_id)

    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at:
        errors.append("generated_at must be a non-empty string")
    return errors
