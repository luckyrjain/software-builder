"""Tests for the C4c-1 filesystem and git pieces of `benchmark_gate.py`: `export_tree`, tree hash and seal,
`cleanup_root`, and the `export` / `cleanup` CLIs.

Everything git-related runs against real temporary repositories (no network, hooks or signing); hostile trees (`.git`
entries, `..`, case collisions, escaping symlinks) are built with `git mktree`, since `git add` refuses them.
Design: docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md (APIs table, `compare` row).
"""

from __future__ import annotations

import collections
import concurrent.futures
import importlib.util
import json
import multiprocessing
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


bg = _load(_SCRIPTS / "benchmark_gate.py", "benchmark_gate")
Err = bg.BenchmarkGateError
IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
BENCH = "benchmarks/bench_orders.py"
BENCH_SRC = b'import hashlib\n\n\ndef test_bench():\n    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(b"x").hexdigest())\n'

# --- helpers: scrubbed git, real repositories, hostile trees ---

GIT_ENV = {
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/nonexistent", "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
}
GIT_FLAGS = ["-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
             "-c", "protocol.file.allow=never"]

def git(cwd, *args, inp=None) -> str:
    done = subprocess.run(["git", *GIT_FLAGS, *args], cwd=cwd, env=GIT_ENV, input=inp, capture_output=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return done.stdout.decode().strip()

def make_repo(tmp_path, name="repo", fmt="sha1") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q", f"--object-format={fmt}")
    return repo

def commit(repo, files=None, msg="c") -> str:
    """Apply `files` ({path: bytes | str | None (delete) | ("link", target) | ("exec", bytes)}) and commit."""
    for rel, value in (files or {}).items():
        path = repo / rel
        if value is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, tuple) and value[0] == "link":
            path.symlink_to(value[1])
            continue
        data = value[1] if isinstance(value, tuple) else value
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        path.chmod(0o755 if isinstance(value, tuple) else 0o644)
    git(repo, "add", "-A", "-f")
    git(repo, "commit", "-q", "--allow-empty", "-m", msg)
    return git(repo, "rev-parse", "HEAD")

def hostile_commit(repo, lines: list[str]) -> str:
    tree = git(repo, "mktree", inp=("\n".join(lines) + "\n").encode())
    return git(repo, "commit-tree", tree, "-m", "hostile")

def blob(repo, data=b"x\n") -> str:
    return git(repo, "hash-object", "-w", "--stdin", inp=data)

def dir_with(repo, name, inner="config", data=b"x\n") -> str:
    inner_tree = git(repo, "mktree", inp=f"100644 blob {blob(repo, data)}\t{inner}\n".encode())
    return f"040000 tree {inner_tree}\t{name}"

@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    """The fixed parent (and every private git directory) lives under tmp_path, never the real temp directory."""
    temp = tmp_path / "tmp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    try:
        bg._require_modern_git()
    except Err as exc:
        shown = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=60).stdout
        found = re.search(r"(\d+)\.(\d+)", shown)  # judged independently of the code under test
        if exc.code != "GIT_TOO_OLD" or found is None or (int(found[1]), int(found[2])) >= (2, 43):
            raise  # a parse regression or a hang must fail, never hide behind a skip
        pytest.skip(f"git >= 2.43 is needed for GIT_ATTR_SOURCE: {exc.detail}")
    return temp

def dest(leaf="head", root="bench-aaaaaaaa") -> str:
    return str(bg.fixed_parent() / root / leaf)

def tree_files(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and not p.is_symlink()}

@pytest.fixture
def repo_a(tmp_path):
    repo = make_repo(tmp_path)
    sha = commit(repo, {"src/app/__init__.py": "x = 1\n", "src/app/run.sh": ("exec", "#!/bin/sh\n"), "README.md": "r\n",
                        "link": ("link", "src/app/__init__.py"), BENCH: BENCH_SRC})
    return repo, sha


# --- export_tree ---

def test_export_is_pristine_writable_without_git_and_records_the_owner(repo_a):
    repo, sha = repo_a
    out = bg.export_tree(repo, sha, dest())
    assert out == Path(dest()) and tree_files(out)["src/app/__init__.py"] == b"x = 1\n"
    assert os.access(out / "src/app/run.sh", os.X_OK) and not os.access(out / "README.md", os.X_OK)
    assert os.readlink(out / "link") == "src/app/__init__.py"
    assert not [p for p in out.rglob("*") if p.name.lower().startswith(".git")]
    (out / "new.txt").write_text("writable")  # left writable for the install and the overlay
    marker = json.loads((out.parent / bg._MARKER_NAME).read_text())
    assert (marker["pid"], marker["kind"], marker["root"]) == (os.getpid(), bg._MARKER_KIND, out.parent.name)
    assert json.loads((out.parent / "head.export.json").read_text())["commit"] == sha
    assert {stat.S_IMODE(os.stat(p).st_mode) for p in (out.parent / bg._MARKER_NAME, out.parent / "head.export.json")} == {0o600}
    assert not [n for n in os.listdir(tempfile.gettempdir()) if n.startswith("bench-git-")]  # no private git directory left
    assert not [n for n in os.listdir(out.parent.parent) if n.startswith(".new-")]  # no half-made root left
    assert bg.export_tree(repo, sha, dest("base"), owner_pid=1) == Path(dest("base"))  # second export reuses the root
    assert json.loads((out.parent / bg._MARKER_NAME).read_text())["pid"] == os.getpid()

def test_export_ignores_the_trees_own_attributes_and_the_repos_own_config(tmp_path):
    repo = make_repo(tmp_path)
    canary = tmp_path / "canary"
    files = {".gitattributes": "* text eol=crlf\n*.py filter=evil\nid.txt ident\nv.txt export-subst\nx.txt export-ignore\n",
             "a.py": "a\nb\n", "id.txt": "$Id$\n", "v.txt": "$Format:%H$\n", "x.txt": "kept\n"}
    sha = commit(repo, files)
    git(repo, "config", "filter.evil.smudge", f"touch {canary}; cat")
    git(repo, "config", "core.fsmonitor", f"touch {canary}")
    git(repo, "config", "core.hooksPath", str(tmp_path))
    out = bg.export_tree(repo, sha, dest())
    assert tree_files(out) == {k: v.encode() for k, v in files.items()}  # byte-identical: no CRLF, no ident, nothing dropped
    assert not canary.exists()

def test_export_sha256_repository(tmp_path):
    try:
        repo = make_repo(tmp_path, fmt="sha256")
    except AssertionError:
        pytest.skip("this git cannot create sha256 repositories")
    sha = commit(repo, {"a.py": "x\n"})
    assert len(sha) == 64 and tree_files(bg.export_tree(repo, sha, dest())) == {"a.py": b"x\n"}

def test_export_from_a_linked_worktree_and_odd_file_names(tmp_path):
    repo = make_repo(tmp_path)
    names = {"-dash.py": "1", "sp ace.py": "2", "café.py": "3", "new\nline.py": "4", "d/ends.py\n": "5"}
    sha = commit(repo, names)
    git(repo, "worktree", "add", "-q", str(tmp_path / "wt"), "-b", "other")
    got = tree_files(bg.export_tree(tmp_path / "wt", sha, dest()))
    assert got == {k: v.encode() for k, v in names.items()}

def test_export_reports_gitlinks_as_empty_directories_and_lfs_pointers(tmp_path, repo_a, capsys):
    repo, sha = repo_a
    lfs = b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"a" * 64 + b"\nsize 5\n"
    (repo / "big.bin").write_bytes(lfs)
    git(repo, "add", "big.bin")
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{sha},vendor/sub")
    git(repo, "commit", "-q", "-m", "gitlink")
    sha2 = git(repo, "rev-parse", "HEAD")
    out, notes = bg._export(repo, sha2, dest(), None)
    assert (out / "vendor/sub").is_dir() and not list((out / "vendor/sub").iterdir())
    assert notes == {"gitlinks": ["vendor/sub"], "lfs_pointers": ["big.bin"]}
    assert (out / "big.bin").read_bytes() == lfs  # unresolved, not fetched
    assert bg.main(["export", "--repo", str(repo), "--commit", sha2, "--dest", dest("other")]) == 0
    err = capsys.readouterr().err
    assert "submodule left as an empty directory: vendor/sub" in err and "LFS pointer left unresolved: big.bin" in err

@pytest.mark.parametrize("builder, code", [
    (lambda r, b: [dir_with(r, ".git")], "EXPORT_PATH_REJECTED"),
    (lambda r, b: [dir_with(r, ".GIT")], "EXPORT_PATH_REJECTED"),
    (lambda r, b: [dir_with(r, ".git ")], "EXPORT_PATH_REJECTED"),
    (lambda r, b: [dir_with(r, ".g‌it")], "EXPORT_PATH_REJECTED"),
    (lambda r, b: [dir_with(r, "GIT~1")], "EXPORT_PATH_REJECTED"),
    (lambda r, b: [dir_with(r, "..")], "EXPORT_PATH_REJECTED"),
    (lambda r, b: [dir_with(r, ".")], "EXPORT_PATH_REJECTED"),
    (lambda r, b: [f"100644 blob {b}\tFoo.py", f"100644 blob {b}\tfoo.py"], "EXPORT_PATH_COLLISION"),
    (lambda r, b: [f"100644 blob {b}\tcafé.py", f"100644 blob {b}\tcafé.py"], "EXPORT_PATH_COLLISION"),
    (lambda r, b: [f"100644 blob {b}\ta", dir_with(r, "A")], "EXPORT_PATH_COLLISION"),
    (lambda r, b: [f"120000 blob {blob(r, b'../../etc/passwd')}\tesc"], "EXPORT_SYMLINK_ESCAPES"),
    (lambda r, b: [f"120000 blob {blob(r, b'/etc/passwd')}\tabs"], "EXPORT_SYMLINK_ESCAPES"),
    (lambda r, b: [f"120000 blob {blob(r, b'../head.export.json')}\tsibling"], "EXPORT_SYMLINK_ESCAPES"),  # shares the "head" prefix
    (lambda r, b: [f"120000 blob {blob(r, b'.')}\tself", f"120000 blob {blob(r, b'self/../..')}\tchain"], "EXPORT_SYMLINK_ESCAPES"),
])
def test_export_refuses_hostile_trees_and_leaves_nothing_behind(tmp_path, capsys, builder, code):
    repo = make_repo(tmp_path)
    sha = hostile_commit(repo, builder(repo, blob(repo)))
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code == code and code in bg.EXPORT_REFUSAL_CODES
    assert not Path(dest()).exists() and not Path(dest() + ".export.json").exists()  # a new root, if any, keeps only its marker
    assert bg.main(["export", "--repo", str(repo), "--commit", sha, "--dest", dest()]) == 1
    cap = capsys.readouterr()
    assert cap.out == code + "\n" and cap.err.startswith("detail: ")

