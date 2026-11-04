"""Tests for the C4c-2b pieces of `benchmark_gate.py`: `protected_path_diff` and `token_tripwire`.

Both run against real temporary git repositories (scrubbed environment), because what they guard is git's own record of the two
commits. Design: docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md (`compare`, protected-path diff
and token tripwire).
"""

from __future__ import annotations

import importlib.util
import os
import re
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

BENCH = "benchmarks/bench_orders.py"
BENCH_SRC = b'import hashlib\n\n\ndef test_bench():\n    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(b"x").hexdigest())\n'

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
    """Apply `files` ({path: bytes | str | None (delete) | ("link", target)}) and commit; returns the commit id."""
    for rel, value in (files or {}).items():
        path = repo / rel
        if value is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or path.exists():
            path.unlink()
        if isinstance(value, tuple) and value[0] == "link":
            path.symlink_to(value[1])
            continue
        path.write_bytes(value.encode() if isinstance(value, str) else value)
    git(repo, "add", "-A", "-f")
    git(repo, "commit", "-q", "--allow-empty", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    temp = tmp_path / "tmp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    try:
        bg._require_modern_git()
    except Err as exc:
        shown = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=60).stdout
        found = re.search(r"(\d+)\.(\d+)", shown)
        if exc.code != "GIT_TOO_OLD" or found is None or (int(found[1]), int(found[2])) >= (2, 43):
            raise
        pytest.skip(f"git >= 2.43 is needed: {exc.detail}")
    return temp


@pytest.fixture
def repo(tmp_path):
    r = make_repo(tmp_path)
    base = commit(r, {"src/app/__init__.py": "x = 1\n", "README.md": "r\n", BENCH: BENCH_SRC, "tests/test_a.py": "def test_a(): pass\n"})
    return r, base


def pair(repo, files):
    """(repo, base, head) where head applies `files` on top of the base commit."""
    r, base = repo
    return r, base, commit(r, files)


def check(function, repo, files, path=BENCH):
    r, base, head = pair(repo, files)
    return function(r, base, head, path)


def refused(function, repo, files, code, path=BENCH):
    with pytest.raises(Err) as info:
        check(function, repo, files, path)
    assert info.value.code == code, info.value.detail
    return info.value


# --- vocabulary ---

def test_the_diff_codes_are_part_of_the_error_vocabulary():
    assert bg.DIFF_REFUSAL_CODES == ("PROTECTED_PATH_CHANGED", "BENCHMARK_AWARE_CODE")
    assert bg.ERROR_CODES[-2:] == bg.DIFF_REFUSAL_CODES
    assert len(set(bg.ERROR_CODES)) == len(bg.ERROR_CODES)


# --- protected_path_diff ---

PROTECTED = [
    "conftest.py", "tests/conftest.py", "CONFTEST.PY", "sitecustomize.py", "sitecustomize_extra.py", "lib/usercustomize.py",
    "evil.pth", "src/evil.pth", "pytest.ini", "pyproject.toml", "sub/pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "noxfile.py",
    "MANIFEST.in", "requirements.txt", "requirements-dev.txt", "requirements/base.txt", "docs/requirements/x.txt", "constraints.txt",
    "constraints-3.12.txt", "deps.in", "environment.yml", "Pipfile", "Pipfile.lock", "poetry.lock", "uv.lock", "pdm.lock",
    "pylock.toml", "pkg/__pycache__/x.cpython-312.pyc", "foo.pyc", "foo.pyo",
    "json.py", "src/json.py", "hashlib/__init__.py", "src/os/x.py", "Json.py",
    "benchmarks/__init__.py", "benchmarks/helper.py",
]


@pytest.mark.parametrize("path", PROTECTED)
def test_a_protected_path_added_in_the_head_is_refused(repo, path):
    error = refused(bg.protected_path_diff, repo, {path: "x\n"}, "PROTECTED_PATH_CHANGED")
    assert path in error.detail


