from __future__ import annotations

import json
from pathlib import Path

from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.host_adapter import HOSTS, validate_host_adapter_interface
from scripts.registry.routing_sync import validate_skill_routing_references
from scripts.registry.schema import parse_registry
from scripts.registry.skill_frontmatter_schema import automation_only_guard_errors
from scripts.yaml_safety import load_unique_yaml_file, require_mapping

SKILL_SURFACES = {"per_skill_generated", "canonical_root"}


def _generated_surface_errors(root: Path, directory: Path, suffix: str, skills: set[str], host: str) -> list[str]:
    errors: list[str] = []
    actual = {path.stem for path in directory.glob(f"*{suffix}")}
    if actual != skills:
        return [f"error: {host} skill surface drift: missing={sorted(skills-actual)}, extra={sorted(actual-skills)}"]
    for skill_id in sorted(skills):
        path = directory / f"{skill_id}{suffix}"
        text = path.read_text(encoding="utf-8")
        if f"{skill_id}/SKILL.md" not in text:
            errors.append(f"error: {host} adapter {path.name} lost canonical {skill_id}/SKILL.md reference")
    return errors


def _plugin_errors(path: Path, host: str) -> list[str]:
    if not path.is_file():
        return [f"error: {host} package manifest missing: {path}"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if payload.get("name") != "software-builder":
        errors.append(f"error: {host} package identity drift")
    if payload.get("skills") != "./":
        errors.append(f"error: {host} package must point at canonical root skill tree")
    return errors


def validate_host_portability(root: Path) -> list[str]:
    """Validate items 30–34: adapter contract plus host packaging semantic parity."""
    errors = validate_host_adapter_interface(root)
    registry = parse_registry(root / "skills.yaml")
    skills = set(registry.skills)
    contracts = require_mapping(load_unique_yaml_file(root / "scripts/registry/host_contracts.yaml"), "host contracts")
    host_map = require_mapping(contracts.get("hosts"), "hosts")
    expected = require_mapping(load_unique_yaml_file(root / "evals/host-parity/expected.yaml"), "host parity expected")
    if expected.get("schema_version") != 1:
        errors.append("error: host parity expected schema_version must be 1")
    snapshots = require_mapping(expected.get("hosts"), "host parity expected hosts")
    if set(snapshots) != HOSTS:
        errors.append(f"error: host parity snapshot must cover exactly {sorted(HOSTS)}")

    for host in sorted(HOSTS & set(host_map) & set(snapshots)):
        actual = require_mapping(host_map[host], f"hosts.{host}")
        snapshot = require_mapping(snapshots[host], f"expected.hosts.{host}")
        if actual.get("adapter") != snapshot.get("adapter"):
            errors.append(f"error: {host}: adapter identity drift")
        if snapshot.get("skill_surface") not in SKILL_SURFACES:
            errors.append(f"error: {host}: invalid skill_surface {snapshot.get('skill_surface')!r}")

    errors.extend(_generated_surface_errors(root, root / ".cursor/rules", ".mdc", skills, "Cursor"))
    errors.extend(_generated_surface_errors(root, root / ".kiro/steering", ".md", skills, "Kiro"))
    errors.extend(_plugin_errors(root / ".claude-plugin/plugin.json", "Claude"))
    errors.extend(_plugin_errors(root / ".codex-plugin/plugin.json", "Codex/ChatGPT"))

    # Every host ultimately delegates execution to canonical SKILL.md. Keep
    # automation-only semantics in the canonical registry/frontmatter contract.
    for skill_id, entry in sorted(registry.skills.items()):
        skill_md = root / entry.path / "SKILL.md"
        if not skill_md.is_file():
            errors.append(f"error: canonical root skill missing for {skill_id}")
            continue
        frontmatter = load_skill_frontmatter(skill_md)
        for error in automation_only_guard_errors(entry.invocation, frontmatter):
            errors.append(f"error: host invocation semantics {skill_id}: {error}")

    if expected.get("invocation_source") != "skills.yaml":
        errors.append("error: host parity invocation source drift")
    routing_rel = expected.get("routing_source")
    if routing_rel != "docs/skill-framework/shared/skill-routing.md":
        errors.append("error: host parity routing source drift")
    else:
        routing_path = root / str(routing_rel)
        if not routing_path.is_file():
            errors.append("error: canonical routing source missing")
        else:
            errors.extend(validate_skill_routing_references(root, registry))
            routing_text = routing_path.read_text(encoding="utf-8")
            runtime_contracts = expected.get("runtime_contracts")
            if not isinstance(runtime_contracts, list) or not runtime_contracts:
                errors.append("error: host parity runtime_contracts must be a non-empty list")
            else:
                for doc in runtime_contracts:
                    if not isinstance(doc, str) or not doc:
                        errors.append("error: host parity runtime contract names must be non-empty strings")
                        continue
                    path = root / "docs/skill-framework/shared" / doc
                    if not path.is_file():
                        errors.append(f"error: missing canonical runtime contract {doc}")
                    elif doc not in routing_text:
                        errors.append(f"error: skill-routing.md does not inherit {doc}")
    return errors
