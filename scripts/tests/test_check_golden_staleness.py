"""Tests for scripts/check_golden_staleness.py.

Uses a real tmp_path git repository (git init + deterministic commit dates via
GIT_AUTHOR_DATE/GIT_COMMITTER_DATE) rather than mocking subprocess, following the
same pattern scripts/tests/test_install_rollback.py uses for its git fixture: a
committed skills.yaml + skill directories, `-c commit.gpgsign=false` so a machine
with commit signing turned on globally can't block the fixture commit.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scripts.check_golden_staleness import find_stale_golden_fixtures

_SKILLS_YAML = """schema_version: 1
skills:
  fresh-skill:
    path: fresh-skill
    category: architecture
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    capabilities:
      required: [host.repository.read]
    lint:
      skill_md_max_lines: 180
      target: fresh-skill
    risk_class: [read-only]
  stale-skill:
    path: stale-skill
    category: architecture
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    capabilities:
      required: [host.repository.read]
    lint:
      skill_md_max_lines: 180
      target: stale-skill
    risk_class: [read-only]
"""


def _skill_md(description: str) -> str:
    return f"---\nname: skill\ndescription: {description}\n---\n\nBody.\n"


def _git_commit(repo: Path, *, message: str, commit_date: str) -> None:
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    env = {
        **os.environ,
        "GIT_AUTHOR_DATE": commit_date,
        "GIT_COMMITTER_DATE": commit_date,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    # -c commit.gpgsign=false: don't depend on the invoking machine's global Git
    # signing config (see scripts/tests/test_install_rollback.py's identical comment).
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", message],
        cwd=repo,
        check=True,
        env=env,
    )


def _write_golden_fixture(path: Path, *, skill: str, case_id: str, last_refreshed_at: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"skill: {skill}",
        f"case_id: {case_id}",
        "tier: 3",
        "description: test fixture",
        "recorded_output:",
        "  status: ok",
        "assertions:",
        "  - type: field_present",
        "    path: status",
    ]
    if last_refreshed_at is not None:
        lines += [
            "refresh_meta:",
            f"  last_refreshed_at: '{last_refreshed_at}'",
            "  refresh_note: test",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_repo(tmp_path: Path) -> Path:
    """A repo with two skills exercising both branches of the staleness check.

    fresh-skill: SKILL.md's only commit is 2020-01-01; its golden fixture was
    refreshed in 2023 -- refresh postdates the commit, so no warning.

    stale-skill: SKILL.md is first committed in 2020, then edited and
    recommitted in 2022; its golden fixture was refreshed back in 2021 --
    the 2022 SKILL.md edit postdates that refresh, so a warning is expected.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "skills.yaml").write_text(_SKILLS_YAML, encoding="utf-8")
    (repo / "fresh-skill").mkdir()
    (repo / "fresh-skill" / "SKILL.md").write_text(_skill_md("fresh"), encoding="utf-8")
    (repo / "stale-skill").mkdir()
    (repo / "stale-skill" / "SKILL.md").write_text(_skill_md("stale v1"), encoding="utf-8")

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    _git_commit(repo, message="initial", commit_date="2020-01-01T00:00:00+00:00")

    # Only stale-skill's SKILL.md changes again, after the fixture refresh dates below.
    (repo / "stale-skill" / "SKILL.md").write_text(_skill_md("stale v2 -- behavior changed"), encoding="utf-8")
    _git_commit(repo, message="update stale-skill", commit_date="2022-01-01T00:00:00+00:00")

    _write_golden_fixture(
        repo / "evals" / "golden" / "fresh-skill" / "happy.yaml",
        skill="fresh-skill",
        case_id="happy",
        last_refreshed_at="2023-01-01T00:00:00Z",  # after fresh-skill's only (2020) commit
    )
    _write_golden_fixture(
        repo / "evals" / "golden" / "stale-skill" / "happy.yaml",
        skill="stale-skill",
        case_id="happy",
        last_refreshed_at="2021-01-01T00:00:00Z",  # before stale-skill's 2022 commit
    )
    return repo


def test_fixture_refreshed_after_skill_md_commit_is_not_flagged(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)

    stale = find_stale_golden_fixtures(repo)

    assert not any(item.skill == "fresh-skill" for item in stale)


def test_fixture_refreshed_before_skill_md_commit_is_flagged(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)

    stale = find_stale_golden_fixtures(repo)

    matches = [item for item in stale if item.skill == "stale-skill"]
    assert len(matches) == 1
    flagged = matches[0]
    assert flagged.case_id == "happy"
    assert flagged.last_refreshed_at == "2021-01-01T00:00:00Z"
    assert flagged.skill_md_last_commit_at.startswith("2022-01-01")


def test_fixture_with_no_refresh_meta_is_not_flagged(tmp_path: Path) -> None:
    """No refresh_meta at all is a different gap (never refreshed) from this
    check's target (a stamped refresh a later SKILL.md edit has overtaken) --
    find_stale_golden_fixtures skips it rather than guessing.
    """
    repo = _build_repo(tmp_path)
    _write_golden_fixture(
        repo / "evals" / "golden" / "stale-skill" / "no-refresh-meta.yaml",
        skill="stale-skill",
        case_id="no-refresh-meta",
        last_refreshed_at=None,
    )

    stale = find_stale_golden_fixtures(repo)

    assert not any(item.case_id == "no-refresh-meta" for item in stale)


def test_check_golden_staleness_never_fails_on_the_real_repo() -> None:
    """Advisory only (ADR-0003/0004): running it against this repository's real
    fixtures must always exit 0 and must never raise, regardless of whether any
    fixture happens to be stale today.
    """
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["python3", "scripts/check_golden_staleness.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
