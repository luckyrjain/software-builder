from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from scripts.registry.composition_contracts import load_contracts
from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.schema import parse_registry
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_PATH = Path(__file__).resolve().parent / "platform_contracts.yaml"
_CORE_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_IDENTIFIER_RE = re.compile(r"^[0-9A-Za-z-]+$")
_ALLOWED_TYPES = {"leaf", "router", "orchestrator", "trigger"}
_REQUIRED_EVIDENCE = {"OBSERVED", "INFERRED", "UNKNOWN", "CONFLICTED", "NOT_APPLICABLE"}
_REQUIRED_EVIDENCE_FIELDS = {"claim", "status", "provenance", "limitations"}
_REQUIRED_COMPLETION = {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "ESCALATED"}
_REQUIRED_COMPLETION_FIELDS = {
    "status",
    "evidence_status",
    "blockers",
    "artifacts",
    "recommended_next_skill",
}
_REQUIRED_GATES = {
    "read_only": "none",
    "local_reversible_write": "explicit_task_authorization",
    "remote_non_destructive_write": "explicit_task_authorization",
    "destructive_or_high_impact": "explicit_action_authorization",
}


def _validate_semver_identifiers(raw: str, *, prerelease: bool) -> bool:
    identifiers = raw.split(".")
    if not identifiers or any(not item or not _IDENTIFIER_RE.fullmatch(item) for item in identifiers):
        return False
    if prerelease and any(item.isdigit() and len(item) > 1 and item.startswith("0") for item in identifiers):
        return False
    return True


def _normalize_version(raw: Any) -> str:
    if raw is None or raw == "":
        return "1.0.0"
    if isinstance(raw, bool):
        raise ValueError(f"invalid skill_version {raw!r}; expected semantic version string or integer major")
    if isinstance(raw, int):
        value = f"{raw}.0.0"
    elif isinstance(raw, str):
        value = raw.strip()
        if re.fullmatch(r"\d+", value):
            value = f"{value}.0.0"
        elif re.fullmatch(r"\d+\.\d+", value):
            value = f"{value}.0"
    else:
        raise ValueError(
            f"invalid skill_version {raw!r}; expected semantic version string or integer major",
        )

    core_and_pre, plus, build = value.partition("+")
    core, dash, prerelease = core_and_pre.partition("-")
    valid = bool(_CORE_SEMVER_RE.fullmatch(core))
    if dash:
        valid = valid and _validate_semver_identifiers(prerelease, prerelease=True)
    if plus:
        valid = valid and _validate_semver_identifiers(build, prerelease=False)
    if not valid:
        raise ValueError(f"invalid skill_version {raw!r}; expected semantic version")
    return value


