"""Tests for the C4c filesystem and git pieces of `benchmark_gate.py`: `export_tree`, tree hash and seal,
`cleanup_root`, `overlay_benchmark_file`, `protected_path_changes`, `benchmark_aware_tokens`, the venv snapshot and
its `.pth` content check, and the `export` / `snapshot-venv` / `cleanup` CLIs.

Everything git-related runs against real temporary repositories (no network, no hooks, no signing). Hostile trees
(`.git` entries, `..`, case collisions, escaping symlinks) are built with `git mktree`, since `git add` refuses them.
Design: docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md (APIs table, `compare` row).
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
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

# ---------------------------------------------------------------------------
# helpers: scrubbed git, real repositories, hostile trees
# ---------------------------------------------------------------------------

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
    """A commit whose root tree is `git mktree` of `lines` ("<mode> <type> <sha>\\t<name>"); blobs via `blob()`."""
    tree = git(repo, "mktree", inp=("\n".join(lines) + "\n").encode())
    return git(repo, "commit-tree", tree, "-m", "hostile")


def blob(repo, data=b"x\n") -> str:
    return git(repo, "hash-object", "-w", "--stdin", inp=data)


def dir_with(repo, name, inner="config", data=b"x\n") -> str:
    """The mktree line of a directory `name` holding one file."""
    inner_tree = git(repo, "mktree", inp=f"100644 blob {blob(repo, data)}\t{inner}\n".encode())
    return f"040000 tree {inner_tree}\t{name}"


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    """The fixed parent (and every private git directory) lives under tmp_path, never the real temp directory."""
    temp = tmp_path / "tmp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
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


# ---------------------------------------------------------------------------
# export_tree
# ---------------------------------------------------------------------------

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
    (lambda r, b: [dir_with(r, ".git.")], "EXPORT_PATH_REJECTED"),
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


def test_export_refuses_an_oversize_tree(repo_a, monkeypatch):
    repo, sha = repo_a
    monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", 2)
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code == "EXPORT_TOO_LARGE"


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
    bg.export_tree(repo, sha, dest())
    with pytest.raises(Err) as info:  # dest exists
        bg.export_tree(repo, sha, dest())
    assert info.value.code == "DEST_REJECTED"
    with pytest.raises(Err):
        bg.export_tree(repo, sha, dest("other"), owner_pid=0)


def test_export_refuses_a_root_that_is_not_ours_or_a_symlinked_parent(repo_a, tmp_path):
    repo, sha = repo_a
    (bg.fixed_parent()).mkdir(mode=0o700)
    (bg.fixed_parent() / "bench-bbbbbbbb").mkdir()  # no marker
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest(root="bench-bbbbbbbb"))
    assert info.value.code == "MARKER_MISSING"
    bg.fixed_parent().rmdir() if False else None
    outside = tmp_path / "outside"
    outside.mkdir()
    (bg.fixed_parent() / "bench-cccccccc").symlink_to(outside)
    with pytest.raises(Err):
        bg.export_tree(repo, sha, dest(root="bench-cccccccc"))
    assert not list(outside.iterdir())


def test_export_refuses_a_group_writable_fixed_parent(repo_a):
    repo, sha = repo_a
    bg.fixed_parent().mkdir(mode=0o700)
    bg.fixed_parent().chmod(0o777)
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest())
    assert info.value.code == "DEST_REJECTED"


def test_git_runs_with_a_scrubbed_environment(repo_a, monkeypatch):
    repo, sha = repo_a
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG_COUNT", "GIT_EXTERNAL_DIFF", "GIT_SSH_COMMAND"):
        monkeypatch.setenv(name, "/nonexistent")
    seen = []
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: seen.append((argv, kw)) or real(argv, **kw))
    bg.export_tree(repo, sha, dest())
    assert seen and all(isinstance(argv, list) and kw["stdin"] == subprocess.DEVNULL and kw["timeout"] for argv, kw in seen)
    assert all(not kw.get("shell") for _, kw in seen)
    for _, kw in seen:
        env = kw["env"]
        assert env["GIT_CONFIG_NOSYSTEM"] == "1" and env["GIT_CONFIG_GLOBAL"] == os.devnull and env["GIT_TERMINAL_PROMPT"] == "0"
        assert "GIT_EXTERNAL_DIFF" not in env and "GIT_SSH_COMMAND" not in env and "GIT_CONFIG_COUNT" not in env
        assert env.get("GIT_INDEX_FILE", "").startswith(str(bg.fixed_parent().parent)) or "GIT_INDEX_FILE" not in env
        assert not str(repo) in env.get("GIT_DIR", "")


# ---------------------------------------------------------------------------
# hash_tree, seal_tree, unseal_tree
# ---------------------------------------------------------------------------

@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "t"
    (root / "d").mkdir(parents=True)
    (root / "d/a.txt").write_text("a")
    (root / "b.txt").write_text("b")
    (root / "link").symlink_to("b.txt")
    return root


def test_hash_tree_is_deterministic_and_sensitive_to_every_input(tree, tmp_path):
    base = bg.hash_tree(tree)
    assert base == bg.hash_tree(str(tree)) and len(base) == 64
    copy = tmp_path / "copy"
    import shutil
    shutil.copytree(tree, copy, symlinks=True)
    assert bg.hash_tree(copy) == base  # path and timestamps are not inputs
    os.utime(copy / "b.txt", (1, 1))
    assert bg.hash_tree(copy) == base

    def mutate(kind):
        root = tmp_path / f"m-{kind}"
        shutil.copytree(tree, root, symlinks=True)
        if kind == "content":
            (root / "b.txt").write_text("B")
        elif kind == "mode":
            (root / "b.txt").chmod(0o755)
        elif kind == "dir-mode":
            (root / "d").chmod(0o700)
        elif kind == "rename":
            (root / "b.txt").rename(root / "c.txt")
        elif kind == "empty-dir":
            (root / "e").mkdir()
        elif kind == "new-file":
            (root / "d/n.pyc").write_bytes(b"")
        elif kind == "delete":
            (root / "d/a.txt").unlink()
        elif kind == "link-target":
            (root / "link").unlink()
            (root / "link").symlink_to("d/a.txt")
        elif kind == "link-to-file":  # same bytes, different type
            (root / "link").unlink()
            (root / "link").write_text("b.txt")
        return bg.hash_tree(root)

    kinds = ["content", "mode", "dir-mode", "rename", "empty-dir", "new-file", "delete", "link-target", "link-to-file"]
    hashes = {kind: mutate(kind) for kind in kinds}
    assert base not in hashes.values() and len(set(hashes.values())) == len(kinds)


def test_hash_tree_never_opens_special_files_or_follows_links(tree, tmp_path):
    if hasattr(os, "mkfifo"):
        os.mkfifo(tree / "fifo")
    (tree / "out").symlink_to(tmp_path)  # a link out of the tree is hashed as a link, not walked
    before = bg.hash_tree(tree)
    (tmp_path / "unrelated.txt").write_text("changes outside the tree")
    assert bg.hash_tree(tree) == before


@pytest.mark.skipif(IS_ROOT, reason="root reads mode-0 files")
def test_hash_tree_fails_closed_on_an_unreadable_entry(tree):
    (tree / "b.txt").chmod(0)
    with pytest.raises(Err) as info:
        bg.hash_tree(tree)
    assert info.value.code == "TREE_UNREADABLE"


def test_walk_is_bounded_and_refuses_a_symlink_or_missing_root(tree, tmp_path, monkeypatch):
    with pytest.raises(Err) as info:
        bg.hash_tree(tree / "link")
    assert info.value.code == "TREE_UNREADABLE"
    with pytest.raises(Err):
        bg.hash_tree(tmp_path / "missing")
    monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", 3)
    with pytest.raises(Err) as info:
        bg.hash_tree(tree)
    assert info.value.code == "TREE_TOO_LARGE"


@pytest.mark.skipif(IS_ROOT, reason="root ignores write bits")
def test_seal_removes_every_write_bit_keeps_the_hash_stable_and_unseal_restores(tree, tmp_path):
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
    sealed = bg.hash_tree(tree)
    assert (tree / "d/a.txt").read_text() == "a" and bg.hash_tree(tree) == sealed  # reading changes nothing
    bg.seal_tree(tree)  # idempotent
    assert bg.hash_tree(tree) == sealed
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


# ---------------------------------------------------------------------------
# cleanup_root, claim_root, pid liveness
# ---------------------------------------------------------------------------

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
    if not IS_ROOT:
        with pytest.raises(PermissionError):
            shutil_rmtree_plain(root / "head")  # a plain removal of the sealed tree fails: unseal must come first
    assert bg.cleanup_root(root) == "REMOVED" and not root.exists()
    assert (outside / "canary").read_text() == "alive" and outside.exists()
    assert bg.cleanup_root(root) == "ABSENT"


def shutil_rmtree_plain(path):
    import shutil
    shutil.rmtree(path)


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


def test_cleanup_refuses_while_the_owner_lives_and_claim_root_moves_the_owner(root):
    write_marker(root, pid=os.getpid())
    assert bg.cleanup_root(root) == "OWNER_ALIVE" and root.exists()
    write_marker(root)
    bg.claim_root(root)
    assert json.loads((root / bg._MARKER_NAME).read_text())["pid"] == os.getpid()
    assert bg.cleanup_root(root) == "OWNER_ALIVE"
    bg.claim_root(root, dead_pid())
    assert bg.cleanup_root(root) == "REMOVED"
    with pytest.raises(Err):
        bg.claim_root(root)


def test_pid_liveness(monkeypatch):
    assert bg._pid_alive(os.getpid()) and not bg._pid_alive(dead_pid())
    for exc, alive in ((PermissionError(), True), (OSError(), True), (OverflowError(), True)):
        monkeypatch.setattr(os, "kill", lambda pid, sig, exc=exc: (_ for _ in ()).throw(exc))
        assert bg._pid_alive(5) is alive
    monkeypatch.setattr(os, "kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))
    assert bg._pid_alive(5) is False
    monkeypatch.setattr(os, "name", "nt")
    assert bg._pid_alive(5) is True  # never os.kill off POSIX: on Windows that terminates the process


def test_cleanup_cli_exit_codes(root, capsys):
    write_marker(root, pid=os.getpid())
    assert bg.main(["cleanup", "--root", str(root)]) == 1 and capsys.readouterr().out == "OWNER_ALIVE\n"
    write_marker(root)
    assert bg.main(["cleanup", "--root", str(root)]) == 0 and capsys.readouterr().out == "REMOVED\n"
    assert bg.main(["cleanup", "--root", str(root)]) == 0 and capsys.readouterr().out == "ABSENT\n"
    assert bg.main(["cleanup"]) == 2


# ---------------------------------------------------------------------------
# overlay_benchmark_file
# ---------------------------------------------------------------------------

@pytest.fixture
def pair(tmp_path):
    """Two commits: base has `benchmarks/bench_pre.py` and no `bench_orders.py`; head adds the latter."""
    repo = make_repo(tmp_path)
    base = commit(repo, {"src/app.py": "a = 1\n", "benchmarks/bench_pre.py": BENCH_SRC})
    head = commit(repo, {BENCH: BENCH_SRC})
    base_root = bg.export_tree(repo, base, dest("base"))
    head_root = bg.export_tree(repo, head, dest("head"))
    return repo, base, head, base_root, head_root


def test_overlay_copies_a_builder_authored_benchmark_and_reports_pre_existing_ones(pair):
    _, base, _, base_root, head_root = pair
    assert bg.overlay_benchmark_file(base_root, head_root, base, BENCH) == "BUILDER_AUTHORED"
    assert (base_root / BENCH).read_bytes() == BENCH_SRC and stat.S_IMODE((base_root / BENCH).stat().st_mode) == 0o644
    assert bg.overlay_benchmark_file(base_root, head_root, base, "benchmarks/bench_pre.py") == "PRE_EXISTING"
    assert bg.overlay_benchmark_file(base_root, head_root, base, BENCH) == "PRE_EXISTING"  # now present at base, equal bytes


def test_overlay_creates_missing_parent_directories_only_inside_base(pair):
    _, base, _, base_root, head_root = pair
    deep = "perf/deep/bench_deep.py"
    (head_root / "perf/deep").mkdir(parents=True)
    (head_root / deep).write_bytes(BENCH_SRC)
    assert bg.overlay_benchmark_file(base_root, head_root, base, deep) == "BUILDER_AUTHORED"
    assert (base_root / deep).read_bytes() == BENCH_SRC


def test_overlay_refuses_to_overwrite_a_different_base_file(pair):
    _, base, _, base_root, head_root = pair
    (head_root / "benchmarks/bench_pre.py").write_bytes(BENCH_SRC + b"# changed\n")
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file(base_root, head_root, base, "benchmarks/bench_pre.py")
    assert info.value.code == "BENCHMARK_MODIFIED" and (base_root / "benchmarks/bench_pre.py").read_bytes() == BENCH_SRC


def test_overlay_rejections(pair, tmp_path):
    _, base, head, base_root, head_root = pair
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = tmp_path / "secret.py"
    secret.write_bytes(BENCH_SRC)

    def reject(*args, code="OVERLAY_REJECTED"):
        with pytest.raises(Err) as info:
            bg.overlay_benchmark_file(*args)
        assert info.value.code == code, (args, info.value.code, info.value.detail)

    for path in ("../x.py", "/abs/bench_x.py", "benchmarks/../bench_orders.py", "src/app.py", "benchmarks/bench_orders.pyc",
                 "benchmarks/bench_orders.py\n", "", None, 5, "benchmarks/.git/bench_x.py"):
        reject(base_root, head_root, base, path)
    reject(base_root, head_root, head, BENCH)  # not an export of that commit
    reject(base_root, head_root, "a" * 40, BENCH)
    reject(base_root, head_root, "xyz", BENCH, code="COMMIT_INVALID")
    reject(base_root, base_root, base, BENCH)
    reject(base_root, base_root / "sub", base, BENCH)
    reject(tmp_path / "missing", head_root, base, BENCH)
    (head_root / BENCH).unlink()
    reject(base_root, head_root, base, BENCH)  # missing at head
    (head_root / BENCH).symlink_to(secret)
    reject(base_root, head_root, base, BENCH)  # symlink at head
    (head_root / BENCH).unlink()
    (head_root / BENCH).write_bytes(b"#" * (16 * 1024 + 1))
    reject(base_root, head_root, base, BENCH)  # over 16 KiB
    (head_root / BENCH).unlink()
    (head_root / "benchmarks").rename(head_root / "benchmarks_moved")
    (outside / "bench_orders.py").write_bytes(BENCH_SRC)
    (head_root / "benchmarks").symlink_to(outside)
    reject(base_root, head_root, base, BENCH)  # symlinked parent at head
    (head_root / "benchmarks").unlink()
    (head_root / "benchmarks_moved").rename(head_root / "benchmarks")
    (head_root / BENCH).write_bytes(BENCH_SRC)
    (outside / "bench_orders.py").unlink()
    (base_root / "benchmarks").rename(base_root / "benchmarks_moved")
    (base_root / "benchmarks").symlink_to(outside)
    reject(base_root, head_root, base, BENCH)  # symlinked parent at base: nothing may be written through it
    assert not list(outside.iterdir())
    (base_root / "benchmarks").unlink()
    (base_root / "benchmarks_moved").rename(base_root / "benchmarks")
    (base_root / BENCH).mkdir()
    reject(base_root, head_root, base, BENCH)  # a directory squats the name
    (base_root / BENCH).rmdir()
    Path(str(base_root) + ".export.json").unlink()
    reject(base_root, head_root, base, BENCH)  # no sidecar: not one of our exports


def test_overlay_exact_name_lookup_does_not_confuse_case_variants(pair):
    _, base, _, base_root, head_root = pair
    variant = "benchmarks/bench_Pre.py"  # differs from base's bench_pre.py only by case
    (head_root / variant).write_bytes(BENCH_SRC + b"# other\n")
    try:
        assert bg.overlay_benchmark_file(base_root, head_root, base, variant) == "BUILDER_AUTHORED"
    except Err as exc:  # a case-insensitive filesystem cannot hold both files: it must fail closed
        assert exc.code == "OVERLAY_REJECTED"
    assert (base_root / "benchmarks/bench_pre.py").read_bytes() == BENCH_SRC


# ---------------------------------------------------------------------------
# protected_path_changes
# ---------------------------------------------------------------------------

PROTECTED = [
    "conftest.py", "sub/dir/conftest.py", "a/Conftest.PY", "sitecustomize.py", "a/b/sitecustomize.py", "usercustomize.py",
    "src/sitecustomize.py", "sitecustomize_x.py", "b/SiteCustomize.py", "sitecustomize/__init__.py", "x.pth", "a/x.PTH",
    "pytest.ini", "pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "noxfile.py", "MANIFEST.in", "requirements.txt",
    "requirements-dev.txt", "requirements/dev.txt", "a/requirements/b.txt", "constraints.txt", "constraints-3.txt",
    "deps.in", "environment.yml", "Pipfile", "Pipfile.lock", "poetry.lock", "uv.lock", "pdm.lock", "pylock.toml",
    "pylock.x.toml", "json.py", "src/json.py", "typing/__init__.py", "src/types/__init__.py", "os.cpython-312-x.so",
    "src/Json/x.py", "a.pyc", "pkg/__pycache__/x.cpython-312.pyc", "__pycache__/f.txt", "benchmarks/__init__.py",
    "benchmarks/helper.py", "benchmarks/sub/deep.py", "-dash/conftest.py", "sp ace/conftest.py",
    "café/conftest.py", "new\nline/conftest.py",
]
UNPROTECTED = [
    "README.md", "src/app/core.py", "docs/requirements.md", "tests/test_x.py", "benchmarks_extra/x.py", BENCH, "src/jsonx.py",
    "lib/json.py", "notconftest.py", "docs/conftest.txt", "src/app/types.py", "setup.py.txt", "requirements.md", "b.py",
]


@pytest.fixture
def two(tmp_path):
    repo = make_repo(tmp_path)
    return repo, commit(repo, {"a.py": "a\n", "app.py": "x\n", "setup.py": "s\n", "conftest.py": "c\n"})


def changes(repo, base, head, bench=BENCH):
    return bg.protected_path_changes(repo, base, head, bench)


def test_protected_paths_are_flagged_and_ordinary_ones_are_not(two):
    repo, base = two
    commit(repo, {path: "x\n" for path in PROTECTED + UNPROTECTED})
    # `Benchmarks/` would merge into `benchmarks/` on a case-insensitive filesystem: add it to the index only.
    git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob(repo)},Benchmarks/x.py")
    git(repo, "commit", "-q", "-m", "case")
    head = git(repo, "rev-parse", "HEAD")
    got = changes(repo, base, head)
    assert got == sorted({*PROTECTED, "Benchmarks/x.py"}, key=os.fsencode)  # conftest.py exists at base: modified, still listed
    assert set(UNPROTECTED).isdisjoint(got) and changes(repo, head, head) == []


def test_protected_case_variants_at_the_root(tmp_path):
    for path in ("JSON.py", "Conftest.py", "SITECUSTOMIZE.PY"):
        repo = make_repo(tmp_path, name="r" + path)
        base = commit(repo, {"a.py": "a\n"})
        assert changes(repo, base, commit(repo, {path: "x\n"})) == [path]


@pytest.mark.parametrize("kind", ["rename", "delete", "mode", "type"])
def test_protected_operations_count_even_when_git_would_call_it_a_rename(two, kind):
    repo, base = two
    if kind == "rename":  # rename detection is OFF: identical content moved is a delete plus an add
        (repo / "setup.py").rename(repo / "build.txt")
        (repo / "conftest.py").rename(repo / "docs_conf.py")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "mv")
        expected = ["conftest.py", "setup.py"]
    elif kind == "delete":
        commit(repo, {"conftest.py": None})
        expected = ["conftest.py"]
    elif kind == "mode":
        (repo / "setup.py").chmod(0o755)
        (repo / "app.py").chmod(0o755)
        git(repo, "commit", "-q", "-am", "chmod")
        expected = ["setup.py"]
    else:
        (repo / "conftest.py").unlink()
        commit(repo, {"conftest.py": ("link", "app.py")})
        expected = ["conftest.py"]
    assert changes(repo, base, git(repo, "rev-parse", "HEAD")) == expected


def test_protected_diff_arguments_fail_closed(two):
    repo, base = two
    for args, code in ((("x", base), "COMMIT_INVALID"), ((base, "A" * 40), "COMMIT_INVALID"), ((base, "1" * 64), "COMMIT_INVALID"),
                       (("1" * 64, base), "COMMIT_INVALID"), ((base, "1" * 40), "COMMIT_NOT_FOUND"), (("1" * 40, base), "COMMIT_NOT_FOUND")):
        with pytest.raises(Err) as info:
            changes(repo, *args)
        assert info.value.code == code, args
    for bench in ("../x.py", "a.py", None):
        with pytest.raises(Err) as info:
            changes(repo, base, base, bench)
        assert info.value.code == "PROTECTED_DIFF_FAILED"


def test_diff_commands_never_run_the_repositorys_drivers(two, tmp_path):
    repo, base = two
    canary = tmp_path / "canary"
    (repo / ".gitattributes").write_text("*.py diff=evil\n")
    git(repo, "config", "diff.evil.textconv", f"touch {canary}; cat")
    git(repo, "config", "diff.external", f"touch {canary}; true")
    head = commit(repo, {"setup.py": "t\n", "a.py": "sys.argv\n"})
    assert changes(repo, base, head) == [".gitattributes", "setup.py"][1:] and bg.benchmark_aware_tokens(repo, base, head, BENCH)
    assert not canary.exists()


# ---------------------------------------------------------------------------
# benchmark_aware_tokens
# ---------------------------------------------------------------------------

def test_tripwire_reports_added_lines_with_a_token_outside_the_benchmark(two):
    repo, base = two
    files = {
        "src/a.py": "import os\nx = os.environ['PYTEST_CURRENT_TEST']\n", "src/b.py": "d = 'BENCH_RESULT_DIGEST'\n",
        "src/c.py": "t = 'BENCH_TRACE_LINES'\n", "src/d.py": "os._exit(0)\n", "src/e.py": "import sys\nsys.argv\n",
        "src/f.py": f"p = '{BENCH}'\n", "src/sys.argv.py": "x = 1\n", "src/plus.py": "++ sys.argv\n", "-dash.py": "sys.argv\n", "new\nline.py": "sys.argv\n",
        BENCH: BENCH_SRC + b"os._exit(0)  # the benchmark itself is not scanned\n", "src/clean.py": "x = 1\n",
        "bin.dat": b"\x00\x01os._exit\x00\xff\xfe", "latin.py": b"caf\xe9 = 'sys.argv'\n",
    }
    head = commit(repo, files)
    hits = bg.benchmark_aware_tokens(repo, base, head, BENCH)
    assert {h.split(": ")[0] for h in hits} == {
        "src/a.py", "src/b.py", "src/c.py", "src/d.py", "src/e.py", "src/f.py", "src/plus.py", "'-dash.py", "new line.py", "bin.dat", "latin.py"}
    assert {h.split(": ")[1] for h in hits} == {"PYTEST_CURRENT_TEST", "BENCH_RESULT_DIGEST", "BENCH_TRACE_LINES", "os._exit", "sys.argv", BENCH}
    assert hits == bg.benchmark_aware_tokens(repo, base, head, BENCH) and all(h.isascii() and "\n" not in h for h in hits)


def test_tripwire_ignores_context_removed_lines_and_deleted_files(tmp_path):
    repo = make_repo(tmp_path)
    base = commit(repo, {"old.py": "sys.argv\nkeep = 1\n", "gone.py": "os._exit\n", "chg.py": "sys.argv\nz = 1\n"})
    head = commit(repo, {"old.py": "sys.argv\nkeep = 1\nnew = 2\n", "gone.py": None, "chg.py": "z = 1\n"})
    assert bg.benchmark_aware_tokens(repo, base, head, BENCH) == []


def test_tripwire_is_bounded_and_fails_closed(two, monkeypatch):
    repo, base = two
    head = commit(repo, {"a.py": "x\n" * 50, "b.py": "y\n"})
    for name, value in (("_MAX_TRIPWIRE_FILES", 1), ("_TRIPWIRE_FILE_CAP", 20), ("_TRIPWIRE_TOTAL_CAP", 5)):
        monkeypatch.setattr(bg, name, value)
        with pytest.raises(Err) as info:
            bg.benchmark_aware_tokens(repo, base, head, BENCH)
        assert info.value.code == "TRIPWIRE_LIMIT", name
        monkeypatch.undo()
    with pytest.raises(Err):
        bg.benchmark_aware_tokens(repo, base, head, "../x.py")
    with pytest.raises(Err):
        bg.benchmark_aware_tokens(repo, base, "1" * 40, BENCH)


# ---------------------------------------------------------------------------
# snapshot_venv and venv_addition_violations
# ---------------------------------------------------------------------------

def fake_venv(tmp_path, files=None):
    """A venv without an interpreter: pyvenv.cfg, bin/, lib/python3.12/site-packages (and lib64 -> lib)."""
    venv = Path(tempfile.mkdtemp(dir=tmp_path, prefix="venv-"))
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (venv / "bin").mkdir()
    site = venv / "lib/python3.12/site-packages"
    site.mkdir(parents=True)
    (venv / "lib64").symlink_to("lib")
    populate(site, files or {})
    return venv, site


def populate(site: Path, files: dict):
    for name, value in files.items():
        if isinstance(value, tuple) and value[0] == "link":
            (site / name).symlink_to(value[1])
        elif isinstance(value, tuple):
            (site / name).mkdir()
        else:
            (site / name).write_bytes(value.encode() if isinstance(value, str) else value)


@pytest.fixture
def export_dir(tmp_path):
    export = tmp_path / "export"
    (export / "src").mkdir(parents=True)
    (export / "linkdir").symlink_to(tmp_path)
    (tmp_path / "export-evil").mkdir()
    return export


def violations(tmp_path, export, added, pre=None):
    venv, site = fake_venv(tmp_path, pre)
    before = bg.snapshot_venv(venv / "bin")
    populate(site, added)
    return bg.venv_addition_violations(before, bg.snapshot_venv(venv / "bin"), export)


def editable_forms(export):
    src = f"{export}/src"
    return {
        "setuptools finder": {"__editable__.proj-0.1.pth": "import __editable___proj_0_1_finder; __editable___proj_0_1_finder.install()\n"},
        "setuptools path": {"__editable__.proj.pth": f"{src}\n"},
        "hatchling path": {"_proj.pth": f"{src}\n"},
        "hatchling impl import": {"_editable_impl_proj.pth": "import _editable_impl_proj\n"},
        "hatchling impl path": {"_editable_impl_proj.pth": f"{src}\n"},
        "pdm-backend": {"_editable_impl_proj.pth": f"# pdm\n{src}\n"},
        "flit-core": {"proj.pth": f"{src}\n"},
        "poetry-core": {"proj.pth": f"{export}\n{src}\n"},
        "crlf, bom, blank lines": {"proj.pth": "﻿\r\n" + f"{src}\r\n\r\n"},
    }


def test_honest_editable_installs_are_accepted(tmp_path, export_dir):
    for label, added in editable_forms(export_dir).items():
        assert violations(tmp_path, export_dir, added) == [], label


@pytest.mark.parametrize("added, expected", [
    ({"a1_coverage.pth": "import coverage; coverage.process_startup()\n"}, ["PTH_IMPORT_LINE"]),
    ({"x.pth": "import os; os._exit(0)\n"}, ["PTH_IMPORT_LINE"]),
    ({"x.pth": "import\tos\n"}, ["PTH_IMPORT_LINE"]),
    ({"x.pth": "import __editable___p_finder; evil()\n"}, ["PTH_IMPORT_LINE"]),
    ({"x.pth": "import __editable___p_finder; __editable___q_finder.install()\n"}, ["PTH_IMPORT_LINE"]),
    ({"x.pth": "import _editable_impl_p; evil()\n"}, ["PTH_IMPORT_LINE"]),
    ({"x.pth": "@SRC@\nimport os\n"}, ["PTH_IMPORT_LINE"]),
    ({"x.pth": "/etc\n"}, ["PTH_PATH_OUTSIDE_EXPORT"]),
    ({"x.pth": "@EXPORT@/../other\n"}, ["PTH_PATH_OUTSIDE_EXPORT"]),
    ({"x.pth": "@EXPORT@/src/../../export-evil\n"}, ["PTH_PATH_OUTSIDE_EXPORT"]),
    ({"x.pth": "@EXPORT@-evil\n"}, ["PTH_PATH_OUTSIDE_EXPORT"]),
    ({"x.pth": "@EXPORT@/linkdir\n"}, ["PTH_PATH_OUTSIDE_EXPORT"]),
    ({"x.pth": "relative/dir\n"}, ["PTH_PATH_OUTSIDE_EXPORT"]),
    ({"x.pth": "@SRC@/../src\n"}, ["PTH_PATH_OUTSIDE_EXPORT"]),  # resolves inside, but `..` is never an honest install's line
    ({"x.pth": " import os\n"}, ["PTH_PATH_OUTSIDE_EXPORT"]),
    ({"x.pth": "importlib\n"}, ["PTH_PATH_OUTSIDE_EXPORT"]),
    ({"x.pth": "/etc\rimport os\r"}, ["PTH_IMPORT_LINE", "PTH_PATH_OUTSIDE_EXPORT"]),
    ({"x.pth": "@SRC@; import os\n"}, ["PTH_PATH_NOT_DIRECTORY"]),
    ({"x.pth": "@EXPORT@/missing\n"}, ["PTH_PATH_NOT_DIRECTORY"]),
    ({"x.pth": "@SRC@\0\n"}, ["PTH_BAD_ENCODING"]),
    ({"x.pth": b"\xff\xfe/x\n"}, ["PTH_BAD_ENCODING"]),
    ({"x.pth": "#" * 5000}, ["PTH_UNREADABLE"]),
    ({"evil.pth": ("link", "/etc/hosts")}, ["VENV_ENTRY_NOT_REGULAR"]),
    ({"evil.pth": ("dir",)}, ["VENV_ENTRY_NOT_REGULAR"]),
    ({"sitecustomize.py": "print(1)\n"}, ["STARTUP_FILE_ADDED"]),
    ({"usercustomize.py": ""}, ["STARTUP_FILE_ADDED"]),
    ({"SiteCustomize.PY": ""}, ["STARTUP_FILE_ADDED"]),
    ({"sitecustomize": ("dir",)}, ["STARTUP_FILE_ADDED"]),
    ({"sitecustomize.cpython-312.so": "x"}, ["STARTUP_FILE_ADDED"]),
])
def test_hostile_venv_additions_are_rejected_with_stable_codes(tmp_path, export_dir, added, expected):
    added = {k: v.replace("@SRC@", f"{export_dir}/src").replace("@EXPORT@", str(export_dir)) if isinstance(v, str) else v
             for k, v in added.items()}
    assert violations(tmp_path, export_dir, added) == expected


def test_a_relative_line_is_rejected_even_when_it_resolves_inside_the_export(tmp_path, export_dir, monkeypatch):
    monkeypatch.chdir(export_dir)  # `src` relative to the cwd IS a directory inside the export
    assert violations(tmp_path, export_dir, {"x.pth": "src\n"}) == ["PTH_PATH_OUTSIDE_EXPORT"]


def test_only_new_lines_are_judged_and_removals_are_ignored(tmp_path, export_dir):
    venv, site = fake_venv(tmp_path, {"base.pth": "import legacy_hook\n", "gone.pth": "import x\n"})
    before = bg.snapshot_venv(venv / "bin")
    (site / "gone.pth").unlink()
    assert bg.venv_addition_violations(before, bg.snapshot_venv(venv / "bin"), export_dir) == []
    (site / "base.pth").write_text(f"import legacy_hook\n{export_dir}/src\n")  # an honest line appended
    assert bg.venv_addition_violations(before, bg.snapshot_venv(venv / "bin"), export_dir) == []
    (site / "base.pth").write_text("import legacy_hook\nimport evil\n")  # a new hostile line in an existing file
    assert bg.venv_addition_violations(before, bg.snapshot_venv(venv / "bin"), export_dir) == ["PTH_IMPORT_LINE"]


@pytest.mark.parametrize("bad", [None, {}, [], {"format": 2, "files": {}}, {"format": 1, "files": []}, {"format": 1},
                                 {"format": 1, "files": {"a": 1}}, {"format": 1, "files": {"a": {"kind": "x"}}}])
def test_invalid_snapshots_are_a_violation_not_a_crash(export_dir, bad):
    good = {"format": 1, "files": {}}
    assert bg.venv_addition_violations(bad, good, export_dir) == ["SNAPSHOT_INVALID"]
    assert bg.venv_addition_violations(good, bad, export_dir) == ["SNAPSHOT_INVALID"]
    assert bg.venv_addition_violations(good, good, export_dir) == []


def test_snapshot_format_and_cli_round_trip(tmp_path, capsys):
    venv, _ = fake_venv(tmp_path, {"a.pth": "/x\n", "link.pth": ("link", "/etc/hosts"), "notwatched.txt": "x", "big.pth": "#" * 5000})
    out = tmp_path / "snap.json"
    assert bg.main(["snapshot-venv", "--bin", str(venv / "bin"), "--out", str(out)]) == 0
    snap = bg.load_snapshot(out)
    assert snap == bg.snapshot_venv(venv / "bin") and snap["format"] == 1
    key = "lib/python3.12/site-packages/"  # lib64 -> lib is deduplicated: one set of keys
    assert sorted(snap["files"]) == [key + "a.pth", key + "big.pth", key + "link.pth"]
    assert snap["files"][key + "a.pth"] == {"kind": "file", "size": 3, "sha256": bg.hashlib.sha256(b"/x\n").hexdigest(), "hex": b"/x\n".hex()}
    assert snap["files"][key + "big.pth"]["hex"] is None and snap["files"][key + "link.pth"] == {"kind": "symlink", "target": "/etc/hosts"}
    assert capsys.readouterr().out == ""


def test_snapshot_fails_closed(tmp_path, monkeypatch, capsys):
    venv, _ = fake_venv(tmp_path)
    (venv / "pyvenv.cfg").unlink()
    with pytest.raises(Err) as info:
        bg.snapshot_venv(venv / "bin")
    assert info.value.code == "SNAPSHOT_FAILED"
    assert bg.main(["snapshot-venv", "--bin", str(venv / "bin"), "--out", str(tmp_path / "no.json")]) == 2
    assert not (tmp_path / "no.json").exists() and capsys.readouterr().out == ""
    escaping, _ = fake_venv(tmp_path)  # a site-packages directory that is a symlink out of the venv
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (escaping / "lib/python3.12/site-packages").rmdir()
    (escaping / "lib/python3.12/site-packages").symlink_to(elsewhere)
    with pytest.raises(Err):
        bg.snapshot_venv(escaping / "bin")
    crowded, site = fake_venv(tmp_path, {"a.pth": "", "b.pth": ""})
    monkeypatch.setattr(bg, "_MAX_SNAPSHOT_ENTRIES", 1)
    with pytest.raises(Err):
        bg.snapshot_venv(crowded / "bin")
    monkeypatch.undo()
    if not IS_ROOT:
        (site / "a.pth").chmod(0)
        with pytest.raises(Err):
            bg.snapshot_venv(crowded / "bin")  # unreadable file => fail closed
    for text in ("", "{", "[]x"):
        (tmp_path / "bad.json").write_text(text)
        with pytest.raises(Err):
            bg.load_snapshot(tmp_path / "bad.json")
    with pytest.raises(Err):
        bg.load_snapshot(tmp_path / "missing.json")


# ---------------------------------------------------------------------------
# CLI and vocabularies
# ---------------------------------------------------------------------------

def test_export_cli_prints_the_path_records_the_owner_and_rejects_bad_usage(repo_a, capsys):
    repo, sha = repo_a
    assert bg.main(["export", "--repo", str(repo), "--commit", sha, "--dest", dest(), "--owner-pid", "1"]) == 0
    cap = capsys.readouterr()
    assert cap.out == dest() + "\n" and cap.err == ""
    assert json.loads((Path(dest()).parent / bg._MARKER_NAME).read_text())["pid"] == 1
    for argv in (["export"], ["export", "--repo", "r", "--commit", sha], ["snapshot-venv", "--bin", "b"], ["cleanup", "--root"]):
        assert bg.main(argv) == 2


def test_code_vocabularies_are_pinned():
    assert bg.EXPORT_REFUSAL_CODES == tuple(
        "EXPORT_PATH_REJECTED EXPORT_PATH_COLLISION EXPORT_ENTRY_MODE EXPORT_TOO_LARGE EXPORT_SYMLINK_ESCAPES EXPORT_VERIFY_FAILED".split())
    assert bg.CLEANUP_CODES == tuple(
        "REMOVED ABSENT NOT_UNDER_FIXED_PARENT NOT_A_DIRECTORY NOT_OWNED MARKER_MISSING MARKER_INVALID OWNER_ALIVE REMOVE_FAILED".split())
    assert bg.VENV_VIOLATION_CODES == tuple(
        """SNAPSHOT_INVALID PTH_IMPORT_LINE PTH_PATH_OUTSIDE_EXPORT PTH_PATH_NOT_DIRECTORY PTH_BAD_ENCODING PTH_UNREADABLE
        VENV_ENTRY_NOT_REGULAR STARTUP_FILE_ADDED""".split())
    assert bg.ERROR_CODES == tuple(
        """COMMIT_INVALID COMMIT_NOT_FOUND REPO_UNREADABLE DEST_REJECTED GIT_FAILED GIT_TIMEOUT GIT_OUTPUT_TOO_LARGE TREE_UNREADABLE
        TREE_TOO_LARGE SEAL_FAILED SNAPSHOT_FAILED TRIPWIRE_LIMIT PROTECTED_DIFF_FAILED MARKER_MISSING MARKER_INVALID
        OVERLAY_REJECTED BENCHMARK_MODIFIED""".split())
    assert bg.BENCHMARK_AWARE_CODE == "BENCHMARK_AWARE_CODE"
    for vocabulary in (bg.EXPORT_REFUSAL_CODES, bg.CLEANUP_CODES, bg.VENV_VIOLATION_CODES, bg.ERROR_CODES):
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
