#!/usr/bin/env python3
"""Fail-closed lifecycle validation for loop-task-implementer state."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


SKILL_ROOT = Path(__file__).resolve().parents[1]
_UNSET = object()


def _load_shared_runtime() -> ModuleType:
    candidates = (
        SKILL_ROOT / "docs/skill-framework/shared/review_contract_runtime.py",
        SKILL_ROOT.parent / "docs/skill-framework/shared/review_contract_runtime.py",
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        checked = ", ".join(str(candidate) for candidate in candidates)
        raise RuntimeError(f"unable to load shared review runtime; checked: {checked}")
    spec = importlib.util.spec_from_file_location("loop_shared_review_contract_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load shared review runtime: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _same_hex(left: object, right: object) -> bool:
    return isinstance(left, str) and isinstance(right, str) and left.lower() == right.lower()


def _identity_shas_changed(stored: object, current: object) -> bool:
    if not isinstance(stored, dict) or not isinstance(current, dict):
        return False
    for field in ("base_sha", "head_sha", "merge_base_sha"):
        if not _same_hex(stored.get(field), current.get(field)):
            return True
    return False


def _lens_errors(
    name: str,
    lens: dict[str, object],
    current_identity: object,
    *,
    current_requirements_ref: object = _UNSET,
    conflict_resolution_occurred: bool | None,
) -> list[str]:
    errors: list[str] = []
    status = lens.get("status")
    evidence = lens.get("review_evidence")
    reviewed_identity = lens.get("reviewed_change_identity")

    if status == "CLEAN" and not isinstance(evidence, dict):
        errors.append(f"{name} CLEAN requires review_evidence")
        return errors
    if status != "CLEAN":
        return errors

    if not isinstance(reviewed_identity, dict):
        errors.append(f"{name} CLEAN requires reviewed_change_identity")
    elif isinstance(evidence, dict) and evidence.get("change_identity") != reviewed_identity:
        errors.append(f"{name} reviewed_change_identity must equal review_evidence.change_identity")

    shared = _load_shared_runtime()
    sha_transition = _identity_shas_changed(
        evidence.get("change_identity") if isinstance(evidence, dict) else None,
        current_identity,
    )
    if conflict_resolution_occurred is not None and type(conflict_resolution_occurred) is not bool:
        errors.append("conflict_resolution_occurred must be boolean or null")
        conflict_for_shared = True
    elif sha_transition and conflict_resolution_occurred is None:
        errors.append(
            f"{name} cannot establish freshness: conflict_resolution_occurred is unknown after identity SHA transition"
        )
        conflict_for_shared = True
    else:
        conflict_for_shared = bool(conflict_resolution_occurred)

    kwargs: dict[str, object] = {
        "current_identity": current_identity,
        "conflict_resolution_occurred": conflict_for_shared,
    }
    if current_requirements_ref is not _UNSET:
        kwargs["current_requirements_ref"] = current_requirements_ref
    shared_errors = shared.validate_review_evidence(evidence, **kwargs)
    errors.extend(f"{name}: {error}" for error in shared_errors)
    return errors


def validate_lifecycle_state(state: object) -> list[str]:
    """Validate the official loop state before READY, COMPLETE, or merge."""
    if not isinstance(state, dict):
        return ["lifecycle state must be an object"]

    errors: list[str] = []
    task = _mapping(state.get("task"))
    workspace = _mapping(state.get("workspace"))
    review = _mapping(state.get("review"))
    ci = _mapping(state.get("ci"))
    readiness = _mapping(state.get("merge_readiness"))

    current_identity = workspace.get("change_identity")
    shared = _load_shared_runtime()
    identity_errors = shared.validate_change_identity(current_identity)
    errors.extend(f"current {error}" for error in identity_errors)

    current_head = workspace.get("current_head_commit")
    if isinstance(current_identity, dict) and isinstance(current_head, str):
        if not _same_hex(current_identity.get("head_sha"), current_head):
            errors.append("workspace.change_identity.head_sha must equal workspace.current_head_commit")

    conflict = workspace.get("conflict_resolution_occurred")
    provenance = workspace.get("conflict_resolution_provenance")
    if conflict is True and not isinstance(provenance, str):
        errors.append("conflict_resolution_occurred=true requires conflict_resolution_provenance")

    requirements_ref = task.get("requirements_ref", _UNSET)
    lens_a = _mapping(review.get("lens_a"))
    lens_b = _mapping(review.get("lens_b"))
    if not identity_errors:
        errors.extend(
            _lens_errors(
                "lens_a",
                lens_a,
                current_identity,
                current_requirements_ref=requirements_ref,
                conflict_resolution_occurred=conflict if conflict in (True, False, None) else conflict,
            )
        )
        errors.extend(
            _lens_errors(
                "lens_b",
                lens_b,
                current_identity,
                current_requirements_ref=requirements_ref,
                conflict_resolution_occurred=conflict if conflict in (True, False, None) else conflict,
            )
        )

    if lens_a.get("status") == "CLEAN" and lens_b.get("status") == "CLEAN":
        a_identity = lens_a.get("reviewed_change_identity")
        b_identity = lens_b.get("reviewed_change_identity")
        if a_identity != b_identity:
            errors.append("both CLEAN lenses must reference the same reviewed_change_identity")

    if workspace.get("third_party_change_detected") is True:
        errors.append("third_party_change_detected blocks lifecycle readiness until re-baselined and re-reviewed")

    if ci.get("required_checks_green") is True:
        ci_commit = ci.get("commit")
        if not _same_hex(ci_commit, current_head):
            errors.append("required checks are not authoritative for current head: ci.commit must equal current_head_commit")

    ready = readiness.get("ready") is True or task.get("status") in {"READY", "COMPLETE"}
    if ready:
        if identity_errors:
            errors.append("ready cannot be true with invalid current change_identity")
        if lens_a.get("status") != "CLEAN" or lens_b.get("status") != "CLEAN":
            errors.append("ready cannot be true until both review lenses are CLEAN")
        if ci.get("required_checks_green") is not True:
            errors.append("ready cannot be true until required checks are green")
        if workspace.get("third_party_change_detected") is True:
            errors.append("ready cannot be true while third_party_change_detected")
        if errors and not any(error.startswith("ready cannot be true") for error in errors):
            errors.append("ready cannot be true while lifecycle validation has errors")

    return errors
