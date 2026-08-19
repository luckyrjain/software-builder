#!/usr/bin/env python3
"""Fail-closed validation for shared change identity and review evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath

import yaml

_SHA_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_FP_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_MAX_NESTING_DEPTH = 32
_REQUIRED_IDENTITY = {"schema_version", "base_sha", "head_sha", "merge_base_sha", "normalized_diff_fingerprint", "changed_paths", "generated_paths", "dependency_changes", "config_changes"}
_REQUIRED_EVIDENCE = {"schema_version", "change_identity", "requirements_ref", "review_mode", "inspection_status", "inspected_surfaces", "unable_to_inspect", "findings", "generated_at"}
_FINDING_BUCKETS = {"defect", "suggestion", "question"}
_REVIEW_MODES = ["normal", "exhaustive"]
_INSPECTION_STATUSES = ["complete", "partial", "unable"]
_UNABLE_FIELDS = ["surface", "reason", "mandatory"]
_FINDING_FIELDS = ["id", "category", "summary", "evidence"]
_IDENTITY_FORMATS = {
    "sha_format": "git_sha_40_or_64_hex",
    "fingerprint_format": "sha256_hex_64",
    "path_format": "repository_relative_posix",
    "nested_value_format": "json_portable",
    "nested_value_max_depth": _MAX_NESTING_DEPTH,
}
_CHANGE_DOC_FIELDS = {"schema_version", "change_identity", "normalization", "freshness"}
_IDENTITY_SPEC_FIELDS = {"required_fields", "schema_version_value", "closed_v1", *_IDENTITY_FORMATS}
_EVIDENCE_DOC_FIELDS = {"schema_version", "review_evidence"}
_EVIDENCE_SPEC_FIELDS = {
    "required_fields", "schema_version_value", "requirements_ref_type", "nested_value_max_depth",
    "review_modes", "inspection_status_values", "finding_categories",
    "unable_to_inspect_required_fields", "finding_required_fields", "rules",
}
_EXCLUDED_TRANSPORT_METADATA = ["commit_message", "provider_diff_headers", "review_comment_text"]
_ORDERING = {
    "changed_paths": "lexicographic",
    "generated_paths": "lexicographic",
    "dependency_changes": "canonical_object_order",
    "config_changes": "canonical_object_order",
}
_REQUIRED_RULES = {
    "envelope_is_closed_v1": True,
    "questions_are_non_blocking_until_promoted": True,
    "complete_forbidden_with_mandatory_unable_surface": True,
    "unable_status_requires_unable_to_inspect_entry": True,
    "stale_change_identity_invalidates_envelope": True,
    "requirements_change_invalidates_envelope": True,
    "categories_are_disjoint": True,
    "finding_entries_are_closed_v1": True,
    "unable_entries_are_closed_v1": True,
    "requirements_ref_is_json_portable": True,
}
_FRESHNESS_RULES = {
    "unchanged_effective_patch_may_preserve_review": True,
    "content_neutral_base_update_requires_synced_merge_base": True,
    "conflict_resolution_invalidates_review": True,
    "content_change_invalidates_review": True,
    "generated_file_change_invalidates_review": True,
}
_EFFECTIVE_PATCH_FIELDS = ("changed_paths", "generated_paths", "dependency_changes", "config_changes")
_ROOT = Path(__file__).resolve().parents[1]
_UNSET = object()


def normalized_diff_fingerprint(canonical_effective_patch: str) -> str:
    if not isinstance(canonical_effective_patch, str):
        raise TypeError("canonical_effective_patch must be a string")
    normalized = canonical_effective_patch.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _valid_repo_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and path != PurePosixPath(".") and ".." not in path.parts and str(path) == value


def _portable_scalar(value: object) -> bool:
    if value is None or type(value) in (str, bool, int):
        return True
    return type(value) is float and math.isfinite(value)


def _portable_value(value: object, *, _depth: int = 0, _seen: set[int] | None = None) -> bool:
    if _depth > _MAX_NESTING_DEPTH:
        return False
    if not isinstance(value, (dict, list)):
        return _portable_scalar(value)
    seen = set() if _seen is None else _seen
    marker = id(value)
    if marker in seen:
        return False
    seen.add(marker)
    try:
        if isinstance(value, dict):
            return all(
                isinstance(k, str) and _portable_value(v, _depth=_depth + 1, _seen=seen)
                for k, v in value.items()
            )
        return all(_portable_value(item, _depth=_depth + 1, _seen=seen) for item in value)
    finally:
        seen.remove(marker)


def _canonical_mapping_value(value: object, *, _depth: int = 0, _seen: set[int] | None = None) -> bool:
    if _depth > _MAX_NESTING_DEPTH:
        return False
    if not isinstance(value, (dict, list)):
        return _portable_scalar(value)
    seen = set() if _seen is None else _seen
    marker = id(value)
    if marker in seen:
        return False
    seen.add(marker)
    try:
        if isinstance(value, dict):
            keys = list(value)
            return (
                all(isinstance(k, str) for k in keys)
                and keys == sorted(keys)
                and all(_canonical_mapping_value(v, _depth=_depth + 1, _seen=seen) for v in value.values())
            )
        return all(_canonical_mapping_value(item, _depth=_depth + 1, _seen=seen) for item in value)
    finally:
        seen.remove(marker)


def _canonical_json(value: object) -> str | None:
    if not _portable_value(value):
        return None
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        return None


def _json_equivalent(left: object, right: object) -> bool:
    left_json = _canonical_json(left)
    right_json = _canonical_json(right)
    return left_json is not None and right_json is not None and left_json == right_json


def _same_hex(left: object, right: object) -> bool:
    return isinstance(left, str) and isinstance(right, str) and left.lower() == right.lower()


def _canonical_object_key(value: dict[str, object]) -> str:
    canonical = _canonical_json(value)
    if canonical is None:
        raise ValueError("object must be JSON-portable")
    return canonical


def _valid_schema_version(value: object) -> bool:
    return type(value) is int and value == 1


def _required_fields_match(value: object, expected: set[str]) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) for item in value)
        and len(value) == len(expected)
        and set(value) == expected
    )


def _unknown_fields(payload: dict[object, object], expected: set[str]) -> list[str]:
    unknown = [key for key in payload if not isinstance(key, str) or key not in expected]
    return sorted(repr(key) for key in unknown)


def validate_change_identity(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["change_identity must be an object"]
    errors: list[str] = []
    missing = sorted(_REQUIRED_IDENTITY - set(payload))
    if missing:
        errors.append(f"change_identity missing required fields: {', '.join(missing)}")
    unknown = _unknown_fields(payload, _REQUIRED_IDENTITY)
    if unknown:
        errors.append(f"change_identity contains unknown v1 fields: {', '.join(unknown)}")
    if "schema_version" in payload and not _valid_schema_version(payload.get("schema_version")):
        errors.append("change_identity schema_version must be integer 1")
    for field in ("base_sha", "head_sha", "merge_base_sha"):
        value = payload.get(field)
        if field in payload and (not isinstance(value, str) or not _SHA_RE.fullmatch(value)):
            errors.append(f"{field} must be a 40- or 64-character Git SHA")
    fp = payload.get("normalized_diff_fingerprint")
    if "normalized_diff_fingerprint" in payload and (not isinstance(fp, str) or not _FP_RE.fullmatch(fp)):
        errors.append("normalized_diff_fingerprint must be a 64-character SHA-256 hex value")
    for field in ("changed_paths", "generated_paths"):
        value = payload.get(field)
        if field in payload:
            if not isinstance(value, list) or not all(_valid_repo_path(x) for x in value):
                errors.append(f"{field} must be a list of canonical repository-relative POSIX paths")
            elif value != sorted(value) or len(value) != len(set(value)):
                errors.append(f"{field} must be sorted and contain no duplicates")
    changed_paths = payload.get("changed_paths")
    generated_paths = payload.get("generated_paths")
    if (
        isinstance(changed_paths, list)
        and isinstance(generated_paths, list)
        and all(_valid_repo_path(x) for x in changed_paths)
        and all(_valid_repo_path(x) for x in generated_paths)
        and not set(generated_paths).issubset(set(changed_paths))
    ):
        errors.append("generated_paths must be a subset of changed_paths")
    for field in ("dependency_changes", "config_changes"):
        value = payload.get(field)
        if field in payload:
            if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
                errors.append(f"{field} must be a list of objects")
            elif not all(_canonical_mapping_value(x) for x in value):
                errors.append(f"{field} objects must use recursively sorted string keys, JSON-portable finite scalar values, and at most {_MAX_NESTING_DEPTH} nested levels")
            else:
                keys = [_canonical_object_key(x) for x in value]
                if keys != sorted(keys) or len(keys) != len(set(keys)):
                    errors.append(f"{field} must use canonical object ordering and contain no duplicate objects")
    return errors


def _effective_patch_unchanged(stored: object, current: object) -> bool:
    return (
        isinstance(stored, dict)
        and isinstance(current, dict)
        and _same_hex(stored.get("normalized_diff_fingerprint"), current.get("normalized_diff_fingerprint"))
        and all(_json_equivalent(stored.get(k), current.get(k)) for k in _EFFECTIVE_PATCH_FIELDS)
    )


def _identity_fresh(stored: object, current: object, *, conflict_resolution_occurred: bool) -> bool:
    if conflict_resolution_occurred or not isinstance(stored, dict) or not isinstance(current, dict):
        return False
    if not _effective_patch_unchanged(stored, current):
        return False
    sha_fields = ("base_sha", "head_sha", "merge_base_sha")
    if all(_same_hex(stored.get(field), current.get(field)) for field in sha_fields):
        return True
    return (
        _same_hex(stored.get("base_sha"), stored.get("merge_base_sha"))
        and _same_hex(current.get("base_sha"), current.get("merge_base_sha"))
        and not _same_hex(stored.get("base_sha"), current.get("base_sha"))
    )


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
    unknown = _unknown_fields(payload, _REQUIRED_EVIDENCE)
    if unknown:
        errors.append(f"review_evidence contains unknown v1 fields: {', '.join(unknown)}")
    if "schema_version" in payload and not _valid_schema_version(payload.get("schema_version")):
        errors.append("review_evidence schema_version must be integer 1")
    identity = payload.get("change_identity")
    errors.extend(validate_change_identity(identity))
    if current_identity is not None:
        current_errors = validate_change_identity(current_identity)
        errors.extend(f"current {e}" for e in current_errors)
        if not current_errors and not _identity_fresh(identity, current_identity, conflict_resolution_occurred=conflict_resolution_occurred):
            errors.append("stale change_identity: review evidence does not match the current change/base state")
    requirements_ref = payload.get("requirements_ref")
    if "requirements_ref" in payload and requirements_ref is not None:
        if not isinstance(requirements_ref, dict):
            errors.append("requirements_ref must be an object or null")
        elif not _portable_value(requirements_ref):
            errors.append(f"requirements_ref must contain only JSON-portable finite values with string object keys and at most {_MAX_NESTING_DEPTH} nested levels")
    if current_requirements_ref is not _UNSET:
        if current_requirements_ref is not None and (not isinstance(current_requirements_ref, dict) or not _portable_value(current_requirements_ref)):
            errors.append(f"current requirements_ref must be a JSON-portable object or null with at most {_MAX_NESTING_DEPTH} nested levels")
        elif not _json_equivalent(requirements_ref, current_requirements_ref):
            errors.append("stale requirements_ref: review evidence does not match current requirements surface")
    mode = payload.get("review_mode")
    if "review_mode" in payload and (not isinstance(mode, str) or mode not in _REVIEW_MODES):
        errors.append("review_mode must be normal or exhaustive")
    status = payload.get("inspection_status")
    if "inspection_status" in payload and (not isinstance(status, str) or status not in _INSPECTION_STATUSES):
        errors.append("inspection_status must be complete, partial, or unable")
    inspected = payload.get("inspected_surfaces")
    if "inspected_surfaces" in payload and (not isinstance(inspected, list) or not all(isinstance(x, str) and x for x in inspected)):
        errors.append("inspected_surfaces must be a list of non-empty strings")
    unavailable = payload.get("unable_to_inspect")
    if "unable_to_inspect" in payload:
        if not isinstance(unavailable, list):
            errors.append("unable_to_inspect must be a list")
        else:
            for item in unavailable:
                if not isinstance(item, dict) or set(item) != set(_UNABLE_FIELDS):
                    errors.append("unable_to_inspect entries must contain exactly surface, reason, and mandatory")
                    continue
                if not isinstance(item.get("surface"), str) or not item.get("surface") or not isinstance(item.get("reason"), str) or not item.get("reason") or type(item.get("mandatory")) is not bool:
                    errors.append("unable_to_inspect entries require non-empty surface/reason strings and boolean mandatory")
            if status == "unable" and not unavailable:
                errors.append("inspection_status unable requires at least one unable_to_inspect entry")
            if status == "complete" and any(isinstance(item, dict) and item.get("mandatory") is True for item in unavailable):
                errors.append("inspection_status complete is invalid with a mandatory unable-to-inspect surface")
    findings = payload.get("findings")
    if "findings" in payload:
        if not isinstance(findings, dict) or set(findings) != _FINDING_BUCKETS:
            errors.append("finding buckets must be exactly defect, suggestion, and question")
        else:
            finding_ids: set[str] = set()
            for bucket, items in findings.items():
                if not isinstance(items, list):
                    errors.append(f"findings.{bucket} must be a list")
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        errors.append(f"findings.{bucket} entries must be objects")
                        continue
                    if set(item) != set(_FINDING_FIELDS):
                        errors.append(f"findings.{bucket} entries must contain exactly id, category, summary, and evidence")
                    if item.get("category") != bucket:
                        errors.append(f"findings.{bucket} entry category must equal {bucket}")
                    for field in ("id", "summary", "evidence"):
                        if not isinstance(item.get(field), str) or not item[field]:
                            errors.append(f"findings.{bucket} entry {field} must be a non-empty string")
                    finding_id = item.get("id")
                    if isinstance(finding_id, str) and finding_id:
                        if finding_id in finding_ids:
                            errors.append(f"finding id {finding_id} must be unique across all categories")
                        finding_ids.add(finding_id)
    if "generated_at" in payload and (not isinstance(payload.get("generated_at"), str) or not payload["generated_at"]):
        errors.append("generated_at must be a non-empty string")
    return errors


def validate_contract_documents(root: Path = _ROOT) -> list[str]:
    errors: list[str] = []
    docs: dict[str, object] = {}
    for name, rel in (("change identity", "docs/skill-framework/shared/change-identity.yaml"), ("review evidence", "docs/skill-framework/shared/review-evidence.yaml")):
        try:
            docs[name] = yaml.safe_load((root / rel).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            errors.append(f"{name} contract unreadable: {exc}")

    change = docs.get("change identity")
    if not isinstance(change, dict):
        errors.append("change identity contract must be an object")
    else:
        if set(change) != _CHANGE_DOC_FIELDS:
            errors.append("change identity contract top-level fields drifted")
        identity_spec = change.get("change_identity")
        if not _valid_schema_version(change.get("schema_version")) or not isinstance(identity_spec, dict):
            errors.append("change identity contract must be schema_version 1 with change_identity object")
        else:
            if set(identity_spec) != _IDENTITY_SPEC_FIELDS:
                errors.append("change identity contract spec fields drifted")
            if not _required_fields_match(identity_spec.get("required_fields"), _REQUIRED_IDENTITY):
                errors.append("change identity contract required fields drifted")
            if identity_spec.get("schema_version_value") != 1:
                errors.append("change identity contract payload schema version drifted")
            if identity_spec.get("closed_v1") is not True:
                errors.append("change identity contract closed_v1 drifted")
            if any(identity_spec.get(key) != value for key, value in _IDENTITY_FORMATS.items()):
                errors.append("change identity contract format declarations drifted")
            normalization = change.get("normalization")
            freshness = change.get("freshness")
            if (
                not isinstance(normalization, dict)
                or normalization.get("source") != "canonical_effective_patch"
                or normalization.get("include_generated_paths") is not True
                or normalization.get("excluded_transport_metadata") != _EXCLUDED_TRANSPORT_METADATA
                or normalization.get("ordering") != _ORDERING
            ):
                errors.append("change identity contract normalization drifted")
            if freshness != _FRESHNESS_RULES:
                errors.append("change identity contract freshness rules drifted")

    evidence = docs.get("review evidence")
    if not isinstance(evidence, dict):
        errors.append("review evidence contract must be an object")
    else:
        if set(evidence) != _EVIDENCE_DOC_FIELDS:
            errors.append("review evidence contract top-level fields drifted")
        spec = evidence.get("review_evidence")
        if not _valid_schema_version(evidence.get("schema_version")) or not isinstance(spec, dict):
            errors.append("review evidence contract must be schema_version 1 with review_evidence object")
        else:
            if set(spec) != _EVIDENCE_SPEC_FIELDS:
                errors.append("review evidence contract spec fields drifted")
            if not _required_fields_match(spec.get("required_fields"), _REQUIRED_EVIDENCE):
                errors.append("review evidence contract required fields drifted")
            if spec.get("schema_version_value") != 1:
                errors.append("review evidence contract payload schema version drifted")
            if spec.get("requirements_ref_type") != "object_or_null":
                errors.append("review evidence contract requirements_ref_type drifted")
            if spec.get("nested_value_max_depth") != _MAX_NESTING_DEPTH:
                errors.append("review evidence contract nested_value_max_depth drifted")
            if spec.get("review_modes") != _REVIEW_MODES:
                errors.append("review evidence contract review modes drifted")
            if spec.get("inspection_status_values") != _INSPECTION_STATUSES:
                errors.append("review evidence contract inspection statuses drifted")
            if spec.get("finding_categories") != ["defect", "suggestion", "question"]:
                errors.append("review evidence contract finding taxonomy drifted")
            if spec.get("unable_to_inspect_required_fields") != _UNABLE_FIELDS:
                errors.append("review evidence contract unable-to-inspect fields drifted")
            if spec.get("finding_required_fields") != _FINDING_FIELDS:
                errors.append("review evidence contract finding fields drifted")
            if spec.get("rules") != _REQUIRED_RULES:
                errors.append("review evidence contract rules drifted")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.contracts_only:
        parser.error("--contracts-only is required")
    errors = validate_contract_documents()
    for error in errors:
        print(f"error: {error}")
    if errors:
        return 1
    print("ok: shared review contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
