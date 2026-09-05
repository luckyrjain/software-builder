"""Canonical versioned manifest loader and legacy projection renderer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scripts.registry.envelope_contract import SKILL_TYPES
from scripts.registry.host_adapter import HOSTS
from scripts.registry.schema import load_registry_raw, parse_registry
from scripts.yaml_safety import load_unique_frontmatter, load_unique_yaml_file, require_mapping

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_CONTRACTS = {"platform", "composition_runtime", "composition"}
MANIFEST_KIND = "canonical"
# The standalone file each contract section is projected to for repositories that predate
# the canonical shape. One table drives both the writer (`render_legacy_projection`) and the
# reader (`load_contract_section`), so the two sides cannot name different files. A section
# absent from this table has no standalone projection at all and is only ever read out of
# skills.yaml -- which is the `platform` section's situation: nothing outside skills.yaml
# ever read platform_contracts.yaml, so the file was deleted rather than kept generated.
LEGACY_PROJECTION_FILENAMES = {
    "composition_runtime": "composition_runtime.yaml",
    "composition": "composition_contracts.yaml",
}
# Marks the projections as machine-written, the same way the generated Cursor/Kiro
# adapters are marked -- a maintainer opening a 1,300-line projection must be able to see
# that `make generate` will overwrite it.
GENERATED_MARKER = "# GENERATED from skills.yaml contracts — do not edit; run make generate"


def has_canonical_manifest_shape(raw: object) -> bool:
    """Return whether a skills.yaml claims the reserved canonical shape."""
    return isinstance(raw, dict) and ("manifest_kind" in raw or "contracts" in raw)


def _raw_manifest(root: Path) -> object:
    """skills.yaml's raw mapping, or None when this root has no skills.yaml at all."""
    try:
        return load_registry_raw(root / "skills.yaml")
    except FileNotFoundError:
        return None


def is_semver(value: str) -> bool:
    """Validate SemVer components without a backtracking regex."""
    if not isinstance(value, str) or len(value) > 256:
        return False
    def valid_identifier(identifier: str) -> bool:
        return bool(identifier) and all(
            ("0" <= char <= "9")
            or ("A" <= char <= "Z")
            or ("a" <= char <= "z")
            or char == "-"
            for char in identifier
        )

    if value.count("+") > 1:
        return False
    core_and_prerelease, _, build = value.partition("+")
    if value.endswith("+") or (
        build and any(not valid_identifier(part) for part in build.split("."))
    ):
        return False
    core, separator, prerelease = core_and_prerelease.partition("-")
    core_parts = core.split(".")
    if len(core_parts) != 3 or any(
        not part
        or not all("0" <= char <= "9" for char in part)
        or (len(part) > 1 and part[0] == "0")
        for part in core_parts
    ):
        return False
    if not separator:
        return True
    identifiers = prerelease.split(".")
    if any(not valid_identifier(identifier) for identifier in identifiers):
        return False
    return all(
        not all("0" <= char <= "9" for char in identifier)
        or len(identifier) == 1
        or identifier[0] != "0"
        for identifier in identifiers
    )


