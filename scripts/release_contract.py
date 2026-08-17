#!/usr/bin/env python3
"""Machine-readable release contract: repository version, tag shape, release
artifact names, compatibility policy, and required provenance fields.

`provenance.required_fields` is genuinely the single source of truth for what
a release manifest must carry: package_release.py's manifest builder validates
its (necessarily hardcoded, so it has concrete values to write) field set
against required_provenance_fields() here immediately after building it, and
verify_release_bundle.py's field check calls required_provenance_fields()
directly -- so a field added here without also updating package_release.py's
manifest_fields fails closed at build time with a message naming the actual
mismatch, rather than surfacing later as a confusing verify-time failure.
`tag_pattern` and
`artifact_name_templates` are declarative policy checked here for
well-formedness and consistency with VERSION, but -- unlike required_fields --
nothing downstream derives its actual tag/filename strings from them yet;
verify_release_tag.py and package_release.py/.github/workflows/release.yml
still compute those independently. Keep that gap in mind when editing either
field: this validator won't catch it drifting from what actually ships.
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


def _required_provenance_fields_from_contract(contract: dict) -> set[str]:
    provenance = require_mapping(contract.get("provenance"), "release contract.provenance")
    fields = provenance.get("required_fields")
    if not isinstance(fields, list) or not fields or not all(isinstance(item, str) for item in fields):
        raise ValueError("release contract.provenance.required_fields must be a non-empty list of strings")
    return set(fields)


def required_provenance_fields(path: Path = CONTRACT_PATH) -> set[str]:
    return _required_provenance_fields_from_contract(_load_contract(path))


def _compatibility_schema_versions_from_contract(contract: dict) -> dict[str, int]:
    compatibility = require_mapping(contract.get("compatibility"), "release contract.compatibility")
    versions: dict[str, int] = {}
    for key in ("registry_schema_version", "host_contract_schema_version"):
        value = compatibility.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"release contract.compatibility.{key} must be an integer")
        versions[key] = value
    return versions


def compatibility_schema_versions(path: Path = CONTRACT_PATH) -> dict[str, int]:
    """registry_schema_version/host_contract_schema_version a release manifest must
    declare to be compatible with this contract.

    Shared with verify_release_bundle.py so a manifest's schema-version fields are
    checked against the same compatibility policy validate_release_contract() enforces
    on a live repository -- not just checked for being well-typed integers, which would
    let a bundle embedding a stale or wrong schema version (a package_release.py bug, or
    a tampered manifest with self-consistent file hashes) verify cleanly.
    """
    return _compatibility_schema_versions_from_contract(_load_contract(path))


def validate_release_contract(root: Path = ROOT) -> list[str]:
    # Load the contract from root's own scripts/release_contract.yaml, not the
    # hardcoded CONTRACT_PATH default -- otherwise a caller that passes a root
    # other than this script's own repo (e.g. `--repo-root` pointed at a
    # different checkout) would silently validate that repo's VERSION/
    # skills.yaml/host_contracts.yaml against *this* repo's contract instead
    # of its own. For the common case (root is this repo), the two paths
    # resolve identically, so default behavior is unchanged.
    try:
        contract = _load_contract(root / "scripts" / "release_contract.yaml")
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
            except (KeyError, IndexError, ValueError, AttributeError, TypeError):
                # ValueError also covers a malformed format spec/conversion (e.g. a typo'd
                # "{version:04d}" or "{version!z}") -- str.format() raises ValueError for
                # those, not KeyError/IndexError. AttributeError and TypeError cover a
                # typo'd dotted/subscript field (e.g. "{version.major}" raises
                # AttributeError since version is a plain str; "{version[abc]}" raises
                # TypeError for the same reason) -- str.format()'s field-name mini-language
                # accepts that syntax and only fails once it tries to resolve it against the
                # actual value passed in. Without every one of these, a contract-file typo
                # crashes this validator with a raw traceback instead of a clean error.
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
            # Don't also prefix {path} here: read_schema_version()'s ValueError and a
            # missing-file OSError both already embed the path in str(exc), so adding
            # it again produced doubled output, e.g. "... contract: X: X: schema_version
            # must be an integer".
            errors.append(f"error: release contract: {exc}")
            continue
        if actual != expected:
            errors.append(
                f"error: release contract: {path} schema_version {actual!r} does not match "
                f"compatibility.{key} {expected!r}",
            )

    try:
        _required_provenance_fields_from_contract(contract)
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
