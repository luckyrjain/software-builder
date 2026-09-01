"""Golden tests for the legacy install.sh CLI behavior.

Candidate 0 of the universal-agent-compatibility rollout
(docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md) requires this behavior to
be frozen as executable evidence before any registry-driven resolver replaces install.sh's hard-coded
destination logic. Every test in this file must set HOME to an isolated tmp_path via run_installer --
never the real environment HOME -- since a real (non---dry-run) install mutates whatever directory HOME
points at.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import os
from pathlib import Path

from scripts.install_support import registry_skill_ids
from scripts.reference_utils import MANIFEST_NAME

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


def test_legacy_real_install_writes_manifest_with_expected_shape(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = run_installer("--agent", "cursor", "pr-review", home=home)
    assert result.returncode == 0, result.stderr
    dest = home / ".cursor" / "skills" / "pr-review"
    stdout_lines = result.stdout.splitlines()
    # validate_references.py's own "ok: <staging-dir>" line carries a random mktemp suffix,
    # so it can't be matched literally -- only its prefix and the two deterministic lines are golden.
    assert len(stdout_lines) == 3
    assert stdout_lines[0].startswith("ok: ")
    assert stdout_lines[1:] == [
        f"Installed pr-review → {dest}",
        "Restart Cursor to load the skill(s).",
    ]
    assert (dest / "SKILL.md").is_file()

    manifest = json.loads((dest / MANIFEST_NAME).read_text(encoding="utf-8"))
    # Golden shape as of Phase 1 (pre universal-agent-compatibility): exactly these eight
    # top-level keys, no manifest_schema_version/target_id/package_format yet. §18 of the
    # design spec plans to add those fields additively while keeping `host` readable --
    # this test is the baseline this repo commits to not silently reshaping.
    assert set(manifest) == {
        "skill",
        "distribution_version",
        "source_repo",
        "source_sha",
        "installed_at",
        "host",
        "framework_files",
        "files",
    }
    assert manifest["skill"] == "pr-review"
    assert manifest["host"] == "cursor"
    assert isinstance(manifest["files"], dict)
    assert "SKILL.md" in manifest["files"]
    assert all(isinstance(value, str) and value for value in manifest["files"].values())


def test_legacy_real_install_agent_all_writes_both_destinations(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = run_installer("--agent", "all", "pr-review", home=home)
    assert result.returncode == 0, result.stderr

    cursor_dest = home / ".cursor" / "skills" / "pr-review"
    claude_dest = home / ".claude" / "skills" / "pr-review"
    assert (cursor_dest / "SKILL.md").is_file()
    assert (claude_dest / "SKILL.md").is_file()

    cursor_manifest = json.loads((cursor_dest / MANIFEST_NAME).read_text(encoding="utf-8"))
    claude_manifest = json.loads((claude_dest / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert cursor_manifest["host"] == "cursor"
    assert claude_manifest["host"] == "claude-user"

    stdout_lines = [line for line in result.stdout.splitlines() if not line.startswith("ok: ")]
    assert stdout_lines == [
        f"Installed pr-review → {cursor_dest}",
        f"Installed pr-review → {claude_dest}",
        "Restart Cursor and start a new Claude Code session to load the skill(s).",
    ]


def test_legacy_verify_succeeds_on_a_real_install(tmp_path: Path) -> None:
    home = tmp_path / "home"
    install_result = run_installer("--agent", "claude-user", "pr-review", home=home)
    assert install_result.returncode == 0, install_result.stderr
    dest = home / ".claude" / "skills" / "pr-review"

    verify_result = run_installer("--verify", str(dest), home=home)
    assert verify_result.returncode == 0, verify_result.stderr
    assert verify_result.stdout.splitlines() == [f"ok: {dest} (pr-review)"]
    assert verify_result.stderr == ""


def test_legacy_uninstall_removes_installed_skill_and_reports(tmp_path: Path) -> None:
    home = tmp_path / "home"
    install_result = run_installer("--agent", "cursor", "pr-review", home=home)
    assert install_result.returncode == 0, install_result.stderr
    dest = home / ".cursor" / "skills" / "pr-review"
    assert dest.is_dir()

    uninstall_result = run_installer("--agent", "cursor", "--uninstall", "pr-review", home=home)
    assert uninstall_result.returncode == 0, uninstall_result.stderr
    assert uninstall_result.stdout.splitlines() == [f"Uninstalled pr-review from {dest}"]
    assert not dest.exists()


def test_legacy_uninstall_of_absent_skill_warns_without_failing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = run_installer("--agent", "cursor", "--uninstall", "pr-review", home=home)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    dest = home / ".cursor" / "skills" / "pr-review"
    assert f"warning: not installed: {dest}" in result.stderr


def test_legacy_uninstall_refuses_to_remove_a_symlink(tmp_path: Path) -> None:
    home = tmp_path / "home"
    skills_dir = home / ".cursor" / "skills"
    skills_dir.mkdir(parents=True)
    real_target = tmp_path / "outside-target"
    real_target.mkdir()
    symlink_dest = skills_dir / "pr-review"
    symlink_dest.symlink_to(real_target)

    result = run_installer("--agent", "cursor", "--uninstall", "pr-review", home=home)
    assert result.returncode != 0
    assert f"refusing to remove symlink at {symlink_dest}" in result.stderr
    assert symlink_dest.is_symlink()
    assert real_target.is_dir()


def test_legacy_install_aborts_loudly_when_destination_resolution_fails(tmp_path: Path) -> None:
    """Regression test for a real bug found while building Candidate 5: destination resolution
    used to run inside `< <(resolve_targets)` process substitution, whose internal failure only
    killed that subshell -- the main script's `while read` loop just saw zero lines and fell
    through to a false "Restart Cursor..." success message with exit 0. Now resolve_targets is
    captured via command substitution first and explicitly checked, so a failure aborts the
    script loudly instead of silently installing nothing. Exercised here via a repo copy that's
    missing agent-hosts.yaml -- a real (if unusual) way destination resolution can fail."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    for name in ("scripts", "skills.yaml", "VERSION", "pr-review"):
        source = ROOT / name
        destination = repo / name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            destination.write_bytes(source.read_bytes())
    # Deliberately no agent-hosts.yaml copied.

    env = os.environ.copy()
    env.update({"HOME": str(home), "PYTHONPATH": str(repo)})
    result = subprocess.run(
        ["bash", str(repo / "scripts" / "install.sh"), "--agent", "cursor", "pr-review"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Restart Cursor" not in result.stdout
    assert "Installed" not in result.stdout
    assert not (home / ".cursor" / "skills" / "pr-review").exists()


def test_legacy_install_refuses_to_replace_a_symlink_destination(tmp_path: Path) -> None:
    home = tmp_path / "home"
    skills_dir = home / ".cursor" / "skills"
    skills_dir.mkdir(parents=True)
    real_target = tmp_path / "outside-target"
    real_target.mkdir()
    symlink_dest = skills_dir / "pr-review"
    symlink_dest.symlink_to(real_target)

    result = run_installer("--agent", "cursor", "pr-review", home=home)
    assert result.returncode != 0
    assert f"refusing to replace symlink at {symlink_dest}" in result.stderr
    assert symlink_dest.is_symlink()


def test_legacy_install_refuses_to_replace_an_unowned_directory(tmp_path: Path) -> None:
    """Candidate 6 ownership hardening: a directory with no .software-builder-manifest.json --
    unrelated third-party content that happens to share the skill's name -- must never be
    silently overwritten."""
    home = tmp_path / "home"
    dest = home / ".cursor" / "skills" / "pr-review"
    dest.mkdir(parents=True)
    (dest / "README.md").write_text("not ours", encoding="utf-8")

    result = run_installer("--agent", "cursor", "pr-review", home=home)
    assert result.returncode != 0
    assert f"refusing to replace unowned directory at {dest}" in result.stderr
    assert (dest / "README.md").read_text(encoding="utf-8") == "not ours"
    assert not (dest / "SKILL.md").exists()


def test_legacy_install_refuses_to_replace_a_directory_with_corrupt_manifest(tmp_path: Path) -> None:
    home = tmp_path / "home"
    dest = home / ".cursor" / "skills" / "pr-review"
    dest.mkdir(parents=True)
    (dest / MANIFEST_NAME).write_text("{not valid json", encoding="utf-8")

    result = run_installer("--agent", "cursor", "pr-review", home=home)
    assert result.returncode != 0
    assert f"refusing to replace {dest}: install manifest is missing, unreadable, or names a different skill" in result.stderr


def test_legacy_install_replaces_a_previous_software_builder_owned_install(tmp_path: Path) -> None:
    """Reinstalling the same skill -- the normal upgrade/refresh path -- must keep working: a
    destination whose manifest already names this skill is SOFTWARE_BUILDER_OWNED, not UNOWNED."""
    home = tmp_path / "home"
    first = run_installer("--agent", "cursor", "pr-review", home=home)
    assert first.returncode == 0, first.stderr

    second = run_installer("--agent", "cursor", "pr-review", home=home)
    assert second.returncode == 0, second.stderr
    assert "warning: replacing existing install" in second.stderr
    dest = home / ".cursor" / "skills" / "pr-review"
    assert (dest / "SKILL.md").is_file()


def test_legacy_uninstall_refuses_to_remove_an_unowned_directory(tmp_path: Path) -> None:
    home = tmp_path / "home"
    dest = home / ".cursor" / "skills" / "pr-review"
    dest.mkdir(parents=True)
    (dest / "README.md").write_text("not ours", encoding="utf-8")

    result = run_installer("--agent", "cursor", "--uninstall", "pr-review", home=home)
    assert result.returncode != 0
    assert f"refusing to remove unowned directory at {dest}" in result.stderr
    assert (dest / "README.md").is_file()


def test_legacy_uninstall_refuses_to_remove_a_directory_with_corrupt_manifest(tmp_path: Path) -> None:
    home = tmp_path / "home"
    dest = home / ".cursor" / "skills" / "pr-review"
    dest.mkdir(parents=True)
    (dest / MANIFEST_NAME).write_text('{"skill": "some-other-skill"}', encoding="utf-8")

    result = run_installer("--agent", "cursor", "--uninstall", "pr-review", home=home)
    assert result.returncode != 0
    assert f"refusing to remove {dest}: install manifest is missing, unreadable, or names a different skill" in result.stderr
    assert dest.is_dir()


def test_legacy_dry_run_agents_selector_previews_universal_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"

    user_result = run_installer("--agent", "agents", "--dry-run", "pr-review", home=home)
    assert user_result.returncode == 0, user_result.stderr
    assert user_result.stdout.splitlines() == [
        f"dry-run: would install pr-review → {home / '.agents' / 'skills' / 'pr-review'} (host=agents-user)"
    ]

    project_result = run_installer(
        "--agent", "agents", "--target-dir", str(project), "--dry-run", "pr-review", home=home
    )
    assert project_result.returncode == 0, project_result.stderr
    assert project_result.stdout.splitlines() == [
        f"dry-run: would install pr-review → {project / '.agents' / 'skills' / 'pr-review'} "
        "(host=agents-project)"
    ]


def test_legacy_real_install_agents_selector_writes_to_universal_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = run_installer("--agent", "agents", "pr-review", home=home)
    assert result.returncode == 0, result.stderr

    dest = home / ".agents" / "skills" / "pr-review"
    assert (dest / "SKILL.md").is_file()
    manifest = json.loads((dest / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["host"] == "agents-user"
    assert "Skill(s) installed to the universal Agent Skills target." in result.stdout


def test_legacy_agents_selector_respects_ownership_hardening(tmp_path: Path) -> None:
    """The universal target is explicitly a shared, multi-tool directory (spec Section 15) --
    Candidate 6's ownership hardening must already protect it, with no extra wiring needed."""
    home = tmp_path / "home"
    dest = home / ".agents" / "skills" / "pr-review"
    dest.mkdir(parents=True)
    (dest / "README.md").write_text("installed by some other tool", encoding="utf-8")

    result = run_installer("--agent", "agents", "pr-review", home=home)
    assert result.returncode != 0
    assert f"refusing to replace unowned directory at {dest}" in result.stderr
    assert (dest / "README.md").read_text(encoding="utf-8") == "installed by some other tool"