@pytest.mark.parametrize("record, code", [
    (b"100666 blob abc 1\tweird\0", "EXPORT_ENTRY_MODE"), (b"160000 blob abc 1\tg\0", "EXPORT_ENTRY_MODE"),
    (b"100644 commit abc 1\tg\0", "EXPORT_ENTRY_MODE"), (b"040000 tree abc -\td\0", "EXPORT_ENTRY_MODE"),
    (b"100644 blob abc 1\ta/./b\0", "EXPORT_PATH_REJECTED"), (b"100644 blob abc 1\ta//b\0", "EXPORT_PATH_REJECTED"),
    (b"100644 blob abc 1\t/abs\0", "EXPORT_PATH_REJECTED"), (b"100644 blob abc 1\t\0", "EXPORT_PATH_REJECTED"),
    (b"100644 blob abc x\tf\0", "GIT_FAILED"), (b"100644 blob abc 1\tf", "GIT_FAILED"), (b"garbage\0", "GIT_FAILED"),
    (b"100644 blob abc 2000000000\tf\0", "EXPORT_TOO_LARGE"),
])
def test_listing_parser_refuses_what_it_cannot_export_safely(record, code):
    with pytest.raises(Err) as info:
        bg._parse_listing(record)
    assert info.value.code == code
    assert bg._parse_listing(b"") == {}

def test_oversize_is_one_condition_files_and_directories_together(repo_a, monkeypatch):
    repo, sha = repo_a  # 5 files in 3 directories: 9 entries with the root, the same count the verification walk uses
    monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", 8)
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code == "EXPORT_TOO_LARGE"
    monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", 9)
    assert bg.export_tree(repo, sha, dest()).is_dir()

def test_export_verification_catches_a_conversion_that_changed_bytes(repo_a, monkeypatch):
    repo, sha = repo_a  # a git too old to honour GIT_ATTR_SOURCE would convert: the size check must then fail closed
    real = subprocess.run

    def old_git(argv, **kw):
        return real(argv, **{**kw, "env": {k: v for k, v in kw["env"].items() if k != "GIT_ATTR_SOURCE"}})

    monkeypatch.setattr(subprocess, "run", old_git)
    sha_crlf = commit(repo, {".gitattributes": "* text eol=crlf\n", "a.py": "a\nb\n"})
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha_crlf, dest())
    assert info.value.code == "EXPORT_VERIFY_FAILED"
    assert not Path(dest()).exists()

@pytest.mark.parametrize("commit_arg", ["", "abc", "A" * 40, "g" * 40, "-" + "a" * 39, "a" * 41, "a" * 40 + "\n", "a" * 40 + "\0", None, 7])
def test_export_rejects_malformed_commits(repo_a, commit_arg):
    with pytest.raises(Err) as info:
        bg.export_tree(repo_a[0], commit_arg, dest())
    assert info.value.code == "COMMIT_INVALID"

def test_export_errors_are_clean_and_exit_2(repo_a, tmp_path, capsys):
    repo, sha = repo_a
    tag = git(repo, "tag", "-a", "-m", "t", "v1") or git(repo, "rev-parse", "v1")
    cases = [(repo, "1" * 40, dest(), "COMMIT_NOT_FOUND"), (repo, tag, dest(), "COMMIT_NOT_FOUND"),
             (tmp_path / "missing", sha, dest(), "REPO_UNREADABLE"), (tmp_path, sha, dest(), "REPO_UNREADABLE"),
             (repo, sha, str(tmp_path / "elsewhere" / "head"), "DEST_REJECTED"),
             (repo, sha, str(bg.fixed_parent() / "short" / "head"), "DEST_REJECTED"),
             (repo, sha, str(bg.fixed_parent() / "bench-aaaaaaaa" / ".hidden"), "DEST_REJECTED"),
             (repo, sha, str(bg.fixed_parent() / "bench-aaaaaaaa" / "a" / "b"), "DEST_REJECTED")]
    for repo_arg, commit_arg, dest_arg, code in cases:
        with pytest.raises(Err) as info:
            bg.export_tree(repo_arg, commit_arg, dest_arg)
        assert info.value.code == code, (code, info.value.code)
        assert bg.main(["export", "--repo", str(repo_arg), "--commit", commit_arg, "--dest", dest_arg]) == 2
        assert capsys.readouterr().out == ""

def test_export_refuses_a_root_that_is_not_ours_or_a_symlinked_root(repo_a, tmp_path):
    repo, sha = repo_a
    (bg.fixed_parent()).mkdir(mode=0o700)
    (bg.fixed_parent() / "bench-bbbbbbbb").mkdir()
    (bg.fixed_parent() / "bench-bbbbbbbb" / "stray").write_text("x")  # not ours: no marker (an EMPTY directory would be replaced)
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest(root="bench-bbbbbbbb"))
    assert info.value.code == "MARKER_MISSING"
    outside = tmp_path / "elsewhere" / "bench-cccccccc"  # a real root of the same name with a VALID marker, outside the parent
    outside.mkdir(parents=True)
    bg._write_marker(str(outside), os.getpid())
    (bg.fixed_parent() / "bench-cccccccc").symlink_to(outside)
    with pytest.raises(Err) as info:  # the marker alone would pass: only the lstat check refuses the symlinked root
        bg.export_tree(repo, sha, dest(root="bench-cccccccc"))
    assert info.value.code == "DEST_REJECTED" and sorted(os.listdir(outside)) == [bg._MARKER_NAME]

def test_git_runs_with_a_scrubbed_environment(repo_a, monkeypatch):
    repo, sha = repo_a
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG_COUNT", "GIT_EXTERNAL_DIFF", "GIT_SSH_COMMAND"):
        monkeypatch.setenv(name, "/nonexistent")
    seen = []
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: seen.append((argv, kw)) or real(argv, **kw))
    bg.export_tree(repo, sha, dest())
    assert seen and all(isinstance(argv, list) and kw["stdin"] == subprocess.DEVNULL and kw["timeout"] for argv, kw in seen)
    for _, kw in seen:  # argv lists, never a shell
        env = kw["env"]
        assert env["GIT_CONFIG_NOSYSTEM"] == "1" and env["GIT_CONFIG_GLOBAL"] == os.devnull and env["GIT_TERMINAL_PROMPT"] == "0"
        assert "GIT_EXTERNAL_DIFF" not in env and "GIT_SSH_COMMAND" not in env and "GIT_CONFIG_COUNT" not in env


# --- seal_tree, unseal_tree ---

@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "t"
    (root / "d").mkdir(parents=True)
    (root / "d/a.txt").write_text("a")
    (root / "b.txt").write_text("b")
    (root / "link").symlink_to("b.txt")
    for path, mode in ((root, 0o755), (root / "d", 0o777), (root / "d/a.txt", 0o644), (root / "b.txt", 0o666)):
        path.chmod(mode)  # explicit (independent of the umask); group/other write bits so a seal must clear them too
    yield root
    for directory, names, _files in os.walk(root):  # leave nothing sealed or unlistable behind
        os.chmod(directory, 0o755)

def test_walk_is_bounded_and_refuses_a_symlink_or_missing_root(tree, tmp_path, monkeypatch):
    for bad in (tree / "link", tmp_path / "missing"):
        with pytest.raises(Err) as info:
            list(bg._walk_tree(str(bad)))
        assert info.value.code == "TREE_UNREADABLE"
    monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", 3)
    with pytest.raises(Err) as info:
        list(bg._walk_tree(str(tree)))
    assert info.value.code == "TREE_TOO_LARGE"

@pytest.mark.skipif(IS_ROOT, reason="root ignores write bits")
def test_seal_removes_every_write_bit_and_unseal_restores(tree, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("o")
    outside.chmod(0o644)
    (tree / "esc").symlink_to(outside)
    bg.seal_tree(tree)
    for p in [tree, *tree.rglob("*")]:
        if not p.is_symlink():
            assert not p.stat().st_mode & 0o222, p
    assert stat.S_IMODE(outside.stat().st_mode) == 0o644  # a symlink is never followed
    with pytest.raises(PermissionError):
        (tree / "new.txt").write_text("x")
    with pytest.raises(PermissionError):
        (tree / "b.txt").write_text("x")
    assert (tree / "d/a.txt").read_text() == "a"  # still readable
    bg.seal_tree(tree)  # idempotent
    bg.unseal_tree(tree)
    (tree / "new.txt").write_text("x")
    assert stat.S_IMODE(outside.stat().st_mode) == 0o644

@pytest.mark.skipif(IS_ROOT, reason="root ignores permissions")
def test_unseal_handles_unlistable_directories_and_seal_fails_closed(tree):
    (tree / "d").chmod(0)
    with pytest.raises(Err) as info:
        bg.seal_tree(tree)
    assert info.value.code in ("SEAL_FAILED", "TREE_UNREADABLE")
    bg.unseal_tree(tree)
    assert (tree / "d/a.txt").read_text() == "a" and stat.S_IMODE((tree / "d").stat().st_mode) == 0o700  # not 0o777


# --- cleanup_root, pid liveness ---

def dead_pid() -> int:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=60)
    return child.pid

@pytest.fixture
def root(repo_a):
    repo, sha = repo_a
    bg.export_tree(repo, sha, dest(), owner_pid=dead_pid())
    return Path(dest()).parent

def test_cleanup_removes_a_sealed_root_with_a_dead_owner_and_never_follows_links(root, tmp_path):
    outside = tmp_path / "keep"
    outside.mkdir()
    (outside / "canary").write_text("alive")
    (root / "head" / "out").symlink_to(outside)
    (root / "toplink").symlink_to(outside)  # a top-level link is unlinked, never followed
    bg.seal_tree(root / "head")
    assert bg.cleanup_root(root) == "REMOVED" and not root.exists()
    assert (outside / "canary").read_text() == "alive" and outside.exists()
    assert bg.cleanup_root(root) == "ABSENT"

