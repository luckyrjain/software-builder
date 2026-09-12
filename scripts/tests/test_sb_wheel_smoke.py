"""End-to-end proof that the sb package actually builds, installs, and runs as a real
installed command -- every other cli/ test runs `python -m sb` from the source tree, which
never exercises the wheel's file selection (hatchling's `artifacts` config, Task 3) or the
console_script entry point (Task 3's [project.scripts]). This is the one test that would catch
either being silently misconfigured.

Marked slow: builds a real wheel and creates a real venv. Not part of the default fast test
loop -- run explicitly via `python3 -m pytest scripts/tests/test_sb_wheel_smoke.py -v`.
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

import pytest

from scripts.build_sb_snapshot import build_snapshot

ROOT = Path(__file__).resolve().parents[2]
CLI_ROOT = ROOT / "cli"


@pytest.mark.slow
@pytest.mark.mutates_repository_root
def test_sb_wheel_builds_installs_and_runs(tmp_path: Path) -> None:
    build_snapshot(ROOT)

    dist_dir = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir), str(CLI_ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(dist_dir.glob("software_builder_cli-*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, found {wheels}"

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    venv_python = venv_dir / "bin" / "python3"

    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet", str(wheels[0])],
        check=True,
        capture_output=True,
        text=True,
    )

    sb_executable = venv_dir / "bin" / "sb"
    assert sb_executable.is_file()

    result = subprocess.run(
        [str(sb_executable), "list"], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "pr-review" in result.stdout

    result = subprocess.run(
        [str(sb_executable), "explain", "pr-review"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Skill: pr-review" in result.stdout

    result = subprocess.run(
        [str(sb_executable), "doctor", "--skill", "pr-review", "--install-root", "/nonexistent"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode in (0, 1)
    assert "pr-review:" in result.stdout

    result = subprocess.run(
        [str(sb_executable), "compatibility", "--host", "claude", "--skill", "pr-review"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "claude pr-review:" in result.stdout
