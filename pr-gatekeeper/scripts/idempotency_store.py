#!/usr/bin/env python3
"""Reference file-based idempotency store + per-MR lock for pr-gatekeeper integrators.

Not invoked by the skill itself — webhook handlers call this (or equivalent) before
dispatching pr-gatekeeper. See reference/idempotency.md.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def _store_path(root: Path, project: str, merge_request_iid: int) -> Path:
    safe_project = project.replace("/", "__")
    return root / safe_project / f"mr-{merge_request_iid}.json"


@contextmanager
def mr_lock(root: Path, project: str, merge_request_iid: int):
    lock_dir = root / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    safe_project = project.replace("/", "__")
    lock_path = lock_dir / f"{safe_project}-mr-{merge_request_iid}.lock"
    with open(lock_path, "w", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


def load_record(root: Path, project: str, merge_request_iid: int) -> dict[str, Any]:
    path = _store_path(root, project, merge_request_iid)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_record(root: Path, project: str, merge_request_iid: int, record: dict[str, Any]) -> None:
    path = _store_path(root, project, merge_request_iid)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def should_process(root: Path, project: str, merge_request_iid: int, head_sha: str) -> bool:
    """Double-checked locking helper: True when head_sha is new."""
    record = load_record(root, project, merge_request_iid)
    return record.get("last_processed_head_sha") != head_sha


def mark_processed(root: Path, project: str, merge_request_iid: int, head_sha: str) -> None:
    save_record(
        root,
        project,
        merge_request_iid,
        {"last_processed_head_sha": head_sha},
    )


def run_if_new(
    root: Path,
    project: str,
    merge_request_iid: int,
    head_sha: str,
    command: list[str],
) -> int:
    """Acquire lock, skip when head_sha is duplicate, else run command and mark on success."""
    with mr_lock(root, project, merge_request_iid):
        if not should_process(root, project, merge_request_iid, head_sha):
            return 1
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            mark_processed(root, project, merge_request_iid, head_sha)
        return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-root", required=True, type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--merge-request-iid", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument(
        "action",
        choices=("check", "mark", "run-if-new"),
        help=(
            "check: exit 0 when new head, 1 when duplicate (lock held only for the check — "
            "use run-if-new for the full gatekeeper invocation); "
            "mark: persist head after successful run (under lock); "
            "run-if-new: hold lock, skip duplicate heads, run trailing command, mark on exit 0"
        ),
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command for run-if-new (prefix with -- before the command)",
    )
    args = parser.parse_args(argv)

    if args.action == "run-if-new":
        if not args.command or args.command[0] == "":
            print("error: run-if-new requires a command after --", file=sys.stderr)
            return 2
        cmd = args.command[1:] if args.command[0] == "--" else args.command
        if not cmd:
            print("error: run-if-new requires a command after --", file=sys.stderr)
            return 2
        return run_if_new(args.store_root, args.project, args.merge_request_iid, args.head_sha, cmd)

    with mr_lock(args.store_root, args.project, args.merge_request_iid):
        if args.action == "check":
            return 0 if should_process(args.store_root, args.project, args.merge_request_iid, args.head_sha) else 1
        mark_processed(args.store_root, args.project, args.merge_request_iid, args.head_sha)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
