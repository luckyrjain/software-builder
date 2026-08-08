#!/usr/bin/env python3
"""Create a checksummed release bundle for software-builder."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tarfile
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from release_info import git_source_sha, read_distribution_version

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {".git", ".cursor", ".kiro", "__pycache__", ".pytest_cache", "node_modules", "dist"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_release_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        if rel_parts[0].startswith(".") and rel_parts[0] not in {".github"}:
            continue
        files.append(path)
    return files


def package_release(root: Path, output_dir: Path) -> tuple[Path, Path]:
    version = read_distribution_version(root)
    sha = git_source_sha(root)
    bundle_name = f"software-builder-{version}"
    staging = output_dir / f".{bundle_name}.staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    for path in _collect_release_files(root):
        rel = path.relative_to(root)
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)

    manifest_lines = [
        f"version={version}",
        f"source_sha={sha}",
        "",
    ]

    (staging / "RELEASE.txt").write_text("\n".join(manifest_lines), encoding="utf-8")

    checksum_lines: list[str] = []
    for path in sorted(staging.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(staging).as_posix()
        digest = _sha256_file(path)
        checksum_lines.append(f"{digest}  {rel}")
    checksum_lines.sort()

    checksum_path = output_dir / f"{bundle_name}.sha256"
    archive_path = output_dir / f"{bundle_name}.tar.gz"

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(staging, arcname=bundle_name)

    archive_digest = _sha256_file(archive_path)
    checksum_path.write_text(f"{archive_digest}  {archive_path.name}\n", encoding="utf-8")
    (output_dir / f"{bundle_name}.files.sha256").write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(staging)
    return archive_path, checksum_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="package_release")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args(argv)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive_path, checksum_path = package_release(args.repo_root, args.output_dir)
    print(f"ok: {archive_path}")
    print(f"ok: {checksum_path}")
    print(f"ok: {args.output_dir / f'{archive_path.stem}.files.sha256'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
