"""Tests for sb install/uninstall/verify -- runs the real sb subprocess against a real,
isolated target directory (never the developer's actual ~/.cursor or ~/.claude)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1]


def _run_sb(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sb", *args],
        cwd=CLI_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
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


def test_install_warns_when_shadowed_by_a_higher_precedence_divergent_copy(tmp_path: Path) -> None:
    # claude-project (precedence 10) and claude-user (precedence 20) both resolve under one
    # target_dir/home pair, so writing the same skill to each lets the second write's shadow
    # check see the first. The manifest hash is corrupted afterward to simulate a stale,
    # divergent copy already sitting at the higher-precedence root -- package_skill's own output
    # doesn't happen to differ by host label for this skill, so an untouched second install would
    # land on DUPLICATE_IDENTICAL (silent) instead of exercising the SHADOWED warning path.
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    env = {**os.environ, "HOME": str(fake_home)}

    project_result = _run_sb(
        "install", "pr-review", "--host", "claude-project", "--target-dir", str(target_dir), env=env
    )
    assert project_result.returncode == 0, project_result.stderr

    manifest_path = target_dir / ".claude" / "skills" / "pr-review" / ".software-builder-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    a_file = next(iter(manifest["files"]))
    manifest["files"][a_file] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    user_result = _run_sb(
        "install", "pr-review", "--host", "claude-user", "--target-dir", str(target_dir), env=env
    )

    assert user_result.returncode == 0, user_result.stderr
    assert (fake_home / ".claude" / "skills" / "pr-review" / "SKILL.md").is_file()
    expected_shadow_path = target_dir / ".claude" / "skills" / "pr-review"
    assert (
        "warning: this install may be shadowed by a higher-precedence, divergent copy at "
        f"{expected_shadow_path} -- claude will likely load that one instead" in user_result.stderr
    )


def test_install_warns_unknown_precedence_when_higher_root_manifest_is_unreadable(
    tmp_path: Path,
) -> None:
    """The other half of Candidate 8's warning pair (UNKNOWN_PRECEDENCE, not SHADOWED) on the
    `sb install` call site -- previously only unit-tested at the detect_shadow() level."""
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    env = {**os.environ, "HOME": str(fake_home)}

    project_result = _run_sb(
        "install", "pr-review", "--host", "claude-project", "--target-dir", str(target_dir), env=env
    )
    assert project_result.returncode == 0, project_result.stderr

    manifest_path = target_dir / ".claude" / "skills" / "pr-review" / ".software-builder-manifest.json"
    manifest_path.write_text("{not valid json", encoding="utf-8")

    user_result = _run_sb(
        "install", "pr-review", "--host", "claude-user", "--target-dir", str(target_dir), env=env
    )

    assert user_result.returncode == 0, user_result.stderr
    expected_shadow_path = target_dir / ".claude" / "skills" / "pr-review"
    assert (
        f"warning: a higher-precedence root at {expected_shadow_path} exists but its install "
        "manifest could not be read, so it's unknown whether this install is shadowed"
        in user_result.stderr
    )


def test_install_does_not_warn_when_no_higher_precedence_copy_exists(tmp_path: Path) -> None:
    target_dir = tmp_path / "target-repo"
    target_dir.mkdir()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    env = {**os.environ, "HOME": str(fake_home)}

    result = _run_sb(
        "install", "pr-review", "--host", "claude-user", "--target-dir", str(target_dir), env=env
    )

    assert result.returncode == 0, result.stderr
    assert "shadow" not in result.stderr.lower()


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