@pytest.mark.parametrize("path", [
    "README.md", "src/app/__init__.py", "src/app/json.py", "src/app/sitecustomize.txt", "docs/conftest.txt", "tests/test_b.py",
    "benchmarks/sub/helper.py", "requirements.md", "mypkg.pth.bak", "src/app/requirements.py", "pytest.ini.example",
])
def test_ordinary_paths_are_not_protected(repo, path):
    check(bg.protected_path_diff, repo, {path: "x\n"})


def test_the_benchmark_itself_may_differ(repo):
    check(bg.protected_path_diff, repo, {BENCH: BENCH_SRC + b"# more\n"})
    check(bg.protected_path_diff, repo, {BENCH: None})


def test_a_changed_protected_file_is_refused_not_only_an_added_one(tmp_path):
    r = make_repo(tmp_path)
    base = commit(r, {"conftest.py": "a = 1\n", BENCH: BENCH_SRC})
    head = commit(r, {"conftest.py": "a = 2\n"})
    with pytest.raises(Err) as info:
        bg.protected_path_diff(r, base, head, BENCH)
    assert info.value.code == "PROTECTED_PATH_CHANGED"


def test_a_removed_protected_file_is_refused(tmp_path):
    r = make_repo(tmp_path)
    base = commit(r, {"conftest.py": "import time; time.sleep(1)\n", BENCH: BENCH_SRC})
    head = commit(r, {"conftest.py": None})
    with pytest.raises(Err) as info:
        bg.protected_path_diff(r, base, head, BENCH)
    assert info.value.code == "PROTECTED_PATH_CHANGED"


def test_a_type_change_of_a_protected_path_is_refused(tmp_path):
    r = make_repo(tmp_path)
    base = commit(r, {"conftest.py": "a = 1\n", BENCH: BENCH_SRC})
    head = commit(r, {"conftest.py": ("link", "/etc/passwd")})
    with pytest.raises(Err) as info:
        bg.protected_path_diff(r, base, head, BENCH)
    assert info.value.code == "PROTECTED_PATH_CHANGED"


def test_an_unchanged_protected_file_is_not_a_difference(tmp_path):
    r = make_repo(tmp_path)
    base = commit(r, {"conftest.py": "a = 1\n", "setup.py": "s\n", BENCH: BENCH_SRC})
    head = commit(r, {"src/new.py": "y = 2\n"})
    bg.protected_path_diff(r, base, head, BENCH)


def test_the_directory_rule_follows_the_benchmarks_own_directory(repo):
    other = "perf/bench_other.py"
    check(bg.protected_path_diff, repo, {"benchmarks/helper.py": "x\n"}, path=other)  # not beside THIS benchmark
    refused(bg.protected_path_diff, repo, {"perf/helper.py": "x\n"}, "PROTECTED_PATH_CHANGED", path=other)


def test_a_stdlib_shadow_is_only_a_top_level_one(repo):
    check(bg.protected_path_diff, repo, {"src/app/json.py": "x\n", "tests/os.py": "x\n"})
    refused(bg.protected_path_diff, repo, {"src/json/__init__.py": "x\n"}, "PROTECTED_PATH_CHANGED")


def test_the_detail_names_at_most_five_paths_and_counts_all(repo):
    files = {f"p{i}/conftest.py": "x\n" for i in range(8)}
    error = refused(bg.protected_path_diff, repo, files, "PROTECTED_PATH_CHANGED")
    assert error.detail.startswith("protected paths differ, 8, first 5: p0/conftest.py")
    assert "p5/" not in error.detail


def test_a_hostile_path_name_is_escaped_in_the_detail(repo):
    error = refused(bg.protected_path_diff, repo, {"x\ny`z/conftest.py": "x\n"}, "PROTECTED_PATH_CHANGED")
    assert "\n" not in error.detail and "`" not in error.detail


def test_sha256_repositories_work(tmp_path):
    r = make_repo(tmp_path, fmt="sha256")
    base = commit(r, {BENCH: BENCH_SRC})
    head = commit(r, {"conftest.py": "x\n"})
    assert len(base) == 64
    with pytest.raises(Err) as info:
        bg.protected_path_diff(r, base, head, BENCH)
    assert info.value.code == "PROTECTED_PATH_CHANGED"


