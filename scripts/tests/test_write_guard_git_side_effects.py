"""The test-creator write guard inspects a repository without acting on it.

Git reads a repository's own configuration -- fsmonitor hooks, clean filters,
submodule filters, a repo-local `git` on PATH -- so a guard that shells out
naively lets the repository it is inspecting execute code and mutate state.
Each test here pins one such side effect to "did not happen".
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.test_creator_write_guard import check_write_safety


def _committed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "guard@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Write Guard"], cwd=repo, check=True)
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], cwd=repo, check=True)
    return repo


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


def test_guard_does_not_recurse_into_submodule_filters(tmp_path: Path) -> None:
    source_root = tmp_path / "submodule-source-parent"
    source_root.mkdir()
    source = _committed_repo(source_root)
    (source / "tracked.txt").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=source, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "tracked"], cwd=source, check=True)

    super_root = tmp_path / "super-parent"
    super_root.mkdir()
    repo = _committed_repo(super_root)
    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "submodule", "add", str(source), "modules/child"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", ".gitmodules", "modules/child"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "submodule"], cwd=repo, check=True)

    child = repo / "modules" / "child"
    subprocess.run(["git", "config", "user.email", "review@example.invalid"], cwd=child, check=True)
    subprocess.run(["git", "config", "user.name", "Final Review"], cwd=child, check=True)
    (child / ".gitattributes").write_text("tracked.txt filter=review-evil\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitattributes"], cwd=child, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "attributes"], cwd=child, check=True)
    subprocess.run(["git", "add", "modules/child"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "advance submodule"], cwd=repo, check=True)

    marker = tmp_path / "submodule-filter-executed"
    hook = tmp_path / "submodule-filter.py"
    hook.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed\\n', encoding='utf-8')\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    subprocess.run(["git", "config", "filter.review-evil.clean", str(hook)], cwd=child, check=True)
    tracked = child / "tracked.txt"
    stat = tracked.stat()
    os.utime(tracked, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))

    result = check_write_safety(repo, ["generated_test.py"])

    assert result.status == "ALLOWED"
    assert not marker.exists(), "guard recursed into submodule and executed its clean filter"


def test_nested_repo_root_does_not_scan_sibling_filter(tmp_path: Path) -> None:
    repo = _committed_repo(tmp_path)
    project = repo / "project"
    project.mkdir()
    (project / "tracked.py").write_text("fixture\n", encoding="utf-8")
    sibling = repo / "outside.txt"
    sibling.write_text("fixture\n", encoding="utf-8")
    (repo / ".gitattributes").write_text("outside.txt filter=review-evil\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "nested root"], cwd=repo, check=True)

    marker = tmp_path / "sibling-filter-executed"
    hook = tmp_path / "sibling-filter.py"
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
    stat = sibling.stat()
    os.utime(sibling, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))

    result = check_write_safety(project, ["generated_test.py"])

    assert result.status == "ALLOWED"
    assert not marker.exists(), "nested guard scanned sibling outside repo_root"


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable shim regression")
def test_guard_does_not_execute_repo_local_git_from_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _committed_repo(tmp_path)
    real_git = shutil.which("git")
    assert real_git is not None
    marker = tmp_path / "repo-git-executed"
    bin_dir = repo / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        f"printf executed > {str(marker)!r}\n"
        f"exec {real_git!r} \"$@\"\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    result = check_write_safety(repo, ["generated_test.py"])

    assert result.status == "ALLOWED"
    assert not marker.exists(), "guard executed repo-local git from PATH"
