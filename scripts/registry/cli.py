from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

from scripts.registry.backfill_capabilities import cmd_backfill
from scripts.registry.capability_family_sync import validate_capability_families
from scripts.registry.capability_sync import validate_capability_catalog_sync
from scripts.registry.composition import render_composition_mermaid
from scripts.registry.composition_runtime import (
    handoff_allowed,
    render_dependency_graph,
    validate_composition_runtime,
)
from scripts.registry.crosscheck import find_stale_generated_adapters, validate_registry
from scripts.registry.generate_compatibility import render_compatibility_matrix
from scripts.registry.generate_cursor import generate_cursor_rules
from scripts.registry.generate_docs import (
    render_install_mermaid,
    update_readme_badge,
    update_repository_table,
)
from scripts.registry.generate_kiro import generate_kiro_steering
from scripts.registry.load import load_descriptions, load_registry
from scripts.registry.manifest import validate_manifest
from scripts.registry.p1_validation import validate_p1_contracts
from scripts.registry.runtime_manifest import validate_runtime_manifest

ROOT = Path(__file__).resolve().parents[2]


def _collect_outputs(root: Path) -> dict[Path, str]:
    registry = load_registry(root)
    descriptions = load_descriptions(root, registry)
    outputs: dict[Path, str] = {}
    outputs.update(generate_cursor_rules(root, registry, descriptions))
    outputs.update(generate_kiro_steering(root, registry))
    outputs[root / "README.md"] = update_readme_badge(
        (root / "README.md").read_text(encoding="utf-8"),
        len(registry.skills),
    )
    outputs[root / "docs" / "REPOSITORY.md"] = update_repository_table(
        (root / "docs" / "REPOSITORY.md").read_text(encoding="utf-8"),
        registry,
    )
    outputs[root / "generated" / "catalogue" / "install-deps.mmd"] = render_install_mermaid(
        registry,
    )
    outputs[root / "generated" / "catalogue" / "composition-deps.mmd"] = render_composition_mermaid(
        registry,
    )
    compatibility_catalog = root / "scripts" / "registry" / "capability_catalog.yaml"
    composition_contracts = root / "scripts" / "registry" / "composition_contracts.yaml"
    if compatibility_catalog.is_file() and composition_contracts.is_file():
        outputs[root / "generated" / "catalogue" / "compatibility-matrix.md"] = (
            render_compatibility_matrix(root)
        )
    composition_runtime = _composition_runtime_path(root)
    if composition_runtime.is_file() and composition_contracts.is_file():
        outputs[root / "generated" / "catalogue" / "composition-runtime.mmd"] = render_dependency_graph(
            registry,
            runtime_path=composition_runtime,
            contracts_path=composition_contracts,
        )
    return outputs


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
    try:
        return action()
    except (ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _capability_catalog_path(root: Path) -> Path:
    return root / "scripts" / "registry" / "capability_catalog.yaml"


def _capability_families_path(root: Path) -> Path:
    return root / "scripts" / "registry" / "capability_families.yaml"


def _platform_contracts_path(root: Path) -> Path:
    return root / "scripts" / "registry" / "platform_contracts.yaml"


def _composition_runtime_path(root: Path) -> Path:
    return root / "scripts" / "registry" / "composition_runtime.yaml"


def _p1_layer_paths(root: Path) -> list[Path]:
    return [
        root / "scripts" / "registry" / "host_contracts.yaml",
        root / "scripts" / "registry" / "eval_contracts.yaml",
        root / "docs" / "skill-framework" / "shared" / "runtime-contract.md",
        root / "docs" / "skill-framework" / "shared" / "host-adapter-contract.md",
        root / "docs" / "skill-framework" / "shared" / "eval-contract.md",
    ]


def _validate_for_generate(root: Path) -> list[str]:
    errors = validate_registry(root)
    if _capability_catalog_path(root).is_file():
        errors.extend(validate_capability_catalog_sync(root))
    if _capability_catalog_path(root).is_file() and _capability_families_path(root).is_file():
        errors.extend(
            validate_capability_families(
                catalog_path=_capability_catalog_path(root),
                families_path=_capability_families_path(root),
            )
        )
    if _platform_contracts_path(root).is_file():
        errors.extend(validate_manifest(root))
    if any(path.is_file() for path in _p1_layer_paths(root)):
        errors.extend(validate_p1_contracts(root))
    if _composition_runtime_path(root).is_file():
        errors.extend(
            validate_composition_runtime(
                load_registry(root),
                runtime_path=_composition_runtime_path(root),
                contracts_path=root / "scripts" / "registry" / "composition_contracts.yaml",
            )
        )
    return errors


def _validate_all(root: Path) -> list[str]:
    # Strict superset of _validate_for_generate: same optional-layer gating,
    # plus the integrated runtime manifest once the P1 layer is present.
    errors = _validate_for_generate(root)
    if any(path.is_file() for path in _p1_layer_paths(root)):
        errors.extend(validate_runtime_manifest(root))
    return errors


def cmd_validate(root: Path) -> int:
    errors = _validate_all(root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(
        "ok: skills registry, capability catalogue, integrated runtime manifest, "
        "P1 contracts and composition contracts validate"
    )
    return 0


def cmd_generate(root: Path, check_only: bool) -> int:
    if not check_only:
        _prune_stale_adapters(root)

    validation_errors = _validate_for_generate(root)
    if validation_errors:
        for error in validation_errors:
            print(error, file=sys.stderr)
        return 1

    outputs = _collect_outputs(root)
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
    removed = _prune_stale_adapters(root)
    print(f"ok: generated {len(outputs)} files; removed {removed} stale adapters")
    return 0


def cmd_check_handoff(root: Path, target_skill: str, visited_skills: list[str], depth: int) -> int:
    allowed, reason = handoff_allowed(
        target_skill,
        visited_skills=visited_skills,
        depth=depth,
        runtime_path=_composition_runtime_path(root),
    )
    if allowed:
        print(f"ok: handoff to {target_skill!r} allowed at depth {depth}")
        return 0
    print(f"error: handoff to {target_skill!r} blocked: {reason}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.registry")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="validate skills.yaml, capabilities and platform contracts")

    generate_parser = subparsers.add_parser("generate", help="generate adapters and derived docs")
    generate_parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if generated files would change",
    )

    backfill_parser = subparsers.add_parser(
        "backfill-capabilities",
        help="insert capabilities blocks from capability_catalog.yaml",
    )
    backfill_parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if any skill is missing a capabilities block",
    )
    backfill_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="regenerate every skill's capabilities block from the catalog, even if already valid",
    )

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

    args = parser.parse_args(argv)
    if args.command == "validate":
        return _run_command(lambda: cmd_validate(ROOT))
    if args.command == "generate":
        return _run_command(lambda: cmd_generate(ROOT, check_only=args.check))
    if args.command == "backfill-capabilities":
        return cmd_backfill(
            check_only=args.check,
            overwrite=args.overwrite,
            skills_path=ROOT / "skills.yaml",
        )
    if args.command == "check-handoff":
        visited = [skill_id for skill_id in args.visited.split(",") if skill_id]
        return _run_command(
            lambda: cmd_check_handoff(ROOT, args.target_skill, visited, args.depth)
        )

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())