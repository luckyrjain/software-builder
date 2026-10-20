"""Tests for the C4c-1a git pieces of `benchmark_gate.py`: `export_tree`, the read-only tree walk,
and the `export` / `fixed-parent` CLIs. (`seal_tree`, `unseal_tree` and `cleanup_root` are C4c-1b.)

Everything git-related runs against real temporary repositories (no network, hooks or signing); hostile trees (`.git`
entries, `..`, case collisions, escaping symlinks) are built with `git mktree`, since `git add` refuses them.
Design: docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md (APIs table, `compare` row).
"""

from __future__ import annotations

import concurrent.futures
import importlib.util
import json
import os
import re
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


# --- the read-only tree walk and shared fixtures ---

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





def dead_pid() -> int:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=60)
    return child.pid

@pytest.fixture
def root(repo_a):
    repo, sha = repo_a
    bg.export_tree(repo, sha, dest(), owner_pid=dead_pid())
    return Path(dest()).parent









# --- CLI and vocabularies ---

def test_export_cli_prints_the_path_records_the_owner_and_rejects_bad_usage(repo_a, capsys):
    repo, sha = repo_a
    assert bg.main(["export", "--repo", str(repo), "--commit", sha, "--dest", dest(), "--owner-pid", "1"]) == 0
    cap = capsys.readouterr()
    assert cap.out == dest() + "\n" and cap.err == ""
    assert json.loads((Path(dest()).parent / bg._MARKER_NAME).read_text())["pid"] == 1
    for argv in (["export"], ["export", "--repo", "r", "--commit", sha], ["fixed-parent", "--bogus"]):
        assert bg.main(argv) == 2

def test_code_vocabularies_are_pinned():
    assert bg.EXPORT_REFUSAL_CODES == tuple(
        "EXPORT_PATH_REJECTED EXPORT_PATH_COLLISION EXPORT_ENTRY_MODE EXPORT_TOO_LARGE EXPORT_SYMLINK_ESCAPES EXPORT_VERIFY_FAILED".split())
    assert bg.ERROR_CODES == tuple(
        """COMMIT_INVALID COMMIT_NOT_FOUND REPO_UNREADABLE DEST_REJECTED GIT_FAILED GIT_TOO_OLD GIT_TIMEOUT GIT_OUTPUT_TOO_LARGE TREE_UNREADABLE
        TREE_TOO_LARGE MARKER_MISSING MARKER_INVALID""".split())
    for vocabulary in (bg.EXPORT_REFUSAL_CODES, bg.ERROR_CODES):
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
    fake.write_text("#!/bin/sh\nif [ \"$1\" = -c ]; then shift 6; fi\nif [ \"$1\" = hang ]; then sleep 20; fi\nyes x | head -c 5000\n")
    fake.chmod(0o755)
    monkeypatch.setattr(shutil, "which", lambda *a, **k: str(fake))
    monkeypatch.setattr(bg, "_GIT_TIMEOUT_SECONDS", 1)
    env = bg._git_env(str(tmp_path))
    with pytest.raises(Err) as info:
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

def test_the_fixed_parent_is_per_user_private_and_checked_by_export(repo_a, root, capsys):
    repo, sha = repo_a
    parent = bg.fixed_parent()
    assert parent.name == f"software-builder-bench-{os.getuid()}" and stat.S_IMODE(parent.stat().st_mode) == 0o700
    assert bg.main(["fixed-parent"]) == 0 and capsys.readouterr().out == f"{parent}\n"
    parent.chmod(0o777)  # another user could now plant entries: both sides refuse, with codes and no traceback
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest("other"))
    assert info.value.code == "DEST_REJECTED"
    parent.chmod(0o700)
    moved = parent.with_name("moved")
    parent.rename(moved)
    parent.symlink_to(moved)  # a symlinked fixed parent is not a directory
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest("other"))
    assert info.value.code == "DEST_REJECTED"

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
    assert bg.export_tree(repo, sha, dest("base")).is_dir() and bg._read_marker(str(root_dir))["pid"] == os.getpid()


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
        assert bg._read_marker(str(Path(dest()).parent.with_name(f"bench-fail{attempt:04d}")))["pid"] > 0  # intact





@pytest.mark.parametrize("planted", ["file", "directory"])
def test_a_failed_export_never_removes_a_sidecar_it_did_not_write(repo_a, monkeypatch, planted):
    repo, sha = repo_a
    bg.export_tree(repo, sha, dest("base"))
    sidecar = Path(dest("head") + ".export.json")
    sidecar.mkdir() if planted == "directory" else sidecar.write_text("planted")
    monkeypatch.setattr(bg, "_verify_export", lambda *a: (_ for _ in ()).throw(Err("EXPORT_VERIFY_FAILED", "forced")))
    with pytest.raises(Err) as info:
        bg.export_tree(repo, sha, dest("head"))
    assert info.value.code == "EXPORT_VERIFY_FAILED" and not Path(dest("head")).exists()  # the original error, not an OSError
    assert sidecar.is_dir() if planted == "directory" else sidecar.read_text() == "planted"


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
    assert info.value.code == "DEST_REJECTED" and not list(Path(dest()).parent.iterdir()) if replaced == "root" else info.value.code == "DEST_REJECTED"
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














