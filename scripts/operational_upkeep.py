from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "scripts" / "operational_upkeep.yaml"
GENERATOR_VERSION = "1.0"
_ID_RE = re.compile(r"^(route|stop|report)\.[a-z0-9][a-z0-9.-]*$")


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("operational upkeep policy must be a mapping")
    return data


def _git_revision(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-3])
    if pattern.startswith("/"):
        return pattern[1:] in path
    return fnmatch.fnmatch(path, pattern) or pattern in path


def classify_file_role(path: str, policy: dict[str, Any]) -> str | None:
    matches: list[str] = []
    for role, config in policy["file_roles"].items():
        if any(_matches(path, pattern) for pattern in config["patterns"]):
            matches.append(role)
    if not matches:
        return None
    # Runtime beats reference when a broad reference glob also catches a runtime path;
    # maintainer paths are intentionally disjoint from skill runtime/reference paths.
    for role in ("runtime", "reference", "maintainer"):
        if role in matches:
            return role
    return matches[0]


def _load_codeowners(root: Path) -> str:
    path = root / "CODEOWNERS"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _validate_deprecated_yaml(path: Path, required: set[str]) -> list[str]:
    errors: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return errors
    if not isinstance(data, dict):
        return errors
    if data.get("status") != "deprecated" and data.get("deprecated") is not True:
        return errors
    block = data.get("deprecation")
    if not isinstance(block, dict):
        return [f"error: {path}: deprecated item requires a deprecation mapping"]
    missing = sorted(required - set(block))
    if missing:
        errors.append(f"error: {path}: deprecation missing fields: {', '.join(missing)}")
    return errors


def validate_policy(root: Path = ROOT) -> list[str]:
    policy = load_policy(root / "scripts" / "operational_upkeep.yaml")
    errors: list[str] = []
    if policy.get("schema_version") != 1:
        errors.append("error: operational-upkeep: unsupported schema_version")

    roles = policy.get("file_roles", {})
    if set(roles) != {"runtime", "reference", "maintainer"}:
        errors.append("error: operational-upkeep: file_roles must be runtime/reference/maintainer")

    seen: set[str] = set()
    stable_ids = policy.get("stable_ids", {})
    for group in ("routes", "stop_conditions", "report_fields"):
        for item in stable_ids.get(group, []):
            item_id = str(item.get("id", ""))
            if not _ID_RE.fullmatch(item_id):
                errors.append(f"error: operational-upkeep: invalid stable id {item_id!r}")
            if item_id in seen:
                errors.append(f"error: operational-upkeep: duplicate stable id {item_id}")
            seen.add(item_id)

    codeowners = _load_codeowners(root)
    for name, contract in policy.get("contract_owners", {}).items():
        contract_path = root / str(contract.get("path", ""))
        owner = str(contract.get("owner", ""))
        if not contract_path.is_file():
            errors.append(f"error: operational-upkeep: owner contract {name} path missing: {contract_path.relative_to(root)}")
        if not owner.startswith("@"):
            errors.append(f"error: operational-upkeep: owner contract {name} has invalid owner {owner!r}")
        if owner and owner not in codeowners:
            errors.append(f"error: operational-upkeep: owner {owner} for {name} is absent from CODEOWNERS")

    required = set(policy.get("deprecation", {}).get("required_fields", []))
    for path in sorted((root / "scripts" / "registry").glob("*.yaml")):
        errors.extend(_validate_deprecated_yaml(path, required))

    # Mandatory surfaces must have a visible role so generated health output cannot
    # silently drop the most consequential prompt-system files.
    mandatory = [
        "pr-review/SKILL.md",
        "pr-review/workflow/inputs.md",
        "pr-review/reference/smoke-test.md",
        "scripts/registry/eval_contracts.yaml",
    ]
    for path in mandatory:
        if classify_file_role(path, policy) is None:
            errors.append(f"error: operational-upkeep: no file role for {path}")
    return errors


