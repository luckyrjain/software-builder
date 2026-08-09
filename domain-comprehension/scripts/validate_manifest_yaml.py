#!/usr/bin/env python3
"""Validate domain-comprehension manifest.yaml (schema_version 2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
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
ARTIFACT_STATUS = frozenset({"ok", "stub", "missing", "waived", "n_a"})
DIAGRAM_STATUS = frozenset({"pending", "ok", "waived", "n_a"})
QUESTION_STATUS = frozenset({"DRAFT", "PARTIAL", "COMPLETE", "UNKNOWN"})
CONFIDENCE = frozenset({"HIGH", "MEDIUM", "LOW", "UNKNOWN"})
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


def _resolve_effective_root(workspace_root: Path, engagement: Any) -> tuple[Path, list[str]]:
    """Resolve where phase deliverables actually live.

    manifest.yaml itself always stays at workspace_root (see reference/run-scoped-artifacts.md),
    but when a run namespaces its deliverables under `engagement.artifact_root` (e.g. parallel
    runs, large workspaces, QUICK-mode phase packets), every other file the validator checks —
    EXEC_SUMMARY.md, the map file, E2E_FLOW.md, RISK_MAP.md, the Postman export — lives under that
    subdirectory instead of directly at workspace_root.
    """
    if not isinstance(engagement, dict):
        return workspace_root, []
    artifact_root = engagement.get("artifact_root")
    if not artifact_root:
        return workspace_root, []
    artifact_root_str = str(artifact_root)
    candidate = Path(artifact_root_str)
    if candidate.is_absolute() or ".." in candidate.parts:
        return workspace_root, [
            f"engagement.artifact_root must be a relative path with no '..' segments: {artifact_root_str}"
        ]
    return workspace_root / candidate, []


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
        for field in ("path", "phase"):
            if not isinstance(item.get(field), str) or not str(item.get(field)).strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        phase = item.get("phase")
        if isinstance(phase, str) and phase not in PHASE_KEYS:
            errors.append(f"{prefix}.phase unknown: {phase}")
        status = item.get("status")
        if status not in status_set:
            errors.append(f"{prefix}.status must be one of {sorted(status_set)}")
        if label == "artifacts" and not isinstance(item.get("required"), bool):
            errors.append(f"{prefix}.required must be a boolean")
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
            value = item.get(field)
            if value is not None and value not in allowed:
                errors.append(f"{prefix}.{field} invalid: {value}")
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

        # Separator row: after stripping leading/trailing "|" and whitespace,
        # every remaining character is "-", ":", or whitespace.
        if set(stripped.strip("|").replace(" ", "")) <= {"-", ":"}:
            continue

        if status_index is None or len(cells) <= status_index:
            continue

        value = cells[status_index].strip()
        value = value.strip("`*").strip()
        if value.lower().startswith("status:"):
            value = value[len("status:") :].strip()
        if value.lower() == "open":
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

    engagement = data.get("engagement")
    if isinstance(engagement, dict):
        for key in REQUIRED_ENGAGEMENT:
            if key not in engagement:
                errors.append(f"engagement missing field: {key}")
        if engagement.get("status") not in ENGAGEMENT_STATUS:
            errors.append("engagement.status invalid")
    else:
        errors.append("engagement must be an object")

    phases = data.get("phases")
    if isinstance(phases, dict):
        missing_phases = PHASE_KEYS - set(phases.keys())
        for key in sorted(missing_phases):
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

    map_file = ""
    if isinstance(engagement, dict):
        map_file = str(engagement.get("map_file") or "")

    if workspace_root is not None:
        if not workspace_root.is_dir():
            errors.append(f"workspace_root not a directory: {workspace_root}")
        else:
            effective_root, root_errors = _resolve_effective_root(workspace_root, engagement)
            errors.extend(root_errors)

            for item in data.get("artifacts") or []:
                if not isinstance(item, dict):
                    continue
                rel = str(item.get("path") or "")
                if item.get("id") == "map_file" and map_file:
                    rel = map_file
                status = item.get("status")
                if status in ("ok", "stub") and rel:
                    if not (effective_root / rel).is_file():
                        errors.append(f"artifact file missing on disk: {rel} (status={status})")

            if strict and isinstance(engagement, dict):
                if engagement.get("status") == "FIRST_PASS_COMPLETE":
                    for item in data.get("artifacts") or []:
                        if not isinstance(item, dict) or not item.get("required"):
                            continue
                        if item.get("status") not in ("ok", "waived"):
                            errors.append(
                                f"strict: required artifact {item.get('id')} status={item.get('status')}"
                            )
                    for item in data.get("diagrams") or []:
                        if not isinstance(item, dict) or not item.get("required"):
                            continue
                        if item.get("status") not in ("ok", "waived", "n_a"):
                            errors.append(
                                f"strict: required diagram {item.get('id')} status={item.get('status')}"
                            )
                    for key, value in (phases or {}).items():
                        if isinstance(value, dict) and value.get("status") not in (
                            "complete",
                            "skipped",
                        ):
                            errors.append(f"strict: phase {key} not complete or skipped")

            if check_content:
                errors.extend(
                    _validate_exec_summary_content(effective_root / "EXEC_SUMMARY.md")
                )
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
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help="Verify artifact paths exist under this directory",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce FIRST_PASS_COMPLETE readiness rules",
    )
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
