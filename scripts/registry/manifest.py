"""Build the normalized runtime manifest from the canonical skills.yaml."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from scripts.registry.canonical_manifest import (
    has_canonical_manifest_shape,
    is_semver,
    load_canonical_manifest,
    validate_canonical_manifest,
)
from scripts.registry.composition_contracts import load_contracts
from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.models import Registry
from scripts.registry.schema import load_registry_raw, parse_registry
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file, require_mapping

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_PATH = ROOT / "skills.yaml"
LEGACY_NUMERIC_VERSION_RE = re.compile(
    r"^skill_version:\s*([0-9]+\.[0-9]+)\s*(?:#.*)?$", re.MULTILINE
)


def _version_input(skill_md: Path, raw_version: Any) -> Any:
    if not isinstance(raw_version, float):
        return raw_version
    match = LEGACY_NUMERIC_VERSION_RE.search(skill_md.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("legacy numeric skill_version could not be recovered")
    return match.group(1)


def _normalize_version(raw: Any) -> str:
    if raw is None or raw == "":
        raise ValueError("skill_version is mandatory")
    if isinstance(raw, bool) or isinstance(raw, float):
        raise ValueError(
            "invalid skill_version; expected semantic version string or integer major"
        )
    if isinstance(raw, int):
        value = f"{raw}.0.0"
    else:
        value = str(raw).strip()
        if re.fullmatch(r"\d+", value):
            value += ".0.0"
        elif re.fullmatch(r"\d+\.\d+", value):
            value += ".0"
    if not is_semver(value):
        raise ValueError(f"invalid skill_version {raw!r}; expected semantic version string or integer major")
    return value


def _load_platform_contracts(path: Path | None = None) -> dict[str, Any]:
    if path is None or path.name == "skills.yaml":
        root = path.parent if path is not None else ROOT
        manifest = load_canonical_manifest(root)
        contracts = require_mapping(manifest.get("contracts"), "canonical manifest.contracts")
        raw = require_mapping(contracts.get("platform"), "contracts.platform")
    else:
        raw = require_mapping(load_unique_yaml_file(path), "platform contracts")

    schema_version = raw.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, (int, str)):
        raise ValueError("platform contracts.schema_version must be an integer")
    try:
        if int(schema_version) != 1:
            raise ValueError("platform contracts: unsupported schema_version")
    except ValueError as exc:
        raise ValueError("platform contracts.schema_version must be an integer") from exc

    def exact(value: Any, expected: set[str], label: str) -> None:
        if not isinstance(value, list) or set(value) != expected or len(value) != len(expected):
            raise ValueError(f"{label} must define each canonical value exactly once")

    evidence = require_mapping(raw.get("evidence"), "platform contracts.evidence")
    exact(evidence.get("statuses"), {"OBSERVED", "INFERRED", "UNKNOWN", "CONFLICTED", "NOT_APPLICABLE"}, "platform contracts.evidence.statuses")
    exact(evidence.get("required_fields"), {"claim", "status", "provenance", "limitations"}, "platform contracts.evidence.required_fields")
    completion = require_mapping(raw.get("completion"), "platform contracts.completion")
    exact(completion.get("statuses"), {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "ESCALATED"}, "platform contracts.completion.statuses")
    exact(completion.get("required_fields"), {"status", "evidence_status", "blockers", "artifacts", "recommended_next_skill"}, "platform contracts.completion.required_fields")
    dod = require_mapping(raw.get("definition_of_done"), "platform contracts.definition_of_done")
    exact(dod.get("required_fields"), {"required_artifacts", "required_checks", "completed_checks", "blocked_conditions", "partial_result_behavior"}, "platform contracts.definition_of_done.required_fields")
    gates = require_mapping(raw.get("action_gates"), "platform contracts.action_gates")
    expected_gates = {"read_only": "none", "local_reversible_write": "explicit_task_authorization", "remote_non_destructive_write": "explicit_task_authorization", "destructive_or_high_impact": "explicit_action_authorization"}
    if {str(k): str(v) for k, v in gates.items()} != expected_gates:
        raise ValueError("platform contracts.action_gates must define the canonical authorization policy")
    skill_types = require_mapping(raw.get("skill_types"), "platform contracts.skill_types")
    if set(map(str, skill_types.values())) - {"leaf", "router", "orchestrator", "trigger"}:
        raise ValueError("platform contracts.skill_types has invalid types")
    return raw


def _build_manifest(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    canonical = load_canonical_manifest(root)
    errors = validate_canonical_manifest(root)
    if errors:
        raise ValueError("; ".join(errors))

    registry = parse_registry(root / "skills.yaml")
    platform = _load_platform_contracts(root / "skills.yaml")
    _, _, _, composition = load_contracts(root / "skills.yaml")

    canonical_skills = require_mapping(canonical.get("skills"), "canonical manifest.skills")
    skills: dict[str, Any] = {}
    for skill_id, entry in registry.skills.items():
        raw = require_mapping(canonical_skills.get(skill_id), f"skills.{skill_id}")
        artifact = composition[skill_id]
        skill = dict(raw)
        skill["name"] = skill_id
        skill["version"] = _normalize_version(skill["version"])
        skill["version_source"] = str(raw.get("version_source", "canonical_manifest"))
        skill["authority"] = str(raw["authority"])
        skill["composition"] = {
            "invokes": list(entry.composition.invokes),
            "escalation_targets": list(entry.composition.escalation_targets),
            "mode": entry.composition.mode,
        }
        skill["dependencies"] = list(raw["dependencies"])
        skill["artifacts"] = {
            "produces": list(artifact.produces),
            "consumes": list(artifact.consumes),
            "produce_fields": {name: list(fields) for name, fields in artifact.produce_fields.items()},
            "consume_fields": {name: list(fields) for name, fields in artifact.consume_fields.items()},
        }
        skills[skill_id] = skill

    manifest = {
        "manifest_schema_version": canonical["schema_version"],
        "registry_schema_version": canonical["schema_version"],
        "contracts": dict(platform),
        "skills": skills,
    }
    return manifest, platform


def build_manifest(root: Path = ROOT) -> dict[str, Any]:
    manifest, _platform = _build_manifest(root)
    return manifest


def skill_versions(root: Path = ROOT, *, registry: Registry | None = None) -> dict[str, str]:
    raw = require_mapping(
        load_registry_raw(root / "skills.yaml"),
        "skills.yaml root",
    )
    if not has_canonical_manifest_shape(raw):
        legacy_registry = registry or parse_registry(root / "skills.yaml")
        versions: dict[str, str] = {}
        for skill_id, entry in legacy_registry.skills.items():
            skill_md = root / entry.path / "SKILL.md"
            frontmatter = load_skill_frontmatter(skill_md)
            versions[skill_id] = _normalize_version(
                _version_input(skill_md, frontmatter.get("skill_version"))
            )
        return versions
    canonical = load_canonical_manifest(root)
    skills = require_mapping(canonical.get("skills"), "canonical manifest.skills")
    return {
        skill_id: _normalize_version(require_mapping(entry, f"skills.{skill_id}")["version"])
        for skill_id, entry in skills.items()
    }


def validate_manifest(root: Path = ROOT) -> list[str]:
    errors = validate_canonical_manifest(root)
    if errors:
        return errors
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
