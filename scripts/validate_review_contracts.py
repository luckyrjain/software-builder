#!/usr/bin/env python3
"""Fail-closed validation for the shared change-identity and review-evidence contracts.

The payload validators are not defined here: docs/skill-framework/shared/review_contract_runtime.py
is the copy vendored into installed skill packages and executed by their own scripts, so it is the
copy this repository's CI must exercise too. It used to be a hand-maintained fork of this file,
kept honest only by example-based parity tests. This module now loads it and adds the two things
only the repository has -- the contract-YAML drift checks and the CLI.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file  # noqa: E402

_SHARED_RUNTIME = _ROOT / "docs/skill-framework/shared/review_contract_runtime.py"


def _load_shared_runtime() -> ModuleType:
    """Load the vendored runtime from this checkout's own fixed path.

    Loaded by path rather than imported: the runtime lives under docs/ precisely so it can be
    copied verbatim into installed packages, which must not depend on this repository's
    `scripts.*` import graph.
    """
    spec = importlib.util.spec_from_file_location("shared_review_contract_runtime", _SHARED_RUNTIME)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load shared review runtime: {_SHARED_RUNTIME}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shared_runtime = _load_shared_runtime()

validate_change_identity = shared_runtime.validate_change_identity
validate_review_evidence = shared_runtime.validate_review_evidence

_REQUIRED_IDENTITY = shared_runtime.REQUIRED_IDENTITY_FIELDS
_REQUIRED_EVIDENCE = shared_runtime.REQUIRED_EVIDENCE_FIELDS
_MAX_NESTING_DEPTH = shared_runtime.MAX_NESTING_DEPTH
_REVIEW_MODES = list(shared_runtime.REVIEW_MODES)
_INSPECTION_STATUSES = list(shared_runtime.INSPECTION_STATUSES)
_FINDING_CATEGORIES = list(shared_runtime.FINDING_CATEGORIES)
_UNABLE_FIELDS = list(shared_runtime.UNABLE_TO_INSPECT_FIELDS)
_FINDING_FIELDS = list(shared_runtime.FINDING_FIELDS)

# Facts about the contract *documents* rather than the runtime: the shapes the two YAML files
# must keep declaring, checked against the runtime's own vocabulary above.
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


def normalized_diff_fingerprint(canonical_effective_patch: str) -> str:
    if not isinstance(canonical_effective_patch, str):
        raise TypeError("canonical_effective_patch must be a string")
    normalized = canonical_effective_patch.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _valid_schema_version(value: object) -> bool:
    return type(value) is int and value == 1


def _required_fields_match(value: object, expected: frozenset[str] | set[str]) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) for item in value)
        and len(value) == len(expected)
        and set(value) == set(expected)
    )


def validate_contract_documents(root: Path = _ROOT) -> list[str]:
    errors: list[str] = []
    docs: dict[str, object] = {}
    for name, rel in (("change identity", "docs/skill-framework/shared/change-identity.yaml"), ("review evidence", "docs/skill-framework/shared/review-evidence.yaml")):
        try:
            docs[name] = load_unique_yaml_file(root / rel)
        except (OSError, UnicodeDecodeError, *YAML_SAFETY_ERRORS) as exc:
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
                or normalization.get("generated_paths_subset_of_changed_paths") is not True
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
            if spec.get("finding_categories") != _FINDING_CATEGORIES:
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
