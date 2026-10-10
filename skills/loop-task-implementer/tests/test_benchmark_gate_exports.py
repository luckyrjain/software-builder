"""Tests for the C4c-1 filesystem and git pieces of `benchmark_gate.py`: `export_tree`, tree hash and seal,
`cleanup_root`, and the `export` / `cleanup` CLIs.

Everything git-related runs against real temporary repositories (no network, hooks or signing); hostile trees (`.git`
entries, `..`, case collisions, escaping symlinks) are built with `git mktree`, since `git add` refuses them.
Design: docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md (APIs table, `compare` row).
"""

from __future__ import annotations

import concurrent.futures
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
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
        pytest.skip(f"the host git cannot run the export tests: {exc.detail}")  # GIT_ATTR_SOURCE needs git >= 2.43
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

def test_export_reports_gitlinks_as_empty_directories_and_lfs_pointers(tmp_path, repo_a):
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
    (lambda r, b: [f"120000 blob {blob(r, b'.')}\tself", f"120000 blob {blob(r, b'self/../..')}\tchain"], "EXPORT_SYMLINK_ESCAPES"),
])
def test_export_refuses_hostile_trees_and_leaves_nothing_behind(tmp_path, builder, code):
    repo = make_repo(tmp_path)
    sha = hostile_commit(repo, builder(repo, blob(repo)))
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code == code and code in bg.EXPORT_REFUSAL_CODES
    assert not Path(dest()).parent.exists()  # the root this call created is removed too
    assert bg.main(["export", "--repo", str(repo), "--commit", sha, "--dest", dest()]) == 1

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
    outside = tmp_path / "outside"
    outside.mkdir()
    (bg.fixed_parent() / "bench-cccccccc").symlink_to(outside)
    with pytest.raises(Err):
        bg.export_tree(repo, sha, dest(root="bench-cccccccc"))
    assert not list(outside.iterdir())

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
    for path, mode in ((root, 0o755), (root / "d", 0o755), (root / "d/a.txt", 0o644), (root / "b.txt", 0o644)):
        path.chmod(mode)  # explicit: independent of the umask
    return root

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
    assert (tree / "d/a.txt").read_text() == "a"


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
    write_marker(root, pid=os.getpid())
    assert bg.main(["cleanup", "--root", str(root)]) == 1 and capsys.readouterr().out == "OWNER_ALIVE\n"
    write_marker(root)
    assert bg.main(["cleanup", "--root", str(root)]) == 0 and capsys.readouterr().out == "REMOVED\n"
    assert bg.main(["cleanup", "--root", str(root)]) == 0 and capsys.readouterr().out == "ABSENT\n"
    assert bg.main(["cleanup"]) == 2


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
        "REMOVED ABSENT NOT_UNDER_FIXED_PARENT NOT_A_DIRECTORY NOT_OWNED MARKER_MISSING MARKER_INVALID OWNER_ALIVE REMOVE_FAILED".split())
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


def swap_for_symlink_on_open(monkeypatch, parent: Path, name: str, outside: Path):
    """A hostile process, deterministically: just before the walk opens directory `name`, swap it for a symlink to `outside`."""
    real_open, done = os.open, []

    def hooked(path, flags, mode=0o777, *, dir_fd=None):
        if path == name and dir_fd is not None and not done:
            done.append(True)
            os.rename(parent / name, parent / (name + ".moved"))
            os.symlink(outside, parent / name)
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
    return {str(p): (stat.S_IMODE(p.stat().st_mode), None if p.is_dir() else p.read_text()) for p in [base, *base.rglob("*")]}

@pytest.mark.skipif(IS_ROOT, reason="root ignores mode bits")
@pytest.mark.parametrize("operation", ["seal", "unseal", "cleanup"])
def test_a_directory_swapped_for_a_symlink_mid_walk_is_never_followed(tree, root, tmp_path, monkeypatch, operation):
    # seal must not strip outside write bits; unseal and cleanup must not add them (outside starts restrictive)
    writable = operation == "seal"
    outside = tmp_path / "outside"
    snapshot = outside_tree(outside, 0o755 if writable else 0o500, 0o644 if writable else 0o400)
    target, victim = (tree, "d") if operation != "cleanup" else (root / "head", "src")
    if operation == "unseal":
        bg.seal_tree(tree)
    done = swap_for_symlink_on_open(monkeypatch, target, victim, outside)
    try:
        if operation == "cleanup":
            assert bg.cleanup_root(root) == "REMOVED"
        else:
            with pytest.raises(Err):
                (bg.seal_tree if operation == "seal" else bg.unseal_tree)(tree)
    finally:
        monkeypatch.undo()
    assert done and {str(p): (stat.S_IMODE(p.stat().st_mode), None if p.is_dir() else p.read_text())
                     for p in [outside, *outside.rglob("*")]} == snapshot
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

def test_racing_cleanups_all_report_removed_or_absent(root):
    for index in range(300):
        (root / "head" / f"f{index}.txt").write_text("x")
    gate = threading.Barrier(8)

    def run(_):
        gate.wait()
        return bg.cleanup_root(root)

    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        results = list(pool.map(run, range(8)))
    assert set(results) <= {"REMOVED", "ABSENT"} and "REMOVED" in results and not root.exists()

def test_old_git_is_an_environment_error_not_a_hostile_tree_verdict(repo_a, monkeypatch, capsys):
    repo, sha = repo_a
    monkeypatch.setattr(bg, "_git_version", (2, 34))
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code == "GIT_TOO_OLD" and "2.43" in info.value.detail and not Path(dest()).parent.exists()
    assert bg.main(["export", "--repo", str(repo), "--commit", sha, "--dest", dest()]) == 2
    assert capsys.readouterr().out == ""
    real = subprocess.run  # and the version really is parsed from `git --version`
    monkeypatch.setattr(bg, "_git_version", None)
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: real(["/bin/echo", "git version 2.39.5 (Apple Git-154)"] if "--version" in argv else argv, **kw))
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code == "GIT_TOO_OLD" and "found 2.39" in info.value.detail

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

def test_a_failed_export_drops_its_new_root_only_when_nothing_else_uses_it(repo_a, monkeypatch):
    repo, sha = repo_a
    seen = []
    real_marker = bg._write_marker  # the marker is written BEFORE the root becomes visible (temp directory, then rename)
    monkeypatch.setattr(bg, "_write_marker", lambda root, pid, name=None: (seen.append(os.path.lexists(os.path.join(os.path.dirname(root), name or ""))), real_marker(root, pid, name))[1])
    root_dir = Path(dest()).parent

    def fail_verify(_dest, _entries):
        if shared:
            (root_dir / "other-export").mkdir()  # another exporter put its tree into the root meanwhile
        raise Err("EXPORT_VERIFY_FAILED", "forced")

    monkeypatch.setattr(bg, "_verify_export", fail_verify)
    for shared in (False, True):
        with pytest.raises(Err):
            bg.export_tree(repo, sha, dest())
        assert not Path(dest()).exists() and root_dir.exists() is shared
        assert shared is False or (root_dir / bg._MARKER_NAME).exists()
        shutil.rmtree(root_dir, ignore_errors=True)
    assert seen == [False, False]


def test_cleanup_verdict_is_what_is_left_and_a_vanished_root_is_absent(root, monkeypatch):
    real_rmtree, real_open = shutil.rmtree, bg._open_dir
    monkeypatch.setattr(shutil, "rmtree", lambda *a, **k: None)
    assert bg.cleanup_root(root) == "REMOVE_FAILED"  # the verdict is whether the root still exists
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
