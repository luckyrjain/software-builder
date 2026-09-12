"""Tests for scripts/install_engine.py's install_skill() -- mirrors the rollback and
same-filesystem-staging scenarios scripts/tests/test_install_rollback.py and
scripts/tests/test_install_concurrency.py already lock in for install.sh."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import install_engine
from scripts.install_engine import install_skill

ROOT = Path(__file__).resolve().parents[2]


def _minimal_repo(tmp_path: Path, *, skill_id: str = "demo-skill", broken: bool = False) -> Path:
    """A minimal, self-contained repo root with one registered skill -- valid enough for
    package_skill() to package it and (unless broken=True) for validate_tree() to accept it.

    Mirrors test_install_rollback.py's real fixture-building approach: a fresh git repository
    (package_skill.py's release provenance shells out to `git rev-parse HEAD`, so an
    uncommitted tree fails packaging outright) with a *flat* skill directory (`repo/<skill_id>`,
    not the nested `repo/skills/<skill_id>` the brief's own illustrative template used) and a
    plain YAML skills.yaml (not JSON) -- matching the shape entry.path defaults to (skill_id
    itself) in scripts/registry/paths.py's skill_dir(). Unlike test_install_rollback.py's own
    fixture (which drives the real install.sh via subprocess, and so also needs its own copies
    of scripts/, agent-hosts.yaml, and a scripts/registry/skills.d/ fragment for install.sh's
    shelled-out Python to find), install_skill() here is called in-process against this
    checkout's own scripts.registry.schema module, so none of that copying is needed -- only a
    skills.yaml entry with every field _parse_skill_entry requires (schema.py falls back to the
    default {cursor, claude, kiro} host set when no sibling agent-hosts.yaml exists, and each of
    those three hosts' block is mandatory regardless of which ones are actually declared).
    """
    repo = tmp_path / "repo"
    skill_dir = repo / skill_id
    skill_dir.mkdir(parents=True)
    if broken:
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: Demo test skill.\n---\n\n"
            "See [missing](reference/missing.md)\n",
            encoding="utf-8",
        )
    else:
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: Demo test skill.\n---\n\n"
            "A minimal test skill.\n",
            encoding="utf-8",
        )
    (repo / "skills.yaml").write_text(
        f"""schema_version: 1
skills:
  {skill_id}:
    invocation: ambient
    hosts:
      cursor: {{discovery: manual}}
      claude: {{install: true}}
      kiro: {{discovery: manual}}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: {skill_id}
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    (repo / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    # -c commit.gpgsign=false: don't depend on the invoking machine's global Git signing
    # config (commit signing turned on would otherwise block this fixture commit on a
    # passphrase/hardware-key prompt or fail outright).
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=repo, check=True
    )
    return repo


def test_install_succeeds_into_an_empty_destination(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "installed"
    assert (dest_root / "demo-skill" / "SKILL.md").is_file()
    assert (dest_root / "demo-skill" / ".software-builder-manifest.json").is_file()


def test_dry_run_makes_no_filesystem_changes(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"

    outcome = install_skill(
        "demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor", dry_run=True
    )

    assert outcome.status == "dry_run"
    assert not (dest_root / "demo-skill").exists()


def test_validation_failure_restores_previous_install_unchanged(tmp_path: Path) -> None:
    """Mirrors test_install_rollback.py's test_install_restores_previous_package_when_validation_fails:
    a pre-existing, software-builder-owned install with a marker file must survive a failed
    (broken-link) install byte-for-byte."""
    repo = _minimal_repo(tmp_path, broken=True)
    dest_root = tmp_path / "dest"
    existing = dest_root / "demo-skill"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("# Previous good install\n", encoding="utf-8")
    (existing / "KEEP_ME.txt").write_text("do not touch\n", encoding="utf-8")
    (existing / ".software-builder-manifest.json").write_text(
        json.dumps({"manifest_version": 1, "skill": "demo-skill", "files": {}}), encoding="utf-8"
    )

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "failed"
    assert (existing / "KEEP_ME.txt").read_text(encoding="utf-8") == "do not touch\n"
    assert (existing / "SKILL.md").read_text(encoding="utf-8") == "# Previous good install\n"
    # no leftover staging/backup directories
    assert not list(dest_root.glob(".demo-skill.staging.*"))
    assert not list(dest_root.glob(".demo-skill.backup.*"))
    assert not list(dest_root.glob(".demo-skill.lock*"))


def test_reinstall_backup_survives_a_missing_system_tmp_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mirrors test_install_concurrency.py's test_reinstall_backup_survives_a_missing_system_tmp_dir:
    proves staging/backup directories are created under dest_root, never under $TMPDIR, by
    pointing TMPDIR at a path that does not exist and confirming install still succeeds."""
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"
    existing = dest_root / "demo-skill"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("# Old\n", encoding="utf-8")
    (existing / ".software-builder-manifest.json").write_text(
        json.dumps({"manifest_version": 1, "skill": "demo-skill", "files": {}}), encoding="utf-8"
    )
    monkeypatch.setenv("TMPDIR", str(tmp_path / "does-not-exist"))

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "installed"
    assert (
        dest_root / "demo-skill" / "SKILL.md"
    ).read_text(encoding="utf-8") == "---\nname: demo-skill\ndescription: Demo test skill.\n---\n\nA minimal test skill.\n"


def test_keyboard_interrupt_during_staging_propagates_after_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """install.sh's own INT/TERM trap (on_install_interrupt) runs cleanup_failed_install()
    and then `exit 130`, terminating the whole process -- it does NOT fall through to
    per-skill failure bookkeeping and continue to the next skill, the way an ordinary
    validation failure (a plain `return 1`) does. A Ctrl-C mid-install must behave the same
    way here: cleanup still runs, but the interrupt propagates out of install_skill() instead
    of being swallowed into a normal InstallOutcome(status="failed", ...) that a future
    multi-skill caller could mistake for just one more failed skill."""
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"

    seen_stage_dirs: list[Path] = []

    def _interrupt(stage_dir: Path, **_kwargs: object) -> list[str]:
        seen_stage_dirs.append(stage_dir)
        raise KeyboardInterrupt

    monkeypatch.setattr(install_engine, "validate_tree", _interrupt)

    with pytest.raises(KeyboardInterrupt):
        install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert seen_stage_dirs, "validate_tree was never reached"
    # cleanup ran before propagating: the staging dir is gone, nothing landed at the
    # destination, and held_lock's own finally released the lock.
    assert not seen_stage_dirs[0].exists()
    assert not (dest_root / "demo-skill").exists()
    assert not list(dest_root.glob(".demo-skill.lock*"))


def test_symlinked_destination_is_refused(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    real_target = tmp_path / "elsewhere"
    real_target.mkdir()
    (dest_root / "demo-skill").symlink_to(real_target)

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "failed"
    assert "symlink" in outcome.message.lower()
