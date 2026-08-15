from __future__ import annotations

import argparse
import gzip
import io
import re
import sys
import tarfile
from pathlib import Path

from scripts.registry.schema import parse_registry

PACKAGE_ROOT = "software-builder"
EXCLUDED_PARTS = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
SENSITIVE_NAMES = {".env", ".netrc", "credentials.json", "secrets.yaml", "secrets.yml"}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
MARKDOWN_LINK_RE = re.compile(r"\]\(([a-zA-Z0-9_./~-]+\.md)(?:#[a-zA-Z0-9_-]+)?\)")


def _is_safe_file(root: Path, path: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    if path.name in SENSITIVE_NAMES or path.name.startswith(".env.") or path.suffix.lower() in SENSITIVE_SUFFIXES:
        raise ValueError(f"generic package refuses potentially sensitive file: {rel}")
    if path.is_symlink():
        raise ValueError(f"generic package refuses symlink: {rel}")
    return path.is_file()


def _validate_output_path(root: Path, output: Path) -> None:
    root = root.resolve()
    output = output.resolve()
    try:
        rel = output.relative_to(root)
    except ValueError:
        return
    if not any(part in EXCLUDED_PARTS for part in rel.parts):
        raise ValueError(
            f"generic package output inside repository must live under an excluded directory such as dist/: {rel}",
        )


def _markdown_without_fences(text: str) -> str:
    """Mirror the repository link linter's fenced-code exclusion semantics."""
    visible: list[str] = []
    fence_len = 0
    for raw in text.splitlines():
        line = raw
        leading = len(line) - len(line.lstrip(" "))
        candidate = line[leading:] if leading <= 3 else line
        if fence_len == 0:
            opening = re.match(r"`{3,}", candidate)
            if opening:
                fence_len = len(opening.group(0))
                continue
            visible.append(raw)
            continue

        closing = candidate.rstrip(" \t\r")
        if closing and set(closing) == {"`"} and len(closing) >= fence_len:
            fence_len = 0
    return "\n".join(visible)


def _markdown_targets(root: Path, path: Path) -> set[Path]:
    text = _markdown_without_fences(path.read_text(encoding="utf-8"))
    targets: set[Path] = set()
    for match in MARKDOWN_LINK_RE.finditer(text):
        rel = match.group(1)
        if rel.startswith("~"):
            continue
        unresolved = path.parent / rel
        if unresolved.is_symlink():
            raise ValueError(
                f"generic package reference uses symlink: {rel} referenced in {path.relative_to(root)}",
            )
        target = unresolved.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"generic package reference escapes repository: {rel} referenced in {path.relative_to(root)}",
            ) from exc
        if not target.is_file():
            raise ValueError(
                f"generic package dangling markdown reference: {rel} referenced in {path.relative_to(root)}",
            )
        if not _is_safe_file(root, target):
            raise ValueError(
                f"generic package reference points to excluded file: {rel} referenced in {path.relative_to(root)}",
            )
        targets.add(target)
    return targets


def _package_files(root: Path) -> list[Path]:
    root = root.resolve()
    registry = parse_registry(root / "skills.yaml")

    candidates: set[Path] = {root / "skills.yaml"}
    license_path = root / "LICENSE"
    if license_path.is_file():
        candidates.add(license_path)

    framework = root / "docs" / "skill-framework"
    if not framework.is_dir():
        raise ValueError("generic package requires docs/skill-framework")
    candidates.update(path for path in framework.rglob("*") if _is_safe_file(root, path))

    for skill_id, entry in registry.skills.items():
        skill_root = root / entry.path
        if not (skill_root / "SKILL.md").is_file():
            raise ValueError(f"generic package missing canonical SKILL.md for {skill_id}")
        candidates.update(path for path in skill_root.rglob("*") if _is_safe_file(root, path))

    # Follow only references reachable from the portable skill/framework roots.
    # This keeps the archive self-contained without sweeping unrelated historical
    # plans/specs into the artifact merely because they live in the repository.
    queue = [path for path in candidates if path.suffix.lower() == ".md"]
    inspected: set[Path] = set()
    while queue:
        path = queue.pop()
        if path in inspected:
            continue
        inspected.add(path)
        for target in _markdown_targets(root, path):
            if target in candidates:
                continue
            candidates.add(target)
            if target.suffix.lower() == ".md":
                queue.append(target)

    return sorted(candidates, key=lambda path: path.relative_to(root).as_posix())


def build_generic_package_bytes(root: Path) -> bytes:
    root = root.resolve()
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
    root = root.resolve()
    output = output.resolve()
    _validate_output_path(root, output)
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