@pytest.mark.parametrize("function", ["protected_path_diff", "token_tripwire"])
def test_argument_errors_have_their_own_codes(repo, function):
    r, base = repo
    head = commit(r, {"README.md": "again\n"})
    run = getattr(bg, function)
    cases = [
        ((r, "x" * 40, head, BENCH), "COMMIT_INVALID"),
        ((r, base, head.upper(), BENCH), "COMMIT_INVALID"),
        ((r, base, "a" * 64, BENCH), "COMMIT_INVALID"),
        ((r, base, 5, BENCH), "COMMIT_INVALID"),
        ((r, base, "0" * 40, BENCH), "COMMIT_NOT_FOUND"),
        ((r, "0" * 40, head, BENCH), "COMMIT_NOT_FOUND"),
        ((r, base, head, "../bench_x.py"), "OVERLAY_PATH_REJECTED"),
        ((r, base, head, "src/app.py"), "OVERLAY_PATH_REJECTED"),
        ((r, base, head, None), "OVERLAY_PATH_REJECTED"),
        ((r / "nowhere", base, head, BENCH), "REPO_UNREADABLE"),
        ((None, base, head, BENCH), "REPO_UNREADABLE"),
    ]
    for args, code in cases:
        with pytest.raises(Err) as info:
            run(*args)
        assert info.value.code == code, (args, info.value.detail)


def test_a_tree_commit_id_is_not_a_commit(repo):
    r, base = repo
    head = commit(r, {"README.md": "again\n"})
    tree = git(r, "rev-parse", f"{head}^{{tree}}")
    with pytest.raises(Err) as info:
        bg.protected_path_diff(r, base, tree, BENCH)
    assert info.value.code == "COMMIT_NOT_FOUND"


def test_the_repositorys_own_configuration_cannot_run(tmp_path):
    r = make_repo(tmp_path)
    base = commit(r, {".gitattributes": "*.py diff=evil\n", "a.py": "x = 1\n", BENCH: BENCH_SRC})
    head = commit(r, {"a.py": "x = 2\nsys.argv\n"})
    canary = tmp_path / "ran"  # configured only now: the test's own git commands above must not trigger it
    script = tmp_path / "hook.sh"
    script.write_text(f"#!/bin/sh\ntouch {canary}\ncat \"$1\"\n")
    script.chmod(0o755)
    for key in ("diff.external", "diff.evil.textconv", "core.fsmonitor", "core.attributesFile"):
        git(r, "config", key, str(script))
    bg.protected_path_diff(r, base, head, BENCH)
    with pytest.raises(Err) as info:
        bg.token_tripwire(r, base, head, BENCH)
    assert info.value.code == "BENCHMARK_AWARE_CODE"
    assert not canary.exists()


def test_git_failures_are_codes_not_exceptions(repo, monkeypatch):
    r, base = repo
    head = commit(r, {"README.md": "again\n"})

    def boom(self, *args, **kwargs):
        raise RuntimeError("injected")

    monkeypatch.setattr(bg._PrivateGit, "run", boom)
    for function in (bg.protected_path_diff, bg.token_tripwire):
        with pytest.raises(Err) as info:
            function(r, base, head, BENCH)
        assert info.value.code == "GIT_FAILED"


def test_a_malformed_diff_tree_listing_is_a_git_failure(repo, monkeypatch):
    r, base = repo
    head = commit(r, {"README.md": "again\n"})
    for bad in (b":100644 100644 a b M\0README.md", b":100644 100644 a b M\0", b"junk\0README.md\0"):
        monkeypatch.setattr(bg._PrivateGit, "run", lambda self, *args, **kwargs: bad)
        with pytest.raises(Err) as info:
            bg.protected_path_diff(r, base, head, BENCH)
        assert info.value.code == "GIT_FAILED"


# --- token_tripwire ---