def load_canonical_manifest(root: Path = ROOT) -> dict[str, Any]:
    raw = require_mapping(
        load_registry_raw(root / "skills.yaml"),
        "canonical manifest",
    )
    schema_version = raw.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, (int, str)):
        raise ValueError("canonical manifest.schema_version must be an integer")
    try:
        schema_version = int(schema_version)
    except ValueError as exc:
        raise ValueError("canonical manifest.schema_version must be an integer") from exc
    if schema_version != 1:
        raise ValueError("canonical manifest.schema_version must be 1")
    if raw.get("manifest_kind") != MANIFEST_KIND:
        raise ValueError(f"canonical manifest.manifest_kind must be {MANIFEST_KIND!r}")
    raw["schema_version"] = schema_version
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
        artifact_runtime = platform.get("artifact_runtime")
        if not isinstance(artifact_runtime, dict):
            errors.append("error: canonical manifest missing contracts.platform.artifact_runtime")
        elif artifact_runtime.get("schema_version") != 1:
            errors.append("error: canonical manifest artifact_runtime.schema_version must be 1")
        # The per-skill sub-mappings of these three sections (skill_types, skill_permissions,
        # composition.skills) are derived from the same skill entries this function validates --
        # manifest_merge.derive_contract_sections regenerates them on every `make generate`, so
        # the coverage and per-field equality checks that used to live here could only ever fail
        # on a skills.yaml someone hand-edited past the generator. `make generate-check` catches
        # that case for the whole file at once. What remains here is the shape of the sections
        # themselves, which is not derived.
        _mapping(platform.get("skill_types"), "contracts.platform.skill_types")
        _mapping(runtime.get("skill_types"), "contracts.composition_runtime.skill_types")
        _mapping(platform.get("skill_permissions"), "contracts.platform.skill_permissions")
        _mapping(composition.get("skills"), "contracts.composition.skills")
        registry = parse_registry(root / "skills.yaml")

        required = {
            "version",
            "type",
            "category",
            "invocation",
            "authority",
            "permissions",
            "supported_hosts",
            "entrypoint",
            "output_contract",
            "dependencies",
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
            if not isinstance(version, str) or not is_semver(version):
                errors.append(f"error: {skill_id}: version must be semantic version")
            skill_type = skill.get("type")
            if skill_type not in SKILL_TYPES:
                errors.append(f"error: {skill_id}: invalid type {skill_type!r}")
            for field in ("category", "invocation"):
                value = skill.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"error: {skill_id}: {field} must be a non-empty string")
            _mapping(skill.get("permissions"), f"skills.{skill_id}.permissions")
            _mapping(skill.get("output_contract"), f"skills.{skill_id}.output_contract")
            dependencies = skill.get("dependencies")
            if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
                errors.append(f"error: {skill_id}: dependencies must be a list of strings")
            elif skill_id in registry.skills and dependencies != registry.skills[skill_id].install.requires:
                errors.append(f"error: {skill_id}: dependency projection drift")
            hosts = skill.get("supported_hosts")
            if not isinstance(hosts, list) or not hosts or not all(isinstance(item, str) for item in hosts):
                errors.append(f"error: {skill_id}: supported_hosts must be a non-empty list")
            elif len(hosts) != len(set(hosts)):
                errors.append(f"error: {skill_id}: supported_hosts must not contain duplicates")
            elif skill_id in registry.skills:
                registry_hosts = HOSTS
                if set(hosts) != registry_hosts:
                    errors.append(f"error: {skill_id}: supported host projection drift")
            if skill.get("entrypoint") != "SKILL.md":
                errors.append(f"error: {skill_id}: entrypoint must be SKILL.md")
            entrypoint_dir = (root / str(skill.get("path", skill_id))).resolve()
            try:
                entrypoint_dir.relative_to(root.resolve())
            except ValueError:
                errors.append(f"error: {skill_id}: path escapes repository root")
                continue
            if skill.get("path", skill_id) != skill_id:
                errors.append(f"error: {skill_id}: path must match skill id")
            entrypoint = entrypoint_dir / "SKILL.md"
            if not entrypoint.is_file():
                errors.append(f"error: {skill_id}: missing entrypoint {entrypoint}")
            else:
                frontmatter = load_unique_frontmatter(entrypoint)
                if "skill_version" in frontmatter or "platform_contract" in frontmatter:
                    errors.append(f"error: {skill_id}: legacy platform metadata remains in frontmatter")
                if frontmatter.get("name") != skill_id:
                    errors.append(f"error: {skill_id}: frontmatter name drift")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"error: canonical manifest: {exc}")
    return errors


def legacy_projection_path(root: Path, section: str) -> Path:
    """Where `section` is projected to for repositories that have not adopted the canonical shape."""
    if section not in LEGACY_PROJECTION_FILENAMES:
        raise ValueError(f"unknown legacy projection: {section}")
    return root / "scripts" / "registry" / LEGACY_PROJECTION_FILENAMES[section]


def contract_section_source(root: Path, section: str) -> Path | None:
    """The file `root` reads `section` from, or None when neither source exists.

    One rule for every contract section, mirroring `render_legacy_projection`'s single
    writer: a repository that has opted into the canonical shape owns every section in
    skills.yaml, and one that has not reads the standalone projection. Returning None (rather
    than a path that does not exist) lets callers use this directly as the layer-active test,
    and is also the answer for a section that has no standalone projection at all.
    """
    if has_canonical_manifest_shape(_raw_manifest(root)):
        return root / "skills.yaml"
    if section not in LEGACY_PROJECTION_FILENAMES:
        return None
    projection = legacy_projection_path(root, section)
    return projection if projection.is_file() else None


def contract_document_path(root: Path, section: str) -> Path:
    """The file `load_contract_section` will actually read for `section`.

    Differs from `contract_section_source` only in the last case: with neither a canonical
    manifest nor a projection, skills.yaml itself is read as the contract document. Callers
    asking "is there a dedicated source for this section" want `contract_section_source`;
    callers asking "which file will be read" want this.
    """
    return contract_section_source(root, section) or root / "skills.yaml"


def load_contract_section(root: Path, section: str) -> dict[str, Any]:
    """Read one contract section through `contract_section_source`'s decision.

    The forgiving fallback is deliberate and shared by all three sections: when a repository
    is neither canonical nor carrying a projection, skills.yaml itself is read as the contract
    document, which is what keeps the deliberately minimal registry fixtures working.
    """
    if has_canonical_manifest_shape(_raw_manifest(root)):
        manifest = load_canonical_manifest(root)
        contracts = _mapping(manifest.get("contracts"), "canonical manifest.contracts")
        return _mapping(contracts.get(section), f"contracts.{section}")
    source = contract_document_path(root, section)
    return _mapping(load_unique_yaml_file(source), f"{source}: {section} contracts")


def render_legacy_projection(root: Path, section: str) -> str:
    if section not in LEGACY_PROJECTION_FILENAMES:
        raise ValueError(f"unknown legacy projection: {section}")
    manifest = load_canonical_manifest(root)
    contracts = _mapping(manifest.get("contracts"), "canonical manifest.contracts")
    value = _mapping(contracts.get(section), f"contracts.{section}")
    body = yaml.safe_dump(value, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return f"{GENERATED_MARKER}\n{body}"
