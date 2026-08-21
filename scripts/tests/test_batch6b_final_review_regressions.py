"""Regressions found during the final PR 148 review passes."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts.registry import generic_package
from scripts.test_creator_catalog import TEST_CREATOR_SKILLS
from scripts.test_creator_write_guard import check_write_safety

ROOT = Path(__file__).resolve().parents[2]
COMMON_WORKFLOW = ROOT / "docs" / "skill-framework" / "shared" / "test-creator-common-workflow.md"


def _committed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "review@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Final Review"], cwd=repo, check=True)
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=repo, check=True)
    return repo


def test_common_workflow_requires_separate_report_and_state_guards() -> None:
    text = COMMON_WORKFLOW.read_text(encoding="utf-8")

    assert "fresh report-only guard" in text
    assert "fresh state-only guard" in text
    assert text.index("fresh report-only guard") < text.index("fresh state-only guard")


def test_common_workflow_preserves_unverified_when_execution_is_unavailable() -> None:
    text = COMMON_WORKFLOW.read_text(encoding="utf-8")

    assert "remain `UNVERIFIED`" in text
    assert "unsafe repository state" in text


def test_test_writer_aggregate_change_is_versioned_in_2_4_changelog() -> None:
    aggregate = (ROOT / "test-writer" / "workflow" / "aggregate.md").read_text(encoding="utf-8")
    changelog = (ROOT / "test-writer" / "CHANGELOG.md").read_text(encoding="utf-8")
    current_entry = changelog.split("## [2.4.0]", 1)[1].split("## [2.3.0]", 1)[0]

    assert "workflow_version: 1.6" in aggregate
    assert "`workflow/aggregate.md` → 1.6" in current_entry


@pytest.mark.parametrize(
    "required_rel",
    [
        "scripts/test_creator_write_guard.py",
        "scripts/git_paths.py",
    ],
)
def test_generic_package_requires_test_creator_runtime(
    monkeypatch: pytest.MonkeyPatch,
    required_rel: str,
) -> None:
    tracked = generic_package._tracked_files(ROOT)
    missing = (ROOT / required_rel).resolve()
    monkeypatch.setattr(
        generic_package,
        "_tracked_files",
        lambda root: {path for path in tracked if path.resolve() != missing},
    )

    with pytest.raises(ValueError, match="test-creator runtime"):
        generic_package._package_files(ROOT)


@pytest.mark.parametrize("config_source", ["repo_local", "explicit_global", "home_global"])
def test_guard_does_not_execute_git_fsmonitor_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config_source: str,
) -> None:
    repo = _committed_repo(tmp_path)
    marker = tmp_path / "fsmonitor-executed"
    hook = tmp_path / "fsmonitor.py"
    hook.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    config = tmp_path / "ambient.gitconfig"
    config.write_text(f"[core]\n\tfsmonitor = {hook}\n", encoding="utf-8")

    monkeypatch.delenv("GIT_CONFIG_GLOBAL", raising=False)
    if config_source == "repo_local":
        subprocess.run(["git", "config", "core.fsmonitor", str(hook)], cwd=repo, check=True)
    elif config_source == "explicit_global":
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    else:
        home = tmp_path / "home"
        home.mkdir()
        (home / ".gitconfig").write_text(config.read_text(encoding="utf-8"), encoding="utf-8")
        monkeypatch.setenv("HOME", str(home))

    result = check_write_safety(repo, ["generated_test.py"])

    assert result.status == "ALLOWED"
    assert not marker.exists(), "guard Git commands executed core.fsmonitor"


def test_guard_ignores_git_trace_file_side_effect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _committed_repo(tmp_path)
    trace = tmp_path / "git-trace.log"
    monkeypatch.setenv("GIT_TRACE", str(trace))

    result = check_write_safety(repo, ["generated_test.py"])

    assert result.status == "ALLOWED"
    assert not trace.exists(), "read-only guard wrote a Git trace file"


def test_guard_does_not_refresh_git_index_metadata(tmp_path: Path) -> None:
    repo = _committed_repo(tmp_path)
    tracked = repo / "README.md"
    index = repo / ".git" / "index"
    before = index.read_bytes()
    stat = tracked.stat()
    os.utime(tracked, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))

    result = check_write_safety(repo, ["generated_test.py"])

    assert result.status == "ALLOWED"
    assert index.read_bytes() == before, "read-only guard refreshed .git/index metadata"


def test_guard_does_not_execute_repository_clean_filter(tmp_path: Path) -> None:
    repo = _committed_repo(tmp_path)
    attributes = repo / ".gitattributes"
    attributes.write_text("README.md filter=review-evil\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitattributes"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "attributes"], cwd=repo, check=True)

    marker = tmp_path / "clean-filter-executed"
    hook = tmp_path / "clean-filter.py"
    hook.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed\\n', encoding='utf-8')\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    subprocess.run(["git", "config", "filter.review-evil.clean", str(hook)], cwd=repo, check=True)

    tracked = repo / "README.md"
    stat = tracked.stat()
    os.utime(tracked, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
    result = check_write_safety(repo, ["generated_test.py"])

    assert result.status == "ALLOWED"
    assert not marker.exists(), "guard Git commands executed repository clean filter"


def test_guard_evidence_stays_structured_not_verbatim_markdown() -> None:
    shared = (
        ROOT / "docs" / "skill-framework" / "shared" / "test-creator-write-safety.md"
    ).read_text(encoding="utf-8")
    assert "safe-output.md" in shared
    assert "must not be rendered verbatim" in shared

    for creator in TEST_CREATOR_SKILLS:
        report = (ROOT / creator / "workflow" / "report.md").read_text(encoding="utf-8")
        assert "canonical `skill_result`" in report, creator
        assert "Do not paste `status_snapshot` or `reason` verbatim" in report, creator
