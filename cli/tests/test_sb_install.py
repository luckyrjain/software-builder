"""Tests for sb install/uninstall/verify -- runs the real sb subprocess against a real,
isolated target directory (never the developer's actual ~/.cursor or ~/.claude)."""

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


def test_install_then_verify_then_uninstall_round_trip(tmp_path: Path) -> None:
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()

    install_result = _run_sb("install", "pr-review", "--host", "cursor", "--target-dir", str(target_dir))
    assert install_result.returncode == 0, install_result.stderr
    installed_path = target_dir / ".cursor" / "skills" / "pr-review"
    assert (installed_path / "SKILL.md").is_file()

    verify_result = _run_sb("verify", str(installed_path))
    assert verify_result.returncode == 0, verify_result.stderr
    assert "ok:" in verify_result.stdout

    uninstall_result = _run_sb("uninstall", "pr-review", "--host", "cursor", "--target-dir", str(target_dir))
    assert uninstall_result.returncode == 0, uninstall_result.stderr
    assert not installed_path.exists()


def test_install_dry_run_makes_no_changes(tmp_path: Path) -> None:
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()

    result = _run_sb(
        "install", "pr-review", "--host", "cursor", "--target-dir", str(target_dir), "--dry-run"
    )

    assert result.returncode == 0
    assert not (target_dir / ".cursor").exists()


def test_install_rejects_unknown_selector(tmp_path: Path) -> None:
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()

    result = _run_sb("install", "pr-review", "--host", "not-a-real-selector", "--target-dir", str(target_dir))

    assert result.returncode == 2
    assert "not-a-real-selector" in result.stderr


def test_multi_skill_install_continues_past_one_failure_and_reports_a_summary(tmp_path: Path) -> None:
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()
    # Pre-create an unowned destination for the second skill so its install is refused,
    # while the first and third succeed -- mirrors
    # test_multi_skill_run_continues_past_a_failure_and_reports_a_summary's intent.
    unowned = target_dir / ".cursor" / "skills" / "security-review"
    unowned.mkdir(parents=True)
    (unowned / "some-file.txt").write_text("not ours\n", encoding="utf-8")

    result = _run_sb(
        "install", "pr-review", "security-review", "system-design",
        "--host", "cursor", "--target-dir", str(target_dir),
    )

    assert result.returncode != 0
    assert "installed: 2" in result.stdout or "installed: 2" in result.stderr
    assert "failed: 1" in result.stdout or "failed: 1" in result.stderr
    assert (target_dir / ".cursor" / "skills" / "pr-review" / "SKILL.md").is_file()
    assert (target_dir / ".cursor" / "skills" / "system-design" / "SKILL.md").is_file()
