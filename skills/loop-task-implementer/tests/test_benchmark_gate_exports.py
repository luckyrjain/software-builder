"""Tests for the C4c-1 filesystem and git pieces of `benchmark_gate.py`: `export_tree`, tree hash and seal,
`cleanup_root` / `claim_root`, and the `export` / `cleanup` CLIs.

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
# CLI and vocabularies
# ---------------------------------------------------------------------------

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
        """COMMIT_INVALID COMMIT_NOT_FOUND REPO_UNREADABLE DEST_REJECTED GIT_FAILED GIT_TIMEOUT GIT_OUTPUT_TOO_LARGE TREE_UNREADABLE
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
