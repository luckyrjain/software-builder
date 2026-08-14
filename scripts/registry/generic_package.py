from __future__ import annotations

import argparse
import gzip
import io
import sys
import tarfile
from pathlib import Path

from scripts.registry.schema import parse_registry

PACKAGE_ROOT = "software-builder"
EXCLUDED_PARTS = {".git", ".github", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _is_safe_file(root: Path, path: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    if path.is_symlink():
        raise ValueError(f"generic package refuses symlink: {rel}")
    return path.is_file()


def _package_files(root: Path) -> list[Path]:
    registry = parse_registry(root / "skills.yaml")
    candidates: set[Path] = {root / "skills.yaml"}
    for optional in ("README.md", "SETUP.md", "LICENSE"):
        path = root / optional
        if path.is_file():
            candidates.add(path)
    framework = root / "docs" / "skill-framework"
    if not framework.is_dir():
        raise ValueError("generic package requires docs/skill-framework")
    candidates.update(path for path in framework.rglob("*") if _is_safe_file(root, path))
    for skill_id, entry in registry.skills.items():
        skill_root = root / entry.path
        if not (skill_root / "SKILL.md").is_file():
            raise ValueError(f"generic package missing canonical SKILL.md for {skill_id}")
        candidates.update(path for path in skill_root.rglob("*") if _is_safe_file(root, path))
    return sorted(candidates, key=lambda path: path.relative_to(root).as_posix())


def build_generic_package_bytes(root: Path) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for path in _package_files(root):
                rel = path.relative_to(root).as_posix()
                arcname = f"{PACKAGE_ROOT}/{rel}"
                data = path.read_bytes()
                info = tarfile.TarInfo(arcname)
                info.size = len(data)
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def build_generic_package(root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_generic_package_bytes(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.registry.generic_package")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=Path("dist/software-builder-skills.tar.gz"))
    args = parser.parse_args(argv)
    try:
        build_generic_package(args.root.resolve(), args.output.resolve())
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"ok: wrote deterministic generic package to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
