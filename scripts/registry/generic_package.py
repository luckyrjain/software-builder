from __future__ import annotations

import argparse
import gzip
import io
import re
import sys
import tarfile
from pathlib import Path

from scripts.git_paths import tracked_relative_paths
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
    "tests",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
NON_RUNTIME_NAMES = {"changelog.md"}
SENSITIVE_NAMES = {".env", ".netrc", "credentials.json", "secrets.yaml", "secrets.yml"}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
MARKDOWN_LINK_RE = re.compile(
    r"\]\(([a-zA-Z0-9_./~-]+\.md)(?:#([a-zA-Z0-9_-]+))?\)",
)
MARKDOWN_NAMED_LINK_RE = re.compile(
    r"(?<!!)\[([^\]\n]+)\]\(([a-zA-Z0-9_./~-]+\.md)(?:#[a-zA-Z0-9_-]+)?\)",
)
PORTABLE_README = """# Software Builder — portable skill bundle

This archive contains the registered Software Builder skills and their runtime framework dependencies.
It is generated for generic agent hosts and intentionally omits repository contribution history,
CI configuration, caches, VCS metadata, test fixtures, and credential-like files.

Start with `skills.yaml` to discover registered skills. Each skill's canonical instructions live in
its `SKILL.md`; shared runtime and routing contracts live under `docs/skill-framework/`.

## Install

Extract the archive into the workspace used by your agent host, then use `skills.yaml` to discover the
available skills and their canonical `SKILL.md` entry points.

## Install for your specific coding agent

This is the generic-agent bundle. Host-specific adapters remain outside this archive; follow the shared
host contract in `docs/skill-framework/shared/host-adapter-contract.md` for capability semantics.
"""
PORTABLE_ADR_INDEX = """# Architecture Decision Records

Lightweight ADRs for platform-level choices in **software-builder**. Each record captures context,
decision, and consequences so portable hosts can understand the runtime contract without repository
maintenance history.

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-skills-registry.md) | Canonical `skills.yaml` registry | Accepted |
| [0002](0002-self-contained-skill-packages.md) | Self-contained skill install packages | Accepted |
| [0003](0003-behavioral-evals-tiers.md) | Tiered behavioral eval harness | Accepted |
| [0004](0004-live-eval-harness.md) | Mock-tool execution harness, kept out of CI | Accepted |
"""


