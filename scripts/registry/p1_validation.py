from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.schema import parse_registry
from scripts.registry.skill_frontmatter_schema import PLATFORM_CONTRACT
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file

RUNTIME_DOCS = {"runtime-contract.md", "host-adapter-contract.md", "eval-contract.md"}
RESULT_FIELDS = {"skill", "version", "status", "confidence", "source_revision", "evidence_status", "artifacts", "blockers", "recommended_next_skill"}
HANDOFF_FIELDS = {"target_skill", "reason", "inputs", "evidence_refs", "assumptions", "unresolved"}
EXECUTION_FIELDS = {"invocation_id", "parent_skill", "visited_skills", "depth"}
STATE_VALUES = {"current_state", "proposed_state", "desired_state", "transitional_state"}
EVAL_DIMENSIONS = {"positive", "negative", "ambiguous", "adversarial", "degraded"}
HOSTS = {"cursor", "claude", "codex", "chatgpt", "kiro", "generic"}
HOST_CAPABILITIES = {"discover_files", "read_repo", "write_repo", "git", "scm", "subagents", "task_isolation", "terminal", "browser", "connectors"}
SUPPORT_VALUES = {"full", "degraded", "unsupported"}
PERMISSION_FIELDS = {"repository", "external_actions", "unattended", "merge"}
REPOSITORY_PERMISSIONS = {"read", "write"}
EXTERNAL_PERMISSIONS = {"none", "read", "write"}


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _strings(value: Any, label: str) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must not contain duplicates")
    return set(value)


def _require_v1(data: dict[str, Any], label: str) -> None:
    if data.get("schema_version") != 1:
        raise ValueError(f"{label}.schema_version must be 1")


def _validate_platform_markers(root: Path) -> list[str]:
    """Every skill in a P1-enabled repository must visibly declare the contract it inherits."""
    errors: list[str] = []
    registry = parse_registry(root / "skills.yaml")
    for skill_id, entry in sorted(registry.skills.items()):
        frontmatter = load_skill_frontmatter(root / entry.path / "SKILL.md")
        actual = frontmatter.get("platform_contract")
        if actual != PLATFORM_CONTRACT:
            errors.append(
                f"error: {skill_id}: platform_contract must be {PLATFORM_CONTRACT!r}, got {actual!r}",
            )
    return errors