@pytest.mark.parametrize("token", ["PYTEST_CURRENT_TEST", "BENCH_RESULT_DIGEST", "BENCH_TRACE_LINES", "os._exit", "sys.argv"])
def test_each_token_added_outside_the_benchmark_is_refused(repo, token):
    error = refused(bg.token_tripwire, repo, {"src/app/run.py": f"import os\nif {token}:\n    pass\n"}, "BENCHMARK_AWARE_CODE")
    assert "src/app/run.py" in error.detail and token in error.detail


def test_the_benchmarks_full_path_is_a_token(repo):
    refused(bg.token_tripwire, repo, {"src/app/run.py": f'P = "{BENCH}"\n'}, "BENCHMARK_AWARE_CODE")


def test_the_benchmarks_file_name_alone_is_not_a_token(repo):
    check(bg.token_tripwire, repo, {"README.md": "run bench_orders.py to measure\n"})  # documentation may name the file


def test_the_tokens_may_appear_in_the_benchmark_file(repo):
    check(bg.token_tripwire, repo, {BENCH: BENCH_SRC + b"# PYTEST_CURRENT_TEST sys.argv os._exit\n"})


def test_a_clean_change_passes(repo):
    check(bg.token_tripwire, repo, {"src/app/__init__.py": "x = 2\n", "README.md": "docs\n"})


def test_a_token_that_was_already_there_is_not_added(tmp_path):
    r = make_repo(tmp_path)
    base = commit(r, {"src/a.py": "import sys\nA = sys.argv\n", BENCH: BENCH_SRC})
    head = commit(r, {"src/a.py": "import sys\nA = sys.argv\nB = 2\n"})
    bg.token_tripwire(r, base, head, BENCH)
    again = commit(r, {"src/a.py": "import sys\nA = sys.argv\nB = 2\nC = sys.argv\n"})
    with pytest.raises(Err) as info:
        bg.token_tripwire(r, base, again, BENCH)
    assert info.value.code == "BENCHMARK_AWARE_CODE"


def test_a_removed_line_with_a_token_is_not_an_addition(tmp_path):
    r = make_repo(tmp_path)
    base = commit(r, {"src/a.py": "A = sys.argv\nB = 1\n", BENCH: BENCH_SRC})
    head = commit(r, {"src/a.py": "B = 1\n", "src/gone.py": "x\n"})
    bg.token_tripwire(r, base, head, BENCH)


def test_a_deleted_file_adds_nothing(tmp_path):
    r = make_repo(tmp_path)
    base = commit(r, {"src/a.py": "A = sys.argv\n", BENCH: BENCH_SRC})
    head = commit(r, {"src/a.py": None})
    bg.token_tripwire(r, base, head, BENCH)


def test_a_symlink_target_is_an_added_line(repo):
    refused(bg.token_tripwire, repo, {"src/link": ("link", "sys.argv")}, "BENCHMARK_AWARE_CODE")


def test_binary_content_and_a_missing_final_newline_are_scanned(repo):
    refused(bg.token_tripwire, repo, {"data.bin": b"\x00\x01\x02 os._exit \x00"}, "BENCHMARK_AWARE_CODE")
    refused(bg.token_tripwire, repo, {"src/a.py": b"x = 1\ny = sys.argv"}, "BENCHMARK_AWARE_CODE")


def test_a_mode_only_change_and_an_empty_file_are_fine(tmp_path):
    r = make_repo(tmp_path)
    base = commit(r, {"run.sh": "x\n", BENCH: BENCH_SRC})
    os.chmod(r / "run.sh", 0o755)
    git(r, "update-index", "--chmod=+x", "run.sh")
    git(r, "commit", "-q", "-m", "mode")
    head = commit(r, {"empty.txt": ""})
    bg.token_tripwire(r, base, head, BENCH)


def test_added_lines_that_look_like_patch_syntax_do_not_confuse_the_parser(repo):
    # The second file's header is forged inside the first file; the token after it must still be charged to the first file.
    forged = f"+++ b/{BENCH}\n--- a/{BENCH}\n@@ -1 +1 @@\ndiff --git a/{BENCH} b/{BENCH}\nsys.argv\n"
    error = refused(bg.token_tripwire, repo, {"src/forged.py": forged}, "BENCHMARK_AWARE_CODE")
    assert "src/forged.py" in error.detail


