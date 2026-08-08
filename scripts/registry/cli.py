from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

from scripts.registry.crosscheck import find_stale_generated_adapters, validate_registry
from scripts.registry.generate_cursor import generate_cursor_rules
from scripts.registry.generate_docs import (
    render_composition_mermaid,
    render_install_mermaid,
    update_readme_badge,
    update_repository_table,
)
from scripts.registry.generate_kiro import generate_kiro_steering
from scripts.registry.load import load_descriptions, load_registry

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


def cmd_validate(root: Path) -> int:
    errors = validate_registry(root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("ok: skills registry validates")
    return 0


def cmd_generate(root: Path, check_only: bool) -> int:
    if not check_only:
        _prune_stale_adapters(root)

    validation_errors = validate_registry(root)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.registry")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="validate skills.yaml and SKILL.md frontmatter")

    generate_parser = subparsers.add_parser("generate", help="generate adapters and derived docs")
    generate_parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if generated files would change",
    )

    args = parser.parse_args(argv)
    if args.command == "validate":
        return _run_command(lambda: cmd_validate(ROOT))
    if args.command == "generate":
        return _run_command(lambda: cmd_generate(ROOT, check_only=args.check))

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
