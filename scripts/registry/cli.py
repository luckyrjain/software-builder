from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

from scripts.registry.capability_catalog import cmd_check_capabilities
from scripts.registry.agent_skills import validate_agent_skills
from scripts.registry.artifact_contracts import validate_artifact_result
from scripts.registry.canonical_manifest import (
    has_canonical_manifest_shape,
    load_canonical_manifest,
    validate_canonical_manifest,
)
from scripts.registry.capability_family_sync import validate_capability_families
from scripts.registry.composition_runtime import handoff_allowed, validate_composition_runtime
from scripts.registry.crosscheck import find_stale_generated_adapters, validate_registry
from scripts.registry.generators import collect_outputs
from scripts.registry.generic_package import build_generic_package
from scripts.registry.host_portability import validate_host_portability
from scripts.registry.host_adapter import (
    validate_host_adapter_identities,
    validate_host_adapter_interface,
)
from scripts.registry.host_registry import HostRegistryParseError, parse_host_registry
from scripts.registry.layers import LAYER_LABELS, OptionalLayers, detect_optional_layers

# Re-exported: scripts/check_platform_files.py and the optional-layer tests reach these
# through this module, which owned them before layers.py existed.
from scripts.registry.layers import optional_layer_paths as optional_layer_paths
from scripts.registry.load import load_registry
from scripts.registry.manifest import validate_manifest, validate_runtime_manifest
from scripts.registry.p1_validation import validate_p1_contracts
from scripts.registry.schema import clear_registry_cache, load_registry_raw
from scripts.release_contract import validate_release_contract

ROOT = Path(__file__).resolve().parents[2]


def _write_outputs(outputs: dict[Path, str]) -> None:
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _prune_stale_adapters(root: Path) -> int:
    registry = load_registry(root)
    stale = find_stale_generated_adapters(root, registry)
    for path in stale:
        path.unlink()
    return len(stale)