def _is_safe_file(root: Path, path: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        return False
    if path.name.lower() in NON_RUNTIME_NAMES or path.suffix in EXCLUDED_SUFFIXES:
        return False
    name = path.name.lower()
    if name in SENSITIVE_NAMES or name.startswith(".env.") or path.suffix.lower() in SENSITIVE_SUFFIXES:
        raise ValueError(f"generic package refuses potentially sensitive file: {rel}")
    if path.is_symlink():
        raise ValueError(f"generic package refuses symlink: {rel}")
    return path.is_file()


def _tracked_files(root: Path) -> set[Path]:
    """Return lexical Git-tracked paths; arbitrary working-tree files are never package inputs."""
    relative_paths, error = tracked_relative_paths(root)
    if error:
        raise ValueError(f"generic package requires a readable Git index: {error}")
    return {root / rel for rel in relative_paths}


def _validate_output_path(root: Path, output: Path) -> None:
    root = root.resolve()
    output = output.resolve()
    try:
        rel = output.relative_to(root)
    except ValueError:
        return
    if rel.parts and rel.parts[0] == "dist":
        return
    raise ValueError(
        f"generic package output inside repository must live under top-level dist/: {rel}",
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


def _strip_non_runtime_links(text: str) -> str:
    """Strip release-history prose links without mutating fenced examples or images."""

    def replace(match: re.Match[str]) -> str:
        label, target = match.groups()
        if Path(target).name.lower() in NON_RUNTIME_NAMES:
            return label
        return match.group(0)

    rewritten: list[str] = []
    fence_len = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        leading = len(line) - len(line.lstrip(" "))
        candidate = line[leading:] if leading <= 3 else line
        if fence_len == 0:
            opening = re.match(r"`{3,}", candidate)
            if opening:
                fence_len = len(opening.group(0))
                rewritten.append(raw)
                continue
            rewritten.append(MARKDOWN_NAMED_LINK_RE.sub(replace, raw))
            continue

        rewritten.append(raw)
        closing = candidate.rstrip(" \t\r")
        if closing and set(closing) == {"`"} and len(closing) >= fence_len:
            fence_len = 0
    return "".join(rewritten)


def _packaged_bytes(root: Path, path: Path) -> bytes:
    """Return archive content, substituting portable docs for repo-only surfaces."""
    resolved = path.resolve()
    if resolved == (root / "README.md").resolve():
        text = PORTABLE_README
    elif resolved == (root / "docs" / "adr" / "README.md").resolve():
        text = PORTABLE_ADR_INDEX
    else:
        data = path.read_bytes()
        if path.suffix.lower() != ".md":
            return data
        text = data.decode("utf-8")
    return _strip_non_runtime_links(text).encode("utf-8")


def _heading_slugs(root: Path, path: Path) -> set[str]:
    """Match the repository Markdown linter's simple GitHub-style heading slug rules."""
    text = _packaged_bytes(root, path).decode("utf-8")
    slugs: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"^#{1,6} (.+)$", line)
        if not match:
            continue
        heading = match.group(1).lower()
        heading = re.sub(r"[^a-z0-9 -]", "", heading)
        heading = re.sub(r" +", " ", heading).replace(" ", "-")
        slugs.add(heading)
    return slugs


def _markdown_targets(root: Path, path: Path, tracked_regular: set[Path]) -> set[Path]:
    text = _markdown_without_fences(_packaged_bytes(root, path).decode("utf-8"))
    targets: set[Path] = set()
    for match in MARKDOWN_LINK_RE.finditer(text):
        rel, anchor = match.groups()
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
        if target not in tracked_regular:
            raise ValueError(
                f"generic package reference points to untracked file: {rel} referenced in {path.relative_to(root)}",
            )
        if not target.is_file():
            raise ValueError(
                f"generic package dangling markdown reference: {rel} referenced in {path.relative_to(root)}",
            )
        if not _is_safe_file(root, target):
            raise ValueError(
                f"generic package reference points to excluded file: {rel} referenced in {path.relative_to(root)}",
            )
        if anchor and anchor.lower() not in _heading_slugs(root, target):
            raise ValueError(
                f"generic package dangling markdown anchor: {rel}#{anchor} referenced in {path.relative_to(root)}",
            )
        targets.add(target)
    return targets


def _package_files(root: Path) -> list[Path]:
    root = root.resolve()
    registry = parse_registry(root / "skills.yaml")
    tracked = _tracked_files(root)
    tracked_regular = {path.resolve() for path in tracked if not path.is_symlink()}

    readme_path = (root / "README.md").resolve()
    skills_path = (root / "skills.yaml").resolve()
    if readme_path not in tracked_regular or not readme_path.is_file():
        raise ValueError("generic package requires tracked README.md")
    if skills_path not in tracked_regular or not skills_path.is_file():
        raise ValueError("generic package requires tracked skills.yaml")
    candidates: set[Path] = {skills_path, readme_path}
    license_path = (root / "LICENSE").resolve()
    if license_path in tracked_regular and license_path.is_file():
        candidates.add(license_path)

    # Test-creator source adapters resolve the canonical guard at the generic
    # bundle root. Keep the guard and its small executable path helper in the
    # portable archive; the rest of the repository's development scripts remain out.
    guard_path = (root / "scripts" / "test_creator_write_guard.py").resolve()
    if guard_path in tracked_regular and guard_path.is_file():
        candidates.add(guard_path)
    git_paths_path = (root / "scripts" / "git_paths.py").resolve()
    if git_paths_path in tracked_regular and git_paths_path.is_file():
        candidates.add(git_paths_path)

    framework = (root / "docs" / "skill-framework").resolve()
    if not framework.is_dir():
        raise ValueError("generic package requires docs/skill-framework")
    for path in tracked:
        try:
            path.relative_to(framework)
        except ValueError:
            continue
        if _is_safe_file(root, path):
            candidates.add(path.resolve())

    for skill_id, entry in registry.skills.items():
        skill_root = (root / entry.path).resolve()
        skill_md = (skill_root / "SKILL.md").resolve()
        if skill_md not in tracked_regular or not skill_md.is_file():
            raise ValueError(f"generic package missing tracked canonical SKILL.md for {skill_id}")
        for path in tracked:
            try:
                path.relative_to(skill_root)
            except ValueError:
                continue
            if _is_safe_file(root, path):
                candidates.add(path.resolve())

    # Follow only references reachable from the portable runtime roots.
    # Per-skill changelogs and test fixtures are deliberately excluded: they are
    # repository history/verification material, not execution dependencies.
    # Packaged Markdown retains the human-readable label for changelog links while
    # removing the prose link itself. All other excluded, untracked, or dangling
    # references and anchors fail closed before an archive is written.
    # If runtime docs reach repository-level overview/index docs, the archive emits
    # portable equivalents at the same paths so links remain valid without importing
    # contribution/history dependencies.
    queue = [path for path in candidates if path.suffix.lower() == ".md"]
    inspected: set[Path] = set()
    while queue:
        path = queue.pop()
        if path in inspected:
            continue
        inspected.add(path)
        for target in _markdown_targets(root, path, tracked_regular):
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
                data = _packaged_bytes(root, path)
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
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"ok: wrote deterministic generic package to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
