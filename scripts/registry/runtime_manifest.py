from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.registry.manifest import ROOT, _build_manifest
from scripts.yaml_safety import YAML_SAFETY_ERRORS

P1_CONTRACT_KEYS = (
    "result_envelope",
    "artifact_runtime",
    "input_resolution",
    "source_precedence",
    "freshness",
    "handoff",
    "execution_context",
    "state_semantics",
    "artifact_ownership",
    "permission_schema",
)


def build_runtime_manifest(root: Path = ROOT) -> dict[str, Any]:
    """Return one normalized manifest for every registered skill and P1 contract."""
    manifest, platform = _build_manifest(root)
    contracts = manifest.get("contracts")
    skills = manifest.get("skills")
    permissions = platform.get("skill_permissions")
    if not isinstance(contracts, dict):
        raise ValueError("platform manifest contracts must be a mapping")
    if not isinstance(skills, dict):
        raise ValueError("platform manifest skills must be a mapping")
    if not isinstance(permissions, dict):
        raise ValueError("platform contracts skill_permissions must be a mapping")

    for key in P1_CONTRACT_KEYS:
        if key not in platform:
            raise ValueError(f"platform contracts missing P1 section: {key}")
        contracts[key] = platform[key]

    if set(skills) != set(permissions):
        raise ValueError("runtime manifest skill/permission coverage drift")
    for skill_id, skill in skills.items():
        if not isinstance(skill, dict):
            raise ValueError(f"runtime manifest skill must be a mapping: {skill_id}")
        skill["permissions"] = permissions[skill_id]
    return manifest


def validate_runtime_manifest(root: Path = ROOT) -> list[str]:
    """Validate the integrated manifest consumed by hosts and orchestrators."""
    try:
        manifest = build_runtime_manifest(root)
        skills = manifest.get("skills")
        if not isinstance(skills, dict) or not skills:
            return ["error: runtime manifest must contain registered skills"]
        return []
    except (OSError, ValueError, *YAML_SAFETY_ERRORS) as exc:
        return [f"error: runtime manifest: {exc}"]