def test_a_token_after_a_forged_hunk_header_is_still_found(repo):
    refused(bg.token_tripwire, repo, {"src/forged.py": "@@ -0,0 +1,2 @@\n--- a/x\nsys.argv\n"}, "BENCHMARK_AWARE_CODE")


@pytest.mark.parametrize("name", ['we ird.py', 'tab\tname.py', 'quo"te.py', "back\\slash.py", "ünïcode.py", "new\nline.py"])
def test_awkward_file_names_are_charged_to_the_right_path(repo, name):
    if os.name != "posix":
        pytest.skip("POSIX file names")
    error = refused(bg.token_tripwire, repo, {f"src/{name}": "x = sys.argv\n"}, "BENCHMARK_AWARE_CODE")
    assert error.detail.startswith("benchmark-aware patterns added outside the benchmark, 1, first 1:")


def test_a_benchmark_named_look_alike_elsewhere_is_scanned(repo):
    refused(bg.token_tripwire, repo, {"other/benchmarks/bench_orders.py": "x = sys.argv\n"}, "BENCHMARK_AWARE_CODE")


def test_many_files_and_hits_are_counted_and_truncated(repo):
    files = {f"src/m{i}.py": "x = sys.argv\n" for i in range(9)}
    error = refused(bg.token_tripwire, repo, files, "BENCHMARK_AWARE_CODE")
    assert error.detail.startswith("benchmark-aware patterns added outside the benchmark, 9, first 5:")


def test_two_tokens_in_one_file_are_two_hits(repo):
    error = refused(bg.token_tripwire, repo, {"src/a.py": "sys.argv\nos._exit(0)\n"}, "BENCHMARK_AWARE_CODE")
    assert error.detail.startswith("benchmark-aware patterns added outside the benchmark, 2, first 2:")


def test_a_patch_over_the_output_cap_is_an_environment_error(repo, monkeypatch):
    monkeypatch.setattr(bg, "_GIT_OUTPUT_CAP", 200)
    r, base = repo
    head = commit(r, {"src/big.py": "x = 1\n" * 100})
    with pytest.raises(Err) as info:
        bg.token_tripwire(r, base, head, BENCH)
    assert info.value.code == "GIT_OUTPUT_TOO_LARGE"


# --- the patch parser on its own ---

def test_added_lines_follow_the_hunk_counts():
    patch = (b"diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n@@ -1,2 +1,2 @@\n-old1\n-old2\n+new1\n+new2\n"
             b"\\ No newline at end of file\n@@ -9 +9,0 @@\n-gone\n@@ -20,0 +21 @@\n+tail\n")
    assert list(bg._added_lines(patch)) == [("f.py", 1, b"new1"), ("f.py", 2, b"new2"), ("f.py", 21, b"tail")]


@pytest.mark.parametrize("patch", [
    b"diff --git a/f.py b/f.py\n@@ -1 +1 @@\n-a\n",          # truncated hunk
    b"diff --git a/f.py b/f.py\n@@ -1 +1 @@\n-a\n x\n",     # a context line where -U0 has none
    b"diff --git a/f.py b/f.py\n@@ nonsense @@\n",
    b"diff --git nonsense\n",
    b'diff --git "a/\\q" "b/\\q"\n',
    b'diff --git "a/\\40" "b/\\40"\n',
])
def test_a_malformed_patch_is_a_git_failure(patch):
    with pytest.raises(Err) as info:
        list(bg._added_lines(patch))
    assert info.value.code == "GIT_FAILED"


def test_header_paths_are_decoded():
    assert bg._header_path(b"diff --git a/src/x.py b/src/x.py") == "src/x.py"
    assert bg._header_path(b'diff --git "a/t\\tab.py" "b/t\\tab.py"') == "t\tab.py"
    assert bg._header_path(b'diff --git "a/\\303\\274.py" "b/\\303\\274.py"') == "ü.py"
    assert bg._header_path(b'diff --git "a/q\\"x.py" "b/q\\"x.py"') == 'q"x.py'


# --- round 1: rules, evidence, shared entry, ancestry ---

