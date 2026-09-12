"""Parity test: sb compatibility must match the checkout's python -m scripts.registry
compatibility for the same host/skill."""

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


def test_sb_compatibility_matches_checkout_compatibility() -> None:
    sb_result = _run_sb("compatibility", "--host", "claude", "--skill", "pr-review")
    checkout_result = _run_checkout_registry_cli(
        "compatibility", "--host", "claude", "--skill", "pr-review"
    )

    assert sb_result.returncode == checkout_result.returncode == 0
    assert sb_result.stdout == checkout_result.stdout


def test_sb_compatibility_rejects_unknown_host() -> None:
    result = _run_sb("compatibility", "--host", "does-not-exist")

    assert result.returncode == 2
    assert "unknown host" in result.stderr


def test_sb_compatibility_surface_matches_checkout() -> None:
    sb_result = _run_sb("compatibility", "--host", "claude", "--skill", "pr-review", "--surface", "LOCAL")
    checkout_result = _run_checkout_registry_cli(
        "compatibility", "--host", "claude", "--skill", "pr-review", "--surface", "LOCAL"
    )

    assert sb_result.returncode == checkout_result.returncode == 0
    assert sb_result.stdout == checkout_result.stdout


def test_sb_compatibility_rejects_unknown_surface() -> None:
    result = _run_sb("compatibility", "--host", "claude", "--surface", "NOT_A_REAL_SURFACE")

    assert result.returncode == 2
    assert "NOT_A_REAL_SURFACE" in result.stderr
