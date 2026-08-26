"""Fail-closed validation and identity helpers for implementation_plan v1."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping, NamedTuple

from scripts.registry.assessment_target import canonical_payload_digest, normalize_repo_identity
from scripts.registry.semantic_document import is_sha256_digest


PLAN_FIELDS = {
    "plan_set_id",
    "plan_id",
    "title",
    "readiness",
    "assessment_target",
    "target_repo",
    "external_dependencies",
    "source_refs",
    "tasks",
    "execution_waves",
    "sequencing_constraints",
    "verification_gates",
    "traceability",
}
TASK_FIELDS = {
    "task_id",
    "title",
    "task_type",
    "executor",
    "scope",
    "target_paths",
    "acceptance_criteria",
    "dependencies",
    "required_tests",
    "verification",
    "rollout_notes",
    "completion_evidence",
    "source_condition_refs",
    "source_action_refs",
    "estimated_scope",
}
ESTIMATE_FIELDS = {
    "estimate_known",
    "files_upper_bound",
    "changed_lines_upper_bound",
    "confidence",
}
EXECUTION_STATE_FIELDS = {
    "schema_version",
    "plan_id",
    "plan_digest",
    "target_repo",
    "state_generation",
    "current_task_id",
    "task_statuses",
    "completed_evidence_refs",
    "observed_head_revision",
    "blocked_reason",
    "updated_at",
}
READINESS = {"READY", "PARTIAL", "BLOCKED"}
TASK_TYPES = {"code", "config", "schema", "migration", "other"}
ESTIMATE_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
TASK_STATUSES = {"PENDING", "IN_PROGRESS", "COMPLETE", "BLOCKED"}
OFFICIAL_TASK_STATUS_MAP = {
    "NOT_STARTED": "PENDING",
    "BUILDING": "IN_PROGRESS",
    "REVIEWING": "IN_PROGRESS",
    "VALIDATING": "IN_PROGRESS",
    "READY": "IN_PROGRESS",
    "COMPLETE": "COMPLETE",
    "ESCALATED": "BLOCKED",
}
SPECIALIST_ARTIFACTS = {
    "api": "api_design_review_report",
    "database": "database_review_report",
    "security": "security_review_report",
    "performance": "performance_review_report",
    "capacity": "capacity_plan",
    "observability": "observability_review_report",
    "resilience": "resilience_review_report",
    "dependency_upgrade": "dependency_upgrade_report",
}
SHA256 = 64
LOOP_TASK_MAX_FILES = 40
LOOP_TASK_MAX_LINES = 1500


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: object, label: str, errors: list[str], *, allow_empty: bool = True) -> None:
    if not isinstance(value, list) or not all(_non_empty_string(item) for item in value):
        errors.append(f"error: {label} must be a list of non-empty strings")
    elif not allow_empty and not value:
        errors.append(f"error: {label} must not be empty")


def _safe_sorted(values: object) -> list[Any]:
    if not isinstance(values, (list, tuple, set, frozenset)):
        return []
    return sorted(values, key=lambda value: (type(value).__name__, repr(value)))


def derive_plan_set_id(
    change_impact_digest: str,
    system_design_digest: str,
    architecture_review_digest: str,
) -> str:
    """Derive the immutable plan-set identity from the three required upstream digests."""
    source = {
        "architecture_review_digest": architecture_review_digest,
        "change_impact_digest": change_impact_digest,
        "system_design_digest": system_design_digest,
    }
    return "PLANSET-" + canonical_payload_digest(source)[:12]


def derive_plan_id(plan_set_id: str, target_repo: str) -> str:
    """Derive the per-repository plan identity from canonical repository identity."""
    normalized = normalize_repo_identity(target_repo)
    return f"{plan_set_id}-{canonical_payload_digest(normalized)[:8]}"


def source_digest_bundle(label: str) -> dict[str, str]:
    """Return a deterministic three-digest bundle for a named set of upstream sources.

    Lets callers (and tests) exercise plan-identity derivation from a stable label instead of
    full artifact payloads; each digest is namespaced by both its own field name and the label
    so two different labels never collide and the same label always reproduces the same bundle.
    """
    return {
        "change_impact_digest": canonical_payload_digest({"label": label, "source": "change_impact_report"}),
        "system_design_digest": canonical_payload_digest({"label": label, "source": "system_design_spec"}),
        "architecture_review_digest": canonical_payload_digest({"label": label, "source": "architecture_review_report"}),
    }


def derive_plan_ids(source: Mapping[str, str], target_repo: str) -> tuple[str, str]:
    """Return ``(plan_set_id, plan_id)`` for a source digest bundle and target repository."""
    plan_set_id = derive_plan_set_id(**dict(source))
    return plan_set_id, derive_plan_id(plan_set_id, target_repo)


def canonical_plan_digest(plan: Mapping[str, Any]) -> str:
    """Digest the complete canonical plan payload for resume and immutability checks."""
    return canonical_payload_digest(dict(plan))


TASK_CONTRACT_FIELDS = (
    "dependencies",
    "target_paths",
    "acceptance_criteria",
    "required_tests",
    "verification",
    "rollout_notes",
    "completion_evidence",
)


def task_contract_digest(task: Mapping[str, Any]) -> str:
    """Digest the binding contract fields of one plan task.

    Only the fields that determine what Builder actually does (dependencies, target paths,
    acceptance criteria, tests, verification, rollout notes, completion evidence) are covered.
    A plan revision that leaves a task's contract untouched keeps the same digest; a revision
    that changes what the task requires must not be able to reuse a prior remote claim.
    """
    contract = {field: task.get(field) for field in TASK_CONTRACT_FIELDS}
    return canonical_payload_digest(contract)


def execution_identity(
    plan_digest: str,
    task_id: str,
    task_digest: str,
    target_repo: str,
    base_revision: str,
) -> str:
    """Return the SHA-256 collision-safe identity binding one plan task execution.

    ``plan_id`` alone is not sufficient for remote adoption because task contents can change
    while source-derived plan identity remains stable; this identity is therefore derived from
    the full plan digest, the task's own contract digest, the canonical target repository, and
    the authoritative base revision observed immediately before Builder dispatch.
    """
    payload = {
        "plan_digest": plan_digest,
        "task_id": task_id,
        "task_digest": task_digest,
        "target_repo": normalize_repo_identity(target_repo),
        "base_revision": base_revision,
    }
    return canonical_payload_digest(payload)


def execution_branch_name(plan_id: str, task_id: str, identity: str) -> str:
    """Return a deterministic, bounded branch name bound to a full execution identity.

    ``identity`` must be the SHA-256 hex digest from :func:`execution_identity`. The branch name
    embeds a collision-resistant prefix of it purely for legibility; it is never treated as
    sufficient proof of identity by itself — callers must re-read and compare the full identity.
    """
    if not is_sha256_digest(identity):
        raise ValueError("execution_branch_name requires a SHA-256 execution identity")
    safe_plan = "".join(char if char.isalnum() or char in "-_" else "-" for char in plan_id).strip("-")
    safe_task = "".join(char if char.isalnum() or char in "-_" else "-" for char in task_id).strip("-")
    return f"loop-plan/{safe_plan[:48]}/{safe_task[:40]}-{identity[:12]}"


class RemoteWriteDecision(NamedTuple):
    """Outcome of :func:`prepare_remote_write`."""

    status: str
    branch_name: str | None
    identity: str | None = None
    reason: str | None = None
    create_fallback_branch: bool = False


def prepare_remote_write(
    plan: Mapping[str, Any],
    task_id: str,
    *,
    base_revision: str,
    actor: str,
    observed_branch_owner: str | None = None,
) -> RemoteWriteDecision:
    """Decide whether ``actor`` may create or advance the deterministic branch for one task.

    The platform exposes no atomic cross-process lease, so this never claims exactly-once
    dispatch across independent invocations. It only enforces the supported contract: the
    deterministic branch/identity is the collision detector, and this never authorizes a
    random-suffix fallback branch. If the deterministic branch is already observed to be owned
    by a different actor, the caller must block rather than create a second remote write.
    """
    task = next(
        (item for item in plan.get("tasks", []) if isinstance(item, Mapping) and item.get("task_id") == task_id),
        None,
    )
    if task is None:
        return RemoteWriteDecision(
            status="BLOCKED", branch_name=None, reason=f"unknown task_id {task_id}", create_fallback_branch=False
        )
    identity = execution_identity(
        canonical_plan_digest(plan),
        task_id,
        task_contract_digest(task),
        str(plan.get("target_repo")),
        base_revision,
    )
    branch_name = execution_branch_name(str(plan.get("plan_id")), task_id, identity)
    if observed_branch_owner is not None and observed_branch_owner != actor:
        return RemoteWriteDecision(
            status="BLOCKED",
            branch_name=branch_name,
            identity=identity,
            reason="deterministic branch is already claimed by another actor",
            create_fallback_branch=False,
        )
    return RemoteWriteDecision(status="READY", branch_name=branch_name, identity=identity, create_fallback_branch=False)


class PushCollisionDecision(NamedTuple):
    """Outcome of :func:`handle_push_collision`."""

    status: str
    force_push: bool = False
    reason: str | None = None


def handle_push_collision(expected_head: str, actual_head: str) -> PushCollisionDecision:
    """Decide the outcome of a push whose precondition was ``expected_head``.

    Pushes use expected-head/fast-forward semantics only; a peer's non-fast-forward update to
    the remote branch is never force-overwritten.
    """
    if expected_head == actual_head:
        return PushCollisionDecision(status="READY", force_push=False)
    return PushCollisionDecision(
        status="BLOCKED", force_push=False, reason="remote head advanced past the expected precondition"
    )


class RemoteClaimDecision(NamedTuple):
    """Outcome of :func:`reconcile_remote_claim`."""

    status: str
    reuse_existing: bool
    create_new_pr: bool
    reason: str | None = None


def reconcile_remote_claim(
    *,
    execution_identity: str,
    existing_pr: Mapping[str, Any] | None,
) -> RemoteClaimDecision:
    """Decide whether an existing PR may be adopted for this execution identity.

    Adoption requires the existing PR to carry the identical execution identity. A matching
    ``plan_id`` is never sufficient by itself: the task contract, plan revision, target
    repository, and base revision must all match, because task contents can change while
    source-derived plan identity remains stable.
    """
    if existing_pr is None:
        return RemoteClaimDecision(status="READY", reuse_existing=False, create_new_pr=True)
    stored_identity = existing_pr.get("execution_identity") if isinstance(existing_pr, Mapping) else None
    if stored_identity == execution_identity:
        return RemoteClaimDecision(status="READY", reuse_existing=True, create_new_pr=False)
    return RemoteClaimDecision(
        status="BLOCKED",
        reuse_existing=False,
        create_new_pr=False,
        reason="existing PR execution identity does not match this plan/task/base-revision",
    )


def _payload(source: object) -> Mapping[str, Any]:
    if isinstance(source, Mapping) and isinstance(source.get("payload"), Mapping):
        return source["payload"]
    return source if isinstance(source, Mapping) else {}


def _source_digest(source: object) -> str:
    payload = _payload(source)
    target = payload.get("assessment_target") if isinstance(payload, Mapping) else None
    if isinstance(target, Mapping) and isinstance(target.get("source_artifact_digest"), str):
        return target["source_artifact_digest"]
    return canonical_payload_digest(payload)


def _validate_declared_source_digest(source: object, label: str, errors: list[str]) -> None:
    payload = _payload(source)
    target = payload.get("assessment_target")
    if not isinstance(target, Mapping) or "source_artifact_digest" not in target:
        return
    if not is_sha256_digest(target.get("source_artifact_digest")):
        errors.append(f"error: {label}.assessment_target.source_artifact_digest must be a SHA-256 hex digest")


def _source_status(source: object, *, default: str = "UNKNOWN") -> str:
    if not isinstance(source, Mapping):
        return default
    result = source.get("skill_result")
    if isinstance(result, Mapping) and isinstance(result.get("status"), str):
        return result["status"]
    payload = _payload(source)
    decision = payload.get("normalized_decision") if isinstance(payload, Mapping) else None
    if isinstance(decision, Mapping) and isinstance(decision.get("status"), str):
        return decision["status"]
    if isinstance(payload.get("readiness"), str):
        readiness = payload["readiness"].lower()
        return {"ready": "READY", "not ready": "NOT_READY", "conditional": "CONDITIONAL"}.get(readiness, default)
    return default


def _items(source: object, field: str) -> list[Mapping[str, Any]]:
    value = _payload(source).get(field)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _item_ref(item: Mapping[str, Any], prefix: str, index: int) -> str:
    value = item.get("id") or item.get("ref") or item.get("key")
    return f"{prefix}:{value}" if _non_empty_string(value) else f"{prefix}:{index + 1}"


def _task_string_values(task: Mapping[str, Any], field: str) -> list[str]:
    value = task.get(field)
    return [item for item in value if _non_empty_string(item)] if isinstance(value, list) else []


def build_implementation_plan(
    sources: Mapping[str, Any],
    *,
    repository_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic single-repository plan from the required upstream artifacts.

    The planner never invents target paths or silently drops a triggered specialist. Missing
    grounding therefore produces a BLOCKED/PARTIAL plan that the validator can explain.
    """
    errors: list[str] = []
    required = ("system_design_spec", "architecture_review_report", "change_impact_report")
    for name in required:
        if name not in sources:
            errors.append(f"missing required source {name}")
    design = _payload(sources.get("system_design_spec"))
    impact = _payload(sources.get("change_impact_report"))
    target = design.get("assessment_target") if isinstance(design.get("assessment_target"), Mapping) else {}
    impact_target = impact.get("assessment_target") if isinstance(impact.get("assessment_target"), Mapping) else {}
    target_repo = (
        impact.get("target_repo")
        or impact_target.get("repo")
        or target.get("repo")
        or sources.get("target_repo")
    )
    if not _non_empty_string(target_repo):
        errors.append("target repository is missing")
        target_repo = "UNKNOWN"
    normalized_repo = normalize_repo_identity(str(target_repo))
    digests = {
        "change_impact_digest": _source_digest(sources.get("change_impact_report")),
        "system_design_digest": _source_digest(sources.get("system_design_spec")),
        "architecture_review_digest": _source_digest(sources.get("architecture_review_report")),
    }
    plan_set_id = derive_plan_set_id(**digests)
    plan_id = derive_plan_id(plan_set_id, normalized_repo)
    source_refs = [f"{name}:{digest}" for name, digest in (
        ("change_impact_report", digests["change_impact_digest"]),
        ("system_design_spec", digests["system_design_digest"]),
        ("architecture_review_report", digests["architecture_review_digest"]),
    )]
    source_refs = sorted(set(source_refs))
    statuses: dict[str, str] = {
        "system_design": _source_status(sources.get("system_design_spec")),
        "architecture": _source_status(sources.get("architecture_review_report")),
    }
    _validate_declared_source_digest(sources.get("system_design_spec"), "system_design_spec", errors)
    _validate_declared_source_digest(sources.get("architecture_review_report"), "architecture_review_report", errors)
    _validate_declared_source_digest(sources.get("change_impact_report"), "change_impact_report", errors)
    impact_status = _source_status(sources.get("change_impact_report"))
    if impact.get("coverage_status") != "COMPLETE":
        impact_status = "PARTIAL"
    statuses["change_impact"] = impact_status
    impacted_repositories = impact.get("impacted_repositories")
    if isinstance(impacted_repositories, list):
        normalized_repositories = sorted({
            normalize_repo_identity(repository)
            for repository in impacted_repositories
            if _non_empty_string(repository)
        })
        if len(normalized_repositories) > 1:
            errors.append("change impact names multiple repositories; invoke planner once per repository")
        elif normalized_repositories and normalized_repo not in normalized_repositories:
            errors.append("target repository is not in the change impact report's impacted_repositories")
    raw_triggers = impact.get("review_triggers", [])
    triggers: list[str] = []
    if not isinstance(raw_triggers, list):
        errors.append("error: change impact review_triggers must be a list")
    else:
        for item in raw_triggers:
            if not isinstance(item, str) or item not in SPECIALIST_ARTIFACTS:
                errors.append(f"error: unknown or malformed specialist trigger: {item!r}")
            else:
                triggers.append(item)
    specialist_sources = sources.get("specialist_reports")
    if not isinstance(specialist_sources, Mapping):
        specialist_sources = {}
    for trigger in sorted(set(triggers)):
        artifact = SPECIALIST_ARTIFACTS[trigger]
        report = specialist_sources.get(trigger) if trigger in specialist_sources else sources.get(artifact)
        statuses[f"specialist:{trigger}"] = _source_status(report)
        if report is None:
            errors.append(f"triggered specialist {trigger} is missing")
        else:
            _validate_declared_source_digest(report, artifact, errors)
            source_refs.append(f"{artifact}:{_source_digest(report)}")
    source_refs = sorted(set(source_refs))
    target_paths = impact.get("target_paths")
    if (not isinstance(target_paths, list) or not target_paths) and isinstance(repository_evidence, Mapping):
        target_paths = repository_evidence.get("target_paths")
    if not isinstance(target_paths, list):
        target_paths = []
    target_paths = sorted({path for path in target_paths if _non_empty_string(path)})
    if not target_paths:
        errors.append("change impact report has no grounded target_paths")
    required_tests = [test for test in impact.get("required_tests", []) if _non_empty_string(test)] if isinstance(impact.get("required_tests"), list) else []
    conditions: list[str] = []
    actions: list[str] = []
    planning_sources: list[tuple[str, object]] = [
        ("design", sources.get("system_design_spec")),
        ("architecture", sources.get("architecture_review_report")),
        ("impact", sources.get("change_impact_report")),
    ]
    for trigger in sorted(set(triggers)):
        artifact = SPECIALIST_ARTIFACTS[trigger]
        report = specialist_sources.get(trigger) if trigger in specialist_sources else sources.get(artifact)
        planning_sources.append((f"specialist:{trigger}", report))
    for name, source in planning_sources:
        conditions.extend(_item_ref(item, f"{name}-condition", index) for index, item in enumerate(_items(source, "conditions")))
        actions.extend(_item_ref(item, f"{name}-action", index) for index, item in enumerate(_items(source, "required_actions")))
    evidence = repository_evidence or {}
    external_dependencies = evidence.get("external_dependencies") if isinstance(evidence.get("external_dependencies"), list) else []
    external_dependency_statuses = evidence.get("external_dependency_statuses") if isinstance(evidence.get("external_dependency_statuses"), Mapping) else {}
    normalized_external_statuses = {
        normalize_repo_identity(str(repo)): str(status).upper()
        for repo, status in external_dependency_statuses.items()
        if _non_empty_string(repo) and isinstance(status, str)
    }
    estimate = evidence.get("estimated_scope") if isinstance(evidence.get("estimated_scope"), Mapping) else None
    if estimate is None:
        estimate = {"estimate_known": False, "files_upper_bound": 0, "changed_lines_upper_bound": 0, "confidence": "UNKNOWN"}
    tasks: list[dict[str, Any]] = []
    for index, path in enumerate(target_paths):
        task_id = f"TASK-{index + 1:03d}-{canonical_payload_digest({'plan_id': plan_id, 'path': path})[:8]}"
        task_tests = required_tests if index == 0 else []
        tasks.append({
            "task_id": task_id,
            "title": f"Implement changes under {path}",
            "task_type": "code",
            "executor": "loop-task-implementer",
            "scope": f"Implement the approved change impact for target path {path} in {normalized_repo}.",
            "target_paths": [path],
            "acceptance_criteria": [f"Implement the approved behavior for {path}.", *task_tests],
            "dependencies": [tasks[-1]["task_id"]] if tasks else [],
            "required_tests": task_tests,
            "verification": ["Run every required test and repository gate for this task."],
            "rollout_notes": ["Use the repository's existing review, CI, and deployment gates."],
            "completion_evidence": ["Committed diff, focused tests, authoritative CI, and review evidence."],
            "source_condition_refs": conditions,
            "source_action_refs": actions,
            "estimated_scope": dict(estimate),
        })
    readiness = "READY"
    if errors:
        readiness = "BLOCKED"
    elif any(status in {"FAIL", "FAILED", "UNKNOWN", "BLOCKED", "NOT_READY", "PARTIAL"} for status in statuses.values()):
        readiness = "BLOCKED"
    elif external_dependencies and any(
        normalized_external_statuses.get(normalize_repo_identity(str(dependency.get("repo")))) not in {"READY", "COMPLETE", "SUCCESS"}
        for dependency in external_dependencies
        if isinstance(dependency, Mapping) and _non_empty_string(dependency.get("repo"))
    ):
        readiness = "PARTIAL"
    elif not repository_evidence or estimate.get("estimate_known") is not True:
        readiness = "PARTIAL"
    traceability = {
        "condition_coverage": {condition: [task["task_id"] for task in tasks] for condition in conditions},
        "action_coverage": {action: [task["task_id"] for task in tasks] for action in actions},
        "required_test_coverage": {test: [task["task_id"] for task in tasks if test in task["required_tests"]] for test in required_tests},
    }
    # Each task depends on the one before it (see the linear chain built above), so each task
    # must occupy its own wave — putting every task after the first into one shared wave breaks
    # validate_implementation_plan's "a dependency must be in an earlier wave" rule as soon as a
    # plan has 3+ tasks, silently demoting an otherwise-healthy plan from READY to BLOCKED.
    waves = [[task["task_id"]] for task in tasks]
    plan = {
        "plan_set_id": plan_set_id,
        "plan_id": plan_id,
        "title": str(design.get("title") or impact.get("title") or "Implementation plan"),
        "readiness": readiness,
        "assessment_target": dict(impact_target or target),
        "target_repo": normalized_repo,
        "external_dependencies": copy.deepcopy(external_dependencies),
        "source_refs": source_refs,
        "tasks": tasks,
        "execution_waves": waves,
        "sequencing_constraints": ["Tasks execute in deterministic dependency-wave order."],
        "verification_gates": ["Every required test, task verification, and traceability item is satisfied."],
        "traceability": traceability,
    }
    validation_errors = validate_implementation_plan(
        plan,
        source_statuses=statuses,
        source_conditions=conditions,
        source_actions=actions,
        required_tests=required_tests,
    )
    if validation_errors and readiness == "READY":
        plan["readiness"] = "BLOCKED"
    return plan


