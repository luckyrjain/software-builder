"""Tests for pr-gatekeeper/scripts/idempotency_store.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "idempotency_store.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_then_mark(tmp_path: Path) -> None:
    base = [
        "--store-root",
        str(tmp_path),
        "--project",
        "group/repo",
        "--merge-request-iid",
        "42",
        "--head-sha",
        "abc123",
    ]
    assert run(*base, "check").returncode == 0
    assert run(*base, "mark").returncode == 0
    assert run(*base, "check").returncode == 1

    base[-1] = "def456"
    assert run(*base, "check").returncode == 0


def test_run_if_new_skips_duplicate(tmp_path: Path) -> None:
    base = [
        "--store-root",
        str(tmp_path),
        "--project",
        "group/repo",
        "--merge-request-iid",
        "42",
        "--head-sha",
        "abc123",
        "run-if-new",
        "--",
        sys.executable,
        "-c",
        "print('ok')",
    ]
    assert run(*base).returncode == 0
    assert run(*base).returncode == 1
