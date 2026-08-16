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
import subprocess
import sys
import tarfile
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from reference_utils import sha256_file
from release_info import MANIFEST_NAME, git_source_sha, read_distribution_version
from yaml_safety import YAML_SAFETY_ERRORS, read_schema_version

ROOT = Path(__file__).resolve().parents[1]


def _ensure_clean_worktree(root: Path) -> None:
    """Refuse to package a release whose tracked files differ from HEAD.

    Without this, an uncommitted local edit to a tracked file would silently
    ship in the archive while RELEASE-MANIFEST.json's source_sha still names
    the last commit -- breaking the "source_sha ... matching ... the Git
    commit the bundle was built from" guarantee docs/RELEASE.md promises.
    Nothing downstream can catch this after the fact: verify_release_bundle.py
    only checks the bundle's internal self-consistency (does the manifest
    match the archive?), not whether that content matches the named commit.
    """
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 1:
        raise ValueError(
            "release inputs must match the Git HEAD commit exactly -- commit or stash "
            "pending changes to tracked files before packaging a release",
        )
    if result.returncode not in (0, 1):
        raise ValueError(f"could not check Git working tree status: {result.stderr.strip()}")


def _tracked_files(root: Path) -> list[tuple[str, Path, int]]:
    """Git-tracked regular files under root, as (posix relative path, absolute
    path, tar mode).

    The tar mode is read from Git's own index (``git ls-files -s``), not from
    the filesystem: a filesystem executable bit that has drifted from Git's
    recorded mode -- e.g. under ``core.fileMode=false``, where the
    ``_ensure_clean_worktree`` diff check can't see the drift -- would
    otherwise make the archive depend on the machine it was built on instead
    of only on the Git tree, breaking reproducibility.

    Raises ValueError if any tracked path is a symlink -- release inputs must
    be plain file content, never a link that could point outside the bundle.
    Raises ValueError if a tracked path is the reserved manifest filename --
    otherwise the per-file loop and the generated-manifest write in
    _write_reproducible_archive would both target the same tar member name,
    silently discarding the tracked file's real content in the archive.
    """
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-s", "-z"],
        check=True,
        capture_output=True,
        text=True,
    )
    entries: list[tuple[str, int]] = []
    for raw_entry in result.stdout.split("\0"):
        if not raw_entry:
            continue
        meta, _, rel = raw_entry.partition("\t")
        git_mode = int(meta.split(" ", 1)[0], 8)
        entries.append((rel, git_mode))

    files: list[tuple[str, Path, int]] = []
    for rel, git_mode in sorted(entries, key=lambda item: item[0]):
        if rel == MANIFEST_NAME:
            raise ValueError(
                f"release inputs must not track the reserved manifest filename: {rel}",
            )
        abs_path = root / rel
        if abs_path.is_symlink():
            raise ValueError(f"release inputs must be regular files; found tracked symlink: {rel}")
        if abs_path.is_file():
            mode = 0o755 if git_mode & 0o111 else 0o644
            files.append((rel, abs_path, mode))
    return files


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


class _HashingReader:
    """Wrap a binary file object, updating `digest` with every chunk read.

    tarfile.addfile() streams a member's content by calling .read(bufsize) on
    the given file object in a loop. Wrapping the handle here lets that one
    read pass -- the pass that copies file content into the archive -- also
    compute the file's SHA-256, instead of reading every tracked file twice
    (once whole, to hash, and again to stream into the tar).
    """

    def __init__(self, fileobj, digest) -> None:
        self._fileobj = fileobj
        self._digest = digest

    def read(self, size: int = -1) -> bytes:
        chunk = self._fileobj.read(size)
        self._digest.update(chunk)
        return chunk


def _write_reproducible_archive(
    archive_path: Path,
    bundle_name: str,
    tracked: list[tuple[str, Path, int]],
    manifest_fields: dict,
) -> tuple[dict[str, str], bytes]:
    """Write every tracked file plus RELEASE-MANIFEST.json into a reproducible
    archive, hashing each tracked file exactly once as it streams into the
    tar. Returns (file_hashes, manifest_bytes) so the caller can write the
    sibling .sha256/.files.sha256 assets without re-reading any file.
    """
    file_hashes: dict[str, str] = {}
    with archive_path.open("wb") as raw:
        # filename="" (not the default of raw.name) keeps the gzip header
        # itself reproducible regardless of the output path chosen.
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for rel, abs_path, mode in tracked:
                    info = _tar_info(f"{bundle_name}/{rel}", size=abs_path.stat().st_size, mode=mode)
                    digest = hashlib.sha256()
                    with abs_path.open("rb") as handle:
                        tar.addfile(info, _HashingReader(handle, digest))
                    file_hashes[rel] = digest.hexdigest()

                manifest = {**manifest_fields, "files": file_hashes}
                manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
                info = _tar_info(f"{bundle_name}/{MANIFEST_NAME}", size=len(manifest_bytes), mode=0o644)
                tar.addfile(info, io.BytesIO(manifest_bytes))
    return file_hashes, manifest_bytes


def package_release(root: Path, output_dir: Path) -> tuple[Path, Path]:
    version = read_distribution_version(root)
    sha = git_source_sha(root)
    _ensure_clean_worktree(root)
    bundle_name = f"software-builder-{version}"

    tracked = _tracked_files(root)
    manifest_fields = {
        "schema_version": 1,
        "distribution_version": version,
        "source_sha": sha,
        "registry_schema_version": read_schema_version(root / "skills.yaml"),
        "host_contract_schema_version": read_schema_version(root / "scripts" / "registry" / "host_contracts.yaml"),
    }

    archive_path = output_dir / f"{bundle_name}.tar.gz"
    file_hashes, manifest_bytes = _write_reproducible_archive(archive_path, bundle_name, tracked, manifest_fields)
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()

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
    try:
        archive_path, checksum_path = package_release(args.repo_root, args.output_dir)
    except (OSError, *YAML_SAFETY_ERRORS) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    bundle_name = checksum_path.name[: -len(".sha256")]
    print(f"ok: {archive_path}")
    print(f"ok: {checksum_path}")
    print(f"ok: {args.output_dir / f'{bundle_name}.files.sha256'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
