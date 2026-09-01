"""Tests for install rollback on validation failure."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_install_restores_previous_package_when_validation_fails(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    skill_dir = repo / "broken-skill"
    shutil.copytree(ROOT / "scripts", repo / "scripts")
    shutil.copy2(ROOT / "skills.yaml", repo / "skills.yaml")
    # install.sh's destination resolution (Candidate 5) reads agent-hosts.yaml as a sibling of
    # skills.yaml -- this fixture invokes the copied install.sh, so it needs its own copy too.
    shutil.copy2(ROOT / "agent-hosts.yaml", repo / "agent-hosts.yaml")
    (repo / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    # Append a registry entry so install.sh allowlist permits the skill.
    skills_yaml = repo / "skills.yaml"
    text = skills_yaml.read_text(encoding="utf-8")
    text = text.rstrip() + """

  broken-skill:
    path: broken-skill
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: broken-skill
    risk_class: [read-only]
"""
    skills_yaml.write_text(text, encoding="utf-8")
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: broken-skill\ndescription: Broken test skill.\n---\n\n"
        "See [missing](reference/missing.md)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    # -c commit.gpgsign=false: don't depend on the invoking machine's global
    # Git signing config (commit signing turned on would otherwise block this
    # fixture commit on a passphrase/hardware-key prompt or fail outright).
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=repo, check=True)

    dest = home / ".cursor" / "skills" / "broken-skill"
    dest.parent.mkdir(parents=True)
    dest.mkdir()
    marker = dest / "KEEP_ME.txt"
    marker.write_text("previous install\n", encoding="utf-8")
    # A real previous install always carries its own manifest (install.sh writes one for every
    # skill it installs) -- without it, Candidate 6's ownership hardening correctly refuses to
    # touch this directory at all as UNOWNED, before ever reaching the rollback path this test
    # means to exercise. This is what marks it SOFTWARE_BUILDER_OWNED for "broken-skill".
    (dest / ".software-builder-manifest.json").write_text('{"skill": "broken-skill"}', encoding="utf-8")

    result = subprocess.run(
        ["bash", str(repo / "scripts" / "install.sh"), "--agent", "cursor", "broken-skill"],
        cwd=repo,
        env={
            "HOME": str(home),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(repo),
            # install.sh shells out to plain `python3`, resolved via PATH. Without
            # this, the subprocess falls back to the OS default PATH instead of
            # the interpreter pytest itself is running under -- landing on a
            # system python3 that doesn't have this repo's dependencies (PyYAML)
            # installed, so install.sh fails with ModuleNotFoundError before
            # ever reaching the behavior under test.
            "PATH": os.environ.get("PATH", ""),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8") == "previous install\n"
    assert "dangling link" in result.stderr or "missing.md" in result.stderr


def test_install_list_does_not_write_skills(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "scripts", repo / "scripts")
    shutil.copy2(ROOT / "skills.yaml", repo / "skills.yaml")
    (repo / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    shutil.copytree(ROOT / "unit-test-creator", repo / "unit-test-creator")
    shutil.copytree(ROOT / "docs" / "skill-framework", repo / "docs" / "skill-framework")

    result = subprocess.run(
        ["bash", str(repo / "scripts" / "install.sh"), "--list"],
        cwd=repo,
        env={
            "HOME": str(home),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(repo),
            # install.sh shells out to plain `python3`, resolved via PATH. Without
            # this, the subprocess falls back to the OS default PATH instead of
            # the interpreter pytest itself is running under -- landing on a
            # system python3 that doesn't have this repo's dependencies (PyYAML)
            # installed, so install.sh fails with ModuleNotFoundError before
            # ever reaching the behavior under test.
            "PATH": os.environ.get("PATH", ""),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "unit-test-creator" in result.stdout
    assert not (home / ".cursor" / "skills").exists()
    assert not (home / ".claude" / "skills").exists()


def test_package_skill_writes_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "unit-test-creator", repo / "unit-test-creator")
    shutil.copytree(ROOT / "docs" / "skill-framework", repo / "docs" / "skill-framework")
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "test_creator_write_guard.py", repo / "scripts" / "test_creator_write_guard.py")
    shutil.copy2(ROOT / "scripts" / "git_paths.py", repo / "scripts" / "git_paths.py")
    (repo / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    # -c commit.gpgsign=false: don't depend on the invoking machine's global
    # Git signing config (commit signing turned on would otherwise block this
    # fixture commit on a passphrase/hardware-key prompt or fail outright).
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=repo, check=True)
    dest = tmp_path / "installed"

    subprocess.run(
        [
            "python3",
            str(ROOT / "scripts" / "package_skill.py"),
            "--skill",
            "unit-test-creator",
            "--dest",
            str(dest),
            "--repo-root",
            str(repo),
            "--host",
            "cursor",
        ],
        check=True,
    )

    manifest = json.loads((dest / ".software-builder-manifest.json").read_text(encoding="utf-8"))
    assert manifest["skill"] == "unit-test-creator"
    assert "SKILL.md" in manifest["files"]
