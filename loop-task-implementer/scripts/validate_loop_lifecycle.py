#!/usr/bin/env python3
"""Fail-closed lifecycle validation for loop-task-implementer state."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


SKILL_ROOT = Path(__file__).resolve().parents[1]
_INSTALL_MANIFEST = ".software-builder-manifest.json"
_UNSET = object()


def _shared_runtime_path() -> Path:
    """Resolve the shared runtime for installed packages or this source repository.

    Installed packages must use their vendored runtime. A source checkout may use the
    repository-level shared runtime only when the surrounding tree proves it is the
    software-builder development layout; this avoids accepting an arbitrary sibling
    ``docs`` tree as executable lifecycle policy.
    """
    vendored = SKILL_ROOT / "docs/skill-framework/shared/review_contract_runtime.py"
    if vendored.is_file():
        return vendored

    # package_skill always writes this manifest into an installed skill. Once it
    # is present, never search outside the package for executable lifecycle policy.
    if (SKILL_ROOT / _INSTALL_MANIFEST).is_file():
        raise RuntimeError(f"unable to load packaged shared review runtime: {vendored}")

    repo_root = SKILL_ROOT.parent
    source_runtime = repo_root / "docs/skill-framework/shared/review_contract_runtime.py"
    source_markers = (
        repo_root / "skills.yaml",
        repo_root / "scripts/package_skill.py",
    )
    if all(marker.is_file() for marker in source_markers) and source_runtime.is_file():
        return source_runtime

    raise RuntimeError(
        "unable to load packaged shared review runtime or verified source-checkout runtime: "
        f"{vendored}"
    )


def _load_shared_runtime() -> ModuleType:
    path = _shared_runtime_path()
    spec = importlib.util.spec_from_file_location("loop_shared_review_contract_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load packaged shared review runtime: {path}")
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


def _clean_evidence_semantic_errors(name: str, evidence: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if evidence.get("inspection_status") != "complete":
        errors.append(f"{name} CLEAN requires review_evidence.inspection_status=complete")
    unavailable = evidence.get("unable_to_inspect")
    if isinstance(unavailable, list) and unavailable:
        errors.append(f"{name} CLEAN requires no unable_to_inspect surfaces")
    findings = evidence.get("findings")
    if isinstance(findings, dict):
        defects = findings.get("defect")
        if isinstance(defects, list) and defects:
            errors.append(f"{name} CLEAN requires zero defect findings")
    return errors


def _isolation_errors(name: str, lens: dict[str, object]) -> list[str]:
    status = lens.get("isolation_status")
    exception = lens.get("isolation_exception_authorized")
    provenance = lens.get("isolation_exception_provenance")
    exception_identity = lens.get("isolation_exception_change_identity")
    reviewed_identity = lens.get("reviewed_change_identity")
    if type(exception) is not bool:
        return [f"{name}.isolation_exception_authorized must be an explicit boolean"]
    if status == "ISOLATED":
        errors: list[str] = []
        if exception:
            errors.append(f"{name} isolation exception must not be authorized when isolation_status=ISOLATED")
        if provenance is not None:
            errors.append(f"{name} isolated review must not retain isolation_exception_provenance")
        if exception_identity is not None:
            errors.append(f"{name} isolated review must not retain isolation_exception_change_identity")
        return errors
    if status != "NOT_ISOLATED":
        return [f"{name}.isolation_status must be ISOLATED or NOT_ISOLATED before lifecycle readiness"]
    if not exception:
        return [f"{name} NOT_ISOLATED blocks lifecycle readiness without explicit human isolation exception"]
    errors = []
    if not isinstance(provenance, str) or not provenance.strip():
        errors.append(f"{name} isolation exception requires non-empty human authorization provenance")
    if not isinstance(exception_identity, dict) or exception_identity != reviewed_identity:
        errors.append(
            f"{name} isolation exception must be bound to the current reviewed_change_identity"
        )
    return errors


def _lens_errors(
    name: str,
    lens: dict[str, object],
    current_identity: object,
    *,
    current_requirements_ref: object = _UNSET,
    conflict_resolution_occurred: bool | None,
    conflict_resolution_provenance: object,
) -> list[str]:
    errors: list[str] = []
    status = lens.get("status")
    evidence = lens.get("review_evidence")
    reviewed_identity = lens.get("reviewed_change_identity")

    if status != "CLEAN":
        errors.append(f"{name} must be CLEAN before lifecycle readiness")
        return errors
    if not isinstance(evidence, dict):
        errors.append(f"{name} CLEAN requires review_evidence")
        return errors

    errors.extend(_clean_evidence_semantic_errors(name, evidence))
    errors.extend(_isolation_errors(name, lens))

    if not isinstance(reviewed_identity, dict):
        errors.append(f"{name} CLEAN requires reviewed_change_identity")
    elif evidence.get("change_identity") != reviewed_identity:
        errors.append(f"{name} reviewed_change_identity must equal review_evidence.change_identity")

    shared = _load_shared_runtime()
    sha_transition = _identity_shas_changed(evidence.get("change_identity"), current_identity)
    if sha_transition:
        if type(conflict_resolution_occurred) is not bool:
            errors.append(
                f"{name} cannot establish freshness: conflict_resolution_occurred is unknown after identity SHA transition"
            )
            conflict_for_shared = True
        else:
            if not isinstance(conflict_resolution_provenance, str) or not conflict_resolution_provenance.strip():
                errors.append(
                    f"{name} cannot establish freshness: identity SHA transition requires conflict_resolution_provenance"
                )
            conflict_for_shared = conflict_resolution_occurred
    else:
        conflict_for_shared = False

    kwargs: dict[str, object] = {
        "current_identity": current_identity,
        "conflict_resolution_occurred": conflict_for_shared,
    }
    if current_requirements_ref is not _UNSET:
        kwargs["current_requirements_ref"] = current_requirements_ref
    shared_errors = shared.validate_review_evidence(evidence, **kwargs)
    errors.extend(f"{name}: {error}" for error in shared_errors)
    return errors


def _merge_policy_errors(readiness: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if readiness.get("acceptance_criteria_complete") is not True:
        errors.append("acceptance criteria must be complete before lifecycle readiness")

    blockers = readiness.get("accepted_blocking_findings_open")
    if type(blockers) is not int or blockers != 0:
        errors.append("accepted_blocking_findings_open must be integer 0 before lifecycle readiness")

    unresolved = readiness.get("security_sensitive_needs_evidence_unresolved")
    if type(unresolved) is not int or unresolved != 0:
        errors.append("security_sensitive_needs_evidence_unresolved must be integer 0 before lifecycle readiness")

    if readiness.get("required_approvals_present") is not True:
        errors.append("required approvals must be satisfied before lifecycle readiness")

    threads = readiness.get("blocking_threads_open")
    if type(threads) is not int or threads != 0:
        errors.append("blocking_threads_open must be integer 0 before lifecycle readiness")

    if readiness.get("integration_state_valid") is not True:
        errors.append("integration state must be valid before lifecycle readiness")
    if readiness.get("circuit_breaker_active") is not False:
        errors.append("circuit breaker must be explicitly inactive before lifecycle readiness")
    return errors


def validate_lifecycle_state(state: object) -> list[str]:
    """Validate eligibility for READY, COMPLETE, or merge from official loop state."""
    if not isinstance(state, dict):
        return ["lifecycle state must be an object"]

    errors: list[str] = []
    task = _mapping(state.get("task"))
    workspace = _mapping(state.get("workspace"))
    review = _mapping(state.get("review"))
    ci = _mapping(state.get("ci"))
    readiness = _mapping(state.get("merge_readiness"))

    if "requirements_ref" not in task:
        errors.append("task.requirements_ref must be present as an object or null")
    requirements_ref = task.get("requirements_ref", _UNSET)

    third_party = workspace.get("third_party_change_detected", _UNSET)
    if type(third_party) is not bool:
        errors.append("workspace.third_party_change_detected must be an explicit boolean")

    if "conflict_resolution_occurred" not in workspace:
        errors.append("workspace.conflict_resolution_occurred must be present as boolean or null")
    conflict = workspace.get("conflict_resolution_occurred")
    if conflict is not None and type(conflict) is not bool:
        errors.append("conflict_resolution_occurred must be boolean or null")
    provenance = workspace.get("conflict_resolution_provenance")
    if conflict is True and (not isinstance(provenance, str) or not provenance.strip()):
        errors.append("conflict_resolution_occurred=true requires conflict_resolution_provenance")

    current_identity = workspace.get("change_identity")
    shared = _load_shared_runtime()
    identity_errors = shared.validate_change_identity(current_identity)
    errors.extend(f"current {error}" for error in identity_errors)

    current_head = workspace.get("current_head_commit")
    if isinstance(current_identity, dict) and isinstance(current_head, str):
        if not _same_hex(current_identity.get("head_sha"), current_head):
            errors.append("workspace.change_identity.head_sha must equal workspace.current_head_commit")
    elif not isinstance(current_head, str):
        errors.append("workspace.current_head_commit must be present for lifecycle readiness")

    third_party_checked_head = workspace.get("third_party_change_checked_head")
    if not isinstance(third_party_checked_head, str):
        errors.append("workspace.third_party_change_checked_head must be present for lifecycle readiness")
    elif not _same_hex(third_party_checked_head, current_head):
        errors.append(
            "third-party branch-change evidence is stale: third_party_change_checked_head must equal current_head_commit"
        )

    lens_a = _mapping(review.get("lens_a"))
    lens_b = _mapping(review.get("lens_b"))
    if not identity_errors:
        errors.extend(
            _lens_errors(
                "lens_a",
                lens_a,
                current_identity,
                current_requirements_ref=requirements_ref,
                conflict_resolution_occurred=conflict,
                conflict_resolution_provenance=provenance,
            )
        )
        errors.extend(
            _lens_errors(
                "lens_b",
                lens_b,
                current_identity,
                current_requirements_ref=requirements_ref,
                conflict_resolution_occurred=conflict,
                conflict_resolution_provenance=provenance,
            )
        )

    if lens_a.get("status") == "CLEAN" and lens_b.get("status") == "CLEAN":
        a_identity = lens_a.get("reviewed_change_identity")
        b_identity = lens_b.get("reviewed_change_identity")
        if a_identity != b_identity:
            errors.append("both CLEAN lenses must reference the same reviewed_change_identity")

    if third_party is True:
        errors.append("third_party_change_detected blocks lifecycle readiness until re-baselined and re-reviewed")
    elif third_party is not False:
        errors.append("third_party_change_detected must be explicitly false before lifecycle readiness")

    if ci.get("required_checks_green") is not True:
        errors.append("required checks must be green before lifecycle readiness")
    else:
        ci_commit = ci.get("commit")
        if not _same_hex(ci_commit, current_head):
            errors.append("required checks are not authoritative for current head: ci.commit must equal current_head_commit")

    errors.extend(_merge_policy_errors(readiness))
    return errors


def _read_state(path: str) -> object:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    return json.loads(raw)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed READY/COMPLETE lifecycle validation for loop-task-implementer state"
    )
    parser.add_argument(
        "--state",
        required=True,
        help="Path to the official lifecycle state serialized as JSON, or '-' to read JSON from stdin",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        state = _read_state(args.state)
        errors = validate_lifecycle_state(state)
    except SystemExit as exc:
        # Argument handling or an imported runtime must never turn incomplete validation into exit 0.
        print(f"lifecycle validation failed closed: validation runtime exited ({exc.code})", file=sys.stderr)
        return 2
    except Exception as exc:
        # Any ordinary input/runtime failure means lifecycle validity could not be established.
        print(f"lifecycle validation failed closed: {exc}", file=sys.stderr)
        return 2

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