def write_marker(directory: Path, **overrides):
    marker = {"kind": bg._MARKER_KIND, "version": 1, "pid": dead_pid(), "created": 1.0, "root": directory.name, **overrides}
    (directory / bg._MARKER_NAME).write_text(json.dumps(marker))

@pytest.mark.parametrize("override", [
    {"pid": True}, {"pid": 0}, {"pid": -5}, {"pid": "1"}, {"pid": 2 ** 40}, {"created": 1e12}, {"created": "now"}, {"created": float("nan")},
    {"created": 0}, {"root": "bench-other"}, {"kind": "x"}, {"version": 2},
])
def test_cleanup_refuses_an_invalid_marker(root, override):
    write_marker(root, **override)
    assert bg.cleanup_root(root) == "MARKER_INVALID" and root.exists()

def test_cleanup_refuses_bad_markers_roots_and_paths(root, tmp_path):
    (root / bg._MARKER_NAME).write_text("{not json")
    assert bg.cleanup_root(root) == "MARKER_INVALID"
    (root / bg._MARKER_NAME).write_text(" " * 5000)
    assert bg.cleanup_root(root) == "MARKER_INVALID"
    (root / bg._MARKER_NAME).unlink()
    assert bg.cleanup_root(root) == "MARKER_MISSING"
    write_marker(root)
    copied = bg.fixed_parent() / "bench-copycopy"  # a copied marker proves nothing (it names its own root)
    copied.mkdir()
    (copied / bg._MARKER_NAME).write_text((root / bg._MARKER_NAME).read_text())
    assert bg.cleanup_root(copied) == "MARKER_INVALID" and copied.exists()
    link = bg.fixed_parent() / "bench-linklink"
    link.symlink_to(root)
    assert bg.cleanup_root(link) == "NOT_A_DIRECTORY" and root.exists()
    plain = bg.fixed_parent() / "bench-plainfile"
    plain.write_text("x")
    assert bg.cleanup_root(plain) == "NOT_A_DIRECTORY" and plain.exists()
    stray = tmp_path / "bench-stray001"
    stray.mkdir()
    write_marker(stray)
    for bad in (stray, bg.fixed_parent(), tmp_path, root / "head", "", "bench", "/", str(stray) + "/../" + stray.name):
        assert bg.cleanup_root(bad) == "NOT_UNDER_FIXED_PARENT", bad
    assert stray.exists() and (root / "head").exists()

def test_pid_liveness(monkeypatch):
    assert bg._pid_alive(os.getpid()) and not bg._pid_alive(dead_pid())
    for exc, alive in ((PermissionError(), True), (OSError(), True), (OverflowError(), True), (ProcessLookupError(), False)):
        monkeypatch.setattr(os, "kill", lambda pid, sig, exc=exc: (_ for _ in ()).throw(exc))
        assert bg._pid_alive(5) is alive
    monkeypatch.setattr(os, "name", "nt")
    assert bg._pid_alive(5) is True  # never os.kill off POSIX: on Windows that terminates the process

def test_cleanup_cli_exit_codes(root, capsys):
    handlers = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
    write_marker(root, pid=os.getpid())
    assert bg.main(["cleanup", "--root", str(root)]) == 1 and capsys.readouterr().out == "OWNER_ALIVE\n"
    write_marker(root)
    assert bg.main(["cleanup", "--root", str(root)]) == 0 and capsys.readouterr().out == "REMOVED\n"
    assert bg.main(["cleanup", "--root", str(root)]) == 0 and capsys.readouterr().out == "ABSENT\n"
    assert bg.main(["cleanup"]) == 2
    assert (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)) == handlers  # the CLI gives the handlers back


# --- CLI and vocabularies ---

def test_export_cli_prints_the_path_records_the_owner_and_rejects_bad_usage(repo_a, capsys):
    repo, sha = repo_a
    assert bg.main(["export", "--repo", str(repo), "--commit", sha, "--dest", dest(), "--owner-pid", "1"]) == 0
    cap = capsys.readouterr()
    assert cap.out == dest() + "\n" and cap.err == ""
    assert json.loads((Path(dest()).parent / bg._MARKER_NAME).read_text())["pid"] == 1
    for argv in (["export"], ["export", "--repo", "r", "--commit", sha], ["cleanup", "--root"]):
        assert bg.main(argv) == 2

def test_code_vocabularies_are_pinned():
    assert bg.EXPORT_REFUSAL_CODES == tuple(
        "EXPORT_PATH_REJECTED EXPORT_PATH_COLLISION EXPORT_ENTRY_MODE EXPORT_TOO_LARGE EXPORT_SYMLINK_ESCAPES EXPORT_VERIFY_FAILED".split())
    assert bg.CLEANUP_CODES == tuple(
        "REMOVED ABSENT NOT_UNDER_FIXED_PARENT NOT_A_DIRECTORY NOT_OWNED MARKER_MISSING MARKER_INVALID OWNER_ALIVE ROOT_CHANGED REMOVE_FAILED".split())
    assert bg.ERROR_CODES == tuple(
        """COMMIT_INVALID COMMIT_NOT_FOUND REPO_UNREADABLE DEST_REJECTED GIT_FAILED GIT_TOO_OLD GIT_TIMEOUT GIT_OUTPUT_TOO_LARGE TREE_UNREADABLE
        TREE_TOO_LARGE SEAL_FAILED MARKER_MISSING MARKER_INVALID""".split())
    for vocabulary in (bg.EXPORT_REFUSAL_CODES, bg.CLEANUP_CODES, bg.ERROR_CODES):
        assert len(set(vocabulary)) == len(vocabulary)
        assert all(code.isascii() and code.replace("_", "").isalpha() and bg.escape_diagnostic(code) == code for code in vocabulary)

def test_git_is_never_taken_from_the_working_directory(repo_a, tmp_path, monkeypatch):
    repo, sha = repo_a
    canary = tmp_path / "ran-fake-git"
    fake = tmp_path / "git"
    fake.write_text(f"#!/bin/sh\ntouch {canary}\nexit 1\n")
    fake.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", f".{os.pathsep}{os.pathsep}relative/bin")
    assert bg.export_tree(repo, sha, dest()).is_dir() and not canary.exists()

@pytest.mark.skipif(IS_ROOT, reason="root ignores write bits")
def test_seal_refuses_a_hard_linked_file_and_unseal_leaves_its_mode_alone(tree, tmp_path):
    shared = tmp_path / "shared.txt"
    shared.write_text("s")
    shared.chmod(0o444)
    os.link(shared, tree / "linked.txt")
    with pytest.raises(Err) as info:
        bg.seal_tree(tree)
    assert info.value.code == "SEAL_FAILED" and stat.S_IMODE(shared.stat().st_mode) == 0o444
    bg.unseal_tree(tree)
    assert stat.S_IMODE(shared.stat().st_mode) == 0o444


# --- review round 1: failure path of export, descriptor walk, unbounded cleanup, environment checks ---

def test_a_second_export_to_an_existing_dest_never_touches_it(repo_a, capsys):
    repo, sha = repo_a
    out = bg.export_tree(repo, sha, dest())
    (out / "installed.txt").write_text("written by the install")
    sidecar = Path(dest() + ".export.json")
    kept = sidecar.read_bytes()
    for _ in range(2):  # it used to alternate rc 0 / rc 2 and destroy the tree being installed into
        with pytest.raises(Err) as info:
            bg.export_tree(repo, sha, dest())
        assert info.value.code == "DEST_REJECTED"
        assert bg.main(["export", "--repo", str(repo), "--commit", sha, "--dest", dest()]) == 2
        assert (out / "installed.txt").read_text() == "written by the install" and sidecar.read_bytes() == kept
        assert (out.parent / bg._MARKER_NAME).exists() and capsys.readouterr().out == ""

def test_a_failed_export_removes_only_what_it_created(repo_a):
    repo, sha = repo_a
    first = bg.export_tree(repo, sha, dest("base"))
    stale = Path(dest("head") + f".export.json.{os.getpid()}.tmp")
    stale.write_text("a crashed run")  # a leftover temp file blocks the sidecar write: a clean error, not a traceback
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest("head"))
    assert info.value.code == "DEST_REJECTED" and not Path(dest("head")).exists() and stale.read_text() == "a crashed run"
    assert first.is_dir() and (first.parent / bg._MARKER_NAME).exists() and Path(dest("base") + ".export.json").exists()

def test_two_concurrent_first_exports_into_a_new_root_both_succeed(repo_a):
    repo, sha = repo_a
    for attempt in range(10):
        gate = threading.Barrier(2)

        def run(leaf, attempt=attempt):
            gate.wait()
            return bg.export_tree(repo, sha, dest(leaf, root=f"bench-race{attempt:04d}"))

        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = [future.result() for future in [pool.submit(run, "head"), pool.submit(run, "base")]]
        assert all(path.is_dir() for path in results)

def swap_for_symlink_on_open(monkeypatch, locate, name: str, outside: Path):
    """A hostile process, deterministically: just before the walk opens `name` under `locate()`, swap it for a symlink to
    `outside`. `done` records whether the swap really happened (a vacuous swap must fail the test, not pass it)."""
    real_open, done = os.open, []

    def hooked(path, flags, mode=0o777, *, dir_fd=None):
        if path == name and dir_fd is not None and not done:
            parent = locate()
            mode_before = stat.S_IMODE(parent.stat().st_mode)
            parent.chmod(0o755)  # the attacker runs as us: a sealed parent does not stop it
            os.rename(parent / name, parent / (name + ".moved"))
            os.symlink(outside, parent / name)
            done.append((parent / name).is_symlink())
            parent.chmod(mode_before)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", hooked)
    return done

def outside_tree(base: Path, dir_mode: int, file_mode: int) -> dict:
    (base / "sub").mkdir(parents=True)
    for path in (base / "a.txt", base / "sub/b.txt"):
        path.write_text("outside")
        path.chmod(file_mode)
    (base / "sub").chmod(dir_mode)
    base.chmod(dir_mode)
    return look(base)