plan_from_sources = build_implementation_plan
"""Alias for :func:`build_implementation_plan` matching the planner's public contract name."""


def _validate_estimate(
    estimate: object,
    label: str,
    readiness: str,
    errors: list[str],
) -> None:
    if not isinstance(estimate, Mapping):
        errors.append(f"error: {label} must be a mapping")
        return
    unknown = _safe_sorted(set(estimate) - ESTIMATE_FIELDS)
    missing = _safe_sorted(ESTIMATE_FIELDS - set(estimate))
    if unknown:
        errors.append(f"error: {label} contains undeclared fields: {', '.join(map(str, unknown))}")
    if missing:
        errors.append(f"error: {label} missing fields: {', '.join(missing)}")
    known = estimate.get("estimate_known")
    files = estimate.get("files_upper_bound")
    lines = estimate.get("changed_lines_upper_bound")
    confidence = estimate.get("confidence")
    if type(known) is not bool:
        errors.append(f"error: {label}.estimate_known must be boolean")
    for name, value in (("files_upper_bound", files), ("changed_lines_upper_bound", lines)):
        if type(value) is not int or value < 0:
            errors.append(f"error: {label}.{name} must be a non-negative integer")
    if not isinstance(confidence, str) or confidence not in ESTIMATE_CONFIDENCE:
        errors.append(f"error: {label}.confidence is invalid")
    if known is False:
        if files != 0 or lines != 0 or confidence != "UNKNOWN":
            errors.append(f"error: {label} unknown estimates require zero bounds and UNKNOWN confidence")
        if readiness == "READY":
            errors.append(f"error: READY plan cannot contain an unknown estimate at {label}")
    elif known is True:
        if confidence not in {"HIGH", "MEDIUM"}:
            errors.append(f"error: {label} known estimates require HIGH or MEDIUM confidence")
        if isinstance(files, int) and files > LOOP_TASK_MAX_FILES:
            errors.append(f"error: {label} exceeds loop-task hard stop of {LOOP_TASK_MAX_FILES} files")
        if isinstance(lines, int) and lines > LOOP_TASK_MAX_LINES:
            errors.append(f"error: {label} exceeds loop-task hard stop of {LOOP_TASK_MAX_LINES} changed lines")


