#!/usr/bin/env python3
"""Create a byte-reproducible, checksummed release bundle for software-builder.

Release inputs are exactly the Git-tracked regular files at ``root`` -- Git is
the single source of truth for what ships, so untracked files (caches, build
output, local secrets) can never leak into a release, and a tracked symlink
is rejected outright rather than silently dereferenced. The archive embeds a
``RELEASE-MANIFEST.json`` with exact provenance (distribution version, source
SHA, registry/host-contract schema versions) and a SHA-256 per bundled file,
so verify_release_bundle.py can check a release independently of how it was
built.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from reference_utils import sha256_file
from release_info import git_source_sha, read_distribution_version
from yaml_safety import load_unique_yaml_file, require_mapping

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "RELEASE-MANIFEST.json"


def _tracked_files(root: Path) -> list[tuple[str, Path]]:
    """Git-tracked regular files under root, as (posix relative path, absolute path).

    Raises ValueError if any tracked path is a symlink -- release inputs must
    be plain file content, never a link that could point outside the bundle.
    """
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
    )
    files: list[tuple[str, Path]] = []
    for rel in sorted(entry for entry in result.stdout.split("\0") if entry):
        abs_path = root / rel
        if abs_path.is_symlink():
            raise ValueError(f"release inputs must be regular files; found tracked symlink: {rel}")
        if abs_path.is_file():
            files.append((rel, abs_path))
    return files


def _schema_version(path: Path) -> int:
    raw = require_mapping(load_unique_yaml_file(path), str(path))
    value = raw.get("schema_version")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{path}: schema_version must be an integer")
    return value


def _tar_info(arcname: str, *, size: int, mode: int) -> tarfile.TarInfo:
    # Every field that could vary between two builds of the same Git tree
    # (mtime, ownership, names) is pinned so the resulting archive is
    # byte-identical run to run.
    info = tarfile.TarInfo(name=arcname)
    info.size = size
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def _write_reproducible_archive(
    archive_path: Path,
    bundle_name: str,
    tracked: list[tuple[str, Path]],
    manifest_bytes: bytes,
) -> None:
    with archive_path.open("wb") as raw:
        # filename="" (not the default of raw.name) keeps the gzip header
        # itself reproducible regardless of the output path chosen.
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for rel, abs_path in tracked:
                    mode = 0o755 if os.access(abs_path, os.X_OK) else 0o644
                    info = _tar_info(f"{bundle_name}/{rel}", size=abs_path.stat().st_size, mode=mode)
                    with abs_path.open("rb") as handle:
                        tar.addfile(info, handle)

                info = _tar_info(f"{bundle_name}/{MANIFEST_NAME}", size=len(manifest_bytes), mode=0o644)
                tar.addfile(info, io.BytesIO(manifest_bytes))


def package_release(root: Path, output_dir: Path) -> tuple[Path, Path]:
    version = read_distribution_version(root)
    sha = git_source_sha(root)
    bundle_name = f"software-builder-{version}"

    tracked = _tracked_files(root)
    file_hashes = {rel: sha256_file(abs_path) for rel, abs_path in tracked}

    manifest = {
        "schema_version": 1,
        "distribution_version": version,
        "source_sha": sha,
        "registry_schema_version": _schema_version(root / "skills.yaml"),
        "host_contract_schema_version": _schema_version(root / "scripts" / "registry" / "host_contracts.yaml"),
        "files": file_hashes,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()

    archive_path = output_dir / f"{bundle_name}.tar.gz"
    _write_reproducible_archive(archive_path, bundle_name, tracked, manifest_bytes)

    checksum_lines = sorted(
        [f"{digest}  {rel}" for rel, digest in file_hashes.items()]
        + [f"{manifest_digest}  {MANIFEST_NAME}"],
    )
    (output_dir / f"{bundle_name}.files.sha256").write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )

    archive_digest = sha256_file(archive_path)
    checksum_path = output_dir / f"{bundle_name}.sha256"
    checksum_path.write_text(f"{archive_digest}  {archive_path.name}\n", encoding="utf-8")

    return archive_path, checksum_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="package_release")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args(argv)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive_path, checksum_path = package_release(args.repo_root, args.output_dir)
    bundle_name = checksum_path.name[: -len(".sha256")]
    print(f"ok: {archive_path}")
    print(f"ok: {checksum_path}")
    print(f"ok: {args.output_dir / f'{bundle_name}.files.sha256'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