@pytest.mark.parametrize("path", [
    "json.so", "json.cpython-312-darwin.so", "json.abi3.so", "json.pyd", "_thread.so", "src/json.cpython-312-x86_64-linux-gnu.so",
    "Json.SO",
])
def test_a_compiled_extension_that_shadows_the_standard_library_is_refused(repo, path):
    refused(bg.protected_path_diff, repo, {path: b"\x7fELF"}, "PROTECTED_PATH_CHANGED")


@pytest.mark.parametrize("path", ["json.md", "json.txt", "json.pyi", "pkg/json.so", "src/pkg/json.so", "myjson.so", "json.a.b.so"])
def test_other_files_named_like_a_standard_library_module_are_not_shadows(repo, path):
    check(bg.protected_path_diff, repo, {path: b"x"})


def test_the_benchmark_directory_rule_ignores_case(repo):
    refused(bg.protected_path_diff, repo, {"Benchmarks/__init__.py": "x\n"}, "PROTECTED_PATH_CHANGED")
    refused(bg.protected_path_diff, repo, {"BENCHMARKS/helper.py": "x\n"}, "PROTECTED_PATH_CHANGED")


def test_the_error_carries_structured_hits_for_the_protected_paths(repo):
    error = refused(bg.protected_path_diff, repo, {"conftest.py": "x\n", "json.py": "y\n"}, "PROTECTED_PATH_CHANGED")
    assert {hit["path"] for hit in error.hits} == {"conftest.py", "json.py"}
    assert all(set(hit) == {"path", "reason"} and hit["reason"] for hit in error.hits)


def test_the_error_carries_the_token_the_line_number_and_the_line(repo):
    error = refused(bg.token_tripwire, repo, {"src/run.py": "a = 1\nb = 2\nimport sys\nargs = sys.argv\n"}, "BENCHMARK_AWARE_CODE")
    assert error.hits == [{"path": "src/run.py", "token": "sys.argv", "line_number": 4, "line": "args = sys.argv"}]


def test_line_numbers_follow_the_new_file_across_hunks(tmp_path):
    r = make_repo(tmp_path)
    base = commit(r, {"src/a.py": "".join(f"l{i}\n" for i in range(1, 31)), BENCH: BENCH_SRC})
    head = commit(r, {"src/a.py": "".join(f"l{i}\n" for i in range(1, 31)).replace("l5\n", "l5\nsys.argv\n").replace("l25\n", "os._exit\nl25\n")})
    with pytest.raises(Err) as info:
        bg.token_tripwire(r, base, head, BENCH)
    assert [(h["token"], h["line_number"]) for h in info.value.hits] == [("sys.argv", 6), ("os._exit", 26)]


def test_a_long_path_does_not_hide_the_token_in_the_detail(repo):
    path = "src/" + "very_long_directory_name/" * 6 + "module_file.py"
    error = refused(bg.token_tripwire, repo, {path: "x = sys.argv\n"}, "BENCHMARK_AWARE_CODE")
    assert error.detail.split("first 1: ")[1].startswith("sys.argv in ")


def test_one_hit_per_path_and_token_but_every_distinct_pair(repo):
    error = refused(bg.token_tripwire, repo, {"src/a.py": "sys.argv\nsys.argv\nos._exit\n", "src/b.py": "sys.argv\n"}, "BENCHMARK_AWARE_CODE")
    assert [(h["path"], h["token"], h["line_number"]) for h in error.hits] == [("src/a.py", "sys.argv", 1), ("src/a.py", "os._exit", 3),
                                                                              ("src/b.py", "sys.argv", 1)]


def test_a_hostile_line_is_escaped_in_the_hits(repo):
    error = refused(bg.token_tripwire, repo, {"src/a.py": "x = sys.argv  `rm -rf`\x1b[31m\n"}, "BENCHMARK_AWARE_CODE")
    line = error.hits[0]["line"]
    assert "`" not in line and "\x1b" not in line and "\n" not in line


def test_diff_checks_passes_a_clean_change(repo):
    check(bg.diff_checks, repo, {"src/app/__init__.py": "x = 2\n"})