@pytest.mark.parametrize("operation", ["seal", "unseal"])
def test_a_directory_swapped_for_a_symlink_mid_walk_is_never_followed(tree, tmp_path, monkeypatch, operation):
    # seal must not strip outside write bits; unseal must not add them (outside starts restrictive)
    writable = operation == "seal"
    outside = tmp_path / "outside"
    snapshot = outside_tree(outside, 0o755 if writable else 0o500, 0o644 if writable else 0o400)
    if operation == "unseal":
        bg.seal_tree(tree)
    done = swap_for_symlink_on_open(monkeypatch, lambda: tree, "d", outside)
    try:
        with pytest.raises(Err):
            (bg.seal_tree if operation == "seal" else bg.unseal_tree)(tree)
    finally:
        monkeypatch.undo()
    assert done == [True] and look(outside) == snapshot
    os.chmod(outside, 0o755)
    os.chmod(outside / "sub", 0o755)

def test_cleanup_removes_a_legal_root_larger_than_the_export_bound(root, repo_a, monkeypatch):
    repo, sha = repo_a
    bg.export_tree(repo, sha, dest("base"))
    bg.seal_tree(root / "head")
    bg.seal_tree(root / "base")
    monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", 5)  # export/hash/seal keep the bound; removal must not apply it
    with pytest.raises(Err):
        bg.seal_tree(root / "base")
    assert bg.cleanup_root(root) == "REMOVED" and not root.exists()

@pytest.mark.skipif(IS_ROOT, reason="root ignores mode bits")
def test_cleanup_removes_a_root_and_subdirectories_with_mode_zero(root):
    (root / "head" / "src" / "locked").mkdir()
    (root / "head" / "src" / "locked" / "f").write_text("x")
    (root / "head" / "src" / "locked").chmod(0)
    root.chmod(0)  # a valid marker inside a mode-0 root: cleanable, not MARKER_MISSING
    assert bg.cleanup_root(root) == "REMOVED" and not root.exists()

def test_cleanup_removes_a_tree_deeper_than_path_max(root, monkeypatch):
    monkeypatch.chdir(root / "head")
    for _ in range(30):  # 30 x 200 characters is far over PATH_MAX; only descriptor-relative calls can reach the bottom
        os.mkdir("d" * 200)
        os.chdir("d" * 200)
    Path("deep.txt").write_text("x")
    monkeypatch.chdir(root.parent)
    assert bg.cleanup_root(root) == "REMOVED" and not root.exists()

def test_old_git_is_an_environment_error_not_a_hostile_tree_verdict(repo_a, monkeypatch, capsys):
    repo, sha = repo_a
    monkeypatch.setattr(bg, "_git_version", (2, 34))
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code == "GIT_TOO_OLD" and "2.43" in info.value.detail and not Path(dest()).parent.exists()
    assert bg.main(["export", "--repo", str(repo), "--commit", sha, "--dest", dest()]) == 2
    assert capsys.readouterr().out == ""

@pytest.mark.parametrize("output, outcome", [
    ("git version 2.43.0", None), ("git version 2.43", None), ("git version 2.100.0", None), ("git version 2.50.1 (Apple Git-155)", None),
    ("git version 2.42.9", "GIT_TOO_OLD"), ("git version 2.9", "GIT_TOO_OLD"), ("git version 1.99.0", "GIT_TOO_OLD"),
    ("garbage", "GIT_FAILED"), ("", "GIT_FAILED"), ("git version two", "GIT_FAILED"), ("x" * 5000, "GIT_OUTPUT_TOO_LARGE"),
])
def test_the_git_version_is_parsed_strictly(monkeypatch, output, outcome):
    real = subprocess.run
    monkeypatch.setattr(bg, "_git_version", None)
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: real(["/bin/echo", "-n", output] if "--version" in argv else argv, **kw))
    if outcome is None:
        bg._require_modern_git()
        return
    with pytest.raises(Err) as info:
        bg._require_modern_git()
    assert info.value.code == outcome

def test_a_hanging_git_is_a_timeout_and_a_chatty_one_is_cut_off(tmp_path, monkeypatch):
    fake = tmp_path / "git"
    fake.write_text("#!/bin/sh\nif [ \"$1\" = -c ]; then shift 6; fi\nif [ \"$1\" = hang ]; then exec sleep 20; fi\nyes x | head -c 5000\n")
    fake.chmod(0o755)
    monkeypatch.setattr(shutil, "which", lambda *a, **k: str(fake))
    env = bg._git_env(str(tmp_path))
    with monkeypatch.context() as scoped, pytest.raises(Err) as info:
        scoped.setattr(bg, "_GIT_TIMEOUT_SECONDS", 1)
        bg._PrivateGit._run_raw(["hang"], env, str(tmp_path))
    assert info.value.code == "GIT_TIMEOUT"
    with pytest.raises(Err) as info:
        bg._PrivateGit._run_raw(["noisy"], env, str(tmp_path), 64)
    assert info.value.code == "GIT_OUTPUT_TOO_LARGE"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(subprocess.SubprocessError("preexec_fn failed")))
    with pytest.raises(Err) as info:
        bg._PrivateGit._run_raw(["x"], env, str(tmp_path), 64)
    assert info.value.code == "GIT_FAILED"

def test_the_output_cap_is_clamped_to_a_lower_hard_limit(tmp_path):
    script = (  # a child whose hard RLIMIT_FSIZE is far below the cap: setrlimit(cap + 1) would raise ValueError
        "import resource, sys, importlib.util\n"
        "spec = importlib.util.spec_from_file_location('bg', sys.argv[1]); bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)\n"
        "resource.setrlimit(resource.RLIMIT_FSIZE, (100000, 100000))\n"
        "code, out = bg._PrivateGit._run_raw(['--version'], bg._git_env(sys.argv[2]), sys.argv[2], 1 << 26)\n"
        "print(code, out.startswith(b'git version'))\n")
    done = subprocess.run([sys.executable, "-c", script, str(_SCRIPTS / "benchmark_gate.py"), str(tmp_path)], capture_output=True, text=True, timeout=120)
    assert (done.returncode, done.stdout.strip()) == (0, "0 True"), done.stderr

@pytest.mark.parametrize("bad", [True, False, 0, -1, 2 ** 31, 1.5, "1", b"1"])
def test_a_bad_owner_pid_is_rejected_before_anything_is_created(root, repo_a, bad):
    before, listing = (root / bg._MARKER_NAME).read_bytes(), sorted(os.listdir(root))
    with pytest.raises(Err) as info:
        bg.export_tree(*repo_a, dest("other"), owner_pid=bad)
    assert info.value.code == "DEST_REJECTED" and not Path(dest("other")).exists()
    assert (root / bg._MARKER_NAME).read_bytes() == before and sorted(os.listdir(root)) == listing

def test_the_fixed_parent_is_per_user_private_and_checked_by_export_and_cleanup(repo_a, root, capsys):
    repo, sha = repo_a
    parent = bg.fixed_parent()
    assert parent.name == f"software-builder-bench-{os.getuid()}" and stat.S_IMODE(parent.stat().st_mode) == 0o700
    assert bg.main(["fixed-parent"]) == 0 and capsys.readouterr().out == f"{parent}\n"
    parent.chmod(0o777)  # another user could now plant entries: both sides refuse, with codes and no traceback
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest("other"))
    assert info.value.code == "DEST_REJECTED" and bg.cleanup_root(root) == "NOT_UNDER_FIXED_PARENT"
    if not IS_ROOT:
        parent.chmod(0)  # lstat of the root then fails with EACCES: a code, not a traceback
        assert bg.cleanup_root(root) == "NOT_A_DIRECTORY"
    parent.chmod(0o700)
    moved = parent.with_name("moved")
    parent.rename(moved)
    parent.symlink_to(moved)  # a symlinked fixed parent is not a directory
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest("other"))
    assert info.value.code == "DEST_REJECTED" and bg.cleanup_root(root) == "NOT_UNDER_FIXED_PARENT"

def test_error_details_are_escaped_where_they_are_built():
    detail = Err("GIT_FAILED", "git x: `rm -rf` | # header\n- item \u00e9 " + "z" * 500).detail
    assert detail == bg.escape_diagnostic(detail) and len(detail) <= 200 and detail.isascii()

def test_a_failed_export_keeps_its_new_root_and_marker_and_leaves_no_partial_state(repo_a, monkeypatch):
    repo, sha = repo_a
    renames, real_rename = [], os.rename  # the root appears by RENAMING a temp directory that already holds the marker
    monkeypatch.setattr(os, "rename", lambda src, dst: (renames.append(os.path.exists(os.path.join(src, bg._MARKER_NAME))), real_rename(src, dst))[1])
    real_verify = bg._verify_export
    monkeypatch.setattr(bg, "_verify_export", lambda *a: (_ for _ in ()).throw(Err("EXPORT_VERIFY_FAILED", "forced")))
    root_dir = Path(dest()).parent
    for _ in range(2):  # the second failure reuses the leaked root: it must stay exportable
        with pytest.raises(Err):
            bg.export_tree(repo, sha, dest())
        assert not Path(dest()).exists() and not Path(dest() + ".export.json").exists() and (root_dir / bg._MARKER_NAME).exists()
    assert renames[0] is True  # (a later export writes its marker into a temp directory too, then loses the rename)
    monkeypatch.setattr(bg, "_verify_export", real_verify)
    assert bg.export_tree(repo, sha, dest("base")).is_dir() and bg.cleanup_root(root_dir) == "OWNER_ALIVE"  # our own pid owns it

def test_a_failing_exporter_never_breaks_a_concurrent_one(repo_a, monkeypatch):
    repo, sha = repo_a
    real = bg._verify_export
    monkeypatch.setattr(bg, "_verify_export", lambda path, entries: (_ for _ in ()).throw(Err("EXPORT_VERIFY_FAILED", "x")) if path.endswith("bad") else real(path, entries))
    for attempt in range(20):
        gate = threading.Barrier(2)

        def run(leaf, attempt=attempt):
            gate.wait()
            return bg.export_tree(repo, sha, dest(leaf, root=f"bench-fail{attempt:04d}"), owner_pid=dead_pid())

        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            bad, good = pool.submit(run, "bad"), pool.submit(run, "good")
            with pytest.raises(Err):
                bad.result()
            assert good.result().is_dir()  # never MARKER_MISSING or FileNotFoundError
        assert bg.cleanup_root(Path(dest()).parent.with_name(f"bench-fail{attempt:04d}")) == "REMOVED"

