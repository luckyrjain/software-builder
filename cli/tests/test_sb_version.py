"""Tests for the sb package's argparse skeleton (before real subcommands land)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1]


def _run_sb(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sb", *args],
        cwd=CLI_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_bare_invocation_prints_help_and_exits_zero() -> None:
    result = _run_sb()

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_version_flag_prints_a_version_string() -> None:
    result = _run_sb("--version")

    assert result.returncode == 0
    assert "sb" in result.stdout


def test_unknown_command_exits_two() -> None:
    result = _run_sb("bogus-command")

    assert result.returncode == 2
