"""Golden tests for the legacy install.sh CLI behavior."""

from __future__ import annotations

import subprocess
import os
from pathlib import Path

from scripts.install_support import registry_skill_ids

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts" / "install.sh"


def run_installer(*args: str, home: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"HOME": str(home), "PATH": f"{ROOT / '.venv' / 'bin'}:{env['PATH']}"})
    return subprocess.run(
        ["bash", str(INSTALLER), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_legacy_dry_run_selectors_preserve_destinations_and_hosts(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    cases = (
        (("--agent", "cursor", "--dry-run", "pr-review"), home / ".cursor" / "skills" / "pr-review", "cursor"),
        (
            ("--agent", "cursor-project", "--target-dir", str(project), "--dry-run", "pr-review"),
            project / ".cursor" / "skills" / "pr-review",
            "cursor-project",
        ),
        (("--agent", "claude-user", "--dry-run", "pr-review"), home / ".claude" / "skills" / "pr-review", "claude-user"),
        (
            ("--agent", "claude-project", "--target-dir", str(project), "--dry-run", "pr-review"),
            project / ".claude" / "skills" / "pr-review",
            "claude-project",
        ),
    )

    for args, destination, host in cases:
        result = run_installer(*args, home=home)
        assert result.returncode == 0, result.stderr
        assert result.stderr == ""
        assert result.stdout.splitlines() == [
            f"dry-run: would install pr-review → {destination} (host={host})"
        ]
        assert not destination.exists()

    all_result = run_installer(
        "--agent", "all", "--target-dir", str(project), "--dry-run", "pr-review", home=home
    )
    assert all_result.returncode == 0, all_result.stderr
    assert all_result.stderr == ""
    assert all_result.stdout.splitlines() == [
        f"dry-run: would install pr-review → {project / '.cursor' / 'skills' / 'pr-review'} "
        "(host=cursor-project)",
        f"dry-run: would install pr-review → {project / '.claude' / 'skills' / 'pr-review'} "
        "(host=claude-project)",
    ]
    assert not (project / ".cursor" / "skills" / "pr-review").exists()
    assert not (project / ".claude" / "skills" / "pr-review").exists()


def test_legacy_list_matches_sorted_registry_ids(tmp_path: Path) -> None:
    result = run_installer("--list", home=tmp_path / "home")
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.splitlines() == registry_skill_ids(ROOT)


def test_legacy_verify_missing_path_fails_independently_of_home(tmp_path: Path) -> None:
    missing = tmp_path / "missing-install"
    result = run_installer("--verify", str(missing), home=tmp_path / "home")
    assert result.returncode != 0
    assert "not a directory" in result.stderr


def test_legacy_unknown_agent_fails_in_stderr(tmp_path: Path) -> None:
    result = run_installer("--agent", "unknown-agent", home=tmp_path / "home")
    assert result.returncode != 0
    assert "unknown --agent" in result.stderr