def test_cleanup_verdict_is_what_is_left_and_a_vanished_root_is_absent(root, monkeypatch):
    real_rmtree, real_open = shutil.rmtree, bg._open_dir
    monkeypatch.setattr(bg, "_open_dir", lambda *a, **k: (_ for _ in ()).throw(OSError(5, "I/O error")))
    assert bg.cleanup_root(root) == "REMOVE_FAILED"  # the repair open failed: not removed, not "absent"
    monkeypatch.setattr(bg, "_open_dir", real_open)
    monkeypatch.setattr(bg, "_open_dir", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    assert bg.cleanup_root(root) == "ABSENT"  # gone between the checks and the repair open
    monkeypatch.setattr(bg, "_open_dir", real_open)
    monkeypatch.setattr(bg, "_read_marker", lambda path: (real_rmtree(path), (_ for _ in ()).throw(Err("MARKER_MISSING")))[1])
    assert bg.cleanup_root(root) == "ABSENT"  # a racing cleanup removed it while the marker was read

def test_unseal_tolerates_an_entry_vanishing_under_it(tree, monkeypatch):
    real = os.stat

    def vanish(path, *args, **kwargs):
        if path == "b.txt" and kwargs.get("dir_fd") is not None and (tree / "b.txt").exists():
            os.unlink(tree / "b.txt")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", vanish)
    bg.unseal_tree(tree)

@pytest.mark.parametrize("planted", ["file", "directory"])
def test_a_failed_export_never_removes_a_sidecar_it_did_not_write(repo_a, monkeypatch, planted):
    repo, sha = repo_a
    sidecar = Path(dest() + ".export.json")

    def plant_then_fail(*args):  # appears after the pre-check, before the failure
        sidecar.mkdir() if planted == "directory" else sidecar.write_text("planted")
        raise Err("EXPORT_VERIFY_FAILED", "forced")

    monkeypatch.setattr(bg, "_verify_export", plant_then_fail)
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code == "EXPORT_VERIFY_FAILED" and not Path(dest()).exists()  # the original error, not an OSError
    assert sidecar.is_dir() if planted == "directory" else sidecar.read_text() == "planted"

@pytest.mark.parametrize("kind", ["file", "directory", "symlink", "dangling", "fifo", "tmp file"])
def test_a_taken_sidecar_path_is_refused_before_any_git_work(repo_a, monkeypatch, tmp_path, kind):
    repo, sha = repo_a
    bg.export_tree(repo, sha, dest("base"))
    planted = Path(dest("head") + (f".export.json.{os.getpid()}.tmp" if kind == "tmp file" else ".export.json"))
    {"file": lambda: planted.write_text("planted"), "tmp file": lambda: planted.write_text("planted"), "directory": planted.mkdir,
     "symlink": lambda: planted.symlink_to(tmp_path), "dangling": lambda: planted.symlink_to(tmp_path / "missing"), "fifo": lambda: os.mkfifo(planted)}[kind]()
    before, calls, real = os.lstat(planted), [], subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or real(*a, **k))
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest("head"))
    assert info.value.code == "DEST_REJECTED" and not calls and not Path(dest("head")).exists()
    assert os.lstat(planted) == before  # byte-identical, nothing replaced

@pytest.mark.parametrize("replaced", ["root", "fixed parent"])
def test_a_root_replaced_while_exporting_is_refused(repo_a, monkeypatch, replaced):
    repo, sha = repo_a
    real = bg._verify_export

    def swap(path, entries):
        result = real(path, entries)
        target = Path(path).parent if replaced == "root" else bg.fixed_parent()
        target.rename(target.with_name("moved-away"))
        target.mkdir() if replaced == "root" else target.symlink_to(target.with_name("moved-away"))  # a same-uid process redirects it
        return result

    monkeypatch.setattr(bg, "_verify_export", swap)
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code == "DEST_REJECTED"
    if replaced == "root":
        assert not list(Path(dest()).parent.iterdir())
    assert not Path(dest() + ".export.json").exists()  # nothing was written into the replacement

def test_the_fixed_parent_failures_are_coded_and_a_bad_dest_creates_nothing(repo_a, tmp_path):
    repo, sha = repo_a
    with pytest.raises(Err) as info:  # outside the fixed parent: refused before the parent is created
        bg.export_tree(repo, sha, str(tmp_path / "elsewhere" / "bench-aaaaaaaa" / "head"))
    assert info.value.code == "DEST_REJECTED" and not bg.fixed_parent().exists()
    temp = bg.fixed_parent().parent
    temp.chmod(0o500)  # the parent cannot be created: a code, not a traceback
    try:
        if not IS_ROOT:
            with pytest.raises(Err) as info:
                bg.export_tree(repo, sha, dest())
            assert info.value.code == "DEST_REJECTED"
    finally:
        temp.chmod(0o700)
    for mode in (0o770, 0o707):
        bg.fixed_parent().mkdir(mode=0o700, exist_ok=True)
        bg.fixed_parent().chmod(mode)
        with pytest.raises(Err) as info:
            bg.export_tree(repo, sha, dest())
        assert info.value.code == "DEST_REJECTED"
    bg.fixed_parent().chmod(0o700)
    (bg.fixed_parent() / "bench-aaaaaaaa").mkdir()
    (bg.fixed_parent() / "bench-aaaaaaaa" / bg._MARKER_NAME).symlink_to(tmp_path)  # a marker that is a symlink is not a marker
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code in ("MARKER_INVALID", "MARKER_MISSING")


GOOD_LISTING = {"a": ("F", 1, False), "b": ("F", 1, False), "d": ("G", 0, False)}

@pytest.mark.parametrize("change", [{}, {"c": ("F", 1, False)}, {"d": None}, {"a": ("L", 1, False)}, {"a": ("F", 1, True)}, {"a": ("F", 2, False)}])
def test_verification_demands_the_written_tree_equal_the_listing(tmp_path, change):
    written = tmp_path / "written"
    written.mkdir()
    (written / "a").write_text("1")
    (written / "b").write_text("1")
    (written / "d").mkdir()  # a gitlink: an empty directory
    for name in ("a", "b"):
        os.chmod(written / name, 0o644)
    listing = {k: v for k, v in {**GOOD_LISTING, **change}.items() if v is not None}
    if not change:
        assert bg._verify_export(str(written), listing) == []
        return
    with pytest.raises(Err) as info:  # missing entry, unexpected directory, type mismatch, executable bit, size
        bg._verify_export(str(written), listing)
    assert info.value.code == "EXPORT_VERIFY_FAILED"

def test_a_file_vanishing_during_removal_is_not_an_error(root, monkeypatch):
    real = shutil.rmtree
    monkeypatch.setattr(shutil, "rmtree", lambda path, onexc, **kw: (onexc(os.unlink, path, FileNotFoundError()), real(path, onexc=onexc, **kw))[1])
    assert bg.cleanup_root(root) == "REMOVED"

@pytest.mark.skipif(IS_ROOT, reason="root can open a mode-0 directory, so there is nothing to repair")
@pytest.mark.parametrize("exchange", ["directory", "symlink"])
def test_a_repair_never_chmods_anything_but_the_verified_directory(tree, tmp_path, monkeypatch, exchange):
    outside = tmp_path / "outside"
    outside.mkdir()
    outside.chmod(0o300)
    (tree / "d").chmod(0)
    real = bg._chmod_dir_nofollow

    def exchanged(parent_fd, name, st):  # between the failed open and the chmod
        os.rename(tree / "d", tree / "d.moved")
        os.rename(outside, tree / "d") if exchange == "directory" else os.symlink(outside, tree / "d")
        return real(parent_fd, name, st)

    monkeypatch.setattr(bg, "_chmod_dir_nofollow", exchanged)
    with pytest.raises(Err):
        bg.unseal_tree(tree)
    monkeypatch.setattr(bg, "_chmod_dir_nofollow", real)
    assert stat.S_IMODE(((tree / "d") if exchange == "directory" else outside).stat().st_mode) == 0o300
    for path in (outside, tree / "d", tree / "d.moved"):
        if path.exists():
            os.chmod(path, 0o755)

def test_a_file_swapped_for_a_symlink_mid_walk_is_never_chmodded(tree, tmp_path, monkeypatch):
    outside = tmp_path / "outside.txt"
    outside.write_text("o")
    outside.chmod(0o644)
    done = swap_for_symlink_on_open(monkeypatch, lambda: tree, "b.txt", outside)
    with pytest.raises(Err):
        bg.seal_tree(tree)
    assert done == [True] and stat.S_IMODE(outside.stat().st_mode) == 0o644

@pytest.mark.skipif(not os.path.isdir("/dev/fd"), reason="needs /dev/fd to count descriptors")
def test_no_descriptor_leaks_when_a_listing_fails(tree, monkeypatch):
    real, state = os.listdir, {"n": 0}

    def failing(arg=".", *rest):
        if isinstance(arg, int):
            state["n"] += 1
            if state["n"] == 2:  # the second directory: its descriptor is open and not yet in a frame
                raise OSError(5, "I/O error")
        return real(arg, *rest)

    def small_root(index):
        small = bg._check_parent(create=True) / f"bench-leak{index:04d}"
        (small / "sub").mkdir(parents=True)
        write_marker(small)
        return small

    before = len(real("/dev/fd"))
    monkeypatch.setattr(os, "listdir", failing)
    for index in range(20):
        for operation in (bg.seal_tree, bg.unseal_tree):
            state["n"] = 0
            with pytest.raises(Err):
                operation(tree)
        state["n"] = 0
        assert bg.cleanup_root(small_root(index)) == "REMOVED"
    monkeypatch.setattr(os, "listdir", real)
    assert len(real("/dev/fd")) == before

@pytest.mark.parametrize("what", ["root", "parent"])
def test_cleanup_refuses_when_the_root_or_its_parent_is_replaced_before_the_claim(root, monkeypatch, what):
    real = bg._pid_alive  # the last step before the claiming rename

    def replace(pid):
        target = root if what == "root" else root.parent
        target.rename(target.with_name("moved-away"))
        target.mkdir() if what == "root" else target.symlink_to(target.with_name("moved-away"))
        return real(pid)

    monkeypatch.setattr(bg, "_pid_alive", replace)
    assert bg.cleanup_root(root) == "ROOT_CHANGED"  # the root EXISTS with another identity (never ABSENT)
    assert root.exists()  # the replacement was not removed (for the parent: the symlink leads to the untouched root)

