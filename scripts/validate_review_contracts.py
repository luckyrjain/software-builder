#!/usr/bin/env python3
"""Fail-closed validation for shared change identity and review evidence."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path, PurePosixPath

import yaml

_SHA_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_FINGERPRINT_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_REQUIRED_IDENTITY = {"base_sha", "head_sha", "merge_base_sha", "normalized_diff_fingerprint", "changed_paths", "generated_paths", "dependency_changes", "config_changes"}
_REQUIRED_EVIDENCE = {"change_identity", "requirements_ref", "review_mode", "inspection_status", "inspected_surfaces", "unable_to_inspect", "findings", "generated_at"}
_FINDING_BUCKETS = {"defect", "suggestion", "question"}
_EFFECTIVE_PATCH_FIELDS = ("normalized_diff_fingerprint", "changed_paths", "generated_paths", "dependency_changes", "config_changes")
_ROOT = Path(__file__).resolve().parents[1]


def normalized_diff_fingerprint(canonical_effective_patch: str) -> str:
    if not isinstance(canonical_effective_patch, str):
        raise TypeError("canonical_effective_patch must be a string")
    normalized = canonical_effective_patch.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _valid_repo_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and str(path) == value


def validate_change_identity(payload: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["change_identity must be an object"]
    missing = sorted(_REQUIRED_IDENTITY - set(payload))
    if missing:
        errors.append(f"change_identity missing required fields: {', '.join(missing)}")
    for field in ("base_sha", "head_sha", "merge_base_sha"):
        if field in payload and (not isinstance(payload[field], str) or not _SHA_RE.fullmatch(payload[field])):
            errors.append(f"{field} must be a 40- or 64-character Git SHA")
    fp = payload.get("normalized_diff_fingerprint")
    if "normalized_diff_fingerprint" in payload and (not isinstance(fp, str) or not _FINGERPRINT_RE.fullmatch(fp)):
        errors.append("normalized_diff_fingerprint must be a 64-character SHA-256 hex value")
    for field in ("changed_paths", "generated_paths"):
        value = payload.get(field)
        if field in payload:
            if not isinstance(value, list) or not all(_valid_repo_path(item) for item in value):
                errors.append(f"{field} must be a list of canonical repository-relative POSIX paths")
            elif value != sorted(value) or len(value) != len(set(value)):
                errors.append(f"{field} must be sorted and contain no duplicates")
    for field in ("dependency_changes", "config_changes"):
        value = payload.get(field)
        if field in payload and (not isinstance(value, list) or not all(isinstance(item, dict) for item in value)):
            errors.append(f"{field} must be a list of objects")
    return errors


def _effective_patch_unchanged(stored: object, current: object) -> bool:
    if not isinstance(stored, dict) or not isinstance(current, dict):
        return False
    return all(stored.get(key) == current.get(key) for key in _EFFECTIVE_PATCH_FIELDS)


def validate_review_evidence(payload: object, *, current_identity: object | None = None, conflict_resolution_occurred: bool = False) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["review_evidence must be an object"]
    missing = sorted(_REQUIRED_EVIDENCE - set(payload))
    if missing:
        errors.append(f"review_evidence missing required fields: {', '.join(missing)}")
    identity = payload.get("change_identity")
    errors.extend(validate_change_identity(identity))
    if current_identity is not None:
        current_errors = validate_change_identity(current_identity)
        errors.extend(f"current {error}" for error in current_errors)
        if not current_errors and (conflict_resolution_occurred or not _effective_patch_unchanged(identity, current_identity)):
            errors.append("stale change_identity: review evidence does not match current effective patch")
    mode = payload.get("review_mode")
    if "review_mode" in payload and (not isinstance(mode, str) or mode not in {"normal", "exhaustive"}):
        errors.append("review_mode must be normal or exhaustive")
    status = payload.get("inspection_status")
    if "inspection_status" in payload and (not isinstance(status, str) or status not in {"complete", "partial", "unable"}):
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
                if not isinstance(item, dict) or not isinstance(item.get("surface"), str) or not isinstance(item.get("reason"), str):
                    errors.append("unable_to_inspect entries require string surface and reason")
            if status == "complete" and any(isinstance(item, dict) and item.get("mandatory") is True for item in unavailable):
                errors.append("inspection_status complete is invalid with a mandatory unable-to-inspect surface")
    findings = payload.get("findings")
    if "findings" in payload:
        if not isinstance(findings, dict) or set(findings) != _FINDING_BUCKETS:
            errors.append("finding buckets must be exactly defect, suggestion, and question")
        else:
            for bucket, items in findings.items():
                if not isinstance(items, list):
                    errors.append(f"findings.{bucket} must be a list")
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        errors.append(f"findings.{bucket} entries must be objects")
                        continue
                    if item.get("category") != bucket:
                        errors.append(f"findings.{bucket} entry category must equal {bucket}")
                    for field in ("id", "summary", "evidence"):
                        if not isinstance(item.get(field), str) or not item[field]:
                            errors.append(f"findings.{bucket} entry {field} must be a non-empty string")
    generated_at = payload.get("generated_at")
    if "generated_at" in payload and (not isinstance(generated_at, str) or not generated_at):
        errors.append("generated_at must be a non-empty string")
    return errors


def validate_contract_documents(root: Path = _ROOT) -> list[str]:
    errors: list[str] = []
    paths = {
        "change identity": root / "docs/skill-framework/shared/change-identity.yaml",
        "review evidence": root / "docs/skill-framework/shared/review-evidence.yaml",
    }
    docs: dict[str, object] = {}
    for name, path in paths.items():
        try:
            docs[name] = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            errors.append(f"{name} contract unreadable: {exc}")
    change = docs.get("change identity")
    if not isinstance(change, dict) or change.get("schema_version") != 1 or not isinstance(change.get("change_identity"), dict):
        errors.append("change identity contract must be schema_version 1 with change_identity object")
    evidence = docs.get("review evidence")
    if not isinstance(evidence, dict) or evidence.get("schema_version") != 1 or not isinstance(evidence.get("review_evidence"), dict):
        errors.append("review evidence contract must be schema_version 1 with review_evidence object")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contracts-only", action="store_true", help="validate committed shared contract documents")
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
