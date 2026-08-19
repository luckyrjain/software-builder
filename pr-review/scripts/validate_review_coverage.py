#!/usr/bin/env python3
"""Validate pr-review inspection coverage against the shared review evidence contracts."""
from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
SURFACES = (
    "cross_file_impact",
    "hidden_consumers",
    "schema_migration_compatibility",
    "rollout_rollback",
    "test_quality",
    "dependency_config_iac",
)
PLAN_FIELDS = {"triggered", "reason", "mandatory", "evidence_sources", "status"}
PLAN_STATUSES = {"pending", "complete", "unable", "not_applicable"}
_DEFECT_ID_RE = re.compile(r"^PRR-(?:[A-Z][A-Z0-9]*-)?\d{3}$")
_UNSET = object()


def _load_shared_validator() -> ModuleType:
    candidates = (
        ROOT / "docs/skill-framework/shared/review_contract_runtime.py",
        ROOT / "scripts/validate_review_contracts.py",
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        rendered = ", ".join(str(candidate) for candidate in candidates)
        raise RuntimeError(f"unable to load shared review validator; checked: {rendered}")
    spec = importlib.util.spec_from_file_location("shared_review_contract_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load shared review validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_summary(value: str) -> str:
    """Canonical summary text used only for deterministic portable IDs."""
    return " ".join(value.split())


def _content_finding_id(category: str, summary: str, evidence: str) -> str:
    prefix = {"suggestion": "PRS", "question": "PRQ"}[category]
    canonical = f"{category}\0{_normalize_summary(summary)}\0{evidence}".encode("utf-8")
    return f"{prefix}-{hashlib.sha256(canonical).hexdigest()[:12]}"


def validate_inspection_plan(plan: object) -> list[str]:
    if not isinstance(plan, dict):
        return ["inspection_plan must be an object"]

    errors: list[str] = []
    expected = set(SURFACES)
    actual = set(plan)
    missing = sorted(expected - actual)
    unknown = sorted(str(item) for item in actual - expected)
    if missing:
        errors.append(f"inspection_plan missing required surfaces: {', '.join(missing)}")
    if unknown:
        errors.append(f"inspection_plan contains unknown inspection surfaces: {', '.join(unknown)}")

    for surface in SURFACES:
        entry = plan.get(surface)
        prefix = f"inspection_plan.{surface}"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if set(entry) != PLAN_FIELDS:
            errors.append(
                f"{prefix} must contain exactly triggered, reason, mandatory, evidence_sources, and status"
            )
            continue

        triggered = entry.get("triggered")
        reason = entry.get("reason")
        mandatory = entry.get("mandatory")
        evidence_sources = entry.get("evidence_sources")
        status = entry.get("status")

        if type(triggered) is not bool:
            errors.append(f"{prefix}.triggered must be a boolean")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{prefix}.reason must be a non-empty string")
        if type(mandatory) is not bool:
            errors.append(f"{prefix}.mandatory must be a boolean")
        if not isinstance(evidence_sources, list) or not all(
            isinstance(item, str) and item.strip() for item in evidence_sources
        ):
            errors.append(f"{prefix}.evidence_sources must be a list of non-empty strings")
        if status not in PLAN_STATUSES:
            errors.append(f"{prefix}.status must be one of {sorted(PLAN_STATUSES)}")
            continue

        if triggered is True and status == "not_applicable":
            errors.append(f"{prefix} is triggered and cannot be not_applicable")
        if triggered is False and status != "not_applicable":
            errors.append(f"{prefix} is not triggered and must be not_applicable")
        if status == "complete" and isinstance(evidence_sources, list) and not evidence_sources:
            errors.append(f"{prefix}.evidence_sources must be non-empty when status=complete")

    return errors


def _validate_portable_finding_ids(review_evidence: dict[str, object]) -> list[str]:
    errors: list[str] = []
    findings = review_evidence.get("findings")
    if not isinstance(findings, dict):
        return errors

    for bucket in ("defect", "suggestion", "question"):
        items = findings.get(bucket)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            finding_id = item.get("id")
            summary = item.get("summary")
            evidence = item.get("evidence")
            if not all(isinstance(value, str) and value for value in (finding_id, summary, evidence)):
                continue
            if bucket == "defect":
                if not _DEFECT_ID_RE.fullmatch(finding_id):
                    errors.append(
                        f"findings.defect id {finding_id!r} must preserve PRR-<CAT>-NNN or legacy PRR-NNN"
                    )
                continue
            expected = _content_finding_id(bucket, summary, evidence)
            if finding_id != expected:
                errors.append(
                    f"findings.{bucket} id {finding_id!r} is not the deterministic content id; expected {expected!r}"
                )
    return errors


def validate_review_coverage(
    inspection_plan: object,
    review_evidence: object,
    *,
    current_identity: object | None = None,
    current_requirements_ref: object = _UNSET,
) -> list[str]:
    """Validate final Phase-2 coverage plus the shared portable review envelope."""
    errors = validate_inspection_plan(inspection_plan)
    shared = _load_shared_validator()

    shared_kwargs: dict[str, object] = {}
    if current_identity is not None:
        shared_kwargs["current_identity"] = current_identity
    if current_requirements_ref is not _UNSET:
        shared_kwargs["current_requirements_ref"] = current_requirements_ref
    errors.extend(shared.validate_review_evidence(review_evidence, **shared_kwargs))

    if not isinstance(inspection_plan, dict) or not isinstance(review_evidence, dict):
        return errors

    errors.extend(_validate_portable_finding_ids(review_evidence))

    inspected_raw = review_evidence.get("inspected_surfaces")
    if isinstance(inspected_raw, list) and all(isinstance(item, str) for item in inspected_raw):
        if len(inspected_raw) != len(set(inspected_raw)):
            errors.append("review_evidence.inspected_surfaces must not contain duplicates")
        inspected = set(inspected_raw)
    else:
        inspected = set()
    unknown_inspected = sorted(inspected - set(SURFACES))
    if unknown_inspected:
        errors.append(
            "review_evidence.inspected_surfaces contains unknown surfaces: "
            + ", ".join(unknown_inspected)
        )

    unable_raw = review_evidence.get("unable_to_inspect")
    unable_entries = unable_raw if isinstance(unable_raw, list) else []
    unable_by_surface: dict[str, list[dict[str, object]]] = {}
    for item in unable_entries:
        if not isinstance(item, dict):
            continue
        surface = item.get("surface")
        if isinstance(surface, str):
            unable_by_surface.setdefault(surface, []).append(item)
            if surface not in SURFACES:
                errors.append(f"review_evidence.unable_to_inspect references unknown surface: {surface}")
    for surface, entries in unable_by_surface.items():
        if len(entries) > 1:
            errors.append(f"{surface} has duplicate unable_to_inspect entries")

    triggered_unable: set[str] = set()
    triggered_complete: set[str] = set()
    for surface in SURFACES:
        entry = inspection_plan.get(surface)
        if not isinstance(entry, dict):
            continue
        triggered = entry.get("triggered") is True
        mandatory = entry.get("mandatory") is True
        status = entry.get("status")

        if not triggered:
            if surface in inspected:
                errors.append(f"{surface} is not triggered and must not appear in inspected_surfaces")
            if surface in unable_by_surface:
                errors.append(f"{surface} is not triggered and must not appear in unable_to_inspect")
            continue

        if status == "complete":
            triggered_complete.add(surface)
            if surface not in inspected:
                errors.append(f"{surface} status=complete must appear in review_evidence.inspected_surfaces")
            if surface in unable_by_surface:
                errors.append(f"{surface} status=complete must not appear in unable_to_inspect")
        elif status == "unable":
            triggered_unable.add(surface)
            matches = unable_by_surface.get(surface, [])
            if not matches:
                errors.append(f"{surface} status=unable requires a matching unable_to_inspect entry")
            elif not any(item.get("mandatory") is mandatory for item in matches):
                errors.append(
                    f"{surface} unable_to_inspect mandatory flag must match inspection_plan.mandatory"
                )
            if surface in inspected:
                errors.append(f"{surface} status=unable must not appear in inspected_surfaces")
        elif status == "pending":
            if mandatory:
                errors.append(f"pending mandatory inspection surface blocks final review: {surface}")
            else:
                errors.append(f"pending triggered inspection surface must be resolved before final review: {surface}")

    evidence_status = review_evidence.get("inspection_status")
    if evidence_status == "complete":
        for surface in SURFACES:
            entry = inspection_plan.get(surface)
            if not isinstance(entry, dict) or entry.get("triggered") is not True:
                continue
            if entry.get("status") != "complete":
                errors.append(
                    f"inspection_status complete requires triggered surface {surface} to be complete"
                )
    elif evidence_status == "partial":
        if not triggered_unable:
            errors.append("inspection_status partial requires at least one triggered surface with status=unable")
        if not triggered_complete:
            errors.append("inspection_status partial requires at least one completed triggered surface")
    elif evidence_status == "unable":
        if triggered_complete or inspected:
            errors.append(
                "inspection_status unable is reserved for primary review failure with no meaningful inspected surfaces"
            )
        if not triggered_unable:
            errors.append("inspection_status unable requires at least one triggered surface with status=unable")

    return errors