def test_an_oserror_while_resolving_the_path_is_a_code_not_a_traceback(root, monkeypatch):
    monkeypatch.setattr(os.path, "realpath", lambda *a, **k: (_ for _ in ()).throw(OSError(22, "Invalid argument")))
    assert bg.cleanup_root(root) == "NOT_UNDER_FIXED_PARENT"

@pytest.mark.skipif(IS_ROOT, reason="root ignores mode bits")
def test_a_refused_cleanup_may_leave_a_restricted_root_at_0700(root):
    write_marker(root, pid=os.getpid())  # repair-then-read: a mode-0 root hides its own marker, so the mode is fixed first
    root.chmod(0o500)
    assert bg.cleanup_root(root) == "OWNER_ALIVE" and stat.S_IMODE(root.stat().st_mode) == 0o700


# --- review round 2 on #340: overlapping cleanups, retryable removal, swapped roots ---

@pytest.mark.parametrize("hook", ["_read_marker", "_pid_alive", "unseal_tree"])
def test_a_cleanup_that_loses_to_another_one_at_any_point_reports_absent_or_removed(root, monkeypatch, hook):
    real, state = getattr(bg, hook), {"busy": False, "nested": None}

    def another_cleanup_completes_here(*args, **kwargs):
        if not state["busy"]:
            state["busy"] = True
            state["nested"] = bg.cleanup_root(root)
        return real(*args, **kwargs)

    monkeypatch.setattr(bg, hook, another_cleanup_completes_here)
    assert bg.cleanup_root(root) in ("ABSENT", "REMOVED") and state["nested"] in ("ABSENT", "REMOVED") and not root.exists()


@pytest.mark.filterwarnings("ignore:.*fork.*:DeprecationWarning")
def test_racing_cleanups_in_processes_report_exactly_one_removed_and_the_rest_absent():
    ctx, parent, owner = multiprocessing.get_context("fork"), bg._check_parent(create=True), dead_pid()
    seen = collections.Counter()
    for index in range(100):
        small = parent / f"bench-race{index:05d}"
        (small / "head/pkg").mkdir(parents=True)
        bg._write_marker(str(small), owner)
        for number in range(5):
            (small / f"head/pkg/f{number}.py").write_text("x")
        gate, queue = ctx.Barrier(8), ctx.Queue()

        def run(small=small, gate=gate, queue=queue):
            gate.wait(60)
            queue.put(bg.cleanup_root(small))

        procs = [ctx.Process(target=run) for _ in range(8)]
        for proc in procs:
            proc.start()
        try:
            results = [queue.get(timeout=120) for _ in procs]
        finally:  # a child that never started must fail the test, not hang it
            for proc in procs:
                proc.join(timeout=60)
                proc.kill()
        seen.update(results)
        assert set(results) <= {"REMOVED", "ABSENT"} and results.count("REMOVED") == 1 and not small.exists(), results
    assert seen["REMOVED"] == 100


@pytest.mark.skipif(IS_ROOT, reason="root deletes a sealed tree without unsealing it")
def test_an_unseal_that_stops_early_leaves_a_retryable_root(root, monkeypatch):
    bg.seal_tree(root / "head")
    real = bg.unseal_tree
    monkeypatch.setattr(bg, "unseal_tree", lambda *a, **k: (_ for _ in ()).throw(Err("TREE_UNREADABLE", "descriptor limit")))
    assert bg.cleanup_root(root) == "REMOVE_FAILED" and (root / bg._MARKER_NAME).exists()
    monkeypatch.setattr(bg, "unseal_tree", real)
    assert bg.cleanup_root(root) == "REMOVED"


@pytest.mark.parametrize("mode, kind", [(0o500, "directory"), (0o300, "directory"), (0o000, "directory"), (0o500, "symlink")])
def test_a_root_swapped_for_another_real_directory_is_refused_before_anything_is_chmodded(root, monkeypatch, mode, kind):
    other = root.parent / "other-directory"  # same parent: renaming a directory across parents needs write on it
    other.mkdir()
    (other / "secret.txt").write_text("s")
    other.chmod(mode)
    real = bg._checked_root

    def swapped(arg):
        result = real(arg)
        root.rename(root.with_name("moved-root"))
        other.rename(root) if kind == "directory" else root.symlink_to(other)
        return result

    monkeypatch.setattr(bg, "_checked_root", swapped)
    assert bg.cleanup_root(root) == "ROOT_CHANGED"
    assert stat.S_IMODE(other.stat().st_mode if kind == "symlink" else root.stat().st_mode) == mode  # untouched
    other.chmod(0o755) if kind == "symlink" else root.chmod(0o755)


