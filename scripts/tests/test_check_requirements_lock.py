"""Tests for requirements.lock consistency checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_check_requirements_lock_passes_on_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_requirements_lock.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
