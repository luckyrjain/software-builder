"""Tests for the shared install.sh subprocess-env test helper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_install_subprocess_env_omits_pythonpath_when_no_repo_given(tmp_path: Path) -> None:
    from scripts.tests.install_test_helpers import install_subprocess_env

    env = install_subprocess_env(tmp_path / "home")
    assert "PYTHONPATH" not in env
    assert env["HOME"] == str(tmp_path / "home")


def test_install_subprocess_env_sets_pythonpath_when_repo_given(tmp_path: Path) -> None:
    from scripts.tests.install_test_helpers import install_subprocess_env

    env = install_subprocess_env(tmp_path / "home", repo=tmp_path / "repo")
    assert env["PYTHONPATH"] == str(tmp_path / "repo")


def test_install_subprocess_env_path_resolves_python3_to_sys_executable(tmp_path: Path) -> None:
    from scripts.tests.install_test_helpers import install_subprocess_env

    env = install_subprocess_env(tmp_path / "home")
    result = subprocess.run(
        ["python3", "-c", "import sys; print(sys.executable)"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    # The shim is a symlink to sys.executable, so the child's own reported
    # sys.executable should point at the same real file this test runs under.
    assert Path(result.stdout.strip()).resolve() == Path(sys.executable).resolve()


def test_install_subprocess_env_path_resolves_a_python3_with_yaml(tmp_path: Path) -> None:
    from scripts.tests.install_test_helpers import install_subprocess_env

    env = install_subprocess_env(tmp_path / "home")
    result = subprocess.run(
        ["python3", "-c", "import yaml"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