@pytest.mark.parametrize("kind", ["directory", "file"])
@pytest.mark.parametrize("operation", ["seal", "unseal"])
def test_a_fifo_swapped_in_is_neither_waited_for_nor_chmodded(kind, operation, tmp_path):
    child = (
        "import importlib.util, os, stat, sys, tempfile\n"
        "spec = importlib.util.spec_from_file_location('bg', sys.argv[1]); bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)\n"
        "tree = os.path.join(tempfile.mkdtemp(dir=sys.argv[4]), 't'); os.makedirs(os.path.join(tree, 'd')); open(os.path.join(tree, 'f'), 'w').close()\n"
        "victim = 'd' if sys.argv[2] == 'directory' else 'f'\n"
        "real_open, done = os.open, []\n"
        "def hooked(path, flags, mode=0o777, *, dir_fd=None):\n"
        "    if path == victim and dir_fd is not None and not done:\n"
        "        done.append(1); os.chmod(tree, 0o755); os.rename(os.path.join(tree, victim), os.path.join(tree, victim + '.moved')); os.mkfifo(os.path.join(tree, victim), 0o600)\n"
        "    return real_open(path, flags, mode, dir_fd=dir_fd)\n"
        "os.open = hooked\n"
        "try:\n"
        "    (bg.seal_tree if sys.argv[3] == 'seal' else bg.unseal_tree)(tree)\n"
        "except bg.BenchmarkGateError:\n"
        "    pass\n"
        "print(done, oct(stat.S_IMODE(os.lstat(os.path.join(tree, victim)).st_mode)))\n")
    # a hard timeout: if O_NONBLOCK / O_DIRECTORY were dropped the open would block on the FIFO and the test FAILS instead of hanging
    done = subprocess.run([sys.executable, "-c", child, str(_SCRIPTS / "benchmark_gate.py"), kind, operation, str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert (done.returncode, done.stdout.strip()) == (0, "[1] 0o600"), done.stderr


@pytest.mark.skipif(IS_ROOT, reason="root can open a mode-0 directory, so there is nothing to repair")
def test_a_swap_between_the_identity_check_and_the_chmod_never_touches_the_swapped_in_object(tree, tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    outside.chmod(0o300)
    (tree / "d").chmod(0)
    real, done = os.chmod, []

    def hooked(path, mode, *args, **kwargs):  # the repair's own chmod: by descriptor-relative name (macOS) or /proc/self/fd (Linux)
        if (kwargs.get("dir_fd") is not None or str(path).startswith("/proc/self/fd/")) and not done:
            os.rename(tree / "d", tree / "d.moved")
            os.symlink(outside, tree / "d")
            done.append((tree / "d").is_symlink())
        return real(path, mode, *args, **kwargs)

    follows = real in os.supports_follow_symlinks  # the repair picks its branch by this membership: keep it
    monkeypatch.setattr(os, "chmod", hooked)
    if follows:
        os.supports_follow_symlinks.add(hooked)
    try:
        bg.unseal_tree(tree)
    except Err:
        pass
    finally:
        os.supports_follow_symlinks.discard(hooked)
    assert done == [True] and stat.S_IMODE(outside.stat().st_mode) == 0o300
    real(outside, 0o755)
    real(tree / "d.moved", 0o755)


def test_the_entry_bound_is_exact(tree, monkeypatch):
    entries = len(list(bg._walk_tree(str(tree))))
    for operation in (lambda: list(bg._walk_tree(str(tree))), lambda: bg.seal_tree(tree), lambda: bg.unseal_tree(tree)):
        monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", entries)
        operation()
        monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", entries - 1)
        with pytest.raises(Err) as info:
            operation()
        assert info.value.code == "TREE_TOO_LARGE"
    monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", 1)
    bg.unseal_tree(tree, bounded=False)  # removal is never bound


@pytest.mark.skipif(not os.path.isdir("/dev/fd"), reason="needs /dev/fd to count descriptors")
def test_no_descriptor_leaks_after_a_successful_walk_or_a_failed_fstat(tmp_path, monkeypatch):
    big = tmp_path / "big"
    for index in range(40):
        (big / f"s{index}").mkdir(parents=True)
    before = len(os.listdir("/dev/fd"))
    for _ in range(5):
        bg.seal_tree(big)
        bg.unseal_tree(big)
    assert len(os.listdir("/dev/fd")) == before
    real, calls = os.fstat, {"n": 0}

    def failing(fd):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError(5, "I/O error")
        return real(fd)

    monkeypatch.setattr(os, "fstat", failing)
    for _ in range(10):
        calls["n"] = 0
        with pytest.raises(Err):
            bg.unseal_tree(big)
    monkeypatch.setattr(os, "fstat", real)
    assert len(os.listdir("/dev/fd")) == before


@pytest.mark.parametrize("code", bg.CLEANUP_CODES)
def test_the_cleanup_cli_maps_every_code_to_an_exit_status(code, monkeypatch, capsys):
    monkeypatch.setattr(bg, "cleanup_root", lambda root: code)
    assert bg.main(["cleanup", "--root", "x"]) == (0 if code in ("REMOVED", "ABSENT") else 1)
    assert capsys.readouterr().out == code + "\n"


def test_a_symlinked_marker_is_not_a_marker_and_a_foreign_root_is_not_ours(root, tmp_path, monkeypatch):
    real_marker = tmp_path / "marker.json"
    real_marker.write_text((root / bg._MARKER_NAME).read_text())
    (root / bg._MARKER_NAME).unlink()
    (root / bg._MARKER_NAME).symlink_to(real_marker)
    assert bg.cleanup_root(root) == "MARKER_MISSING" and root.exists()
    inode, real = root.stat().st_ino, bg._foreign
    monkeypatch.setattr(bg, "_foreign", lambda st: st.st_ino == inode or real(st))
    assert bg.cleanup_root(root) == "NOT_OWNED" and root.exists()


def test_cleanup_edge_paths_and_a_symlink_root_for_seal(root, tree, tmp_path, monkeypatch):
    short = bg.fixed_parent() / "bench-a"  # 7 characters: too short to be a root name, even with a marker
    short.mkdir()
    write_marker(short)
    assert bg.cleanup_root(short) == "NOT_UNDER_FIXED_PARENT" and short.exists()
    via = tmp_path / "viatmp"
    via.symlink_to(tmp_path / "tmp")
    monkeypatch.setattr(tempfile, "tempdir", str(via))  # a symlinked TMPDIR spelling (macOS /var -> /private/var)
    assert bg.cleanup_root(via / bg.fixed_parent().name / root.name) == "REMOVED"
    shutil.rmtree(tmp_path / "tmp" / bg.fixed_parent().name)
    assert bg.cleanup_root(root) == "ABSENT"  # no fixed parent at all
    with pytest.raises(Err) as info:
        bg.seal_tree(tree / "link")
    assert info.value.code == "TREE_UNREADABLE"


def test_seal_and_unseal_change_only_the_write_bits(tmp_path):
    base = tmp_path / "m"
    base.mkdir()
    for name, mode in (("a", 0o640), ("b", 0o444), ("c", 0o600)):
        (base / name).write_text("x")
        (base / name).chmod(mode)
    modes = lambda: {n: stat.S_IMODE((base / n).stat().st_mode) for n in "abc"}  # noqa: E731
    bg.seal_tree(base)
    assert modes() == {"a": 0o440, "b": 0o444, "c": 0o400}  # no read bit widened
    bg.unseal_tree(base)
    assert modes() == {"a": 0o640, "b": 0o644, "c": 0o600}  # owner write only, never group or other


# --- the #336 follow-ups that live in 1a code ---

def test_an_empty_markerless_directory_is_never_replaced_by_a_root(repo_a):
    empty = bg._check_parent(create=True) / "bench-aaaaaaaa"
    empty.mkdir()
    inode = empty.stat().st_ino
    with pytest.raises(Err) as info:
        bg.export_tree(*repo_a, dest())
    assert info.value.code == "MARKER_MISSING" and empty.stat().st_ino == inode and not list(empty.iterdir())


def test_a_restrictive_umask_does_not_poison_the_fixed_parent(repo_a):
    old = os.umask(0o577)  # hides every bit from the owner: nothing may depend on the caller's umask
    try:
        assert bg.export_tree(*repo_a, dest("first")).is_dir()
    finally:
        os.umask(old)
    assert stat.S_IMODE(bg.fixed_parent().stat().st_mode) == 0o700 and stat.S_IMODE((Path(dest()).parent / bg._MARKER_NAME).stat().st_mode) == 0o600
    assert not list(Path(tempfile.tempdir).glob("bench-git-*"))  # the private git directory was removable too
    assert bg.export_tree(*repo_a, dest("second")).is_dir()


def test_the_fixed_parent_is_absolute_even_for_a_relative_tmpdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tempfile, "tempdir", "reltmp")
    assert bg.fixed_parent() == Path(os.getcwd()) / "reltmp" / bg.fixed_parent().name


def test_foreign_owners_and_root_name_boundaries_are_refused(repo_a, monkeypatch):
    real = bg._foreign
    monkeypatch.setattr(bg, "_foreign", lambda st: True)
    with pytest.raises(Err) as info:
        bg.export_tree(*repo_a, dest())
    assert info.value.code == "DEST_REJECTED"  # a fixed parent owned by someone else
    monkeypatch.setattr(bg, "_foreign", real)
    for bad_root, bad_leaf in (("bench-a", "head"), ("a" * 65, "head"), ("bench.abc", "head"), ("bench abc", "head"), ("bench-abcd\n", "head"),
                               ("bench-abcd", "head.export.json"), ("bench-abcd", "he ad"), ("bench-abcd", "head\n")):
        with pytest.raises(Err) as info:
            bg.export_tree(*repo_a, dest(bad_leaf, bad_root))
        assert info.value.code == "DEST_REJECTED", (bad_root, bad_leaf)
    assert bg.export_tree(*repo_a, dest("h", "a" * 8)).is_dir() and bg.export_tree(*repo_a, dest("h", "a" * 64)).is_dir()  # the boundaries


def test_unusual_repositories_and_names_are_coded_refusals(repo_a, tmp_path, capsys):
    bogus = tmp_path / "bogus"
    bogus.mkdir()
    (bogus / ".git").write_text("not a gitdir file")
    for repo in (make_repo(tmp_path, name="re:po"), bogus):
        with pytest.raises(Err) as info:
            bg.export_tree(repo, "a" * 40, dest())
        assert info.value.code == "REPO_UNREADABLE"
    repo = make_repo(tmp_path, name="long")
    sha = hostile_commit(repo, [f"100644 blob {blob(repo)}\t{'a' * 300}"])  # longer than NAME_MAX
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code == "GIT_FAILED"  # an environment failure, not a hostile-tree verdict
    assert bg.main(["export", "--repo", str(repo), "--commit", sha, "--dest", dest("other")]) == 2 and capsys.readouterr().out == ""


def test_the_cli_reports_an_unexpected_oserror_as_a_usage_error(repo_a, monkeypatch, capsys):
    monkeypatch.setattr(bg, "_export", lambda *a: (_ for _ in ()).throw(OSError(5, "I/O error")))
    assert bg.main(["export", "--repo", str(repo_a[0]), "--commit", repo_a[1], "--dest", dest()]) == 2 and capsys.readouterr().out == ""


def test_what_the_claiming_rename_moved_must_be_what_was_validated(root, monkeypatch):
    other = root.parent / "other-directory"
    other.mkdir()
    (other / "secret.txt").write_text("s")
    real = os.rename

    def swapped_then_renamed(src, dst, **kw):
        if src == root.name and ".gone-" in str(dst):  # the swap lands exactly between the identity check and the rename
            real(root, root.with_name("moved-root"))
            real(other, root)
        return real(src, dst, **kw)

    monkeypatch.setattr(os, "rename", swapped_then_renamed)
    assert bg.cleanup_root(root) == "ROOT_CHANGED"
    monkeypatch.setattr(os, "rename", real)
    assert (root / "secret.txt").read_text() == "s" and not list(root.parent.glob(".gone-*"))  # moved back, untouched


def test_the_removal_helper_and_the_root_creation_helper_report_their_failures_as_codes(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    parent = bg._check_parent(create=True)
    real_lstat = os.lstat
    monkeypatch.setattr(os, "lstat", lambda path, *a, **k: (_ for _ in ()).throw(FileNotFoundError()) if str(path) == str(parent) else real_lstat(path, *a, **k))
    with pytest.raises(Err) as info:  # `ABSENT` is a cleanup verdict, never an export error
        bg._check_parent(create=True)
    assert info.value.code == "DEST_REJECTED"
    monkeypatch.setattr(os, "lstat", real_lstat)
    real_mkdtemp = tempfile.mkdtemp
    monkeypatch.setattr(tempfile, "mkdtemp", lambda **kw: (_ for _ in ()).throw(PermissionError(13, "denied")) if kw.get("prefix") == ".new-" else real_mkdtemp(**kw))
    with pytest.raises(Err) as info:
        bg._create_root(str(parent), "bench-aaaaaaaa", 1)
    assert info.value.code == "DEST_REJECTED"
    monkeypatch.setattr(tempfile, "mkdtemp", real_mkdtemp)
    monkeypatch.setattr(bg, "_write_marker", lambda *a: (_ for _ in ()).throw(PermissionError(13, "denied")))
    with pytest.raises(Err) as info:
        bg._create_root(str(parent), "bench-aaaaaaaa", 1)
    assert info.value.code == "DEST_REJECTED" and not list(parent.glob(".new-*"))


def test_an_export_under_a_symlinked_tmpdir_and_a_foreign_root_are_handled(repo_a, tmp_path, monkeypatch):
    via = tmp_path / "viatmp"
    via.symlink_to(tmp_path / "tmp")
    monkeypatch.setattr(tempfile, "tempdir", str(via))
    out = bg.export_tree(*repo_a, dest("one"))  # dest spelled through the symlink
    assert str(out).startswith(str((tmp_path / "tmp").resolve())) and out.is_dir()  # the resolved spelling comes back
    assert bg.export_tree(*repo_a, str(out.parent.parent / out.parent.name / "two")).is_dir()  # and the real spelling works too
    inode, real = out.parent.stat().st_ino, bg._foreign
    monkeypatch.setattr(bg, "_foreign", lambda st: st.st_ino == inode or real(st))
    with pytest.raises(Err) as info:
        bg.export_tree(*repo_a, dest("three"))
    assert info.value.code == "DEST_REJECTED"  # an existing root that someone else owns


# --- review round 2 on #340 (gen 2): the claimed directory is handled by descriptor; an interrupted cleanup is recoverable ---

def claimed(parent: Path) -> list[Path]:
    return [p for p in parent.iterdir() if p.name.startswith(".gone-") and not p.name.endswith(".aside")]

def look(base: Path) -> dict:
    return {str(p): (stat.S_IMODE(p.stat().st_mode), None if p.is_dir() else p.read_text()) for p in [base, *base.rglob("*")]}

@pytest.mark.parametrize("kind", ["symlink", "directory"])
@pytest.mark.parametrize("point", ["before the unseal", "between the unseal and the removal", "during the removal"])
def test_a_claimed_directory_renamed_aside_and_replaced_never_steers_a_delete_or_a_chmod(root, tmp_path, monkeypatch, point, kind):
    outside, done = tmp_path / "outside", []
    before = outside_tree(outside, 0o755, 0o444)  # WRITABLE directories: a delete that followed the link succeeds; read-only files: an unseal would chmod them

    def attack():
        held = claimed(root.parent)[0]
        held.rename(held.with_name(held.name + ".aside"))
        held.symlink_to(outside) if kind == "symlink" else outside.rename(held)
        done.append(held.is_symlink() == (kind == "symlink"))

    owner, attr = {"before the unseal": (bg, "unseal_tree"), "between the unseal and the removal": (bg, "_remove_contents"), "during the removal": (shutil, "rmtree")}[point]
    real = getattr(owner, attr)
    monkeypatch.setattr(owner, attr, lambda *a, **k: (None if done else attack(), real(*a, **k))[1])
    assert bg.cleanup_root(root) == "ROOT_CHANGED" and done == [True]
    assert sorted(map(repr, look(claimed(root.parent)[0]).values())) == sorted(map(repr, before.values()))  # whatever sits at the claimed name is untouched

@pytest.mark.parametrize("case", ["after the marker is deleted", "after every pass", "after the first pass", "ENOENT on a listed entry"])
def test_a_late_entry_never_leaves_a_root_without_its_marker(root, monkeypatch, case):
    real_unlink, real_stat, real_remove = os.unlink, os.stat, bg._remove_contents

    def late():
        (claimed(root.parent)[0] / f"late{time.monotonic_ns()}").write_text("x")

    with monkeypatch.context() as hook:
        if case == "after the marker is deleted":
            hook.setattr(os, "unlink", lambda path, **kw: (real_unlink(path, **kw), late() if path == bg._MARKER_NAME else None)[0])
        elif case in ("after every pass", "after the first pass"):
            passes = []
            hook.setattr(bg, "_remove_contents", lambda cfd: (real_remove(cfd), late() if case == "after every pass" or not passes else None, passes.append(1))[0])
        else:
            hook.setattr(os, "stat", lambda path, **kw: (_ for _ in ()).throw(FileNotFoundError()) if path == "head" and "dir_fd" in kw else real_stat(path, **kw))
        expected = "REMOVED" if case == "after the first pass" else "REMOVE_FAILED"  # a transient late writer is removed by the next pass
        assert bg.cleanup_root(root) == expected
        if expected == "REMOVED":
            return
        assert bg._read_marker(str(root))["root"] == root.name  # the retry finds a valid marker, never MARKER_MISSING
    assert bg.cleanup_root(root) == "REMOVED" and not claimed(root.parent)

@pytest.mark.parametrize("rewrite, code", [(lambda r: write_marker(r, pid=os.getpid()), "OWNER_ALIVE"), (lambda r: (r / bg._MARKER_NAME).write_text("{"), "MARKER_INVALID")])
def test_a_marker_rewritten_between_the_pid_check_and_the_claim_is_honoured_and_the_root_put_back(root, monkeypatch, rewrite, code):
    real, done = bg._pid_alive, []

    def rewritten_after_the_check(pid):  # `claim_root` re-points the marker right here
        alive = real(pid)
        if not done:
            done.append(1)
            rewrite(root)
        return alive

    monkeypatch.setattr(bg, "_pid_alive", rewritten_after_the_check)
    assert bg.cleanup_root(root) == code and done and (root / "head").is_dir() and (root / bg._MARKER_NAME).exists() and not claimed(root.parent)

def test_a_restricted_chain_deeper_than_the_default_descriptor_limit_is_removed_in_one_call(root):
    resource = pytest.importorskip("resource")
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    fd = os.open(root / "head", os.O_RDONLY)
    for level in range(600):  # 600 levels, each unlistable or read-only, far below PATH_MAX: descriptors only
        os.mkdir("d", dir_fd=fd)
        child = os.open("d", os.O_RDONLY, dir_fd=fd)
        os.fchmod(fd, 0o500 if level % 2 else 0)
        os.close(fd)
        fd = child
    os.close(fd)
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, hard))
    try:
        assert bg.cleanup_root(root) == "REMOVED" and not root.exists()
        assert resource.getrlimit(resource.RLIMIT_NOFILE) == (256, hard)  # given back
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))

