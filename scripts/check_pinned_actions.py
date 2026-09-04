#!/usr/bin/env python3
"""Fail on any GitHub Action reference not pinned to a full commit SHA.

A `uses: owner/repo@v4`-style mutable tag can be repointed by the action's maintainer
(compromised or not) to different code after review — the exact supply-chain risk this
repo's existing workflows already avoid by pinning every action to a 40-char commit SHA
with a version comment (e.g. `actions/checkout@<sha> # v7.0.1`). This script enforces that
convention stays true as new workflows are added, rather than relying on manual review to
catch a regression.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.yaml_safety import load_unique_yaml_file  # noqa: E402

_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_ACTION_REF_RE = re.compile(r"^([^@]+)@([^\s@]+)$")


def find_unpinned_actions(workflow_path: Path) -> list[str]:
    """Return one error string per `uses:` reference not pinned to a commit SHA."""
    data = load_unique_yaml_file(workflow_path)
    if not isinstance(data, dict):
        return []

    errors: list[str] = []

    def visit(node: object) -> None:
        if isinstance(node, dict):
            uses = node.get("uses")
            if isinstance(uses, str):
                errors.extend(_check_uses(workflow_path, uses))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(data)
    return errors


def _check_uses(workflow_path: Path, uses: str) -> list[str]:
    # Local reusable workflows (./...) and Docker image references (docker://...) aren't
    # GitHub Action tag references — out of scope for this check.
    if uses.startswith("./") or uses.startswith("docker://"):
        return []

    match = _ACTION_REF_RE.match(uses)
    if not match:
        return [f"{workflow_path}: unrecognized action reference {uses!r} (expected owner/repo@ref)"]

    ref = match.group(2)
    if _SHA_RE.match(ref):
        return []

    return [
        f"{workflow_path}: {uses!r} is pinned to a mutable ref {ref!r}, not a full commit SHA",
    ]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    workflows_dir = repo_root / ".github" / "workflows"
    workflow_files = sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))

    if not workflow_files:
        print(f"error: no workflow files found under {workflows_dir}", file=sys.stderr)
        return 1

    errors: list[str] = []
    for workflow_path in workflow_files:
        errors.extend(find_unpinned_actions(workflow_path))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(
            "hint: pin to the action's full commit SHA with a version comment, "
            "e.g. `owner/repo@<40-char-sha> # v1.2.3`",
            file=sys.stderr,
        )
        return 1

    print(f"ok: every action reference in {len(workflow_files)} workflow file(s) is pinned to a commit SHA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
