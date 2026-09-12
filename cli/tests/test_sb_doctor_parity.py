"""Parity test: sb doctor must produce the same output as python3 -m scripts.doctor, run
against the vendored snapshot instead of a live checkout, for a skill filter with no host/
--available context (both default to UNSPECIFIED capability resolution)."""

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


def _run_checkout_doctor(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.doctor", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sb_doctor_matches_checkout_doctor_for_one_skill() -> None:
    sb_result = _run_sb("doctor", "--skill", "pr-review", "--install-root", "/nonexistent")
    checkout_result = _run_checkout_doctor("--skill", "pr-review", "--install-root", "/nonexistent")

    assert sb_result.returncode == checkout_result.returncode
    assert sb_result.stdout == checkout_result.stdout


def test_sb_doctor_surface_matches_checkout() -> None:
    sb_result = _run_sb(
        "doctor", "--skill", "pr-review", "--agent", "claude", "--surface", "LOCAL",
        "--install-root", "/nonexistent",
    )
    checkout_result = _run_checkout_doctor(
        "--skill", "pr-review", "--agent", "claude", "--surface", "LOCAL",
        "--install-root", "/nonexistent",
    )

    assert sb_result.returncode == checkout_result.returncode
    assert sb_result.stdout == checkout_result.stdout


def test_sb_doctor_rejects_unknown_surface() -> None:
    result = _run_sb(
        "doctor", "--agent", "claude", "--surface", "NOT_A_REAL_SURFACE",
        "--install-root", "/nonexistent",
    )

    assert result.returncode == 2
    assert "NOT_A_REAL_SURFACE" in result.stderr
