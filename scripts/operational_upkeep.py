from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.git_paths import tracked_relative_paths
from scripts.registry.canonical_manifest import load_canonical_manifest
from scripts.registry.schema import resolve_registry_profiles
from scripts.yaml_safety import FRONTMATTER_RE, load_unique_yaml, load_unique_yaml_file

POLICY_PATH = ROOT / "scripts" / "operational_upkeep.yaml"
GENERATOR_VERSION = "1.3"
_ID_RE = re.compile(r"^(route|stop|report)\.[a-z0-9][a-z0-9.-]*$")
_CAPABILITY_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+$")


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    data = load_unique_yaml_file(path)
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


def _tracked_relative_files(root: Path) -> list[Path]:
    """Return tracked regular files so health output depends on repository state, not local debris."""
    tracked, error = tracked_relative_paths(root)
    if error:
        raise RuntimeError(f"prompt-system health requires a Git worktree: {error}")
    return sorted(
        (Path(rel) for rel in tracked if (root / rel).is_file()),
        key=lambda path: path.as_posix(),
    )


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(f"{prefix}/")
    if pattern.startswith("/"):
        # A leading-"/" pattern matches its target as a path *segment*, not an
        # unanchored substring: "/tests/" must match ".../tests/..." and must
        # not match "contests/..." or "protests/..." merely containing "tests/".
        segment = pattern[1:]
        if segment.endswith("/"):
            # Directory-style: the pattern's own trailing "/" is the right
            # boundary already ("tests/" can't be followed by more of the
            # same segment name).
            return path.startswith(segment) or f"/{segment}" in path
        # Filename-style (e.g. "/SKILL.md"): also require a right boundary so
        # "SKILL.md.bak" isn't matched by an unanchored "SKILL.md" prefix.
        return path == segment or path.endswith(f"/{segment}")
    return fnmatch.fnmatch(path, pattern)


def classify_file_role(path: str, policy: dict[str, Any]) -> str | None:
    matches: list[str] = []
    for role, config in policy["file_roles"].items():
        if any(_matches(path, pattern) for pattern in config["patterns"]):
            matches.append(role)
    if not matches:
        return None
    # Runtime controls always win. Maintainer-only trees then override broad
    # reference patterns such as */README.md so build/design docs are not
    # misreported as agent reference material.
    for role in ("runtime", "maintainer", "reference"):
        if role in matches:
            return role
    return matches[0]


def _load_codeowners(root: Path) -> str:
    path = root / "CODEOWNERS"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _codeowner_pattern_matches(path: str, pattern: str) -> bool:
    normalized = pattern.lstrip("/")
    if normalized == "*":
        return True
    if normalized.endswith("/"):
        return path.startswith(normalized)
    return fnmatch.fnmatch(path, normalized) or fnmatch.fnmatch(path, f"**/{normalized}")


def codeowners_for(path: str, text: str) -> list[str]:
    owners: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        pattern, declared = fields[0], fields[1:]
        if _codeowner_pattern_matches(path, pattern):
            owners = declared
    return owners


def _yaml_mapping(path: Path) -> dict[str, Any]:
    data = load_unique_yaml_file(path)
    return data if isinstance(data, dict) else {}


def _source_key_exists(path: Path, source_key: str) -> bool:
    if path.suffix.lower() not in {".yaml", ".yml"}:
        # Markdown sources: require an actual heading, not just an incidental
        # mention of the word anywhere in prose (which stays true even after
        # the referenced section is renamed or removed).
        heading_re = re.compile(rf"^#+\s+{re.escape(source_key)}\s*$", re.IGNORECASE | re.MULTILINE)
        return heading_re.search(path.read_text(encoding="utf-8")) is not None
    current: Any = _yaml_mapping(path)
    for part in source_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def _validate_deprecation_mapping(data: dict[str, Any], label: str, required: set[str]) -> list[str]:
    if data.get("status") != "deprecated" and data.get("deprecated") is not True:
        return []
    block = data.get("deprecation")
    if not isinstance(block, dict):
        return [f"error: {label}: deprecated item requires a deprecation mapping"]
    missing = sorted(required - set(block))
    if missing:
        return [f"error: {label}: deprecation missing fields: {', '.join(missing)}"]
    empty = sorted(
        field
        for field in required - {"aliases"}
        if block.get(field) is None or (isinstance(block.get(field), str) and not block[field].strip())
    )
    if empty:
        return [f"error: {label}: deprecation fields must be non-empty: {', '.join(empty)}"]
    if "aliases" in required and not isinstance(block.get("aliases"), list):
        return [f"error: {label}: deprecation aliases must be a list"]
    return []