def _require_mapping(raw: Any, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a mapping")
    return raw


def _require_schema_version(raw: Any, *, label: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        raise ValueError(f"{label} must be an integer")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer") from exc
    return value


def _validate_exact_string_set(raw: Any, expected: set[str], label: str) -> None:
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError(f"{label} must define the canonical values")
    if len(raw) != len(expected) or len(set(raw)) != len(raw) or set(raw) != expected:
        raise ValueError(f"{label} must define each canonical value exactly once")


def _load_platform_contracts(path: Path = CONTRACTS_PATH) -> dict[str, Any]:
    raw = _require_mapping(load_unique_yaml_file(path), "platform contracts")
    if _require_schema_version(raw.get("schema_version", 0), label="platform contracts.schema_version") != 1:
        raise ValueError("platform contracts: unsupported schema_version")

    evidence = _require_mapping(raw.get("evidence"), "platform contracts.evidence")
    _validate_exact_string_set(
        evidence.get("statuses"),
        _REQUIRED_EVIDENCE,
        "platform contracts.evidence.statuses",
    )
    _validate_exact_string_set(
        evidence.get("required_fields"),
        _REQUIRED_EVIDENCE_FIELDS,
        "platform contracts.evidence.required_fields",
    )
    if str(evidence.get("insufficient_evidence_status", "")) != "UNKNOWN":
        raise ValueError("platform contracts.evidence.insufficient_evidence_status must be UNKNOWN")
    if str(evidence.get("conflicting_evidence_status", "")) != "CONFLICTED":
        raise ValueError("platform contracts.evidence.conflicting_evidence_status must be CONFLICTED")

    completion = _require_mapping(raw.get("completion"), "platform contracts.completion")
    _validate_exact_string_set(
        completion.get("statuses"),
        _REQUIRED_COMPLETION,
        "platform contracts.completion.statuses",
    )
    _validate_exact_string_set(
        completion.get("required_fields"),
        _REQUIRED_COMPLETION_FIELDS,
        "platform contracts.completion.required_fields",
    )

    gates = _require_mapping(raw.get("action_gates"), "platform contracts.action_gates")
    normalized_gates = {str(key): str(value) for key, value in gates.items()}
    if normalized_gates != _REQUIRED_GATES:
        raise ValueError(
            "platform contracts.action_gates must define the canonical authorization policy",
        )

    skill_types = _require_mapping(raw.get("skill_types"), "platform contracts.skill_types")
    invalid_types = sorted({str(value) for value in skill_types.values()} - _ALLOWED_TYPES)
    if invalid_types:
        raise ValueError(
            f"platform contracts.skill_types has invalid types: {', '.join(invalid_types)}",
        )
    return raw


def build_manifest(root: Path = ROOT) -> dict[str, Any]:
    registry = parse_registry(root / "skills.yaml")
    platform = _load_platform_contracts(
        root / "scripts" / "registry" / "platform_contracts.yaml",
    )
    _artifact_types, _artifact_schemas, _authority_levels, composition = load_contracts(
        root / "scripts" / "registry" / "composition_contracts.yaml",
    )

    skill_types = platform["skill_types"]
    registry_ids = set(registry.skills)
    if set(skill_types) != registry_ids:
        missing = sorted(registry_ids - set(skill_types))
        extra = sorted(set(skill_types) - registry_ids)
        details: list[str] = []
        if missing:
            details.append(f"missing types: {', '.join(missing)}")
        if extra:
            details.append(f"unknown types: {', '.join(extra)}")
        raise ValueError(
            "platform contracts.skill_types registry drift: " + "; ".join(details),
        )

    if set(composition) != registry_ids:
        missing = sorted(registry_ids - set(composition))
        extra = sorted(set(composition) - registry_ids)
        details = []
        if missing:
            details.append(f"missing authority contracts: {', '.join(missing)}")
        if extra:
            details.append(f"unknown authority contracts: {', '.join(extra)}")
        raise ValueError(
            "composition contract registry drift: " + "; ".join(details),
        )

    skills: dict[str, Any] = {}
    for skill_id, entry in registry.skills.items():
        frontmatter = load_skill_frontmatter(root / entry.path / "SKILL.md")
        raw_version = frontmatter.get("skill_version")
        version = _normalize_version(raw_version)
        description = frontmatter.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"{skill_id}: description must be a non-empty string")

        artifact_contract = composition[skill_id]
        skills[skill_id] = {
            "name": skill_id,
            "version": version,
            "version_source": (
                "skill_frontmatter" if raw_version not in (None, "") else "implicit_v1"
            ),
            "type": str(skill_types[skill_id]),
            "category": entry.category,
            "description": description.strip(),
            "path": entry.path,
            "invocation": entry.invocation,
            "risk_class": list(entry.risk_class),
            "authority": artifact_contract.write_authority,
            "capabilities": {
                "required": list(entry.capabilities.required),
                "optional": [
                    {"name": item.name, "enables": item.enables}
                    for item in entry.capabilities.optional
                ],
                "any_of": [
                    {
                        "name": path.name,
                        "required": list(path.required),
                        "optional": [
                            {"name": item.name, "enables": item.enables}
                            for item in path.optional
                        ],
                    }
                    for path in entry.capabilities.any_of
                ],
                "degraded_modes": dict(entry.capabilities.degraded_modes),
            },
            "dependencies": list(entry.install.requires),
            "composition": {
                "invokes": list(entry.composition.invokes),
                "escalation_targets": list(entry.composition.escalation_targets),
                "mode": entry.composition.mode,
            },
            "artifacts": {
                "produces": list(artifact_contract.produces),
                "consumes": list(artifact_contract.consumes),
                "produce_fields": {
                    name: list(fields) for name, fields in artifact_contract.produce_fields.items()
                },
                "consume_fields": {
                    name: list(fields) for name, fields in artifact_contract.consume_fields.items()
                },
            },
        }

    return {
        "manifest_schema_version": 1,
        "registry_schema_version": registry.schema_version,
        "contracts": {
            "evidence": platform["evidence"],
            "completion": platform["completion"],
            "action_gates": platform["action_gates"],
        },
        "skills": skills,
    }


def validate_manifest(root: Path = ROOT) -> list[str]:
    try:
        build_manifest(root)
    except (OSError, *YAML_SAFETY_ERRORS) as exc:
        return [f"error: platform manifest: {exc}"]
    return []


def main() -> int:
    try:
        manifest = build_manifest(ROOT)
    except (OSError, *YAML_SAFETY_ERRORS) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(manifest, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