def _validate_permissions(root: Path, platform: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    registry = parse_registry(root / "skills.yaml")
    skill_ids = set(registry.skills)
    schema = _mapping(platform.get("permission_schema"), "permission_schema")
    if _strings(schema.get("required_fields"), "permission fields") != PERMISSION_FIELDS:
        errors.append("error: P1 permission fields drift")
    if _strings(schema.get("repository_values"), "repository permission values") != REPOSITORY_PERMISSIONS:
        errors.append("error: P1 repository permission values drift")
    if _strings(schema.get("external_action_values"), "external permission values") != EXTERNAL_PERMISSIONS:
        errors.append("error: P1 external permission values drift")

    permissions = _mapping(platform.get("skill_permissions"), "skill_permissions")
    if set(permissions) != skill_ids:
        missing = sorted(skill_ids - set(permissions))
        extra = sorted(set(permissions) - skill_ids)
        if missing:
            errors.append("error: P1 permissions missing skills: " + ", ".join(missing))
        if extra:
            errors.append("error: P1 permissions unknown skills: " + ", ".join(extra))

    for skill_id in sorted(skill_ids & set(permissions)):
        permission = _mapping(permissions[skill_id], f"skill_permissions.{skill_id}")
        if set(permission) != PERMISSION_FIELDS:
            errors.append(f"error: {skill_id}: permissions must declare every field exactly once")
            continue
        if permission["repository"] not in REPOSITORY_PERMISSIONS:
            errors.append(f"error: {skill_id}: invalid repository permission")
        if permission["external_actions"] not in EXTERNAL_PERMISSIONS:
            errors.append(f"error: {skill_id}: invalid external_actions permission")
        if not isinstance(permission["unattended"], bool) or not isinstance(permission["merge"], bool):
            errors.append(f"error: {skill_id}: unattended and merge permissions must be booleans")

        risks = set(registry.skills[skill_id].risk_class)
        if (permission["repository"] == "write") != ("repository-write" in risks or "merge" in risks):
            errors.append(f"error: {skill_id}: repository permission does not match risk_class")
        if permission["unattended"] != ("unattended" in risks):
            errors.append(f"error: {skill_id}: unattended permission does not match risk_class")
        if permission["merge"] != ("merge" in risks):
            errors.append(f"error: {skill_id}: merge permission does not match risk_class")
        if "posting" in risks and permission["external_actions"] != "write":
            errors.append(f"error: {skill_id}: posting risk requires external_actions write")
    return errors


def validate_p1_contracts(root: Path) -> list[str]:
    try:
        errors: list[str] = []
        platform = _mapping(load_unique_yaml_file(root / "scripts/registry/platform_contracts.yaml"), "platform contracts")
        _require_v1(platform, "platform contracts")
        errors.extend(_validate_platform_markers(root))
        result = _mapping(platform.get("result_envelope"), "result_envelope")
        if _strings(result.get("required_fields"), "result fields") != RESULT_FIELDS:
            errors.append("error: P1 result envelope fields drift")
        handoff = _mapping(platform.get("handoff"), "handoff")
        if _strings(handoff.get("required_fields"), "handoff fields") != HANDOFF_FIELDS:
            errors.append("error: P1 handoff fields drift")
        execution = _mapping(platform.get("execution_context"), "execution_context")
        if _strings(execution.get("required_fields"), "execution fields") != EXECUTION_FIELDS or execution.get("default_max_depth") != 3:
            errors.append("error: P1 recursion contract drift")
        states = _mapping(platform.get("state_semantics"), "state_semantics")
        if _strings(states.get("values"), "state values") != STATE_VALUES:
            errors.append("error: P1 state semantics drift")
        resolution = _mapping(platform.get("input_resolution"), "input_resolution")
        if resolution.get("order") != ["supplied_facts", "retrievable_authoritative_context", "safe_reversible_defaults", "focused_question"]:
            errors.append("error: P1 input resolution order drift")
        if platform.get("source_precedence") != ["runtime_authoritative_state", "executable_code_config_contracts", "tests_and_executable_examples", "version_controlled_technical_docs", "tickets_and_design_docs", "human_prose_and_comments"]:
            errors.append("error: P1 source precedence drift")
        errors.extend(_validate_permissions(root, platform))

        hosts = _mapping(load_unique_yaml_file(root / "scripts/registry/host_contracts.yaml"), "host contracts")
        _require_v1(hosts, "host contracts")
        if _strings(hosts.get("capability_families"), "host capability families") != HOST_CAPABILITIES:
            errors.append("error: P1 host capability families drift")
        if _strings(hosts.get("allowed_support"), "host support values") != SUPPORT_VALUES:
            errors.append("error: P1 host support values drift")
        host_map = _mapping(hosts.get("hosts"), "hosts")
        if set(host_map) != HOSTS:
            errors.append("error: P1 host coverage drift")
        for host_id, config in host_map.items():
            support = _mapping(_mapping(config, host_id).get("support"), f"{host_id}.support")
            if set(support) != HOST_CAPABILITIES or set(map(str, support.values())) - SUPPORT_VALUES:
                errors.append(f"error: P1 host capability profile drift: {host_id}")

        evals = _mapping(load_unique_yaml_file(root / "scripts/registry/eval_contracts.yaml"), "eval contracts")
        _require_v1(evals, "eval contracts")
        if _strings(evals.get("required_dimensions"), "eval dimensions") != EVAL_DIMENSIONS:
            errors.append("error: P1 eval dimensions drift")
        for dirname in ("fixtures", "golden", "live", "transcripts"):
            if not (root / "evals" / dirname).is_dir():
                errors.append(f"error: missing eval harness directory evals/{dirname}")

        shared = root / "docs/skill-framework/shared"
        routing = (shared / "skill-routing.md").read_text(encoding="utf-8")
        for doc in sorted(RUNTIME_DOCS):
            if not (shared / doc).is_file():
                errors.append(f"error: missing shared contract {doc}")
            elif doc not in routing:
                errors.append(f"error: skill-routing.md must inherit {doc}")
        return errors
    except (OSError, ValueError, *YAML_SAFETY_ERRORS) as exc:
        return [f"error: P1 platform contracts: {exc}"]
