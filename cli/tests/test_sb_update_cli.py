"""Tests for the `sb update` subcommand wiring in cli/sb/__main__.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

CLI_ROOT = Path(__file__).resolve().parents[1]


def _run_sb(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sb", *args],
        cwd=CLI_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_update_help_lists_channel_and_check_flags() -> None:
    result = _run_sb("update", "--help")

    assert result.returncode == 0
    assert "--channel" in result.stdout
    assert "--check" in result.stdout


def test_update_rejects_unsupported_channel() -> None:
    result = _run_sb("update", "--channel", "nightly", "--check")

    assert result.returncode == 2
    assert "unsupported channel" in result.stderr


def test_update_defaults_to_stable_channel() -> None:
    """Doesn't hit the network (unittest.mock via subprocess isn't possible across a process
    boundary) -- instead calls main() in-process with sb._update.run_update mocked, proving
    the CLI dispatch passes the right defaulted arguments through."""
    import sb.__main__ as sb_main

    with patch("sb.__main__.run_update") as mock_run_update:
        mock_run_update.return_value = 0
        exit_code = sb_main.main(["update", "--check"])

    assert exit_code == 0
    mock_run_update.assert_called_once_with(channel="stable", check_only=True)
