"""Canonical versioned manifest loader and legacy projection renderer."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.yaml_safety import load_unique_yaml_file, require_mapping

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_PATH = ROOT / "skills.yaml"
REQUIRED_CONTRACTS = {"platform", "composition_runtime", "composition"}
ALLOWED_TYPES = {"leaf", "router", "orchestrator", "trigger"}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def load_canonical_manifest(root: Path = ROOT) -> dict[str, Any]:
    raw = require_mapping(
        load_unique_yaml_file(root / "skills.yaml"),
        "canonical manifest",
    )
    if raw.get("schema_version") != 1:
        raise ValueError("canonical manifest.schema_version must be 1")
    if not isinstance(raw.get("contracts"), dict):
        raise ValueError("canonical manifest.contracts must be a mapping")
    if not isinstance(raw.get("skills"), dict):
        raise ValueError("canonical manifest.skills must be a mapping")
    return raw


def _mapping(value: object, label: str) -> dict[str, Any]:
    return require_mapping(value, label)


def validate_canonical_manifest(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        manifest = load_canonical_manifest(root)
        contracts = _mapping(manifest.get("contracts"), "canonical manifest.contracts")
        missing = REQUIRED_CONTRACTS - set(contracts)
        if missing:
            errors.append("error: canonical manifest missing contracts: " + ", ".join(sorted(missing)))

        skills = _mapping(manifest.get("skills"), "canonical manifest.skills")
        platform = _mapping(contracts.get("platform"), "contracts.platform")
        runtime = _mapping(contracts.get("composition_runtime"), "contracts.composition_runtime")
        composition = _mapping(contracts.get("composition"), "contracts.composition")
        platform_types = _mapping(platform.get("skill_types"), "contracts.platform.skill_types")
        runtime_types = _mapping(runtime.get("skill_types"), "contracts.composition_runtime.skill_types")
        platform_permissions = _mapping(
            platform.get("skill_permissions"),
            "contracts.platform.skill_permissions",
        )
        composition_skills = _mapping(composition.get("skills"), "contracts.composition.skills")

        if set(skills) != set(platform_types):
            errors.append("error: canonical skill/type coverage drift")
        if set(skills) != set(runtime_types):
            errors.append("error: canonical skill/runtime type coverage drift")
        if set(skills) != set(platform_permissions):
            errors.append("error: canonical skill/permission coverage drift")
        if set(skills) != set(composition_skills):
            errors.append("error: canonical skill/composition coverage drift")

        required = {
            "version",
            "type",
            "authority",
            "permissions",
            "supported_hosts",
            "entrypoint",
            "output_contract",
        }
        for skill_id, skill_raw in skills.items():
            skill = _mapping(skill_raw, f"skills.{skill_id}")
            missing_fields = required - set(skill)
            if missing_fields:
                errors.append(
                    f"error: {skill_id}: missing canonical fields: "
                    + ", ".join(sorted(missing_fields)),
                )
            version = skill.get("version")
            if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
                errors.append(f"error: {skill_id}: version must be semantic version")
            skill_type = skill.get("type")
            if skill_type not in ALLOWED_TYPES:
                errors.append(f"error: {skill_id}: invalid type {skill_type!r}")
            if platform_types.get(skill_id) != skill_type:
                errors.append(f"error: {skill_id}: platform type projection drift")
            if runtime_types.get(skill_id) != skill_type:
                errors.append(f"error: {skill_id}: runtime type projection drift")
            permissions = _mapping(skill.get("permissions"), f"skills.{skill_id}.permissions")
            if platform_permissions.get(skill_id) != permissions:
                errors.append(f"error: {skill_id}: permission projection drift")
            hosts = skill.get("supported_hosts")
            if not isinstance(hosts, list) or not hosts or not all(isinstance(item, str) for item in hosts):
                errors.append(f"error: {skill_id}: supported_hosts must be a non-empty list")
            if skill.get("entrypoint") != "SKILL.md":
                errors.append(f"error: {skill_id}: entrypoint must be SKILL.md")
            if not isinstance(skill.get("output_contract"), dict):
                errors.append(f"error: {skill_id}: output_contract must be a mapping")

            entrypoint = root / str(skill.get("path", skill_id)) / str(skill.get("entrypoint", "SKILL.md"))
            if not entrypoint.is_file():
                errors.append(f"error: {skill_id}: missing entrypoint {entrypoint}")
            else:
                frontmatter = load_skill_frontmatter(entrypoint)
                if "skill_version" in frontmatter or "platform_contract" in frontmatter:
                    errors.append(f"error: {skill_id}: legacy platform metadata remains in frontmatter")
                if frontmatter.get("name") != skill_id:
                    errors.append(f"error: {skill_id}: frontmatter name drift")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"error: canonical manifest: {exc}")
    return errors


def render_legacy_projection(root: Path, section: str) -> str:
    if section not in REQUIRED_CONTRACTS:
        raise ValueError(f"unknown legacy projection: {section}")
    manifest = load_canonical_manifest(root)
    contracts = _mapping(manifest.get("contracts"), "canonical manifest.contracts")
    value = _mapping(contracts.get(section), f"contracts.{section}")
    return yaml.safe_dump(value, sort_keys=False, default_flow_style=False, allow_unicode=True)
