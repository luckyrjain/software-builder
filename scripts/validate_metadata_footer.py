#!/usr/bin/env python3
"""Validate review_metadata / assessment_metadata YAML footers (shared schema v2)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised when PyYAML missing
    yaml = None  # type: ignore[assignment]

ROOT_KEYS = frozenset({"review_metadata", "assessment_metadata"})

REVIEW_TYPE_VALUES = frozenset({"full", "incremental"})
RECOMMENDATION_VALUES = frozenset({"approve", "comment", "request_changes"})
CONFIDENCE_VALUES = frozenset({"high", "medium", "low"})
INVESTIGATION_CONFIDENCE_VALUES = frozenset({"very_high", "high", "medium", "low"})
SEVERITY_VALUES = frozenset({"critical", "high", "medium", "low", "none"})


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_string(meta: dict[str, Any], key: str, errors: list[str], *, prefix: str = "") -> None:
    label = f"{prefix}{key}" if prefix else key
    if key not in meta:
        errors.append(f"missing required field: {label}")
    elif not _is_non_empty_string(meta[key]):
        errors.append(f"{label} must be a non-empty string")


def _require_bool(meta: dict[str, Any], key: str, errors: list[str], *, prefix: str = "") -> None:
    label = f"{prefix}{key}" if prefix else key
    if key not in meta:
        errors.append(f"missing required field: {label}")
    elif not isinstance(meta[key], bool):
        errors.append(f"{label} must be a boolean")


def _require_enum(
    meta: dict[str, Any],
    key: str,
    allowed: frozenset[str],
    errors: list[str],
    *,
    prefix: str = "",
) -> None:
    label = f"{prefix}{key}" if prefix else key
    value = meta.get(key)
    if key not in meta:
        errors.append(f"missing required field: {label}")
    elif not isinstance(value, str) or value not in allowed:
        errors.append(f"{label} must be one of: {', '.join(sorted(allowed))}")


def _validate_review_hash(block: Any, errors: list[str]) -> None:
    if not isinstance(block, dict):
        errors.append("review_hash must be an object")
        return
    if "scope" not in block:
        errors.append("review_hash missing required field: scope")
    elif not _is_non_empty_string(block["scope"]):
        errors.append("review_hash.scope must be a non-empty string")


def _validate_findings(findings: Any, errors: list[str]) -> None:
    if not isinstance(findings, list):
        errors.append("findings must be an array")
        return
    for index, finding in enumerate(findings):
        prefix = f"findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{prefix} must be an object")
            continue
        _require_string(finding, "id", errors, prefix=f"{prefix}.")
        if "severity" in finding:
            severity = finding["severity"]
            if not isinstance(severity, str) or severity not in SEVERITY_VALUES:
                errors.append(
                    f"{prefix}.severity must be one of: {', '.join(sorted(SEVERITY_VALUES))}"
                )


def _validate_history_block(block: Any, errors: list[str], *, kind: str) -> None:
    if block is None:
        return
    if not isinstance(block, dict):
        errors.append(f"{kind} must be an object")
        return
    for snapshot_key in ("first_review", "prior_review", "first_assessment", "prior_assessment"):
        snapshot = block.get(snapshot_key)
        if snapshot is None:
            continue
        if not isinstance(snapshot, dict):
            errors.append(f"{kind}.{snapshot_key} must be an object")
            continue
        _require_string(snapshot, "finished", errors, prefix=f"{kind}.{snapshot_key}.")
        if "recommendation" in snapshot:
            _require_enum(
                snapshot,
                "recommendation",
                RECOMMENDATION_VALUES,
                errors,
                prefix=f"{kind}.{snapshot_key}.",
            )
        if "highest_severity" in snapshot:
            severity = snapshot["highest_severity"]
            if not isinstance(severity, str) or severity not in SEVERITY_VALUES:
                errors.append(
                    f"{kind}.{snapshot_key}.highest_severity must be one of: "
                    f"{', '.join(sorted(SEVERITY_VALUES))}"
                )


def _validate_precision_block(block: Any, errors: list[str], *, kind: str) -> None:
    if block is None:
        return
    if not isinstance(block, dict):
        errors.append(f"{kind} must be an object")


def _validate_quality_block(block: Any, errors: list[str], *, kind: str) -> None:
    if block is None:
        return
    if not isinstance(block, dict):
        errors.append(f"{kind} must be an object")
        return
    if "confidence" in block:
        confidence = block["confidence"]
        if not isinstance(confidence, str) or confidence not in INVESTIGATION_CONFIDENCE_VALUES:
            errors.append(
                f"{kind}.confidence must be one of: "
                f"{', '.join(sorted(INVESTIGATION_CONFIDENCE_VALUES))}"
            )
    for pct_key in ("coverage_pct", "evidence_pct"):
        if pct_key in block and not isinstance(block[pct_key], (int, float)):
            errors.append(f"{kind}.{pct_key} must be a number")


def _validate_repository_health(block: Any, errors: list[str]) -> None:
    if block is None:
        return
    if not isinstance(block, dict):
        errors.append("repository_health must be an object")
        return
    version = block.get("schema_version")
    if version is not None and not isinstance(version, int):
        errors.append("repository_health.schema_version must be an integer")
    dimensions = block.get("dimensions")
    if dimensions is not None and not isinstance(dimensions, dict):
        errors.append("repository_health.dimensions must be an object")


def validate_review_metadata(meta: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(meta, dict):
        return ["review_metadata must be an object"]

    _require_enum(meta, "review_type", REVIEW_TYPE_VALUES, errors)
    _require_string(meta, "started", errors)
    _require_string(meta, "finished", errors)
    _require_string(meta, "head_sha", errors)
    _require_enum(meta, "recommendation", RECOMMENDATION_VALUES, errors)
    _require_enum(meta, "confidence", CONFIDENCE_VALUES, errors)
    _require_bool(meta, "review_complete", errors)

    if "review_hash" not in meta:
        errors.append("missing required field: review_hash")
    else:
        _validate_review_hash(meta["review_hash"], errors)

    if "findings" not in meta:
        errors.append("missing required field: findings")
    else:
        _validate_findings(meta["findings"], errors)

    _validate_history_block(meta.get("history"), errors, kind="history")
    _validate_precision_block(meta.get("precision"), errors, kind="precision")
    _validate_quality_block(meta.get("review_quality"), errors, kind="review_quality")
    _validate_repository_health(meta.get("repository_health"), errors)

    return errors


def validate_assessment_metadata(meta: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(meta, dict):
        return ["assessment_metadata must be an object"]

    _require_enum(meta, "assessment_type", REVIEW_TYPE_VALUES, errors)
    _require_string(meta, "started", errors)
    _require_string(meta, "finished", errors)
    _require_string(meta, "service", errors)
    _require_bool(meta, "assessment_complete", errors)

    is_k8s = "final_decision" in meta
    is_rca = "primary_hypothesis" in meta or "incident_window" in meta

    if is_k8s and is_rca:
        errors.append(
            "assessment_metadata cannot mix k8s fields (final_decision) "
            "with rca fields (primary_hypothesis/incident_window)"
        )
    elif is_k8s:
        _require_string(meta, "final_decision", errors)
        confidence = meta.get("assessment_confidence")
        if "assessment_confidence" not in meta:
            errors.append("missing required field: assessment_confidence")
        elif not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            errors.append("assessment_confidence must be a number between 0 and 1")
    elif is_rca:
        window = meta.get("incident_window")
        if not isinstance(window, dict):
            errors.append("incident_window must be an object")
        else:
            _require_string(window, "from", errors, prefix="incident_window.")
            _require_string(window, "to", errors, prefix="incident_window.")
        _require_string(meta, "primary_hypothesis", errors)
        _require_enum(meta, "confidence", CONFIDENCE_VALUES, errors)
    else:
        errors.append(
            "assessment_metadata must include k8s fields (final_decision) "
            "or rca fields (primary_hypothesis/incident_window)"
        )

    _validate_history_block(meta.get("history"), errors, kind="history")
    _validate_precision_block(meta.get("precision"), errors, kind="precision")
    _validate_quality_block(
        meta.get("investigation_quality"), errors, kind="investigation_quality"
    )

    return errors


def validate_footer_document(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["root must be a YAML mapping"]

    present = [key for key in ROOT_KEYS if key in data]
    if not present:
        return [f"root must contain one of: {', '.join(sorted(ROOT_KEYS))}"]
    if len(present) > 1:
        return [f"root must contain only one metadata key; found: {', '.join(present)}"]

    root_key = present[0]
    if root_key == "review_metadata":
        return validate_review_metadata(data[root_key])
    return validate_assessment_metadata(data[root_key])


def load_yaml(path: Path) -> tuple[Any | None, str | None]:
    if yaml is None:
        return None, "PyYAML is required — pip install PyYAML"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, str(exc)
    except yaml.YAMLError as exc:
        return None, f"YAML parse error: {exc}"
    return data, None


def main(argv: list[str] | None = None) -> int:
    paths = (argv if argv is not None else sys.argv[1:]) or [
        "docs/skill-framework/shared/examples/review-metadata.example.yaml",
        "docs/skill-framework/shared/examples/assessment-metadata-rca.example.yaml",
        "docs/skill-framework/shared/examples/assessment-metadata-k8s.example.yaml",
    ]
    exit_code = 0
    for path_str in paths:
        path = Path(path_str)
        data, load_error = load_yaml(path)
        if load_error:
            print(f"{path}: {load_error}", file=sys.stderr)
            exit_code = 1
            continue
        errors = validate_footer_document(data)
        if errors:
            exit_code = 1
            print(f"{path}: validation failed", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
        else:
            print(f"{path}: ok")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
