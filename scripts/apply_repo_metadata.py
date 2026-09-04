#!/usr/bin/env python3
"""Apply .github/repo-metadata.yaml to the GitHub repository via gh."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.yaml_safety import load_unique_yaml_file  # noqa: E402


def _repo_root() -> Path:
    return ROOT


def _load_metadata(root: Path) -> tuple[str, list[str]]:
    path = root / ".github/repo-metadata.yaml"
    raw = load_unique_yaml_file(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: root must be a mapping")
    description = str(raw.get("description", "")).strip().replace("\n", " ")
    topics = raw.get("topics") or []
    if not description:
        raise ValueError(f"{path}: description is required")
    if not isinstance(topics, list) or not topics:
        raise ValueError(f"{path}: topics must be a non-empty list")
    return description, [str(topic) for topic in topics]


def _git_toplevel(root: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{root} is not a git repository")
    return Path(result.stdout.strip()).resolve()


def _current_topics(root: Path) -> set[str]:
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "repositoryTopics"],
        capture_output=True,
        text=True,
        check=True,
        cwd=root,
    )
    payload = json.loads(result.stdout)
    topics = payload.get("repositoryTopics") or []
    return {str(item["name"]) for item in topics if isinstance(item, dict) and item.get("name")}


def apply_metadata(root: Path, *, dry_run: bool) -> None:
    if _git_toplevel(root) != root.resolve():
        raise RuntimeError(
            f"refusing to edit GitHub metadata: git toplevel {_git_toplevel(root)} != {root.resolve()}",
        )

    description, desired_topics = _load_metadata(root)
    desired_set = set(desired_topics)
    current_set = _current_topics(root)

    to_remove = sorted(current_set - desired_set)
    to_add = sorted(desired_set - current_set)

    cmd = ["gh", "repo", "edit", "--description", description]
    for topic in to_remove:
        cmd.extend(["--remove-topic", topic])
    for topic in to_add:
        cmd.extend(["--add-topic", topic])

    if dry_run:
        print("dry-run:", " ".join(cmd))
        print(f"description: {description}")
        print(f"remove topics: {to_remove or '[]'}")
        print(f"add topics: {to_add or '[]'}")
        return

    subprocess.run(cmd, cwd=root, check=True)
    print(
        f"ok — updated description; removed {len(to_remove)} topic(s), added {len(to_add)} topic(s)",
    )
    print("verify with: gh repo view --json description,repositoryTopics")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=_repo_root(),
        help="Repository root (default: parent of scripts/)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print gh command without executing")
    args = parser.parse_args(argv)

    try:
        apply_metadata(args.root.resolve(), dry_run=args.dry_run)
    except (ValueError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