def _validate_task(task: object, index: int, readiness: str, errors: list[str]) -> tuple[str | None, list[str]]:
    label = f"tasks[{index}]"
    if not isinstance(task, Mapping):
        errors.append(f"error: {label} must be a mapping")
        return None, []
    unknown = _safe_sorted(set(task) - TASK_FIELDS)
    missing = _safe_sorted(TASK_FIELDS - set(task))
    if unknown:
        errors.append(f"error: {label} contains undeclared fields: {', '.join(map(str, unknown))}")
    if missing:
        errors.append(f"error: {label} missing fields: {', '.join(missing)}")
    task_id = task.get("task_id")
    if not _non_empty_string(task_id):
        errors.append(f"error: {label}.task_id must be a non-empty string")
        task_id = None
    for field in ("title", "scope"):
        if not _non_empty_string(task.get(field)):
            errors.append(f"error: {label}.{field} must be a non-empty string")
    if not isinstance(task.get("task_type"), str) or task.get("task_type") not in TASK_TYPES:
        errors.append(f"error: {label}.task_type is invalid")
    if task.get("executor") != "loop-task-implementer":
        errors.append(f"error: {label}.executor must be loop-task-implementer")
    for field in (
        "target_paths", "acceptance_criteria", "dependencies", "required_tests", "verification",
        "rollout_notes", "completion_evidence", "source_condition_refs", "source_action_refs",
    ):
        _string_list(
            task.get(field),
            f"{label}.{field}",
            errors,
            allow_empty=field not in {"target_paths", "acceptance_criteria", "verification", "completion_evidence"},
        )
    paths = task.get("target_paths")
    if isinstance(paths, list):
        for path in paths:
            normalized_path = path.replace("\\", "/").strip() if isinstance(path, str) else ""
            if isinstance(path, str) and (
                path != path.strip()
                or normalized_path.startswith("/")
                or bool(re.match(r"^[A-Za-z]:/", normalized_path))
                or any(part == ".." for part in normalized_path.split("/"))
            ):
                errors.append(f"error: {label}.target_paths must remain inside target_repo")
    _validate_estimate(task.get("estimated_scope"), f"{label}.estimated_scope", readiness, errors)
    dependencies = task.get("dependencies")
    return task_id, [dependency for dependency in dependencies if isinstance(dependency, str)] if isinstance(dependencies, list) else []


