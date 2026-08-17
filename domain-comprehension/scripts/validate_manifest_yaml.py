#!/usr/bin/env python3
"""Validate domain-comprehension manifest.yaml (schema_version 2)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised when PyYAML missing
    yaml = None  # type: ignore

SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = frozenset({2})

PHASE_KEYS = frozenset(
    {
        "session_0",
        "session_0b",
        "p0",
        "p0_25",
        "p0_5",
        "p1",
        "p2",
        "p2b",
        "p3",
        "p3b",
        "p4",
        "p5",
    }
)

PHASE_STATUS = frozenset({"pending", "in_progress", "complete", "skipped"})
ENGAGEMENT_STATUS = frozenset({"IN_PROGRESS", "FIRST_PASS_COMPLETE"})
ARTIFACT_STATUS = frozenset({"ok", "stub", "missing", "stale", "waived", "n_a"})
DIAGRAM_STATUS = frozenset({"pending", "ok", "waived", "n_a"})
QUESTION_STATUS = frozenset({"DRAFT", "PARTIAL", "COMPLETE", "UNKNOWN"})
CONFIDENCE = frozenset({"HIGH", "MEDIUM", "LOW", "UNKNOWN"})
DISCOVERY_BUDGET_PROFILES = frozenset({"QUICK", "FULL", "DELTA", "ADD_REPO", "CUSTOM"})
DISCOVERY_BUDGET_COUNTERS = ("repositories", "search_queries", "deep_file_reads")
# Mirrors domain-model-contract.yaml discovery_budget.default_limits. Non-CUSTOM profiles must
# persist exactly these ceilings so a FULL run cannot silently keep QUICK budgets.
DISCOVERY_BUDGET_DEFAULT_LIMITS: dict[str, dict[str, int]] = {
    "QUICK": {"repositories": 12, "search_queries": 80, "deep_file_reads": 60},
    "FULL": {"repositories": 50, "search_queries": 400, "deep_file_reads": 300},
    "DELTA": {"repositories": 20, "search_queries": 160, "deep_file_reads": 120},
    "ADD_REPO": {"repositories": 20, "search_queries": 160, "deep_file_reads": 120},
}
DISCOVERY_BEARING_PHASES = frozenset(
    {
        "session_0",
        "session_0b",
        "p0",
        "p0_25",
        "p0_5",
        "p1",
        "p2",
        "p2b",
        "p3",
        "p3b",
        "p4",
        "p5",
    }
)
REQUIRED_MACHINE_ARTIFACT_IDS = frozenset(
    {
        "api_event_schema",
        "data_ownership_graph",
        "dependency_graph_machine",
        "capability_traceability",
    }
)
REPO_CLASSIFICATION = frozenset(
    {
        "application",
        "library",
        "sdk",
        "shared_model",
        "infrastructure",
        "schema",
        "configuration",
        "tooling",
        "documentation",
        "experimental",
        "archived",
    }
)
REPO_INVENTORY = frozenset({"pending", "complete"})
REPO_UNDERSTAND = frozenset({"pending", "ok", "failed", "skipped"})
REPO_DEEP_DIVE = frozenset({"pending", "complete", "skipped"})

REQUIRED_TOP = (
    "schema_version",
    "engagement",
    "phases",
    "artifacts",
    "diagrams",
    "five_questions",
    "repos",
    "runtime_validation",
    "overall_confidence",
    "evidence_summary",
)

REQUIRED_ENGAGEMENT = (
    "domain_name",
    "workspace_root",
    "map_file",
    "status",
    "last_updated",
    "last_phase_completed",
    "next_action",
)

EVIDENCE_SUMMARY_KEYS = (
    "repos_scanned",
    "repos_in_scope",
    "files_inspected",
    "runtime_edges_confirmed",
    "events_verified",
    "apis_verified",
    "unknowns_count",
    "omissions_count",
    "last_updated",
)

EXEC_SUMMARY_REQUIRED_SECTIONS = (
    "## Evidence summary",
    "## Engineering Leader Summary",
    "## Section confidences",
)

RUNTIME_VALIDATION_HEADING = "runtime validation"
E2E_FLOW_RUNTIME_HEADING = "runtime validation"
MERGE_CONFLICTS_HEADING = "## merge conflicts"
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[/\\]")
DISTRIBUTED_ARTIFACT_IDS = frozenset({"memory_bank_export"})


def _relative_path_error(value: Any, label: str) -> str | None:
    """Return an error when a manifest-controlled path can escape its intended root."""
    if not isinstance(value, str) or not value.strip():
        return f"{label} must be a non-empty relative path"
    raw = value.strip()
    normalized = raw.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if normalized.startswith("/") or WINDOWS_ABSOLUTE.match(raw) or candidate.is_absolute():
        return f"{label} must be a relative path with no '..' segments: {raw}"
    if ".." in candidate.parts:
        return f"{label} must be a relative path with no '..' segments: {raw}"
    return None


def _artifact_root_error(value: Any) -> str | None:
    """Validate a persisted artifact root without stranding legacy safe-relative engagements.

    New domain-comprehension runs are required by workflow to write below ``docs/``. The manifest
    validator remains backward-compatible with older safe relative roots so RESUME and
    COMPLIANCE_RETROFIT can migrate them instead of rejecting them before they can be read.
    """
    return _relative_path_error(value, "engagement.artifact_root")


def _resolve_effective_root(workspace_root: Path, engagement: Any) -> tuple[Path, list[str]]:
    """Resolve where phase deliverables actually live."""
    if not isinstance(engagement, dict):
        return workspace_root, []
    artifact_root = engagement.get("artifact_root")
    if not artifact_root:
        return workspace_root, []
    error = _artifact_root_error(artifact_root)
    if error:
        return workspace_root, [error]
    normalized = str(artifact_root).replace("\\", "/")
    return workspace_root / Path(normalized), []


def _load_yaml(path: Path) -> tuple[Any, list[str]]:
    if yaml is None:
        return None, ["PyYAML is required — pip install PyYAML"]
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        return None, [f"cannot read {path}: {exc}"]
    except yaml.YAMLError as exc:
        return None, [f"invalid YAML in {path}: {exc}"]
    if data is None:
        return None, ["manifest is empty"]
    if not isinstance(data, dict):
        return None, ["manifest root must be a mapping"]
    return data, []


def _validate_phase_entry(key: str, value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"phases.{key} must be an object"]
    status = value.get("status")
    if status not in PHASE_STATUS:
        errors.append(f"phases.{key}.status must be one of {sorted(PHASE_STATUS)}")
    if status == "skipped" and not value.get("skip_reason"):
        errors.append(f"phases.{key}.skip_reason required when status=skipped")
    completed_at = value.get("completed_at")
    if completed_at is not None and not isinstance(completed_at, str):
        errors.append(f"phases.{key}.completed_at must be a string or null")
    if status == "complete" and not completed_at:
        errors.append(f"phases.{key}.completed_at required when status=complete")
    return errors


def _discovery_budget_required(phases: Any, *, strict: bool) -> bool:
    """Budget is required under --strict or once any discovery-bearing phase has started."""
    if strict:
        return True
    if not isinstance(phases, dict):
        return False
    for key in DISCOVERY_BEARING_PHASES:
        entry = phases.get(key)
        if isinstance(entry, dict) and entry.get("status") in ("in_progress", "complete"):
            return True
    return False


def _validate_discovery_budget(value: Any, *, required: bool = False) -> list[str]:
    """Validate schema-v2 discovery-budget machine state.

    Absence is allowed only for untouched legacy schema-v2 engagements that have not started
    discovery and are not under --strict. New runs create it from the template; RESUME must
    backfill it before performing new discovery.
    """
    if value is None:
        if required:
            return ["discovery_budget is required once discovery has started or under --strict"]
        return []
    if not isinstance(value, dict):
        return ["discovery_budget must be an object"]

    errors: list[str] = []
    profile = value.get("profile")
    if profile not in DISCOVERY_BUDGET_PROFILES:
        errors.append(
            f"discovery_budget.profile must be one of {sorted(DISCOVERY_BUDGET_PROFILES)}"
        )

    limits = value.get("limits")
    consumed = value.get("consumed")
    for label, block, allow_zero in (
        ("limits", limits, False),
        ("consumed", consumed, True),
    ):
        if not isinstance(block, dict):
            errors.append(f"discovery_budget.{label} must be an object")
            continue
        for key in DISCOVERY_BUDGET_COUNTERS:
            counter = block.get(key)
            if not isinstance(counter, int) or isinstance(counter, bool):
                errors.append(f"discovery_budget.{label}.{key} must be an integer")
                continue
            if allow_zero:
                if counter < 0:
                    errors.append(f"discovery_budget.{label}.{key} must be >= 0")
            elif counter <= 0:
                errors.append(f"discovery_budget.{label}.{key} must be > 0")

    if isinstance(limits, dict) and profile in DISCOVERY_BUDGET_DEFAULT_LIMITS:
        expected = DISCOVERY_BUDGET_DEFAULT_LIMITS[profile]
        for key in DISCOVERY_BUDGET_COUNTERS:
            limit = limits.get(key)
            if (
                isinstance(limit, int)
                and not isinstance(limit, bool)
                and limit != expected[key]
            ):
                errors.append(
                    f"discovery_budget.limits.{key} must equal {expected[key]} for profile {profile}"
                )

    if isinstance(limits, dict) and isinstance(consumed, dict):
        for key in DISCOVERY_BUDGET_COUNTERS:
            limit = limits.get(key)
            used = consumed.get(key)
            if (
                isinstance(limit, int)
                and not isinstance(limit, bool)
                and isinstance(used, int)
                and not isinstance(used, bool)
                and used > limit
            ):
                errors.append(
                    f"discovery_budget.consumed.{key} exceeds configured limit ({used} > {limit})"
                )
    return errors


def _validate_strict_completion_artifacts(artifacts: Any) -> list[str]:
    """FIRST_PASS_COMPLETE under --strict requires current PRD + machine artifact rows."""
    errors: list[str] = []
    if not isinstance(artifacts, list):
        return ["strict: artifacts must be an array"]

    by_id: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            by_id[item["id"]] = item

    prd = by_id.get("prd")
    if prd is None:
        errors.append("strict: required artifact prd is missing")
    else:
        if prd.get("required") is not True:
            errors.append("strict: artifact prd must have required=true")
        if prd.get("status") != "ok":
            errors.append(
                f"strict: artifact prd must have status=ok for current-state completion "
                f"(got {prd.get('status')!r}; waived/stale/n_a are not allowed)"
            )

    for artifact_id in sorted(REQUIRED_MACHINE_ARTIFACT_IDS):
        row = by_id.get(artifact_id)
        if row is None:
            errors.append(f"strict: required machine artifact {artifact_id} is missing")
            continue
        if row.get("required") is not True:
            errors.append(f"strict: machine artifact {artifact_id} must have required=true")
        status = row.get("status")
        if status not in ("ok", "waived"):
            errors.append(
                f"strict: machine artifact {artifact_id} status must be ok or waived (got {status!r})"
            )
    return errors


def _validate_artifact_list(items: Any, label: str, status_set: frozenset[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(items, list):
        return [f"{label} must be an array"]
    seen_ids: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"{label}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        elif item_id in seen_ids:
            errors.append(f"duplicate {label} id: {item_id}")
        else:
            seen_ids.add(item_id)

        path_error = _relative_path_error(item.get("path"), f"{prefix}.path")
        if path_error:
            errors.append(path_error)

        phase = item.get("phase")
        if not isinstance(phase, str) or not phase.strip():
            errors.append(f"{prefix}.phase must be a non-empty string")
        elif phase not in PHASE_KEYS:
            errors.append(f"{prefix}.phase unknown: {phase}")

        status = item.get("status")
        if status not in status_set:
            errors.append(f"{prefix}.status must be one of {sorted(status_set)}")
        if label == "artifacts":
            if not isinstance(item.get("required"), bool):
                errors.append(f"{prefix}.required must be a boolean")
            if status == "stale" and item_id != "prd":
                errors.append(f"{prefix}.status=stale is only valid for artifact id 'prd'")
    return errors


def _validate_five_questions(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["five_questions must be an object"]
    for key in ("q1", "q2", "q3", "q4", "q5"):
        entry = value.get(key)
        if not isinstance(entry, dict):
            errors.append(f"five_questions.{key} must be an object")
            continue
        if entry.get("status") not in QUESTION_STATUS:
            errors.append(f"five_questions.{key}.status invalid")
        if entry.get("confidence") not in CONFIDENCE:
            errors.append(f"five_questions.{key}.confidence invalid")
    return errors


def _validate_repos(repos: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(repos, list):
        return ["repos must be an array"]
    for index, item in enumerate(repos):
        prefix = f"repos[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not isinstance(item.get("name"), str) or not str(item.get("name")).strip():
            errors.append(f"{prefix}.name must be a non-empty string")
        classification = item.get("classification")
        if classification is not None and classification not in REPO_CLASSIFICATION:
            errors.append(f"{prefix}.classification invalid: {classification}")
        for field, allowed in (
            ("inventory", REPO_INVENTORY),
            ("understand", REPO_UNDERSTAND),
            ("deep_dive", REPO_DEEP_DIVE),
        ):
            field_value = item.get(field)
            if field_value is not None and field_value not in allowed:
                errors.append(f"{prefix}.{field} invalid: {field_value}")
    return errors


def _validate_evidence_summary(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["evidence_summary must be an object"]
    for key in EVIDENCE_SUMMARY_KEYS:
        if key not in value:
            errors.append(f"evidence_summary missing field: {key}")
    for key in EVIDENCE_SUMMARY_KEYS:
        if key == "last_updated":
            if value.get(key) is not None and not isinstance(value.get(key), str):
                errors.append("evidence_summary.last_updated must be a string")
            continue
        if key in value and not isinstance(value[key], int):
            errors.append(f"evidence_summary.{key} must be an integer")
        elif key in value and value[key] < 0:
            errors.append(f"evidence_summary.{key} must be >= 0")
    return errors


def _file_contains_heading(path: Path, heading_substring: str) -> bool:
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return heading_substring.lower() in text


def _validate_exec_summary_content(exec_summary_path: Path) -> list[str]:
    errors: list[str] = []
    if not exec_summary_path.is_file():
        return [f"check-content: missing {exec_summary_path.name}"]
    try:
        text = exec_summary_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"check-content: cannot read {exec_summary_path.name}: {exc}"]
    for section in EXEC_SUMMARY_REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"check-content: EXEC_SUMMARY.md missing section {section}")
    return errors


def _validate_p2b_runtime_gate(
    workspace_root: Path,
    *,
    map_file: str,
    phases: dict[str, Any] | None,
    runtime_validation: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(phases, dict):
        return errors
    p2b = phases.get("p2b")
    if not isinstance(p2b, dict) or p2b.get("status") != "complete":
        return errors
    if isinstance(runtime_validation, dict) and runtime_validation.get("skipped"):
        return errors

    map_path = workspace_root / map_file if map_file else None
    e2e_path = workspace_root / "E2E_FLOW.md"
    map_has_runtime = map_path is not None and _file_contains_heading(map_path, RUNTIME_VALIDATION_HEADING)
    e2e_has_runtime = _file_contains_heading(e2e_path, E2E_FLOW_RUNTIME_HEADING)

    if map_has_runtime:
        return errors
    if e2e_has_runtime and map_path is not None and map_path.is_file():
        try:
            map_text = map_path.read_text(encoding="utf-8").lower()
        except OSError:
            map_text = ""
        if "e2e_flow.md" in map_text:
            return errors
        errors.append(
            "check-content: P2b complete — map must link to E2E_FLOW.md when runtime table is in supplement"
        )
        return errors

    errors.append(
        "check-content: P2b complete — need map § Runtime validation or E2E_FLOW.md § Runtime validation"
    )
    return errors


def _validate_merge_conflicts_gate(
    workspace_root: Path,
    *,
    phases: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    risk_map_path = workspace_root / "RISK_MAP.md"
    if not risk_map_path.is_file():
        return errors
    try:
        text = risk_map_path.read_text(encoding="utf-8")
    except OSError:
        return errors

    in_section = False
    header_seen = False
    status_index: int | None = None
    has_open_conflict = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped.lower().startswith(MERGE_CONFLICTS_HEADING)
            header_seen = False
            status_index = None
            continue
        if not in_section or not stripped.startswith("|"):
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]

        if not header_seen:
            header_seen = True
            lowered = [c.lower() for c in cells]
            if "status" not in lowered:
                in_section = False
                continue
            status_index = lowered.index("status")
            continue

        if set(stripped.strip("|").replace(" ", "")) <= {"-", ":"}:
            continue

        if status_index is None or len(cells) <= status_index:
            continue

        cell_value = cells[status_index].strip().strip("`*").strip()
        if cell_value.lower().startswith("status:"):
            cell_value = cell_value[len("status:") :].strip()
        if cell_value.lower() == "open":
            has_open_conflict = True

    if not has_open_conflict or not isinstance(phases, dict):
        return errors

    for key in ("p0", "p1"):
        entry = phases.get(key)
        if isinstance(entry, dict) and entry.get("status") == "complete":
            errors.append(
                f"check-content: RISK_MAP.md has an open Merge Conflicts row — phases.{key} must not be complete"
            )
    return errors


def _validate_api_tooling_content(
    workspace_root: Path,
    *,
    artifacts: list[Any] | None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifacts, list):
        return errors
    artifact = next(
        (a for a in artifacts if isinstance(a, dict) and a.get("id") == "api_tooling_export"),
        None,
    )
    if artifact is None or artifact.get("status") != "ok":
        return errors

    collection_path = workspace_root / "postman" / "postman_collection.json"
    if not collection_path.is_file():
        errors.append(
            "check-content: api_tooling_export marked ok but postman/postman_collection.json is missing"
        )
        return errors
    try:
        with collection_path.open(encoding="utf-8") as handle:
            collection = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"check-content: postman/postman_collection.json invalid JSON: {exc}")
        return errors
    if not isinstance(collection, dict) or "info" not in collection or "item" not in collection:
        errors.append("check-content: postman/postman_collection.json missing required 'info'/'item' keys")
    return errors


def validate_manifest(
    data: dict[str, Any],
    *,
    workspace_root: Path | None = None,
    strict: bool = False,
    check_content: bool = False,
) -> list[str]:
    errors: list[str] = []

    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(f"schema_version must be one of {sorted(SUPPORTED_SCHEMA_VERSIONS)}")

    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"missing required top-level field: {key}")

    if data.get("overall_confidence") not in CONFIDENCE:
        errors.append("overall_confidence invalid")

    phases = data.get("phases")
    budget_required = _discovery_budget_required(phases, strict=strict)
    errors.extend(
        _validate_discovery_budget(data.get("discovery_budget"), required=budget_required)
    )

    engagement = data.get("engagement")
    if isinstance(engagement, dict):
        for key in REQUIRED_ENGAGEMENT:
            if key not in engagement:
                errors.append(f"engagement missing field: {key}")
        if engagement.get("status") not in ENGAGEMENT_STATUS:
            errors.append("engagement.status invalid")
        map_error = _relative_path_error(engagement.get("map_file"), "engagement.map_file")
        if map_error:
            errors.append(map_error)
        artifact_root = engagement.get("artifact_root")
        if artifact_root:
            root_error = _artifact_root_error(artifact_root)
            if root_error:
                errors.append(root_error)
    else:
        errors.append("engagement must be an object")

    if isinstance(phases, dict):
        for key in sorted(PHASE_KEYS - set(phases.keys())):
            errors.append(f"phases missing key: {key}")
        for key, value in phases.items():
            if key not in PHASE_KEYS:
                errors.append(f"phases unknown key: {key}")
            else:
                errors.extend(_validate_phase_entry(key, value))
    else:
        errors.append("phases must be an object")

    errors.extend(_validate_artifact_list(data.get("artifacts"), "artifacts", ARTIFACT_STATUS))
    errors.extend(_validate_artifact_list(data.get("diagrams"), "diagrams", DIAGRAM_STATUS))
    errors.extend(_validate_five_questions(data.get("five_questions")))
    errors.extend(_validate_repos(data.get("repos")))
    errors.extend(_validate_evidence_summary(data.get("evidence_summary")))

    runtime = data.get("runtime_validation")
    if not isinstance(runtime, dict):
        errors.append("runtime_validation must be an object")
    else:
        for key in ("edges_total", "edges_confirmed"):
            if key in runtime and not isinstance(runtime[key], int):
                errors.append(f"runtime_validation.{key} must be an integer")

    map_file = str(engagement.get("map_file") or "") if isinstance(engagement, dict) else ""

    if workspace_root is not None:
        if not workspace_root.is_dir():
            errors.append(f"workspace_root not a directory: {workspace_root}")
        else:
            effective_root, root_errors = _resolve_effective_root(workspace_root, engagement)
            errors.extend(root_errors)

            for item in data.get("artifacts") or []:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "")
                rel = str(item.get("path") or "")
                if item_id == "map_file" and map_file:
                    rel = map_file
                if _relative_path_error(rel, "artifact path"):
                    continue
                status = item.get("status")
                if status in ("ok", "stub", "stale") and rel and item_id not in DISTRIBUTED_ARTIFACT_IDS:
                    normalized_rel = rel.replace("\\", "/")
                    target = effective_root / normalized_rel
                    expects_directory = rel.endswith(("/", "\\"))
                    present = target.is_dir() if expects_directory else target.is_file()
                    if not present:
                        kind = "directory" if expects_directory else "file"
                        errors.append(f"artifact {kind} missing on disk: {rel} (status={status})")

            if strict and isinstance(engagement, dict) and engagement.get("status") == "FIRST_PASS_COMPLETE":
                errors.extend(_validate_strict_completion_artifacts(data.get("artifacts")))
                for item in data.get("artifacts") or []:
                    if not isinstance(item, dict):
                        continue
                    item_id = item.get("id")
                    # PRD and machine artifacts have dedicated strict rules above.
                    if item_id == "prd" or item_id in REQUIRED_MACHINE_ARTIFACT_IDS:
                        continue
                    if item.get("required") and item.get("status") not in ("ok", "waived"):
                        errors.append(f"strict: required artifact {item_id} status={item.get('status')}")
                for item in data.get("diagrams") or []:
                    if isinstance(item, dict) and item.get("required") and item.get("status") not in ("ok", "waived", "n_a"):
                        errors.append(f"strict: required diagram {item.get('id')} status={item.get('status')}")
                for key, phase_value in (phases or {}).items():
                    if isinstance(phase_value, dict) and phase_value.get("status") not in ("complete", "skipped"):
                        errors.append(f"strict: phase {key} not complete or skipped")

            if check_content:
                errors.extend(_validate_exec_summary_content(effective_root / "EXEC_SUMMARY.md"))
                errors.extend(
                    _validate_p2b_runtime_gate(
                        effective_root,
                        map_file=map_file,
                        phases=phases if isinstance(phases, dict) else None,
                        runtime_validation=runtime if isinstance(runtime, dict) else None,
                    )
                )
                errors.extend(
                    _validate_merge_conflicts_gate(
                        effective_root,
                        phases=phases if isinstance(phases, dict) else None,
                    )
                )
                errors.extend(
                    _validate_api_tooling_content(
                        effective_root,
                        artifacts=data.get("artifacts") if isinstance(data.get("artifacts"), list) else None,
                    )
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate domain-comprehension manifest.yaml")
    parser.add_argument("manifest", type=Path, help="Path to manifest.yaml")
    parser.add_argument("--workspace-root", type=Path, default=None, help="Verify artifact paths exist under this directory")
    parser.add_argument("--strict", action="store_true", help="Enforce FIRST_PASS_COMPLETE readiness rules")
    parser.add_argument(
        "--check-content",
        action="store_true",
        help="Verify EXEC_SUMMARY.md sections, P2b runtime validation gate, RISK_MAP.md merge-conflicts gate, and postman_collection.json validity (requires --workspace-root)",
    )
    args = parser.parse_args()

    if args.check_content and args.workspace_root is None:
        print("--check-content requires --workspace-root", file=sys.stderr)
        return 1

    data, load_errors = _load_yaml(args.manifest)
    if load_errors:
        for err in load_errors:
            print(err, file=sys.stderr)
        return 1

    errors = validate_manifest(
        data,
        workspace_root=args.workspace_root,
        strict=args.strict,
        check_content=args.check_content,
    )
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    print(f"ok: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
