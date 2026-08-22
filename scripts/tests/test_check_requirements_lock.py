"""Tests for requirements.lock consistency checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from check_requirements_lock import (  # noqa: E402
    direct_package_names_from_lock,
    package_names_from_requirements,
    unsatisfied_locked_requirements,
)


def test_check_requirements_lock_passes_on_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_requirements_lock.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_direct_lock_entries_match_requirements_txt() -> None:
    required = package_names_from_requirements(ROOT / "requirements.txt")
    direct_locked = direct_package_names_from_lock(ROOT / "requirements.lock")
    assert required == direct_locked


def test_extra_direct_lock_entry_fails(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    lockfile = tmp_path / "requirements.lock"
    requirements.write_text("pytest>=9.1.1\n", encoding="utf-8")
    lockfile.write_text(
        "pytest==9.1.1 \\\n    # via -r requirements.txt\n"
        "orphan==1.0.0 \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    required = package_names_from_requirements(requirements)
    direct_locked = direct_package_names_from_lock(lockfile)
    assert "orphan" in direct_locked - required


def test_unsatisfied_locked_version_is_reported(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    lockfile = tmp_path / "requirements.lock"
    requirements.write_text("sqlglot>=30.17.0\n", encoding="utf-8")
    lockfile.write_text(
        "sqlglot==30.15.0 \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    assert unsatisfied_locked_requirements(requirements, lockfile) == [
        "sqlglot==30.15.0 does not satisfy sqlglot>=30.17.0"
    ]


def test_multiline_uv_provenance_marks_direct_entry(tmp_path: Path) -> None:
    lockfile = tmp_path / "requirements.lock"
    lockfile.write_text(
        """packaging==26.3 \\
    --hash=sha256:example
    # via
    #   -r requirements.txt
    #   pytest
""",
        encoding="utf-8",
    )

    assert direct_package_names_from_lock(lockfile) == {"packaging"}

