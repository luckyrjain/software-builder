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
`tag_template` is likewise consumed, not just checked: verify_release_tag.py
renders it against VERSION through release_tag_for_version() and requires the
pushed tag to equal the result, so the tag shape has one declaration.
`artifact_name_templates` is declarative policy checked here for
well-formedness and consistency with VERSION, but nothing downstream derives
its actual filename strings from it yet; package_release.py and
.github/workflows/release.yml still compute those independently. Keep that
gap in mind when editing it: this validator won't catch it drifting from what
actually ships.
"""

from __future__ import annotations

import argparse
import string
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

def release_tag_from_contract(contract: dict, version: str) -> str:
    """The release tag `version` maps to under the contract's `tag_template`.

    The template is plain str.format text with exactly one `{version}` field and no
    other replacement fields -- a tag shape is a literal prefix around the version, and
    keeping it a template (never a pattern) means nothing here compiles data.
    """
    template = contract.get("tag_template")
    if not isinstance(template, str) or not template:
        raise ValueError("release contract.tag_template must be a non-empty string")
    fields = [
        field_name
        for _literal, field_name, _spec, _conversion in string.Formatter().parse(template)
        if field_name is not None
    ]
    if fields != ["version"]:
        raise ValueError(
            "release contract.tag_template must contain exactly one {version} placeholder "
            f"and no other fields, got {template!r}",
        )
    return template.format(version=version)


def release_tag_for_version(version: str, path: Path = CONTRACT_PATH) -> str:
    """Render the contract's tag_template for `version` (verify_release_tag.py's seam)."""
    return release_tag_from_contract(_load_contract(path), version)


def _load_contract(path: Path = CONTRACT_PATH) -> dict:
    raw = require_mapping(load_unique_yaml_file(path), "release contract")
    # Reuses the same "read + type-check schema_version" logic every other schema_version
    # check in this codebase shares (yaml_safety.read_schema_version), instead of
    # re-implementing the int/bool type check inline here too -- otherwise a future change
    # to what counts as a valid schema_version would need to be mirrored in both places or
    # they'd drift, exactly what sharing this helper elsewhere in this module already avoids.
    if read_schema_version(path, raw=raw) != 1:
        raise ValueError(f"{path}: schema_version must be 1")
    return raw


def load_contract(path: Path = CONTRACT_PATH) -> dict:
    """Parse and shape-check the release contract YAML file (schema_version == 1).

    Exposed publicly (unlike _load_contract) so a caller needing more than one
    contract-derived value in a single pass -- verify_release_bundle.py needs both
    required_provenance_fields_from_contract() and
    compatibility_schema_versions_from_contract() -- can read and parse the YAML file
    once and reuse the resulting dict, instead of calling required_provenance_fields()
    and compatibility_schema_versions() separately and re-reading/re-parsing the same
    file from disk for each.
    """
    return _load_contract(path)


def required_provenance_fields_from_contract(contract: dict) -> set[str]:
    provenance = require_mapping(contract.get("provenance"), "release contract.provenance")
    fields = provenance.get("required_fields")
    if not isinstance(fields, list) or not fields or not all(isinstance(item, str) for item in fields):
        raise ValueError("release contract.provenance.required_fields must be a non-empty list of strings")
    return set(fields)


def required_provenance_fields(path: Path = CONTRACT_PATH) -> set[str]:
    return required_provenance_fields_from_contract(_load_contract(path))


def compatibility_schema_versions_from_contract(contract: dict) -> dict[str, int]:
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
    return compatibility_schema_versions_from_contract(_load_contract(path))


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
    except (OSError, ValueError) as exc:
        # OSError (not just ValueError) so a VERSION file that exists but isn't readable
        # (e.g. a permission error) prints a clean error instead of an uncaught traceback --
        # read_distribution_version()'s read_text() call can raise either.
        return [f"error: release contract: {exc}"]

    try:
        release_tag_from_contract(contract, version)
    except ValueError as exc:
        errors.append(f"error: release contract: {exc}")

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
        required_provenance_fields_from_contract(contract)
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