def _yaml_mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_health_report(root: Path = ROOT, revision: str | None = None) -> dict[str, Any]:
    policy = load_policy(root / "scripts" / "operational_upkeep.yaml")
    skills = _yaml_mapping(root / "skills.yaml").get("skills", {})
    composition = _yaml_mapping(root / "scripts" / "registry" / "composition_contracts.yaml")
    runtime = _yaml_mapping(root / "scripts" / "registry" / "composition_runtime.yaml")
    eval_contracts = _yaml_mapping(root / "scripts" / "registry" / "eval_contracts.yaml")

    authority = Counter(
        str(spec.get("write_authority", "unknown"))
        for spec in composition.get("skills", {}).values()
        if isinstance(spec, dict)
    )
    role_counts = Counter()
    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            role = classify_file_role(path.relative_to(root).as_posix(), policy)
            if role:
                role_counts[role] += 1

    route_count = len(policy.get("stable_ids", {}).get("routes", []))
    stop_count = len(policy.get("stable_ids", {}).get("stop_conditions", []))
    report_field_count = len(policy.get("stable_ids", {}).get("report_fields", []))
    eval_case_refs = 0
    for section in ("dimension_coverage", "behavior_scenarios", "degraded_host_cases"):
        for entry in eval_contracts.get(section, {}).values():
            if isinstance(entry, dict):
                eval_case_refs += len(entry.get("case_refs", []))

    return {
        "schema_version": 1,
        "provenance": {
            "repository_revision": revision or _git_revision(root),
            "registry_schema_version": _yaml_mapping(root / "skills.yaml").get("schema_version"),
            "operational_policy_version": policy.get("policy_version"),
            "generator_version": GENERATOR_VERSION,
        },
        "health": {
            "skills": len(skills) if isinstance(skills, dict) else 0,
            "composition_contracts": len(composition.get("skills", {})),
            "artifact_schemas": len(composition.get("artifact_schemas", {})),
            "runtime_handoffs": sum(len(v) for v in runtime.get("handoffs", {}).values()),
            "eval_contract_refs": eval_case_refs,
            "stable_routes": route_count,
            "stable_stop_conditions": stop_count,
            "stable_report_fields": report_field_count,
            "contract_owners": len(policy.get("contract_owners", {})),
            "file_roles": dict(sorted(role_counts.items())),
            "authority_levels": dict(sorted(authority.items())),
        },
    }


def render_health_markdown(report: dict[str, Any]) -> str:
    p = report["provenance"]
    h = report["health"]
    lines = [
        "## Prompt-system health",
        "",
        f"- Repository revision: `{p['repository_revision']}`",
        f"- Registry schema: `{p['registry_schema_version']}`",
        f"- Operational policy: `{p['operational_policy_version']}`",
        f"- Health generator: `{p['generator_version']}`",
        f"- Skills: **{h['skills']}**",
        f"- Composition contracts: **{h['composition_contracts']}**",
        f"- Artifact schemas: **{h['artifact_schemas']}**",
        f"- Runtime handoffs: **{h['runtime_handoffs']}**",
        f"- Eval contract refs: **{h['eval_contract_refs']}**",
        f"- Stable IDs: **{h['stable_routes']} routes / {h['stable_stop_conditions']} stops / {h['stable_report_fields']} report fields**",
        f"- Cross-cutting contract owners: **{h['contract_owners']}**",
        "",
    ]
    return "\n".join(lines)


def classify_diff(paths: list[str], policy: dict[str, Any]) -> tuple[str, list[str]]:
    rules = policy["prompt_diff_risk"]["path_rules"]
    order = policy["prompt_diff_risk"]["order"]
    matched: set[str] = set()
    for path in paths:
        for risk, patterns in rules.items():
            if any(_matches(path, pattern) for pattern in patterns):
                matched.add(risk)
    if not matched:
        return "editorial", []
    risk = max(matched, key=order.index)
    return risk, sorted(matched, key=order.index)


def validate_diff_risk(paths: list[str], policy: dict[str, Any]) -> tuple[str, list[str]]:
    risk, matched = classify_diff(paths, policy)
    high = set(policy["prompt_diff_risk"]["high_risk_classes"])
    evidence_prefixes = tuple(policy["prompt_diff_risk"]["evidence_paths"])
    errors: list[str] = []
    if risk in high and not any(path.startswith(evidence_prefixes) for path in paths):
        errors.append(
            f"error: prompt-diff risk {risk} requires changed eval/test evidence under "
            + " or ".join(evidence_prefixes)
        )
    return risk, errors


def _changed_paths(root: Path, base: str, head: str) -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base}...{head}"], cwd=root, text=True
    )
    return [line for line in output.splitlines() if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    health = sub.add_parser("health")
    health.add_argument("--format", choices=("json", "markdown"), default="json")
    health.add_argument("--revision")
    diff = sub.add_parser("classify-diff")
    diff.add_argument("--base", required=True)
    diff.add_argument("--head", required=True)
    args = parser.parse_args(argv)

    if args.command == "validate":
        errors = validate_policy(ROOT)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print("ok: operational upkeep policy validates")
        return 0
    if args.command == "health":
        report = build_health_report(ROOT, revision=args.revision)
        if args.format == "markdown":
            print(render_health_markdown(report))
        else:
            print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    if args.command == "classify-diff":
        policy = load_policy(POLICY_PATH)
        paths = _changed_paths(ROOT, args.base, args.head)
        risk, errors = validate_diff_risk(paths, policy)
        print(f"prompt_diff_risk={risk}")
        print("changed_paths=" + ",".join(paths))
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