def _validate_traceability(
    plan: Mapping[str, Any],
    errors: list[str],
    source_conditions: list[str] | None,
    source_actions: list[str] | None,
    required_tests: list[str] | None,
) -> None:
    traceability = plan.get("traceability")
    if not isinstance(traceability, Mapping):
        errors.append("error: traceability must be a mapping")
        return
    expected = {"condition_coverage", "action_coverage", "required_test_coverage"}
    if set(traceability) != expected:
        errors.append("error: traceability must contain condition_coverage, action_coverage, and required_test_coverage")
        return
    task_items = [task for task in plan.get("tasks", []) if isinstance(task, Mapping)]
    task_ids = {task.get("task_id") for task in task_items}
    expected_conditions = (
        _safe_sorted({value for value in source_conditions if isinstance(value, str)})
        if source_conditions is not None
        else _safe_sorted({ref for task in task_items for ref in _task_string_values(task, "source_condition_refs")})
    )
    expected_actions = (
        _safe_sorted({value for value in source_actions if isinstance(value, str)})
        if source_actions is not None
        else _safe_sorted({ref for task in task_items for ref in _task_string_values(task, "source_action_refs")})
    )
    expected_tests = (
        _safe_sorted({value for value in required_tests if isinstance(value, str)})
        if required_tests is not None
        else _safe_sorted({test for task in task_items for test in _task_string_values(task, "required_tests")})
    )
    for group, sources in (
        ("condition_coverage", expected_conditions),
        ("action_coverage", expected_actions),
        ("required_test_coverage", expected_tests),
    ):
        coverage = traceability.get(group)
        if not isinstance(coverage, Mapping):
            errors.append(f"error: traceability.{group} must be a mapping")
            continue
        for source in sources:
            targets = coverage.get(source)
            if not isinstance(targets, list) or not targets or not all(target in task_ids for target in targets):
                errors.append(f"error: traceability.{group} does not cover {source}")
                continue
            for target in targets:
                task = next(task for task in task_items if task.get("task_id") == target)
                if group == "condition_coverage" and source not in _task_string_values(task, "source_condition_refs"):
                    errors.append(f"error: traceability.{group} maps {source} to a task that does not cite it")
                elif group == "action_coverage" and source not in _task_string_values(task, "source_action_refs"):
                    errors.append(f"error: traceability.{group} maps {source} to a task that does not cite it")
                elif group == "required_test_coverage" and source not in _task_string_values(task, "required_tests"):
                    errors.append(f"error: traceability.{group} maps {source} to a task that does not run it")
        for source in _safe_sorted(set(coverage) - set(sources)):
            errors.append(f"error: traceability.{group} contains undeclared source {source}")


