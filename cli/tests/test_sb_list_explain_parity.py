"""Parity tests: sb list/explain must produce the same output as the checkout's own
python3 -m scripts.registry list/explain, run against the vendored snapshot instead of a live
checkout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CLI_ROOT.parent


def _run_sb(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sb", *args],
        cwd=CLI_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_checkout_registry_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.registry", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sb_list_matches_checkout_list() -> None:
    sb_result = _run_sb("list")
    checkout_result = _run_checkout_registry_cli("list")

    assert sb_result.returncode == checkout_result.returncode == 0
    assert sb_result.stdout == checkout_result.stdout


def test_sb_explain_matches_checkout_explain() -> None:
    sb_result = _run_sb("explain", "pr-review")
    checkout_result = _run_checkout_registry_cli("explain", "pr-review")

    assert sb_result.returncode == checkout_result.returncode == 0
    assert sb_result.stdout == checkout_result.stdout


def test_sb_explain_rejects_unknown_skill() -> None:
    result = _run_sb("explain", "does-not-exist")

    assert result.returncode == 1
    assert "unknown skill" in result.stderr