def _check_outputs(root: Path, outputs: dict[Path, str]) -> list[str]:
    errors: list[str] = []
    for path, expected in outputs.items():
        rel = path.relative_to(root)
        if not path.exists():
            errors.append(f"error: missing generated file: {rel}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            errors.append(f"error: generated file drift: {rel}")
    registry = load_registry(root)
    for path in find_stale_generated_adapters(root, registry):
        errors.append(f"error: stale generated adapter: {path.relative_to(root)}")
    return errors


def _run_command(action: Callable[[], int]) -> int:
    # Every _run_command-wrapped subcommand is the first (and only) reader of
    # schema.py's load_registry_raw cache in its process today, so this clear is a
    # no-op in practice when reached via main() -- but it makes that guarantee hold
    # here, once, for every subcommand this function wraps, rather than depending on
    # each one independently remembering to clear at its own entry. cmd_list,
    # cmd_explain, cmd_validate_agent_skills, cmd_check_handoff, and
    # cmd_validate_artifact never had their own entry-clear despite reading the same
    # cache; this closes that gap for all of them at once. cmd_validate's own
    # clear_registry_cache() call at its entry is now redundant with this one when
    # reached through main() -- kept anyway since cmd_validate could plausibly be
    # called directly in a test someday, the way cmd_generate already is (see its own
    # comment). cmd_generate's entry clear is NOT redundant: scripts/tests/test_registry.py
    # calls cmd_generate(...) directly, bypassing this function entirely, so its own
    # clear is the only one those callers get; its second clear_registry_cache() call
    # after _write_outputs is separately load-bearing invalidation for the write that
    # just happened, unrelated to entry invalidation. cmd_check_capabilities is wrapped too
    # (see main()'s dispatch) so a malformed skills.d/*.yaml fragment gets the same clean
    # `error:`/exit-2 contract every other subcommand gives Makefile/CI callers, instead of
    # an unhandled traceback from load_registry_raw.
    clear_registry_cache()
    try:
        return action()
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _validate_for_generate(root: Path, layers: OptionalLayers | None = None) -> list[str]:
    layers = layers if layers is not None else detect_optional_layers(root)
    errors = validate_registry(root)
    if layers.host_contracts is not None:
        errors.extend(validate_host_adapter_interface(root))
        errors.extend(validate_host_adapter_identities(root))
    if layers.capability_catalog is not None and layers.capability_families is not None:
        errors.extend(
            validate_capability_families(
                catalog_path=layers.capability_catalog,
                families_path=layers.capability_families,
            )
        )
    raw_manifest = load_registry_raw(root / "skills.yaml")
    if has_canonical_manifest_shape(raw_manifest):
        errors.extend(validate_manifest(root))
    if layers.p1_layer_active:
        errors.extend(validate_p1_contracts(root))
    if layers.composition_runtime is not None:
        errors.extend(
            validate_composition_runtime(
                load_registry(root),
                runtime_path=layers.composition_runtime,
                contracts_path=layers.composition_contracts,
            )
        )
    return errors


def _validate_all(root: Path, layers: OptionalLayers | None = None) -> list[str]:
    # Strict superset of _validate_for_generate: same optional-layer gating,
    # plus integrated runtime and host-portability validation. Portability is
    # intentionally kept out of the mutating generate path because it checks
    # generated Cursor/Kiro surfaces that `generate` may need to repair.
    layers = layers if layers is not None else detect_optional_layers(root)
    errors = _validate_for_generate(root, layers)
    if layers.p1_layer_active:
        errors.extend(validate_runtime_manifest(root))
    errors.extend(validate_host_portability(root))
    if layers.release_contract is not None:
        errors.extend(validate_release_contract(root))
    return errors


def cmd_validate(root: Path) -> int:
    clear_registry_cache()
    layers = detect_optional_layers(root)
    errors = _validate_all(root, layers)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    ran = [label for field, label in LAYER_LABELS if getattr(layers, field) is not None]
    skipped = [label for field, label in LAYER_LABELS if getattr(layers, field) is None]
    if layers.p1_layer_active:
        ran.append("P1 contracts")
        ran.append("integrated runtime manifest")
    else:
        skipped.append("P1 contracts")
        skipped.append("integrated runtime manifest")
    # Name only what actually ran: a success line that lists a layer this root skipped is
    # indistinguishable from one that checked it, which is exactly what makes the
    # `is_file()` gates dangerous.
    message = "ok: skills registry, host portability, " + ", ".join(ran) + " validate"
    if skipped:
        message += " (skipped, not present: " + ", ".join(skipped) + ")"
    print(message)
    return 0


def cmd_validate_agent_skills(root: Path) -> int:
    errors = validate_agent_skills(root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("ok: Agent Skills conformance validates")
    return 0


def cmd_validate_hosts(root: Path) -> int:
    # No longer cross-checks agent-hosts.yaml's host ids against host_adapter.HOSTS as a subset
    # relationship (Candidate 2's original check, added before this registry had grown past
    # cursor/claude/kiro -- all of which happened to already be in HOSTS). Candidate 12 (spec
    # Section 64, "add other agents based on evidence") revealed that constraint to be wrong:
    # agent-hosts.yaml is the canonical, evidence-gated host-identity registry (spec Section 13),
    # and is explicitly meant to grow independently of host_adapter.py's older,
    # adapter-generation-focused HOSTS set -- github-copilot is real evidence-backed data here
    # (see agent-hosts.yaml's own comment) with no host_contracts.yaml/host_adapter.py entry, and
    # requiring one would mean fabricating that older system's per-capability-family support
    # levels with zero evidence, which is exactly what this registry exists to avoid.
    try:
        parse_host_registry(root / "agent-hosts.yaml")
    except HostRegistryParseError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("ok: agent host registry validates")
    return 0


def cmd_generate(root: Path, check_only: bool) -> int:
    # A fresh invocation must never inherit another invocation's cached skills.yaml read
    # (schema.py's load_registry_raw cache) -- e.g. two cmd_generate calls against the
    # same root within one process, as several tests do.
    clear_registry_cache()
    if not check_only:
        _prune_stale_adapters(root)

    validation_errors = _validate_for_generate(root)
    if validation_errors:
        for error in validation_errors:
            print(error, file=sys.stderr)
        return 1

    outputs = collect_outputs(root)
    if check_only:
        drift_errors = _check_outputs(root, outputs)
        if drift_errors:
            for error in drift_errors:
                print(error, file=sys.stderr)
            print("hint: run make generate to refresh generated files", file=sys.stderr)
            return 1
        print("ok: generated files are up to date")
        return 0

    _write_outputs(outputs)
    # skills.yaml may be among the just-written outputs (the skills.d/ fragment-merge
    # projection) -- invalidate before the second _prune_stale_adapters read below, so it
    # sees the just-written state rather than the pre-write cache entry from this same call.
    clear_registry_cache()
    removed = _prune_stale_adapters(root)
    print(f"ok: generated {len(outputs)} files; removed {removed} stale adapters")
    return 0


def cmd_package_generic(root: Path, output: Path) -> int:
    build_generic_package(root, output)
    print(f"ok: wrote deterministic generic package to {output}")
    return 0


def cmd_check_handoff(root: Path, target_skill: str, visited_skills: list[str], depth: int) -> int:
    allowed, reason = handoff_allowed(
        target_skill,
        visited_skills=visited_skills,
        depth=depth,
        # load_composition_runtime resolves canonical-vs-projection itself for a
        # skills.yaml path, so this stays the same decision every other reader takes.
        runtime_path=root / "skills.yaml",
    )
    if allowed:
        print(f"ok: handoff to {target_skill!r} allowed at depth {depth}")
        return 0
    print(f"error: handoff to {target_skill!r} blocked: {reason}", file=sys.stderr)
    return 1


def cmd_validate_artifact(
    root: Path,
    artifact_type: str,
    result_path: Path,
    producer_skill: str,
) -> int:
    """Validate one JSON durable-artifact result at the runtime boundary."""
    def reject_constant(value: str) -> object:
        raise ValueError(f"invalid JSON constant {value!r}")

    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key {key!r}")
            result[key] = value
        return result

    payload = json.loads(
        result_path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_pairs,
        parse_constant=reject_constant,
    )
    errors = validate_artifact_result(root, artifact_type, payload, producer_skill=producer_skill)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"ok: durable artifact {artifact_type!r} validates")
    return 0


def cmd_list(root: Path) -> int:
    manifest = _validated_canonical_manifest(root)
    registry = load_registry(root)
    print("Skill | Version | Type | Category | Invocation | Authority")
    print("----- | ------- | ---- | -------- | ---------- | ---------")
    for skill_id, entry in sorted(registry.skills.items()):
        skill = manifest["skills"].get(skill_id)
        if not isinstance(skill, dict):
            raise ValueError(f"canonical manifest missing skill {skill_id!r}")
        print(
            f"{_display_text(skill_id)} | {_display_text(skill['version'])} | "
            f"{_display_text(skill['type'])} | {_display_text(skill['category'])} | "
            f"{_display_text(skill['invocation'])} | {_display_text(skill['authority'])}"
        )
    return 0


def cmd_explain(root: Path, skill_id: str) -> int:
    manifest = _validated_canonical_manifest(root)
    registry = load_registry(root)
    skill = manifest["skills"].get(skill_id)
    entry = registry.skills.get(skill_id)
    if not isinstance(skill, dict) or entry is None:
        print(f"error: unknown skill {skill_id!r}", file=sys.stderr)
        return 1

    print(f"Skill: {_display_text(skill_id)}")
    print(f"Version: {_display_text(skill['version'])}")
    print(f"Type: {_display_text(skill['type'])}")
    print(f"Category: {_display_text(skill['category'])}")
    print(f"Invocation: {_display_text(skill['invocation'])}")
    print(f"Authority: {_display_text(skill['authority'])}")
    print(f"Permissions: {_display_text(yaml.safe_dump(skill['permissions'], default_flow_style=True).strip())}")
    print(f"Supported hosts: {_display_text(', '.join(skill['supported_hosts']))}")
    print(f"Entrypoint: {_display_text(skill['entrypoint'])}")
    print(f"Output contract: {_display_text(yaml.safe_dump(skill['output_contract'], default_flow_style=True).strip())}")
    dependencies = skill["dependencies"] or []
    print(f"Dependencies: {_display_text(', '.join(dependencies) if dependencies else 'none')}")
    return 0


def _validated_canonical_manifest(root: Path) -> dict:
    raw = load_registry_raw(root / "skills.yaml")
    if not isinstance(raw, dict) or raw.get("manifest_kind") != "canonical":
        raise ValueError("canonical manifest required for this command")
    errors = validate_canonical_manifest(root)
    if errors:
        raise ValueError("\n".join(errors))
    return load_canonical_manifest(root)


def _display_text(value: object) -> str:
    """Keep untrusted manifest text on one terminal line."""
    escaped: list[str] = []
    for char in str(value):
        codepoint = ord(char)
        if char == "\\":
            escaped.append("\\\\")
        elif char == "|":
            escaped.append("\\|")
        elif codepoint < 0x20 or codepoint == 0x7F:
            escaped.append(f"\\x{codepoint:02x}")
        else:
            escaped.append(char)
    return "".join(escaped)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.registry")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="validate skills.yaml, capabilities and platform contracts")

    subparsers.add_parser(
        "validate-agent-skills",
        help="validate portable Agent Skills frontmatter conformance",
    )

    subparsers.add_parser(
        "validate-hosts",
        help="validate the declarative agent host registry",
    )

    subparsers.add_parser("list", help="list registered skills and their canonical metadata")

    explain_parser = subparsers.add_parser(
        "explain",
        help="explain one skill's canonical metadata and runtime contract",
    )
    explain_parser.add_argument("skill_id", help="registered skill identifier")

    generate_parser = subparsers.add_parser("generate", help="generate adapters and derived docs")
    generate_parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if generated files would change",
    )

    package_parser = subparsers.add_parser(
        "package-generic",
        help="build the deterministic generic-agent skill bundle",
    )
    package_parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/software-builder-skills.tar.gz"),
        help="archive output path",
    )

    backfill_parser = subparsers.add_parser(
        "backfill-capabilities",
        help="validate that every registered skill declares a capabilities block",
    )
    # capability_catalog.yaml is generated from the skills.d/ fragments now, so there is no
    # write direction left to select and drift is a generate-check failure. Both flags are
    # accepted, and ignored, so the make targets that pass them keep working while they are
    # retired.
    backfill_parser.add_argument("--check", action="store_true", help=argparse.SUPPRESS)
    backfill_parser.add_argument("--overwrite", action="store_true", help=argparse.SUPPRESS)

    handoff_parser = subparsers.add_parser(
        "check-handoff",
        help="apply the recursion guard before an orchestrator/router/trigger hands off to another skill",
    )
    handoff_parser.add_argument("target_skill", help="skill id the handoff would invoke")
    handoff_parser.add_argument("--depth", type=int, required=True, help="current execution_context.depth")
    handoff_parser.add_argument(
        "--visited",
        default="",
        help="comma-separated execution_context.visited_skills (e.g. release-readiness-checker,pr-review)",
    )

    artifact_parser = subparsers.add_parser(
        "validate-artifact",
        help="validate one JSON durable-artifact result against the canonical runtime contract",
    )
    artifact_parser.add_argument("artifact_type", help="artifact type declared in skills.yaml")
    artifact_parser.add_argument("result_json", type=Path, help="JSON file containing the artifact result")
    artifact_parser.add_argument(
        "--producer-skill",
        required=True,
        help="trusted runtime identity of the producer; must match skill_result.skill",
    )

    args = parser.parse_args(argv)
    if args.command == "validate":
        return _run_command(lambda: cmd_validate(ROOT))
    if args.command == "validate-agent-skills":
        return _run_command(lambda: cmd_validate_agent_skills(ROOT))
    if args.command == "validate-hosts":
        return _run_command(lambda: cmd_validate_hosts(ROOT))
    if args.command == "list":
        return _run_command(lambda: cmd_list(ROOT))
    if args.command == "explain":
        return _run_command(lambda: cmd_explain(ROOT, args.skill_id))
    if args.command == "generate":
        return _run_command(lambda: cmd_generate(ROOT, check_only=args.check))
    if args.command == "package-generic":
        output = args.output if args.output.is_absolute() else ROOT / args.output
        return _run_command(lambda: cmd_package_generic(ROOT, output.resolve()))
    if args.command == "backfill-capabilities":
        return _run_command(lambda: cmd_check_capabilities(skills_path=ROOT / "skills.yaml"))
    if args.command == "check-handoff":
        visited = [skill_id for skill_id in args.visited.split(",") if skill_id]
        return _run_command(
            lambda: cmd_check_handoff(ROOT, args.target_skill, visited, args.depth)
        )
    if args.command == "validate-artifact":
        result_path = args.result_json if args.result_json.is_absolute() else ROOT / args.result_json
        return _run_command(
            lambda: cmd_validate_artifact(
                ROOT,
                args.artifact_type,
                result_path.resolve(),
                args.producer_skill,
            )
        )

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