def _validate_source_readiness(plan: Mapping[str, Any], source_statuses: Mapping[str, str], errors: list[str]) -> None:
    if plan.get("readiness") != "READY":
        return
    blocking = {"FAIL", "FAILED", "UNKNOWN", "BLOCKED", "NOT_READY", "PARTIAL"}
    for source, status in source_statuses.items():
        if status in blocking:
            errors.append(f"error: READY plan has blocking source status {source}={status}")


def validate_external_dependency_cycles(
    plan: Mapping[str, Any],
    sibling_plans: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[str]:
    """Reject only cycles that are provable from the available sibling plan set."""
    available: dict[str, Mapping[str, Any]] = {normalize_repo_identity(str(plan.get("target_repo"))): plan}
    if sibling_plans is not None and not isinstance(sibling_plans, Mapping):
        return ["error: sibling_plans must be a mapping"]
    for repo, sibling in (sibling_plans or {}).items():
        if isinstance(sibling, Mapping) and _non_empty_string(repo):
            sibling_repo = sibling.get("target_repo") or repo
            available[normalize_repo_identity(str(sibling_repo))] = sibling
    graph: dict[str, set[str]] = {repo: set() for repo in available}
    for repo, candidate in available.items():
        dependencies = candidate.get("external_dependencies", [])
        if not isinstance(dependencies, list):
            continue
        for dependency in dependencies:
            if not isinstance(dependency, Mapping):
                continue
            target = dependency.get("repo")
            if isinstance(target, str):
                normalized = normalize_repo_identity(target)
                if normalized in available:
                    graph[repo].add(normalized)
    visiting: set[str] = set()
    visited: set[str] = set()
    errors: list[str] = []

    def visit(repo: str) -> None:
        if repo in visiting:
            errors.append("error: external dependency graph contains a provable cross-repository cycle")
            return
        if repo in visited:
            return
        visiting.add(repo)
        for dependency in graph[repo]:
            visit(dependency)
        visiting.remove(repo)
        visited.add(repo)

    for repo in graph:
        visit(repo)
    return sorted(set(errors))


def validate_implementation_plan(
    plan: object,
    *,
    source_statuses: Mapping[str, str] | None = None,
    source_conditions: list[str] | None = None,
    source_actions: list[str] | None = None,
    required_tests: list[str] | None = None,
    sibling_plans: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[str]:
    """Return validation errors; never raise for caller-controlled plan data."""
    errors: list[str] = []
    if not isinstance(plan, Mapping):
        return ["error: implementation_plan must be a mapping"]
    try:
        canonical_payload_digest(dict(plan))
    except (TypeError, ValueError):
        errors.append("error: implementation_plan must contain only finite JSON-compatible values")
    unknown = _safe_sorted(set(plan) - PLAN_FIELDS)
    missing = _safe_sorted(PLAN_FIELDS - set(plan))
    if unknown:
        errors.append(f"error: implementation_plan contains undeclared fields: {', '.join(map(str, unknown))}")
    if missing:
        errors.append(f"error: implementation_plan missing fields: {', '.join(missing)}")
    readiness = plan.get("readiness")
    if not isinstance(readiness, str) or readiness not in READINESS:
        errors.append("error: readiness must be READY, PARTIAL, or BLOCKED")
        readiness = "BLOCKED"
    for field in ("plan_set_id", "plan_id", "title", "target_repo"):
        if not _non_empty_string(plan.get(field)):
            errors.append(f"error: {field} must be a non-empty string")
    if not isinstance(plan.get("assessment_target"), Mapping):
        errors.append("error: assessment_target must be a mapping")
    if _non_empty_string(plan.get("target_repo")):
        normalized = normalize_repo_identity(plan["target_repo"])
        expected_id = derive_plan_id(str(plan.get("plan_set_id")), normalized)
        if plan.get("plan_id") != expected_id:
            errors.append("error: plan_id is not deterministic for plan_set_id and target_repo")
    for field in ("external_dependencies", "source_refs", "tasks", "execution_waves", "sequencing_constraints", "verification_gates"):
        if not isinstance(plan.get(field), list):
            errors.append(f"error: {field} must be a list")
    _string_list(plan.get("source_refs"), "source_refs", errors, allow_empty=False)
    tasks = plan.get("tasks")
    task_ids: list[str] = []
    dependency_map: dict[str, list[str]] = {}
    if isinstance(tasks, list):
        if not tasks and readiness == "READY":
            errors.append("error: READY plan must contain at least one task")
        for index, task in enumerate(tasks):
            task_id, dependencies = _validate_task(task, index, str(readiness), errors)
            if task_id is not None:
                if task_id in task_ids:
                    errors.append(f"error: duplicate task_id {task_id}")
                task_ids.append(task_id)
                dependency_map[task_id] = dependencies
        known = set(task_ids)
        for task_id, dependencies in dependency_map.items():
            for dependency in dependencies:
                if dependency not in known:
                    errors.append(f"error: {task_id} has unknown dependency {dependency}")
                if dependency == task_id:
                    errors.append(f"error: {task_id} cannot depend on itself")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                errors.append("error: task dependency graph contains a cycle")
                return
            if node in visited:
                return
            visiting.add(node)
            for dependency in dependency_map.get(node, []):
                if dependency in known:
                    visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for task_id in task_ids:
            visit(task_id)
    waves = plan.get("execution_waves")
    if isinstance(waves, list):
        wave_positions: dict[str, int] = {}
        for wave_index, wave in enumerate(waves):
            if not isinstance(wave, list):
                errors.append(f"error: execution_waves[{wave_index}] must be a list")
                continue
            for task_id in wave:
                if not isinstance(task_id, str):
                    errors.append(f"error: execution_waves[{wave_index}] task IDs must be strings")
                    continue
                if task_id not in task_ids:
                    errors.append(f"error: execution_waves contains unknown task {task_id}")
                    continue
                if task_id in wave_positions:
                    errors.append(f"error: task {task_id} must appear exactly once in execution_waves")
                wave_positions[task_id] = wave_index
        for task_id in task_ids:
            if task_id not in wave_positions:
                errors.append(f"error: task {task_id} must appear exactly once in execution_waves")
        for task_id, dependencies in dependency_map.items():
            for dependency in dependencies:
                if dependency in wave_positions and task_id in wave_positions and wave_positions[dependency] >= wave_positions[task_id]:
                    errors.append(f"error: {task_id} dependency {dependency} must be in an earlier wave")
    external = plan.get("external_dependencies")
    if isinstance(external, list):
        for index, dependency in enumerate(external):
            if not isinstance(dependency, Mapping):
                errors.append(f"error: external_dependencies[{index}] must be a mapping")
                continue
            for field in ("repo", "required_state_or_artifact", "reason", "evidence_ref"):
                if not _non_empty_string(dependency.get(field)):
                    errors.append(f"error: external_dependencies[{index}].{field} must be non-empty")
    _validate_traceability(
        plan,
        errors,
        source_conditions,
        source_actions,
        required_tests,
    )
    _validate_source_readiness(plan, source_statuses or {}, errors)
    errors.extend(validate_external_dependency_cycles(plan, sibling_plans))
    return sorted(set(errors))


validate_plan = validate_implementation_plan
"""Alias for :func:`validate_implementation_plan` matching the planner's public contract name."""


def validate_plan_set(plans: list[Mapping[str, Any]]) -> list[str]:
    """Validate every plan in a cross-repository plan set sharing one ``plan_set_id``.

    Each plan is validated on its own terms, using every other plan in the set as sibling
    evidence for external-dependency cycle detection (:func:`validate_external_dependency_cycles`).
    A plan whose sibling is not present in ``plans`` keeps its external dependency unresolved
    rather than being treated as satisfied or as a cycle.
    """
    valid_plans = [plan for plan in plans if isinstance(plan, Mapping)]
    if len(valid_plans) != len(plans):
        return ["error: validate_plan_set requires every entry to be a plan mapping"]
    plan_set_ids = {plan.get("plan_set_id") for plan in valid_plans}
    if len(plan_set_ids) > 1:
        return ["error: validate_plan_set requires every plan to share one plan_set_id"]
    siblings_by_repo = {
        normalize_repo_identity(str(plan.get("target_repo"))): plan
        for plan in valid_plans
        if _non_empty_string(plan.get("target_repo"))
    }
    errors: list[str] = []
    for plan in valid_plans:
        own_repo = (
            normalize_repo_identity(str(plan.get("target_repo"))) if _non_empty_string(plan.get("target_repo")) else None
        )
        siblings = {repo: sibling for repo, sibling in siblings_by_repo.items() if repo != own_repo}
        errors.extend(validate_implementation_plan(plan, sibling_plans=siblings))
    return sorted(set(errors))


def validate_plan_execution_state(
    state: object,
    plan: Mapping[str, Any],
    *,
    current_head: str | None,
    minimum_generation: int | None = None,
    authoritative_task_statuses: Mapping[str, str] | None = None,
) -> list[str]:
    """Validate resumable internal state against immutable plan and observed SCM state."""
    errors: list[str] = []
    if not isinstance(state, Mapping):
        return ["error: plan_execution_state must be a mapping"]
    plan_errors = validate_implementation_plan(plan)
    if plan_errors:
        errors.extend(f"error: invalid implementation_plan: {error}" for error in plan_errors)
    unknown = _safe_sorted(set(state) - EXECUTION_STATE_FIELDS)
    missing = _safe_sorted(EXECUTION_STATE_FIELDS - set(state))
    if unknown:
        errors.append("error: plan_execution_state contains undeclared fields: " + ", ".join(map(str, unknown)))
    if missing:
        errors.append("error: plan_execution_state missing fields: " + ", ".join(missing))
    if state.get("schema_version") != 1:
        errors.append("error: plan_execution_state.schema_version must be 1")
    if state.get("plan_id") != plan.get("plan_id"):
        errors.append("error: plan_execution_state.plan_id does not match implementation_plan")
    if state.get("plan_digest") != canonical_plan_digest(plan):
        errors.append("error: plan_execution_state.plan_digest does not match implementation_plan")
    if state.get("target_repo") != plan.get("target_repo"):
        errors.append("error: plan_execution_state.target_repo does not match implementation_plan")
    generation = state.get("state_generation")
    if type(generation) is not int or generation < 0:
        errors.append("error: plan_execution_state.state_generation must be a non-negative integer")
    elif minimum_generation is not None and generation < minimum_generation:
        errors.append("error: plan_execution_state.state_generation is stale")
    statuses = state.get("task_statuses")
    task_ids = {task.get("task_id") for task in plan.get("tasks", []) if isinstance(task, Mapping)}
    if not isinstance(statuses, Mapping) or set(statuses) != task_ids or any(
        not isinstance(status, str) or status not in TASK_STATUSES for status in statuses.values()
    ):
        errors.append("error: plan_execution_state.task_statuses must cover every plan task with a valid status")
    if authoritative_task_statuses is not None:
        expected_statuses: dict[str, str] = {}
        for task_id in task_ids:
            official = authoritative_task_statuses.get(task_id)
            mapped = OFFICIAL_TASK_STATUS_MAP.get(official) if isinstance(official, str) else None
            if mapped is None:
                errors.append(f"error: authoritative task status is missing or invalid for {task_id}")
            else:
                expected_statuses[task_id] = mapped
        if isinstance(statuses, Mapping) and expected_statuses and dict(statuses) != expected_statuses:
            errors.append("error: plan_execution_state.task_statuses disagrees with authoritative task state")
    if current_head is not None and state.get("observed_head_revision") != current_head:
        errors.append("error: plan_execution_state observed head is stale")
    if not isinstance(state.get("completed_evidence_refs"), list) or not all(_non_empty_string(item) for item in state["completed_evidence_refs"]):
        errors.append("error: plan_execution_state.completed_evidence_refs must be a list of strings")
    if state.get("current_task_id") is not None and state.get("current_task_id") not in task_ids:
        errors.append("error: plan_execution_state.current_task_id is not a plan task")
    if isinstance(statuses, Mapping):
        active = [task_id for task_id, status in statuses.items() if status == "IN_PROGRESS"]
        if len(active) > 1:
            errors.append("error: plan_execution_state may have only one IN_PROGRESS task")
        else:
            expected_current = active[0] if active else None
            if state.get("current_task_id") != expected_current:
                errors.append("error: current_task_id must be the IN_PROGRESS task")
    if not _non_empty_string(state.get("updated_at")):
        errors.append("error: plan_execution_state.updated_at must be a non-empty timestamp")
    return sorted(set(errors))


def select_next_task(
    plan: Mapping[str, Any],
    task_statuses: Mapping[str, str] | None = None,
    *,
    state_reconciled: bool = False,
) -> dict[str, Any] | None:
    """Select the first dependency-satisfied task in the earliest incomplete wave.

    Invalid, non-READY, concurrently active, or blocked plans return ``None``. The returned task is
    a deep copy so a caller cannot mutate the canonical plan while normalizing it for execution.
    """
    if plan.get("readiness") != "READY" or validate_implementation_plan(plan):
        return None
    tasks = {task["task_id"]: task for task in plan.get("tasks", []) if isinstance(task, Mapping)}
    statuses = {task_id: "PENDING" for task_id in tasks}
    if task_statuses is not None:
        if not state_reconciled:
            return None
        if not isinstance(task_statuses, Mapping):
            return None
        if set(task_statuses) != set(tasks) or any(
            not isinstance(status, str) or status not in TASK_STATUSES for status in task_statuses.values()
        ):
            return None
        statuses.update({task_id: status for task_id, status in task_statuses.items() if task_id in tasks})
    if any(status == "IN_PROGRESS" for status in statuses.values()):
        return None
    for wave in plan.get("execution_waves", []):
        eligible: list[Mapping[str, Any]] = []
        for task_id in wave:
            task = tasks.get(task_id)
            if task is None or statuses.get(task_id) != "PENDING":
                continue
            dependencies = task.get("dependencies", [])
            if all(statuses.get(dependency) == "COMPLETE" for dependency in dependencies):
                eligible.append(task)
        if eligible:
            return copy.deepcopy(dict(eligible[0]))
        if any(statuses.get(task_id) == "BLOCKED" for task_id in wave):
            return None
    return None


def _authoritative_selection_statuses(
    plan: Mapping[str, Any],
    authoritative_task_statuses: Mapping[str, str] | None,
) -> tuple[dict[str, str] | None, str | None]:
    """Map official per-task statuses to the internal PENDING/IN_PROGRESS/COMPLETE/BLOCKED vocabulary.

    Returns ``(None, None)`` when no authoritative evidence is supplied at all (every task then
    defaults to PENDING inside :func:`select_next_task` — safe because nothing has claimed
    completion yet). Once evidence is supplied it must cover every plan task; a caller cannot
    selectively omit a task to smuggle in an unverified status for it.
    """
    if authoritative_task_statuses is None:
        return None, None
    if not isinstance(authoritative_task_statuses, Mapping):
        return None, "authoritative task statuses must be a mapping"
    task_ids = {task.get("task_id") for task in plan.get("tasks", []) if isinstance(task, Mapping)}
    mapped: dict[str, str] = {}
    for task_id in task_ids:
        official = authoritative_task_statuses.get(task_id)
        status = OFFICIAL_TASK_STATUS_MAP.get(official) if isinstance(official, str) else None
        if status is None:
            return None, f"authoritative task status is missing or invalid for {task_id}"
        mapped[task_id] = status
    return mapped, None


def select_eligible_task(
    plan: Mapping[str, Any],
    authoritative_task_statuses: Mapping[str, str] | None = None,
) -> str | None:
    """Return the ``task_id`` of the earliest dependency-satisfied task, or ``None``.

    ``authoritative_task_statuses`` must use the host's official per-task status vocabulary
    (NOT_STARTED|BUILDING|REVIEWING|VALIDATING|READY|COMPLETE|ESCALATED); a caller's own claim
    about progress is never trusted directly — see :func:`select_task`.
    """
    result = select_task(plan, authoritative_task_statuses=authoritative_task_statuses)
    task = result["task"]
    return task.get("task_id") if task is not None else None


def select_task(
    plan: Mapping[str, Any],
    *,
    authoritative_task_statuses: Mapping[str, str] | None = None,
    scm_evidence: Mapping[str, Mapping[str, Any]] | None = None,
    repository_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Select one eligible plan task from authoritative task state, never a caller's own claim.

    ``authoritative_task_statuses`` must come from the host's official per-task state (e.g. the
    per-task ``status`` field in reference/state-schema.yaml), not from an unreconciled
    ``plan_execution_state`` checkpoint — a checkpoint is an index, not authority, and a caller
    asserting a task COMPLETE can never by itself unblock the next task. Omit it only when no
    plan task has ever been dispatched, so every task safely defaults to PENDING.

    Also fails closed (``BLOCKED``) instead of dispatching a duplicate Builder run when SCM
    evidence shows an existing active branch or pull request for a candidate task, and fails
    closed requesting a replan when a candidate task's target paths are no longer present in the
    repository snapshot. Never mutates the canonical plan.
    """
    task_statuses, error = _authoritative_selection_statuses(plan, authoritative_task_statuses)
    if error is not None:
        return {"status": "BLOCKED", "task": None, "reason": error}
    task = select_next_task(plan, task_statuses, state_reconciled=task_statuses is not None)
    if task is None:
        return {"status": "BLOCKED", "task": None, "reason": "no eligible task"}
    task_id = task.get("task_id")
    evidence = (scm_evidence or {}).get(task_id) if isinstance(scm_evidence, Mapping) else None
    if isinstance(evidence, Mapping) and any(evidence.get(key) for key in ("active_branch", "active_pr")):
        return {
            "status": "BLOCKED",
            "task": None,
            "reason": f"task {task_id} already has an active branch or pull request",
        }
    if isinstance(repository_snapshot, Mapping) and isinstance(repository_snapshot.get("paths"), list):
        known_paths = repository_snapshot["paths"]
        missing = [path for path in task.get("target_paths", []) if path not in known_paths]
        if missing:
            return {
                "status": "BLOCKED",
                "task": None,
                "reason": f"task {task_id} target paths are stale ({', '.join(missing)}); replan required",
            }
    return {"status": "READY", "task": task, "reason": None}


def normalize_plan_task(task: Mapping[str, Any], *, target_repo: str | None = None) -> dict[str, Any]:
    """Adapt one v1 plan task to the legacy loop-task internal task shape."""
    return {
        "task_id": task["task_id"],
        "scope": task["scope"],
        "acceptance_criteria": list(task["acceptance_criteria"]),
        "request": task["title"],
        "repo_root": target_repo,
        "target": list(task["target_paths"]),
        "level_hint": task["task_type"],
        "specialist_inputs": [*task.get("source_condition_refs", []), *task.get("source_action_refs", [])],
        "test_framework_hint": None,
        "run_tests": list(task["required_tests"]),
        "max_files_per_run": task["estimated_scope"]["files_upper_bound"],
        "deadline": None,
        "session_token_budget": None,
        "output_dir": None,
    }


def normalize_input(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize loop-task-implementer input, preserving legacy behavior unchanged.

    A legacy ``implementation_task`` input (no ``implementation_plan`` key) passes through
    unchanged. An ``implementation_plan`` input is validated and normalized to exactly one
    eligible task in the legacy shape. Task selection is driven only by ``raw["authoritative_task_statuses"]``
    — the host's official per-task state — never by the raw ``plan_execution_state`` checkpoint,
    which is advisory and used here only to label the returned task's ``plan_context``; a caller
    cannot promote a task to complete just by asserting so in that checkpoint. The canonical plan
    itself is never mutated, and no plan field can grant merge or other authority beyond what the
    legacy task schema already carries.
    """
    if not isinstance(raw, Mapping):
        return {"status": "BLOCKED", "reason": "input must be a mapping"}
    plan = raw.get("implementation_plan")
    if plan is None:
        return dict(raw)
    if not isinstance(plan, Mapping) or plan.get("readiness") != "READY":
        return {"status": "BLOCKED", "reason": "implementation_plan is not a valid READY plan"}
    # Full schema/DAG/traceability validation happens once, inside select_task -> select_next_task
    # -> validate_implementation_plan; re-running it here first would validate the same immutable
    # plan twice on every task-selection call for no functional benefit.
    authoritative_task_statuses = raw.get("authoritative_task_statuses")
    result = select_task(
        plan,
        authoritative_task_statuses=authoritative_task_statuses if isinstance(authoritative_task_statuses, Mapping) else None,
        scm_evidence=raw.get("scm_evidence"),
        repository_snapshot=raw.get("repository_snapshot"),
    )
    if result["status"] != "READY" or result["task"] is None:
        return {"status": "BLOCKED", "reason": result.get("reason") or "no eligible plan task"}
    normalized = normalize_plan_task(result["task"], target_repo=plan.get("target_repo"))
    state = raw.get("plan_execution_state")
    state = state if isinstance(state, Mapping) else {}
    normalized["plan_context"] = {
        "plan_id": plan.get("plan_id"),
        "plan_digest": canonical_plan_digest(plan),
        "source_plan_task_id": result["task"].get("task_id"),
        "state_generation": state.get("state_generation"),
    }
    return normalized


def initial_plan_execution_state(
    plan: Mapping[str, Any],
    *,
    current_head: str | None,
    updated_at: str,
) -> dict[str, Any]:
    """Create a generation-zero internal checkpoint without changing the canonical plan."""
    task_ids = [task["task_id"] for task in plan.get("tasks", []) if isinstance(task, Mapping)]
    return {
        "schema_version": 1,
        "plan_id": plan.get("plan_id"),
        "plan_digest": canonical_plan_digest(plan),
        "target_repo": plan.get("target_repo"),
        "state_generation": 0,
        "current_task_id": None,
        "task_statuses": {task_id: "PENDING" for task_id in task_ids},
        "completed_evidence_refs": [],
        "observed_head_revision": current_head,
        "blocked_reason": None,
        "updated_at": updated_at,
    }


def reconcile_plan_state(*, plan_digest: str, state: Mapping[str, Any]) -> dict[str, Any]:
    """Cheap fail-closed guard: block resume immediately on a stale checkpoint plan digest.

    Callers run this before the full :func:`reconcile_plan_execution_state` reconciliation,
    which additionally requires the complete immutable plan and authoritative task state. The
    checkpoint is advisory unless it was produced against the current plan; a mismatched digest
    always blocks rather than resuming against a plan the checkpoint was never validated for.
    """
    if not isinstance(state, Mapping) or state.get("plan_digest") != plan_digest:
        return {"status": "BLOCKED", "reason": "plan_execution_state.plan_digest does not match implementation_plan"}
    return {"status": "READY", "reason": None}


def merge_plan_state(current: Mapping[str, Any], incoming: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return whichever of two internal checkpoints has the higher ``state_generation``.

    A stale writer's checkpoint — one with an equal or lower generation — can never overwrite
    newer state; ties are resolved in favor of ``current`` so a duplicate write is a no-op.
    """
    current_generation = current.get("state_generation") if isinstance(current, Mapping) else None
    incoming_generation = incoming.get("state_generation") if isinstance(incoming, Mapping) else None
    if isinstance(incoming_generation, int) and (
        not isinstance(current_generation, int) or incoming_generation > current_generation
    ):
        return incoming
    return current


def reconcile_plan_execution_state(
    state: object,
    plan: Mapping[str, Any],
    *,
    authoritative_task_statuses: Mapping[str, str],
    current_head: str | None,
    completed_evidence_refs: list[str] | None = None,
    minimum_generation: int | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Reconcile advisory checkpoint data to official task state and current SCM head."""
    if plan.get("readiness") != "READY":
        return None, ["error: implementation_plan must be READY before execution-state reconciliation"]
    if not isinstance(authoritative_task_statuses, Mapping):
        return None, ["error: authoritative task statuses must be a mapping"]
    errors = validate_plan_execution_state(
        state,
        plan,
        current_head=current_head,
        minimum_generation=minimum_generation,
    )
    expected_statuses = {
        task.get("task_id"): OFFICIAL_TASK_STATUS_MAP.get(authoritative_task_statuses.get(task.get("task_id")))
        for task in plan.get("tasks", [])
        if isinstance(task, Mapping)
    }
    if any(not task_id or status is None for task_id, status in expected_statuses.items()):
        errors.append("error: authoritative task statuses do not cover every plan task")
    if errors or not isinstance(state, Mapping):
        return None, errors
    normalized = copy.deepcopy(dict(state))
    normalized["task_statuses"] = {
        task_id: OFFICIAL_TASK_STATUS_MAP[authoritative_task_statuses[task_id]]
        for task_id in normalized["task_statuses"]
    }
    normalized["current_task_id"] = next(
        (task_id for task_id, status in normalized["task_statuses"].items() if status == "IN_PROGRESS"),
        None,
    )
    normalized["completed_evidence_refs"] = sorted(
        {ref for ref in (completed_evidence_refs or []) if _non_empty_string(ref)}
    )
    normalized["observed_head_revision"] = current_head
    return normalized, []


def advance_plan_execution_state(
    state: object,
    plan: Mapping[str, Any],
    *,
    expected_generation: int,
    authoritative_task_statuses: Mapping[str, str],
    current_head: str | None,
    updated_at: str,
    completed_evidence_refs: list[str] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Advance one checkpoint generation; stale writers cannot overwrite newer state."""
    if not isinstance(state, Mapping) or state.get("state_generation") != expected_generation:
        return None, ["error: plan_execution_state generation compare-and-swap failed"]
    normalized, errors = reconcile_plan_execution_state(
        state,
        plan,
        authoritative_task_statuses=authoritative_task_statuses,
        current_head=current_head,
        completed_evidence_refs=completed_evidence_refs,
        minimum_generation=expected_generation,
    )
    if errors or normalized is None:
        return None, errors
    normalized["state_generation"] = expected_generation + 1
    normalized["updated_at"] = updated_at
    return normalized, []


class SkillResult(NamedTuple):
    """The subset of the shared result envelope that carries execution status."""

    status: str


class FinalizedPlan(NamedTuple):
    """Result of :func:`finalize_plan`: the plan payload plus its execution-status envelope."""

    payload: Mapping[str, Any]
    skill_result: SkillResult


_READINESS_TO_STATUS = {"READY": "SUCCESS", "PARTIAL": "PARTIAL", "BLOCKED": "BLOCKED"}


def finalize_plan(plan: object) -> FinalizedPlan:
    """Attach explicit execution-status semantics to a built/validated plan.

    A plan's ``readiness`` is a property of the proposed implementation, not of the planner's
    own execution: READY maps to SUCCESS, PARTIAL to PARTIAL, and BLOCKED (or a plan that fails
    validation while claiming READY) to BLOCKED. ``FAILED`` is reserved for the planner's own
    internal errors — a non-mapping input or schema corruption — never for a plan that validly
    says implementation is blocked.
    """
    if not isinstance(plan, Mapping):
        return FinalizedPlan(payload={}, skill_result=SkillResult(status="FAILED"))
    readiness = plan.get("readiness")
    errors = validate_implementation_plan(plan)
    if errors and readiness == "READY":
        readiness = "BLOCKED"
    status = _READINESS_TO_STATUS.get(readiness) if isinstance(readiness, str) else None
    if status is None:
        return FinalizedPlan(payload=dict(plan), skill_result=SkillResult(status="FAILED"))
    payload = dict(plan)
    payload["readiness"] = readiness
    return FinalizedPlan(payload=payload, skill_result=SkillResult(status=status))


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_nonfinite_json(value: str) -> object:
    raise ValueError(f"non-finite JSON value is not allowed: {value}")


def _load_json(path: Path) -> object:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_object_keys,
        parse_constant=_reject_nonfinite_json,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate implementation_plan v1 or plan_execution_state")
    parser.add_argument("path", type=Path)
    parser.add_argument("--execution-state", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--current-head")
    args = parser.parse_args()
    try:
        value = _load_json(args.path)
        if args.execution_state:
            if args.plan is None:
                parser.error("--plan is required with --execution-state")
            errors = validate_plan_execution_state(
                value,
                _load_json(args.plan),
                current_head=args.current_head,
            )
        else:
            errors = validate_implementation_plan(value)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: unable to load validation input: {exc}")
        return 2
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
