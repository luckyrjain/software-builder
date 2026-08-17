#!/usr/bin/env python3
"""Independently verify a packaged release bundle before it is uploaded.

Extracts the archive into an isolated directory (rejecting path traversal
and other unsafe tar members along the way) and checks: exactly one
top-level directory, a well-formed RELEASE-MANIFEST.json with every required
provenance field, and an exact match between the manifest's file list/hashes
and what is actually in the bundle -- nothing missing, nothing extra,
nothing tampered.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reference_utils import sha256_file
from scripts.release_contract import (
    compatibility_schema_versions_from_contract,
    load_contract,
    required_provenance_fields_from_contract,
)
from scripts.release_info import PACKAGE_NAME, RELEASE_MANIFEST_NAME, SEMVER_RE, SHA_RE
from scripts.yaml_safety import YAML_SAFETY_ERRORS

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _safe_extract(archive: Path, dest: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(dest, filter="data")


def verify_release_bundle(archive: Path) -> list[str]:
    if not archive.is_file():
        return [f"error: release bundle not found: {archive}"]

    with tempfile.TemporaryDirectory() as tmp:
        extract_dir = Path(tmp)
        try:
            _safe_extract(archive, extract_dir)
        except (tarfile.TarError, OSError) as exc:
            return [f"error: unsafe or unreadable release archive: {exc}"]
        except TypeError as exc:
            # tarfile.extractall()'s `filter=` keyword requires Python 3.8.17+/3.9.17+/
            # 3.10.12+/3.11.4+ or 3.12+ (PEP 706); on an older 3.x patch release it's an
            # unknown keyword argument, which is a TypeError, not a TarError/OSError, so
            # without this it crashed with a raw traceback instead of a clean CLI error.
            return [f"error: Python version does not support safe tar extraction: {exc}"]

        roots = list(extract_dir.iterdir())
        if len(roots) != 1 or not roots[0].is_dir():
            return ["error: release bundle must contain exactly one top-level directory"]
        bundle_root = roots[0]

        manifest_path = bundle_root / RELEASE_MANIFEST_NAME
        if not manifest_path.is_file():
            return [f"error: release bundle missing {RELEASE_MANIFEST_NAME}"]
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return [f"error: {RELEASE_MANIFEST_NAME} is not valid JSON: {exc}"]
        if not isinstance(manifest, dict):
            return [f"error: {RELEASE_MANIFEST_NAME} must be a JSON object"]

        # Read the contract the bundle itself embeds (scripts/release_contract.yaml is a
        # regular tracked file, so every bundle ships its own copy) rather than falling
        # back to required_provenance_fields()'s CONTRACT_PATH default -- otherwise
        # verifying a bundle built from a different revision than whatever checkout this
        # verifier happens to be running from (e.g. re-checking an older release's bundle
        # from a fresh clone of main) would silently check it against the wrong,
        # contemporaneous-with-neither contract instead of the bundle's own.
        #
        # Parsed once via load_contract() and reused below for the compatibility-schema
        # check too, instead of calling required_provenance_fields()/
        # compatibility_schema_versions() separately -- each re-reads and re-parses the
        # same YAML file from disk independently.
        contract_path = bundle_root / "scripts" / "release_contract.yaml"
        try:
            contract = load_contract(contract_path)
        except (OSError, *YAML_SAFETY_ERRORS) as exc:
            return [f"error: release contract: {exc}"]
        try:
            fields = required_provenance_fields_from_contract(contract)
        except ValueError as exc:
            return [f"error: release contract: {exc}"]
        missing_fields = sorted(fields - set(manifest))
        if missing_fields:
            return [f"error: {RELEASE_MANIFEST_NAME} missing fields: {missing_fields}"]

        errors: list[str] = []
        schema_version = manifest.get("schema_version")
        if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
            errors.append(f"error: {RELEASE_MANIFEST_NAME} schema_version must be 1")

        version = manifest.get("distribution_version")
        if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
            errors.append(f"error: {RELEASE_MANIFEST_NAME} distribution_version is invalid: {version!r}")
        elif bundle_root.name != f"{PACKAGE_NAME}-{version}":
            # Defends the "nothing tampered" guarantee this verifier exists to provide:
            # without this, a bundle whose top-level directory was renamed after
            # packaging (but whose manifest/file hashes are otherwise self-consistent)
            # would still report "ok: verified" even though it no longer matches the
            # canonical {PACKAGE_NAME}-{version} artifact convention.
            errors.append(
                f"error: release bundle top-level directory {bundle_root.name!r} does not match "
                f"expected '{PACKAGE_NAME}-{version}'",
            )

        source_sha = manifest.get("source_sha")
        if not isinstance(source_sha, str) or not SHA_RE.fullmatch(source_sha):
            errors.append(f"error: {RELEASE_MANIFEST_NAME} source_sha is invalid: {source_sha!r}")

        try:
            expected_schema_versions = compatibility_schema_versions_from_contract(contract)
        except ValueError as exc:
            errors.append(f"error: release contract: {exc}")
            expected_schema_versions = {}

        for key in ("registry_schema_version", "host_contract_schema_version"):
            value = manifest.get(key)
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"error: {RELEASE_MANIFEST_NAME} {key} must be an integer")
            elif key in expected_schema_versions and value != expected_schema_versions[key]:
                # A bundle's compatibility fields being well-typed integers isn't the
                # same as them being the *right* integers -- the "files" hash map never
                # covers these top-level manifest fields, so without this a manifest
                # claiming an incompatible/stale schema version (a package_release.py
                # bug, or a tampered-but-internally-consistent manifest) still reports
                # "ok: verified".
                errors.append(
                    f"error: {RELEASE_MANIFEST_NAME} {key} {value!r} does not match release contract "
                    f"compatibility.{key} {expected_schema_versions[key]!r}",
                )

        supported_hosts = manifest.get("supported_hosts")
        if not isinstance(supported_hosts, list) or not all(isinstance(item, str) for item in supported_hosts):
            errors.append(f"error: {RELEASE_MANIFEST_NAME} supported_hosts must be a list of strings")

        skill_versions = manifest.get("skill_versions")
        if not isinstance(skill_versions, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in skill_versions.items()
        ):
            errors.append(f"error: {RELEASE_MANIFEST_NAME} skill_versions must be a mapping of strings")

        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            errors.append(f"error: {RELEASE_MANIFEST_NAME} files map is empty or invalid")
            return errors

        actual_files: dict[str, str] = {}
        for path in sorted(bundle_root.rglob("*")):
            rel = path.relative_to(bundle_root).as_posix()
            if path.is_symlink():
                errors.append(f"error: unsafe symlink in bundle: {rel}")
                continue
            if not path.is_file():
                continue
            if rel == RELEASE_MANIFEST_NAME:
                continue
            try:
                actual_files[rel] = sha256_file(path)
            except OSError as exc:
                # Every other failure mode in this function (extraction, manifest
                # parsing, contract loading) is caught and turned into a clean error
                # string rather than propagating -- an I/O error hashing one bundled
                # file (disk/filesystem hiccup, permissions) shouldn't be the one path
                # left to crash main() with a raw traceback instead of a CLI error.
                errors.append(f"error: could not hash {rel}: {exc}")

        for rel, digest in sorted(files.items()):
            if not isinstance(rel, str) or not isinstance(digest, str):
                errors.append(f"error: {RELEASE_MANIFEST_NAME} files entry has invalid types: {rel!r}")
                continue
            if not rel or rel.startswith("/") or ".." in Path(rel).parts:
                errors.append(f"error: unsafe file reference in manifest: {rel!r}")
                continue
            if not _HEX64_RE.fullmatch(digest):
                errors.append(f"error: {RELEASE_MANIFEST_NAME} hash for {rel} is not a sha256 digest")
                continue
            if rel not in actual_files:
                errors.append(f"error: manifest lists missing file: {rel}")
                continue
            if actual_files[rel] != digest:
                errors.append(f"error: hash mismatch for {rel}")

        for rel in sorted(set(actual_files) - set(files)):
            errors.append(f"error: bundle contains file not listed in manifest: {rel}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify_release_bundle")
    parser.add_argument("archive", type=Path)
    args = parser.parse_args(argv)

    try:
        errors = verify_release_bundle(args.archive)
    except (OSError, *YAML_SAFETY_ERRORS) as exc:
        # verify_release_bundle() converts every expected failure mode (bad archive,
        # malformed manifest, hash mismatch, ...) into an error string rather than
        # raising, but it doesn't wrap every filesystem call after extraction (e.g.
        # iterdir()/is_symlink() on a bundle member) -- catch the same exception
        # classes package_release.py's and release_contract.py's mains already do,
        # so an unexpected OS-level error still prints a clean CLI error instead of
        # crashing with a raw traceback.
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"ok: {args.archive} verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