def _markdown_frontmatter(path: Path) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        return {}
    data = load_unique_yaml(match.group(1))
    return data if isinstance(data, dict) else {}


def _nested_mappings(value: Any, label: str) -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        yield label, value
        for key, child in value.items():
            yield from _nested_mappings(child, f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _nested_mappings(child, f"{label}[{index}]")


def _deprecation_candidates(root: Path, skill_paths: Iterable[str]) -> Iterable[tuple[str, dict[str, Any]]]:
    registry = root / "scripts" / "registry"
    registry_paths = sorted({*registry.glob("*.yaml"), *registry.glob("*.yml")})
    for path in registry_paths:
        rel = path.relative_to(root).as_posix()
        yield from _nested_mappings(_yaml_mapping(path), rel)
    for skill_path in skill_paths:
        directory = root / skill_path
        skill_md = directory / "SKILL.md"
        if skill_md.is_file():
            rel = skill_md.relative_to(root).as_posix()
            yield from _nested_mappings(_markdown_frontmatter(skill_md), rel)
        for pattern in ("reference/*.yaml", "reference/*.yml", "templates/*.yaml", "templates/*.yml"):
            for path in sorted(directory.glob(pattern)):
                rel = path.relative_to(root).as_posix()
                yield from _nested_mappings(_yaml_mapping(path), rel)


def _canonical_contract(root: Path, section: str, legacy_path: str) -> dict[str, Any]:
    raw = load_unique_yaml_file(root / "skills.yaml")
    from scripts.registry.canonical_manifest import has_canonical_manifest_shape

    if not has_canonical_manifest_shape(raw):
        return _yaml_mapping(root / legacy_path)
    manifest = load_canonical_manifest(root)
    contracts = manifest.get("contracts")
    if not isinstance(contracts, dict) or not isinstance(contracts.get(section), dict):
        raise ValueError(f"canonical manifest contracts.{section} must be a mapping")
    return contracts[section]


def _registered_skills(root: Path) -> dict[str, Any]:
    manifest = resolve_registry_profiles(_yaml_mapping(root / "skills.yaml"))
    skills = manifest.get("skills", {})
    return skills if isinstance(skills, dict) else {}


def validate_policy(root: Path = ROOT) -> list[str]:
    policy = load_policy(root / "scripts" / "operational_upkeep.yaml")
    errors: list[str] = []
    if policy.get("schema_version") != 1:
        errors.append("error: operational-upkeep: unsupported schema_version")
    for key in ("policy_version", "prompt_bundle_version", "evaluator_version"):
        if not isinstance(policy.get(key), str) or not policy[key].strip():
            errors.append(f"error: operational-upkeep: {key} must be a non-empty string")

    roles = policy.get("file_roles", {})
    if set(roles) != {"runtime", "reference", "maintainer"}:
        errors.append("error: operational-upkeep: file_roles must be runtime/reference/maintainer")

    skills = _registered_skills(root)
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
            source_path = root / str(item.get("source_path", ""))
            source_key = str(item.get("source_key", ""))
            if not source_path.is_file():
                errors.append(f"error: operational-upkeep: {item_id} source missing: {source_path.relative_to(root)}")
            elif not source_key or not _source_key_exists(source_path, source_key):
                errors.append(f"error: operational-upkeep: {item_id} source key not reachable: {source_key!r}")
            if group == "routes":
                owner = str(item.get("owner", ""))
                if owner not in skills:
                    errors.append(f"error: operational-upkeep: {item_id} route owner is not a registered skill: {owner!r}")
                budget = item.get("token_budget")
                if not isinstance(budget, int) or budget <= 0:
                    errors.append(f"error: operational-upkeep: {item_id} requires a positive token_budget")

    codeowners = _load_codeowners(root)
    for name, contract in policy.get("contract_owners", {}).items():
        rel = str(contract.get("path", ""))
        contract_path = root / rel
        owner = str(contract.get("owner", ""))
        if not contract_path.is_file():
            errors.append(f"error: operational-upkeep: owner contract {name} path missing: {rel}")
        if not owner.startswith("@"):
            errors.append(f"error: operational-upkeep: owner contract {name} has invalid owner {owner!r}")
        elif owner not in codeowners_for(rel, codeowners):
            errors.append(f"error: operational-upkeep: CODEOWNERS does not assign {owner} to {rel}")

    required = set(policy.get("deprecation", {}).get("required_fields", []))
    if not required:
        errors.append("error: operational-upkeep: deprecation required_fields must not be empty")
    skill_paths = [str(entry.get("path", skill_id)) for skill_id, entry in skills.items() if isinstance(entry, dict)]
    for label, data in _deprecation_candidates(root, skill_paths):
        errors.extend(_validate_deprecation_mapping(data, label, required))

    for skill_id, entry in skills.items():
        if not isinstance(entry, dict):
            continue
        skill_path = str(entry.get("path", skill_id))
        skill_md = root / skill_path / "SKILL.md"
        if not skill_md.is_file():
            continue
        if classify_file_role(f"{skill_path}/SKILL.md", policy) != "runtime":
            errors.append(f"error: operational-upkeep: {skill_path}/SKILL.md must be runtime")
        for path in sorted((root / skill_path / "workflow").glob("*.md")):
            rel = path.relative_to(root).as_posix()
            if classify_file_role(rel, policy) != "runtime":
                errors.append(f"error: operational-upkeep: {rel} must be runtime")
        for path in sorted((root / skill_path / "reference").glob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if classify_file_role(rel, policy) != "reference":
                errors.append(f"error: operational-upkeep: {rel} must be reference")
    return errors


def _collect_capability_names(value: Any) -> set[str]:
    """Collect dotted external-capability identifiers (e.g. ``datadog.query_metrics``).

    Excludes free-text values that merely contain a period (degraded_modes
    prose, filenames mentioned in a sentence) and ``<skill-id>.invoke``
    entries, which reference another registered skill rather than an
    external tool/platform capability.
    """
    names: set[str] = set()
    if isinstance(value, str):
        if _CAPABILITY_NAME_RE.fullmatch(value) and not value.endswith(".invoke"):
            names.add(value)
    elif isinstance(value, list):
        for item in value:
            names.update(_collect_capability_names(item))
    elif isinstance(value, dict):
        for item in value.values():
            names.update(_collect_capability_names(item))
    return names


def _orphan_runtime_modules(skills: dict[str, Any], tracked_files: Iterable[Path]) -> list[str]:
    registered_paths = {
        str(entry.get("path", skill_id))
        for skill_id, entry in skills.items()
        if isinstance(entry, dict)
    }
    discovered = {
        path.parent.as_posix()
        for path in tracked_files
        if path.name == "SKILL.md" and len(path.parts) == 2
    }
    return sorted(discovered - registered_paths)


def build_health_report(root: Path = ROOT, revision: str | None = None) -> dict[str, Any]:
    from scripts.eval_tier_health import build_eval_tier_health

    policy = load_policy(root / "scripts" / "operational_upkeep.yaml")
    skills_file = resolve_registry_profiles(_yaml_mapping(root / "skills.yaml"))
    skills = _registered_skills(root)
    composition = _canonical_contract(
        root, "composition", "scripts/registry/composition_contracts.yaml"
    )
    runtime = _canonical_contract(
        root, "composition_runtime", "scripts/registry/composition_runtime.yaml"
    )
    eval_contracts = _yaml_mapping(root / "scripts" / "registry" / "eval_contracts.yaml")
    eval_tier_health = build_eval_tier_health(root)
    tracked_files = _tracked_relative_files(root)

    authority = Counter(
        str(spec.get("write_authority", "unknown"))
        for spec in composition.get("skills", {}).values()
        if isinstance(spec, dict)
    )
    role_counts = Counter()
    for path in tracked_files:
        role = classify_file_role(path.as_posix(), policy)
        if role:
            role_counts[role] += 1

    route_items = policy.get("stable_ids", {}).get("routes", [])
    stop_items = policy.get("stable_ids", {}).get("stop_conditions", [])
    report_items = policy.get("stable_ids", {}).get("report_fields", [])
    eval_case_refs = 0
    for section in ("dimension_coverage", "behavior_scenarios", "degraded_host_cases"):
        for entry in eval_contracts.get(section, {}).values():
            if isinstance(entry, dict):
                eval_case_refs += len(entry.get("case_refs", []))

    capability_names: set[str] = set()
    for entry in skills.values():
        if isinstance(entry, dict):
            capability_names.update(_collect_capability_names(entry.get("capabilities")))
    external_families = sorted({name.split(".", 1)[0] for name in capability_names})
    orphan_modules = _orphan_runtime_modules(skills, tracked_files)

    return {
        "schema_version": 1,
        "provenance": {
            "repository_revision": revision or _git_revision(root),
            "registry_schema_version": skills_file.get("schema_version"),
            "prompt_bundle_version": policy.get("prompt_bundle_version"),
            "evaluator_version": policy.get("evaluator_version"),
            "operational_policy_version": policy.get("policy_version"),
            "generator_version": GENERATOR_VERSION,
        },
        "health": {
            "skills": len(skills),
            "composition_contracts": len(composition.get("skills", {})),
            "artifact_schemas": len(composition.get("artifact_schemas", {})),
            "runtime_handoffs": sum(len(v) for v in runtime.get("handoffs", {}).values()),
            "eval_contract_refs": eval_case_refs,
            "eval_tiers": eval_tier_health,
            "stable_routes": len(route_items),
            "route_token_budget_coverage": sum(
                1 for item in route_items if isinstance(item.get("token_budget"), int) and item["token_budget"] > 0
            ),
            "stable_stop_conditions": len(stop_items),
            "stable_report_fields": len(report_items),
            "contract_owners": len(policy.get("contract_owners", {})),
            "external_dependency_families": external_families,
            "external_dependency_count": len(external_families),
            "orphan_runtime_modules": orphan_modules,
            "orphan_runtime_module_count": len(orphan_modules),
            "file_roles": dict(sorted(role_counts.items())),
            "authority_levels": dict(sorted(authority.items())),
        },
    }


def render_health_markdown(report: dict[str, Any]) -> str:
    p = report["provenance"]
    h = report["health"]
    eval_tiers = h["eval_tiers"]
    tiers = eval_tiers["tiers"]
    lines = [
        "## Prompt-system health",
        "",
        f"- Repository revision: `{p['repository_revision']}`",
        f"- Registry schema: `{p['registry_schema_version']}`",
        f"- Prompt bundle: `{p['prompt_bundle_version']}`",
        f"- Evaluator: `{p['evaluator_version']}`",
        f"- Operational policy: `{p['operational_policy_version']}`",
        f"- Health generator: `{p['generator_version']}`",
        f"- Skills: **{h['skills']}**",
        f"- Composition contracts: **{h['composition_contracts']}**",
        f"- Artifact schemas: **{h['artifact_schemas']}**",
        f"- Runtime handoffs: **{h['runtime_handoffs']}**",
        f"- Eval contract refs: **{h['eval_contract_refs']}**",
        f"- Eval tiers: **{eval_tiers['covered_tiers']}/{eval_tiers['required_tiers']} covered** "
        f"(T1={tiers['tier_1_structural']}, T2={tiers['tier_2_transcript']}, T3={tiers['tier_3_golden']})",
        f"- Unexpected static eval tiers: **{len(eval_tiers['unexpected_static_tiers'])}**",
        f"- Live model harness: **{'available' if eval_tiers['live_model_harness']['available'] else 'missing'}** (non-blocking)",
        f"- Stable IDs: **{h['stable_routes']} routes / {h['stable_stop_conditions']} stops / {h['stable_report_fields']} report fields**",
        f"- Route token-budget coverage: **{h['route_token_budget_coverage']}/{h['stable_routes']}**",
        f"- External dependency families: **{h['external_dependency_count']}**",
        f"- Orphan runtime modules: **{h['orphan_runtime_module_count']}**",
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


def validate_diff_risk(
    paths: list[str],
    policy: dict[str, Any],
    *,
    evidence_paths: list[str] | None = None,
) -> tuple[str, list[str]]:
    risk, _ = classify_diff(paths, policy)
    high = set(policy["prompt_diff_risk"]["high_risk_classes"])
    evidence_patterns = policy["prompt_diff_risk"]["evidence_paths"]
    candidates = paths if evidence_paths is None else evidence_paths
    errors: list[str] = []
    has_evidence = any(_matches(path, pattern) for path in candidates for pattern in evidence_patterns)
    if risk in high and not has_evidence:
        errors.append(
            f"error: prompt-diff risk {risk} requires changed eval/test evidence under "
            + " or ".join(evidence_patterns)
        )
    return risk, errors


def _changed_paths(
    root: Path,
    base: str,
    head: str,
    *,
    diff_filter: str | None = None,
) -> list[str]:
    command = ["git", "diff", "--name-only"]
    if diff_filter:
        command.append(f"--diff-filter={diff_filter}")
    command.append(f"{base}...{head}")
    output = subprocess.check_output(command, cwd=root, text=True)
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
        evidence_paths = _changed_paths(
            ROOT,
            args.base,
            args.head,
            diff_filter="ACMRTUXB",
        )
        risk, errors = validate_diff_risk(paths, policy, evidence_paths=evidence_paths)
        print(f"prompt_diff_risk={risk}")
        print("changed_paths=" + ",".join(paths))
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
