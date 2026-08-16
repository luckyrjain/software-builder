#!/usr/bin/env python3
"""Machine-readable release contract: repository version, tag shape, release
artifact names, compatibility policy, and required provenance fields.

The contract data lives in release_contract.yaml so package_release.py (which
builds RELEASE-MANIFEST.json) and verify_release_bundle.py (which checks it)
share a single source of truth for the provenance fields a release must
carry, instead of each hardcoding its own copy of the list.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.release_info import read_distribution_version
from scripts.yaml_safety import (
    YAML_SAFETY_ERRORS,
    load_unique_yaml_file,
    read_schema_version,
    require_mapping,
)

CONTRACT_PATH = Path(__file__).resolve().parent / "release_contract.yaml"


def _load_contract(path: Path = CONTRACT_PATH) -> dict:
    raw = require_mapping(load_unique_yaml_file(path), "release contract")
    schema_version = raw.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
        raise ValueError(f"{path}: schema_version must be 1")
    return raw


def required_provenance_fields(path: Path = CONTRACT_PATH) -> set[str]:
    contract = _load_contract(path)
    provenance = require_mapping(contract.get("provenance"), "release contract.provenance")
    fields = provenance.get("required_fields")
    if not isinstance(fields, list) or not fields or not all(isinstance(item, str) for item in fields):
        raise ValueError("release contract.provenance.required_fields must be a non-empty list of strings")
    return set(fields)


def validate_release_contract(root: Path = ROOT) -> list[str]:
    try:
        contract = _load_contract()
    except (OSError, *YAML_SAFETY_ERRORS) as exc:
        return [f"error: release contract: {exc}"]

    errors: list[str] = []

    try:
        version = read_distribution_version(root)
    except ValueError as exc:
        return [f"error: release contract: {exc}"]

    tag_pattern = contract.get("tag_pattern")
    if not isinstance(tag_pattern, str):
        errors.append("error: release contract: tag_pattern must be a string")
    else:
        try:
            tag_matches = re.fullmatch(tag_pattern, f"v{version}")
        except re.error as exc:
            errors.append(f"error: release contract: tag_pattern {tag_pattern!r} is not a valid regex: {exc}")
        else:
            if not tag_matches:
                errors.append(
                    f"error: release contract: VERSION {version!r} does not produce a tag matching "
                    f"{tag_pattern!r}",
                )

    templates = contract.get("artifact_name_templates")
    if not isinstance(templates, list) or not templates or not all(isinstance(item, str) for item in templates):
        errors.append("error: release contract: artifact_name_templates must be a non-empty list of strings")
    else:
        for template in templates:
            try:
                template.format(version=version)
            except (KeyError, IndexError):
                errors.append(f"error: release contract: artifact_name_template {template!r} is malformed")

    try:
        compatibility = require_mapping(contract.get("compatibility"), "release contract.compatibility")
    except ValueError as exc:
        errors.append(f"error: release contract: {exc}")
        compatibility = {}

    schema_checks = {
        "registry_schema_version": root / "skills.yaml",
        "host_contract_schema_version": root / "scripts" / "registry" / "host_contracts.yaml",
    }
    for key, path in schema_checks.items():
        expected = compatibility.get(key)
        if not isinstance(expected, int) or isinstance(expected, bool):
            errors.append(f"error: release contract: compatibility.{key} must be an integer")
            continue
        try:
            actual = read_schema_version(path)
        except (OSError, *YAML_SAFETY_ERRORS) as exc:
            errors.append(f"error: release contract: {path}: {exc}")
            continue
        if actual != expected:
            errors.append(
                f"error: release contract: {path} schema_version {actual!r} does not match "
                f"compatibility.{key} {expected!r}",
            )

    try:
        required_provenance_fields()
    except ValueError as exc:
        errors.append(f"error: release contract: {exc}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release_contract")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    errors = validate_release_contract(args.repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("ok: release contract validates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
