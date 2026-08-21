"""Build the normalized runtime manifest from the canonical skills.yaml."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from scripts.registry.canonical_manifest import (
    load_canonical_manifest,
    validate_canonical_manifest,
)
from scripts.registry.composition_contracts import load_contracts
from scripts.registry.models import Registry
from scripts.registry.schema import parse_registry
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file, require_mapping

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_PATH = ROOT / "skills.yaml"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
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
    if raw is None or raw == "" or isinstance(raw, bool):
        raise ValueError(f"invalid skill version {raw!r}")
    if isinstance(raw, int):
        value = f"{raw}.0.0"
    else:
        value = str(raw).strip()
        if re.fullmatch(r"\d+", value):
            value += ".0.0"
        elif re.fullmatch(r"\d+\.\d+", value):
            value += ".0"
    if not SEMVER_RE.fullmatch(value):
        raise ValueError(f"invalid skill version {raw!r}")
    return value


def _load_platform_contracts(path: Path | None = None) -> dict[str, Any]:
    if path is None or path.name == "skills.yaml":
        root = path.parent if path is not None else ROOT
        manifest = load_canonical_manifest(root)
        contracts = require_mapping(manifest.get("contracts"), "canonical manifest.contracts")
        return require_mapping(contracts.get("platform"), "contracts.platform")
    return require_mapping(load_unique_yaml_file(path), "platform contracts")


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
        skill["version_source"] = "canonical_manifest"
        skill["authority"] = artifact.write_authority
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
    del registry
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