def test_diff_checks_reports_a_protected_path_alone(repo):
    error = refused(bg.diff_checks, repo, {"conftest.py": "x\n"}, "PROTECTED_PATH_CHANGED")
    assert [hit["path"] for hit in error.hits] == ["conftest.py"]


def test_diff_checks_reports_the_tripwire_alone(repo):
    refused(bg.diff_checks, repo, {"src/a.py": "sys.argv\n"}, "BENCHMARK_AWARE_CODE")


def test_diff_checks_puts_the_human_only_code_before_the_fixable_one(repo):
    error = refused(bg.diff_checks, repo, {"conftest.py": "x\n", "src/a.py": "sys.argv\n"}, "BENCHMARK_AWARE_CODE")
    assert [hit["path"] for hit in error.hits] == ["src/a.py"]


def test_diff_checks_uses_one_private_git(repo, monkeypatch):
    r, base = repo
    head = commit(r, {"README.md": "again\n"})
    entered = []
    real_enter = bg._PrivateGit.__enter__

    def counting(self):
        entered.append(1)
        return real_enter(self)

    monkeypatch.setattr(bg._PrivateGit, "__enter__", counting)
    bg.diff_checks(r, base, head, BENCH)
    assert len(entered) == 1


def test_diff_checks_validates_its_arguments_like_the_others(repo):
    r, base = repo
    head = commit(r, {"README.md": "again\n"})
    for args, code in [((r, "x" * 40, head, BENCH), "COMMIT_INVALID"), ((r, base, head, "src/app.py"), "OVERLAY_PATH_REJECTED"),
                       ((r, base, "0" * 40, BENCH), "COMMIT_NOT_FOUND"), ((r / "nowhere", base, head, BENCH), "REPO_UNREADABLE")]:
        with pytest.raises(Err) as info:
            bg.diff_checks(*args)
        assert info.value.code == code


def test_is_ancestor_answers_for_a_line_of_history(tmp_path):
    r = make_repo(tmp_path)
    one = commit(r, {"a": "1\n"})
    two = commit(r, {"a": "2\n"})
    assert bg.is_ancestor(r, one, two) is True
    assert bg.is_ancestor(r, one, one) is True
    assert bg.is_ancestor(r, two, one) is False


def test_is_ancestor_is_false_for_a_sibling_branch_and_true_through_a_merge(tmp_path):
    r = make_repo(tmp_path)
    root = commit(r, {"a": "1\n"})
    git(r, "checkout", "-q", "-b", "side")
    side = commit(r, {"b": "1\n"})
    git(r, "checkout", "-q", "main")
    main = commit(r, {"c": "1\n"})
    assert bg.is_ancestor(r, side, main) is False
    git(r, "merge", "-q", "--no-edit", "side")
    merged = git(r, "rev-parse", "HEAD")
    assert bg.is_ancestor(r, side, merged) is True and bg.is_ancestor(r, root, merged) is True


def test_is_ancestor_works_in_a_sha256_repository(tmp_path):
    r = make_repo(tmp_path, fmt="sha256")
    one = commit(r, {"a": "1\n"})
    two = commit(r, {"a": "2\n"})
    assert bg.is_ancestor(r, one, two) is True and bg.is_ancestor(r, two, one) is False


def test_is_ancestor_validates_and_never_leaks_a_bare_exception(repo, monkeypatch):
    r, base = repo
    with pytest.raises(Err) as info:
        bg.is_ancestor(r, base, "z" * 40)
    assert info.value.code == "COMMIT_INVALID"
    with pytest.raises(Err) as info:
        bg.is_ancestor(r, base, "0" * 40)
    assert info.value.code == "COMMIT_NOT_FOUND"
    real = bg._PrivateGit._run_raw
    monkeypatch.setattr(bg._PrivateGit, "_run_raw",
                        staticmethod(lambda args, *rest: (128, b"fatal: boom") if args[0] == "merge-base" else real(args, *rest)))
    with pytest.raises(Err) as info:
        bg.is_ancestor(r, base, base)
    assert info.value.code == "GIT_FAILED"