@pytest.mark.parametrize("case", ["claiming rename", "top-level entry", "marker unlink", "final rmdir"])
def test_every_failure_of_a_claimed_removal_is_a_coded_failure_with_the_root_retryable(root, monkeypatch, capsys, case):
    (root / "stubborn.txt").write_text("x")
    attr, hit, number = {
        "claiming rename": ("rename", lambda a, b: ".gone-" in b, 18), "top-level entry": ("unlink", lambda a, b: a == "stubborn.txt", 1),
        "marker unlink": ("unlink", lambda a, b: a == bg._MARKER_NAME, 5), "final rmdir": ("rmdir", lambda a, b: ".gone-" in a, 16)}[case]
    original = getattr(os, attr)

    def broken(path, *rest, **kw):
        if hit(path, rest[0] if rest else ""):
            raise OSError(number, "injected")
        return original(path, *rest, **kw)

    monkeypatch.setattr(os, attr, broken)
    assert bg.main(["cleanup", "--root", str(root)]) == 1
    out, err = capsys.readouterr()
    assert out == "REMOVE_FAILED\n" and err.startswith("REMOVE_FAILED: ") and "no detail" not in err and (case != "top-level entry" or "stubborn.txt" in err)  # the code on stdout, the reason (and the first name) on stderr
    monkeypatch.setattr(os, attr, original)
    assert root.exists() and (root / bg._MARKER_NAME).exists()  # marker and all: a failing final step loses nothing
    assert bg.cleanup_root(root) == "REMOVED" and not root.exists() and not claimed(root.parent)

def test_a_root_swapped_for_a_regular_file_is_refused(root, monkeypatch):
    real = bg._checked_root

    def swapped(arg):
        result = real(arg)
        root.rename(root.with_name("moved-root"))
        root.write_text("file")
        return result

    monkeypatch.setattr(bg, "_checked_root", swapped)
    assert bg.cleanup_root(root) == "ROOT_CHANGED" and root.read_text() == "file"

def test_the_claim_name_carries_64_random_bits(root, monkeypatch):
    names, real, other = [], os.rename, root.with_name("bench-second01")
    other.mkdir()
    write_marker(other)
    monkeypatch.setattr(os, "rename", lambda src, dst, **kw: (names.append(dst), real(src, dst, **kw))[1])
    assert bg.cleanup_root(root) == bg.cleanup_root(other) == "REMOVED"
    assert len(names) == 2 and all(re.fullmatch(r"\.gone-bench-[a-z0-9]+-[0-9a-f]{16}", name) for name in names) and names[0][-16:] != names[1][-16:]

def test_a_keyboard_interrupt_before_or_after_any_os_call_leaves_nothing_or_a_retryable_root(monkeypatch):
    names = ["open", "close", "rename", "unlink", "rmdir", "listdir", "stat", "lstat", "fstat", "fchmod", "chmod", "mkdir"]
    real, state, parent, owner = {n: getattr(os, n) for n in names}, {"on": False, "n": 0, "at": 0, "after": False}, bg._check_parent(create=True), dead_pid()

    def wrap(name):
        def hooked(*a, **k):
            state["n"] += state["on"]
            hit = state["on"] and state["n"] == state["at"]
            if hit and not state["after"]:
                raise KeyboardInterrupt
            result = real[name](*a, **k)
            if hit:
                raise KeyboardInterrupt
            return result
        return hooked

    def fresh():
        victim = parent / "bench-inject1"
        (victim / "head/pkg").mkdir(parents=True)
        bg._write_marker(str(victim), owner)
        (victim / "head/pkg/f").write_text("x")
        return victim

    for name in names:
        hooked = wrap(name)
        for supported in (os.supports_follow_symlinks, os.supports_dir_fd, os.supports_fd):
            if real[name] in supported:
                supported.add(hooked)
        monkeypatch.setattr(os, name, hooked)
    calls = 0
    for after, at in [(False, 0)] + [(a, i) for a in (False, True) for i in range(1, 400)]:
        victim = fresh()
        state.update(on=True, n=0, at=at, after=after)
        old = os.umask(0o577)  # a marker written back must not depend on the umask
        try:
            result = bg.cleanup_root(victim)
        except KeyboardInterrupt:
            result = None
        finally:
            os.umask(old)
            state["on"] = False
        calls = calls or state["n"]
        assert calls > 60  # the dry run saw a realistic number of calls
        if at > calls:
            bg.cleanup_root(victim)
            continue  # past the last call: nothing was injected
        assert (result is None) == (at > 0), (after, at, result)  # an interrupt is never swallowed, and only one was injected
        assert not claimed(parent) and (not victim.exists() or bg._read_marker(str(victim))["root"] == victim.name), (after, at)
        assert bg.cleanup_root(victim) in ("REMOVED", "ABSENT") and not victim.exists() and not claimed(parent), (after, at)  # the retry

@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
@pytest.mark.parametrize("point", ["right after the claiming rename", "after the claimed open's chmod", "after the marker was deleted, with a late entry"])
def test_a_real_signal_in_a_short_window_puts_the_tree_back_and_the_cli_exits_1_with_empty_stdout(root, monkeypatch, capsys, sig, point):
    real, fired = {"rename": os.rename, "fchmod": os.fchmod, "unlink": os.unlink}, []

    def after(name, when):
        def hooked(*a, **k):
            result = real[name](*a, **k)
            if not fired and when(*a):
                fired.append(1)
                os.kill(os.getpid(), sig)
            return result
        return hooked

    name, when = {"right after the claiming rename": ("rename", lambda src, dst: ".gone-" in dst), "after the claimed open's chmod": ("fchmod", lambda fd, mode: bool(claimed(root.parent))),
                  "after the marker was deleted, with a late entry": ("unlink", lambda path: path == bg._MARKER_NAME and [(claimed(root.parent)[0] / "late.txt").write_text("x")])}[point]
    monkeypatch.setattr(os, name, after(name, when))
    inherited = signal.signal(signal.SIGINT, signal.SIG_IGN)  # as in a background job: only the CLI's own handler can stop it
    try:
        assert bg.main(["cleanup", "--root", str(root)]) == 1 and fired
    finally:
        signal.signal(signal.SIGINT, inherited)
    assert capsys.readouterr().out == "" and bg._read_marker(str(root))["root"] == root.name and not claimed(root.parent)
    monkeypatch.setattr(os, name, real[name])
    assert bg.cleanup_root(root) == "REMOVED"

def test_a_claimed_directory_that_cannot_be_opened_is_put_back_with_a_refusal(root, monkeypatch):
    real = os.open

    def too_many(path, flags, mode=0o777, *, dir_fd=None):
        if str(path).startswith(".gone-") and flags & os.O_DIRECTORY:
            raise OSError(bg.errno.EMFILE, "too many open files")
        return real(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", too_many)
    assert bg.cleanup_root(root) == "REMOVE_FAILED" and (root / bg._MARKER_NAME).exists() and not claimed(root.parent)
    monkeypatch.setattr(os, "open", real)
    assert bg.cleanup_root(root) == "REMOVED"
