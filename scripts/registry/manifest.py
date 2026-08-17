from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from scripts.registry.composition_contracts import load_contracts
from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.models import Registry
from scripts.registry.schema import parse_registry
from scripts.release_info import SEMVER_RE as _CORE_SEMVER_RE
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file
from scripts.yaml_safety import require_mapping as _require_mapping

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_PATH = Path(__file__).resolve().parent / "platform_contracts.yaml"
# Bare MAJOR.MINOR.PATCH semver core (no prerelease/build metadata) -- shared with
# scripts/release_info.py, which needs the exact same "is this a semver core" definition
# for VERSION/distribution_version/source manifest fields, so the two never drift apart.
_IDENTIFIER_RE = re.compile(r"^[0-9A-Za-z-]+$")
_LEGACY_NUMERIC_VERSION_RE = re.compile(
    r"^skill_version:\s*([0-9]+\.[0-9]+)\s*(?:#.*)?$",
    re.MULTILINE,
)
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
_REQUIRED_DOD_FIELDS = {
    "required_artifacts",
    "required_checks",
    "blocked_conditions",
    "partial_result_behavior",
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
        raise ValueError("skill_version is mandatory")
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


def _version_input(skill_md: Path, raw_version: Any) -> Any:
    """Recover the exact source lexeme for legacy unquoted YAML decimal versions.

    PyYAML turns ``skill_version: 1.10`` into float ``1.1`` before callers see it.
    Reading the source token preserves the intended minor digits without accepting
    arbitrary float values as a public version representation.
    """
    if not isinstance(raw_version, float):
        return raw_version
    match = _LEGACY_NUMERIC_VERSION_RE.search(skill_md.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(
            "legacy numeric skill_version could not be recovered; quote it as a semantic version",
        )
    return match.group(1)


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

    definition_of_done = _require_mapping(
        raw.get("definition_of_done"), "platform contracts.definition_of_done",
    )
    _validate_exact_string_set(
        definition_of_done.get("required_fields"),
        _REQUIRED_DOD_FIELDS,
        "platform contracts.definition_of_done.required_fields",
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


def _resolve_skill_version(skill_id: str, skill_md: Path, frontmatter: dict[str, Any]) -> tuple[str, Any]:
    """Normalized semantic version and the raw frontmatter value it came from.

    Shared by _build_manifest() (which also needs the raw value, to tell a
    legacy-numeric skill_version apart from a plain string for version_source)
    and skill_versions() (which only needs the normalized string), so the two
    never drift on how a skill's skill_version is read and normalized.
    """
    raw_version = frontmatter.get("skill_version")
    try:
        version = _normalize_version(_version_input(skill_md, raw_version))
    except ValueError as exc:
        raise ValueError(f"{skill_id}: {exc}") from exc
    return version, raw_version


def _build_manifest(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the manifest and return it alongside the raw platform contracts
    mapping it was built from, so callers needing P1-only sections don't have
    to re-read and re-parse platform_contracts.yaml a second time.
    """
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
        skill_md = root / entry.path / "SKILL.md"
        frontmatter = load_skill_frontmatter(skill_md)
        version, raw_version = _resolve_skill_version(skill_id, skill_md, frontmatter)
        description = frontmatter.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"{skill_id}: description must be a non-empty string")

        artifact_contract = composition[skill_id]
        version_source = (
            "skill_frontmatter_legacy_numeric" if isinstance(raw_version, float) else "skill_frontmatter"
        )
        skills[skill_id] = {
            "name": skill_id,
            "version": version,
            "version_source": version_source,
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

    manifest = {
        "manifest_schema_version": 1,
        "registry_schema_version": registry.schema_version,
        "contracts": {
            "evidence": platform["evidence"],
            "completion": platform["completion"],
            "action_gates": platform["action_gates"],
            "definition_of_done": platform["definition_of_done"],
        },
        "skills": skills,
    }
    return manifest, platform


def build_manifest(root: Path = ROOT) -> dict[str, Any]:
    manifest, _platform = _build_manifest(root)
    return manifest


def skill_versions(root: Path = ROOT, *, registry: Registry | None = None) -> dict[str, str]:
    """skill_id -> normalized semantic version, for every skill in skills.yaml.

    Lighter than build_manifest(): reads only skills.yaml and each skill's
    SKILL.md frontmatter, so it stays usable (e.g. for release packaging)
    even for a repository that doesn't have platform_contracts.yaml /
    composition_contracts.yaml -- the full P1 platform-contract layer
    build_manifest() requires.

    Pass `registry` when the caller already parsed skills.yaml (e.g. to also
    tracked-check its skills) so this doesn't re-read and re-parse the same
    file a second time; omitted, it parses skills.yaml itself as before.
    """
    if registry is None:
        registry = parse_registry(root / "skills.yaml")
    versions: dict[str, str] = {}
    for skill_id, entry in registry.skills.items():
        skill_md = root / entry.path / "SKILL.md"
        frontmatter = load_skill_frontmatter(skill_md)
        version, _raw_version = _resolve_skill_version(skill_id, skill_md, frontmatter)
        versions[skill_id] = version
    return versions


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
