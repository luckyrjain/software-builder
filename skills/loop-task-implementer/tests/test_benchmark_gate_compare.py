"""C4d-3 ``compare`` and ``run-once``: the tests of the whole feature (spec 4), in file order: vocabularies, result assembly, the dir-fd result
writer (pure, no child, no git); the shared fixtures (a real git repository, two exports, two fake-interpreter venvs, ``fake_trace_builder``);
``fingerprint_tree``, ``interpreter_pin``, ``dependency_parity``, ``verify_export_against_commit``; the pipeline steps 1 to 13 with fake
children and stubbed ``trace_paired``/``measure_paired`` (raise-versus-return rows, the stage table, the precedence list, host checks, step 12);
the CLI (exit codes, the ``RESULT:`` line, the crash contract); two real-pytest rows and the real-child tamper rows; and the T7 pins at the
end (both commands registered, the CLI path uses the default seams, the generated salt is random and recorded).

The pipeline tests drive ``_compare_impl`` through the ``Case`` helper with its seams (``argv_builder``, ``load_probe``, ``order_salt``,
``interpreter_of``, ``min_base_ns``); only the real-pytest rows use the default ``argv_builder``. One ``compare`` per fixture: a second call
on the same exports meets the step-4 untracked-file check. Design: docs/superpowers/specs/2026-11-06-c4d3-compare-and-run-once-design.md.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import types
import venv
from fractions import Fraction
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_gate.py"
spec = importlib.util.spec_from_file_location("benchmark_gate_compare_under_test", SCRIPT)
bg = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bg
spec.loader.exec_module(bg)

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX harness")

REJECTED = "GATE_REJECTED ISOLATION_REJECTED PROTECTED_PATH_CHANGED BENCHMARK_AWARE_CODE DIFF_UNCHECKABLE EXPORT_REJECTED OVERLAY_REJECTED " \
           "BENCHMARK_MODIFIED LINT_REJECTED TRACE_MISMATCH BASE_NONZERO_EXIT DIGEST_MISSING DIGEST_UNSTABLE WORKLOAD_TOO_SHORT".split()
NOT_IMPROVED = "HEAD_NONZERO_EXIT HEAD_TIMEOUT HEAD_OUTPUT_TOO_LARGE DIGEST_MISMATCH BELOW_HALF_THRESHOLD".split()
INCONCLUSIVE = "UNSUPPORTED_PLATFORM HOST_BUSY_START HOST_BUSY_END TRACE_UNAVAILABLE BASE_TIMEOUT BASE_OUTPUT_TOO_LARGE NOISY INCONSISTENT " \
               "BORDERLINE INVALID_INPUT".split()


# --- vocabularies ---

def test_vocabularies_are_pinned_exactly():
    expected = {r: "REJECTED" for r in REJECTED}
    expected.update({r: "NOT_IMPROVED" for r in NOT_IMPROVED})
    expected.update({r: "INCONCLUSIVE" for r in INCONCLUSIVE})
    expected["IMPROVED_CLEAR"] = "IMPROVED"
    assert bg.COMPARE_RESULT_OF_REASON == expected and len(expected) == 30
    assert bg.COMPARE_RESULTS == frozenset({"IMPROVED", "NOT_IMPROVED", "INCONCLUSIVE", "REJECTED"})
    assert set(bg.COMPARE_RESULT_OF_REASON.values()) == bg.COMPARE_RESULTS
    assert bg.ISOLATION_DETAILS == tuple(
        """ROOT_HAS_GIT BIN_NOT_ISOLATED NOT_PROVISIONED INTERPRETER_DIFFERS INTERPRETER_WRITABLE HARNESS_FILE_UNDER_ROOT TRACKED_FILE_DIFFERS
        UNTRACKED_PYTHON_FILE DEPENDENCY_PARITY BENCHMARK_BYTES_DIFFER VENV_NOT_ISOLATED VENV_HOOK_REJECTED SNAPSHOT_CHANGED INTERPRETER_CHANGED
        EXPORT_CHANGED VENV_CHANGED HASH_UNREADABLE FINGERPRINT_FAILED""".split())
    assert bg.COMPARE_STAGES == ("pre_overlay", "overlaid", "ran")
    assert bg.Side._fields == ("root", "commit", "bin_dir", "snapshot", "snapshot_sha256", "interpreter_sha256")
    union = set("GATE_MISSING KEY_MISSING KEY_UNKNOWN TYPE_REJECTED PATH_REJECTED SYMBOL_REJECTED COMMAND_REJECTED BOUNDS_REJECTED "
                "BUDGET_REJECTED".split())
    for part in (bg.ISOLATION_DETAILS, bg.VIOLATION_CODES, bg.OVERLAY_REFUSAL_CODES, bg.DIFF_REFUSAL_CODES, bg.TRACE_FAILURE_KINDS,
                 bg.MEASURE_REFUSAL_CODES, bg.EXPORT_REFUSAL_CODES,
                 "COMMIT_INVALID COMMIT_NOT_FOUND REPO_UNREADABLE DEST_REJECTED GIT_FAILED GIT_TOO_OLD GIT_TIMEOUT GIT_OUTPUT_TOO_LARGE "
                 "TREE_UNREADABLE TREE_TOO_LARGE SEAL_FAILED".split(), tuple(bg.COMPARE_RESULT_OF_REASON)):
        union.update(part)
    assert isinstance(bg.COMPARE_DETAIL_TOKENS, tuple) and set(bg.COMPARE_DETAIL_TOKENS) == union


def test_every_detail_token_is_ascii_and_unique():
    tokens = bg.COMPARE_DETAIL_TOKENS
    assert len(set(tokens)) == len(tokens)
    assert all(t.isascii() and t.replace("_", "").isalnum() and bg.escape_diagnostic(t) == t for t in tokens)
    for name in ("BASE_NOT_ANCESTOR",):
        assert name not in tokens  # it raises; it is never a result detail


def test_error_codes_gain_exactly_base_not_ancestor_appended():
    assert bg.ERROR_CODES[-1] == "BASE_NOT_ANCESTOR" and bg.ERROR_CODES.count("BASE_NOT_ANCESTOR") == 1
    assert bg.ERROR_CODES[-3:-1] == bg.TRACE_REFUSAL_CODES
    assert "BASE_NOT_ANCESTOR" not in bg.CLEANUP_CODES


# --- result assembly ---

KEYS = """schema result reason detail kind stage trace_mismatch_seen trace_fault untrusted_text benchmark_origin improvement ratios
mad_over_median n repeats min_improvement max_noise base_median_ns head_median_ns base_ns head_ns order order_salt digest base_commit head_commit
benchmark_sha256 gate_sha256 harness_sha256 argv trace python interpreter_home interpreter_writable loadavg cpu_count host_check attempt side
phase partial""".split()


def test_result_assembly_from_a_synthetic_verdict():
    verdict = bg._Verdict("REJECTED", "BASE_NONZERO_EXIT", "nonzero", kind="nonzero", stage="ran")
    result = bg._result_dict(verdict, {"base_commit": "a" * 40, "attempt": 1, "interpreter_writable": False})
    assert set(result) == set(KEYS) and len(KEYS) == len(set(KEYS)) == len(bg.COMPARE_RESULT_KEYS)
    assert result["schema"] == "software-builder-bench-compare-v1"
    assert (result["result"], result["reason"], result["detail"], result["kind"], result["stage"]) == (
        "REJECTED", "BASE_NONZERO_EXIT", "nonzero", "nonzero", "ran")
    assert result["base_commit"] == "a" * 40 and result["attempt"] == 1 and result["interpreter_writable"] is False
    assert result["untrusted_text"] == []
    absent = set(KEYS) - {"schema", "result", "reason", "detail", "kind", "stage", "base_commit", "attempt", "interpreter_writable",
                          "untrusted_text"}
    assert all(result[k] is None for k in absent)
    assert isinstance(verdict, Exception) and not isinstance(verdict, bg.BenchmarkGateError)

    extra = {"improvement": Fraction(1, 4), "ratios": [Fraction(3, 4), Fraction(9, 10)], "mad_over_median": Fraction(1, 8),
             "trace": {"base": {"kind": "lines", "value": 3, "interpreter": "3.12 cpython"}}, "partial": {"order": ["base", "head"]}}
    result = bg._result_dict(bg._Verdict("IMPROVED", "IMPROVED_CLEAR", "", stage="ran", extra=extra), {})
    assert result["improvement"] == 0.25 and result["ratios"] == [0.75, 0.9] and result["mad_over_median"] == 0.125
    text = json.dumps(result, ensure_ascii=True, allow_nan=False)
    assert text.isascii() and json.loads(text)["ratios"] == [0.75, 0.9]
    assert bg._result_bytes(result) == (text + "\n").encode("ascii") or json.loads(bg._result_bytes(result)) == json.loads(text)


def test_result_assembly_rejects_internal_inconsistencies():
    ok = {"stage": "ran"}
    with pytest.raises(ValueError):
        bg._result_dict(bg._Verdict("IMPROVED", "BELOW_HALF_THRESHOLD", "", **ok), {})  # result does not belong to the reason
    with pytest.raises(ValueError):
        bg._result_dict(bg._Verdict("REJECTED", "NOT_A_REASON", "", **ok), {})
    with pytest.raises(ValueError):
        bg._result_dict(bg._Verdict("REJECTED", "GATE_REJECTED", "", stage="later"), {})
    with pytest.raises(ValueError):
        bg._result_dict(bg._Verdict("REJECTED", "GATE_REJECTED", "", extra={"surprise": 1}, **ok), {})
    with pytest.raises(ValueError):
        bg._result_dict(bg._Verdict("REJECTED", "GATE_REJECTED", "", **ok), {"result": "IMPROVED"})  # the verdict owns these keys
    with pytest.raises(ValueError):
        bg._result_bytes({"x": float("nan")})


def test_attacker_text_appears_only_in_untrusted_text_and_is_capped():
    hostile = [f"line {i}\n```\x00# heading | table é " + "A" * 500 for i in range(30)]
    verdict = bg._Verdict("REJECTED", "ISOLATION_REJECTED", "TRACKED_FILE_DIFFERS 3", stage="pre_overlay",
                          extra={"untrusted_text": hostile})
    common = {"python": "/tmp/`evil`\n# xé" + "p" * 500, "interpreter_home": "> home\x00" + "h" * 500}
    result = bg._result_dict(verdict, common)
    assert len(result["untrusted_text"]) == 20
    for entry in result["untrusted_text"]:
        assert entry == bg.escape_diagnostic(entry, 200) and len(entry) <= 200
        assert "`" not in entry and "\n" not in entry and "\x00" not in entry and entry.isascii()
    assert result["detail"] == "TRACKED_FILE_DIFFERS 3"
    assert result["python"] == bg.escape_diagnostic(common["python"], 200) and len(result["python"]) <= 200
    assert result["interpreter_home"] == bg.escape_diagnostic(common["interpreter_home"], 200)
    assert result["python"].isascii() and "`" not in result["python"] and result["interpreter_home"].startswith("'")
    # hostile text smuggled into the detail is escaped as well, and no other field carries any
    result = bg._result_dict(bg._Verdict("REJECTED", "ISOLATION_REJECTED", "x\n`y`é", stage="ran"), {})
    assert result["detail"] == bg.escape_diagnostic("x\n`y`é", 200) and result["untrusted_text"] == []
    assert json.dumps(result, ensure_ascii=True).isascii()


# --- out_path validation ---

@pytest.fixture
def outdir(tmp_path):
    directory = tmp_path / "out"
    directory.mkdir()
    directory.chmod(0o700)
    return directory


@posix_only
def test_out_path_rejections(tmp_path, outdir):
    forbidden = []
    for name in ("base-root", "head-root", "base-bin", "head-bin", "base-venv", "head-venv", "dispatch"):
        path = tmp_path / name
        path.mkdir()
        forbidden.append(str(path))
    forbidden.append(str(tmp_path / "snap.json"))
    (tmp_path / "snap.json").write_text("{}")
    good = str(outdir / "result.json")
    ident, name = bg._validate_out_path(good, forbidden)
    st = os.stat(outdir)
    assert ident == (st.st_dev, st.st_ino) and name == "result.json"

    def rejects(path, forbidden=forbidden):
        with pytest.raises(bg.BenchmarkGateError) as exc:
            bg._validate_out_path(path, forbidden)
        assert exc.value.code == "MEASURE_ARGS_INVALID", path

    rejects("result.json")                                            # relative
    rejects(str(outdir) + "/../out/result.json")                       # not normalized
    rejects(str(tmp_path / "missing" / "result.json"))                 # directory missing
    rejects("")
    rejects(None)
    rejects(str(outdir) + "/")                                         # no file name
    rejects(str(outdir / "a\0b"))
    rejects(str(outdir / ("x" * 300)))
    rejects(str(outdir / ".."))
    (outdir / "taken").write_text("x")
    rejects(str(outdir / "taken"))                                     # lexists
    os.symlink("/nonexistent-target", outdir / "dangling")
    rejects(str(outdir / "dangling"))                                  # lexists is true for a dangling link too
    # directory not owned by the user (simulated), group- or other-writable
    for mode in (0o770, 0o707, 0o702):
        outdir.chmod(mode)
        rejects(good)
    outdir.chmod(0o700)
    real_uid = os.getuid()
    original = os.getuid
    try:
        os.getuid = lambda: real_uid + 1
        rejects(good)
    finally:
        os.getuid = original
    # under a forbidden path, by realpath
    for path in forbidden[:7]:
        os.chmod(path, 0o700)
        rejects(os.path.join(path, "result.json"))
        link = tmp_path / ("link-" + os.path.basename(path))
        os.symlink(path, link)
        rejects(str(link / "result.json"))                             # a symlinked directory too
    rejects(str(tmp_path / "snap.json"))                               # the snapshot itself (lexists as well)
    rejects(str(outdir / "x.json"), forbidden=[str(outdir)])           # the directory itself is forbidden
    # a symlinked out directory is refused even when it points somewhere harmless
    os.symlink(outdir, tmp_path / "outlink")
    rejects(str(tmp_path / "outlink" / "result.json"))
    assert bg._validate_out_path(good, forbidden)[1] == "result.json"  # unchanged by all of the above


# --- the dir-fd writer ---

def test_dirfd_writer_creates_exclusively_and_checks_identities(tmp_path, outdir, monkeypatch):
    out = str(outdir / "result.json")
    ident, name = bg._validate_out_path(out, [])
    data = b'{"a": 1}\n'
    digest = bg._write_result(out, ident, name, data)
    assert digest == hashlib.sha256(data).hexdigest() and (outdir / "result.json").read_bytes() == data
    assert os.listdir(outdir) == ["result.json"] and os.stat(out).st_mode & 0o777 == 0o600  # temp unlinked, owner-only

    # a target planted between validation and write: an error, never an overwrite; the temp is gone
    out2 = str(outdir / "second.json")
    ident, name = bg._validate_out_path(out2, [])
    (outdir / "second.json").write_text("planted")
    with pytest.raises(bg.BenchmarkGateError) as exc:
        bg._write_result(out2, ident, name, data)
    assert exc.value.code == "MEASURE_FAILED" and (outdir / "second.json").read_text() == "planted"
    assert sorted(os.listdir(outdir)) == ["result.json", "second.json"]

    # a planted symlink at the name is not followed
    out3 = str(outdir / "third.json")
    ident, name = bg._validate_out_path(out3, [])
    os.symlink(tmp_path / "elsewhere", outdir / "third.json")
    with pytest.raises(bg.BenchmarkGateError):
        bg._write_result(out3, ident, name, data)
    assert not (tmp_path / "elsewhere").exists()

    # a swapped directory: same path, different (dev, ino)
    out4 = str(outdir / "fourth.json")
    ident, name = bg._validate_out_path(out4, [])
    moved = tmp_path / "moved"
    os.rename(outdir, moved)
    outdir.mkdir()
    outdir.chmod(0o700)
    with pytest.raises(bg.BenchmarkGateError) as exc:
        bg._write_result(out4, ident, name, data)
    assert exc.value.code == "MEASURE_FAILED" and os.listdir(outdir) == []
    # the directory replaced by a symlink to the original: O_NOFOLLOW refuses it
    outdir.rmdir()
    os.symlink(moved, outdir)
    with pytest.raises(bg.BenchmarkGateError):
        bg._write_result(out4, ident, name, data)
    os.unlink(outdir)
    os.rename(moved, outdir)

    # a failing os.link leaves no temp; os.replace/os.rename are never used for the result
    def refuse(*args, **kwargs):
        raise AssertionError("path-based or replacing call")
    out5 = str(outdir / "fifth.json")
    ident, name = bg._validate_out_path(out5, [])
    real_link = os.link
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(28, "no space")))
    before = sorted(os.listdir(outdir))
    with pytest.raises(bg.BenchmarkGateError) as exc:
        bg._write_result(out5, ident, name, data)
    assert exc.value.code == "MEASURE_FAILED" and sorted(os.listdir(outdir)) == before
    monkeypatch.setattr(os, "link", real_link)
    monkeypatch.setattr(os, "replace", refuse)
    monkeypatch.setattr(os, "rename", refuse)
    assert bg._write_result(out5, ident, name, data) == hashlib.sha256(data).hexdigest()

    # the final identity check: a link that lands on a different inode than the written one is an error
    out6 = str(outdir / "sixth.json")
    ident, name = bg._validate_out_path(out6, [])
    real_stat = os.stat
    def lying_stat(path, *args, **kwargs):
        info = real_stat(path, *args, **kwargs)
        if path == out6:
            return os.stat_result((info.st_mode, info.st_ino + 1) + tuple(info)[2:])
        return info
    monkeypatch.setattr(os, "stat", lying_stat)
    with pytest.raises(bg.BenchmarkGateError) as exc:
        bg._write_result(out6, ident, name, data)
    assert exc.value.code == "MEASURE_FAILED"


def test_temp_name_is_random_and_a_planted_temp_is_irrelevant(outdir, monkeypatch):
    seen = []
    real_open = os.open
    def spy(path, flags, mode=0o777, *, dir_fd=None):
        if dir_fd is not None and flags & os.O_CREAT:
            seen.append(path)
        return real_open(path, flags, mode, dir_fd=dir_fd)
    monkeypatch.setattr(os, "open", spy)
    for i in range(2):
        out = str(outdir / f"r{i}.json")
        ident, name = bg._validate_out_path(out, [])
        bg._write_result(out, ident, name, b"{}\n")
    assert len(seen) == 2 and seen[0] != seen[1] and all("/" not in s and s != "r0.json" and s != "r1.json" for s in seen)


# --- T2b0 shared fixtures: a real repository, two exports, two venvs, a fake interpreter prefix -------------------------------------------
# Built per test (``world``), never shared: later tasks mutate the exports and the venvs. Helpers are copied from the exports tests (the
# test modules share nothing; there is no conftest).

GIT_ENV = {
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/nonexistent", "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
}
GIT_FLAGS = ["-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never"]
PYX = f"python{sys.version_info.major}.{sys.version_info.minor}"
PYXY = f"python{sys.version_info.major}{sys.version_info.minor}"
VENV_SHAPES = ("homebrew", "uv", "clt")
DISPATCH_ROOT = "bench-c4d3fix"


def git(cwd, *args, inp=None) -> str:
    done = subprocess.run(["git", *GIT_FLAGS, *args], cwd=cwd, env=GIT_ENV, input=inp, capture_output=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return done.stdout.decode().strip()


def make_commit(repo: Path, files: dict, msg: str) -> str:
    """``files``: {path: str | ("exec", str) | ("link", target)}; staged by path (a gitlink is added separately by the caller)."""
    for rel, value in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, tuple) and value[0] == "link":
            path.symlink_to(value[1])
            continue
        path.write_text(value[1] if isinstance(value, tuple) else value)
        path.chmod(0o755 if isinstance(value, tuple) else 0o644)
    git(repo, "add", "-f", "--", *files)  # not -A: the gitlink has no directory on disk, so -A would drop it from the index
    return msg


def build_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """A sha1 repository with two commits. Tracked in both: a regular file, an executable, a symlink and a gitlink (``vendor/sub``); the
    second commit changes ``src/app/core.py`` and adds ``src/app/extra.py``. Returns ``(repo, base_commit, head_commit)``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "--object-format=sha1")
    make_commit(repo, {"src/app/__init__.py": "", "src/app/core.py": "def f():\n    return 1\n", "tools/run.sh": ("exec", "#!/bin/sh\n"),
                       "link": ("link", "src/app/core.py"), "README.md": "r\n"}, "base")
    git(repo, "update-index", "--add", "--cacheinfo", "160000," + "ab" * 20 + ",vendor/sub")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    make_commit(repo, {"src/app/core.py": "def f():\n    return 2\n", "src/app/extra.py": "y = 1\n"}, "head")
    git(repo, "commit", "-q", "-m", "head")
    return repo, base, git(repo, "rev-parse", "HEAD")


def build_fake_prefix(path: Path) -> Path:
    """A small fake interpreter prefix: the shapes ``interpreter_pin`` has to cover, no real Python in it."""
    (path / "bin").mkdir(parents=True)
    exe = path / "bin" / PYX
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(0o755)
    lib = path / "lib" / PYX
    (lib / "lib-dynload").mkdir(parents=True)
    (lib / "__pycache__").mkdir()
    (lib / "os.py").write_text("# fake stdlib\n")
    (lib / "lib-dynload" / "_fake.so").write_bytes(b"\x7fELF-fake")
    (lib / "__pycache__" / "os.cpython-fake.pyc").write_bytes(b"fake")
    (path / "lib" / f"{PYXY}.zip").write_bytes(b"PK\x05\x06" + b"\0" * 18)
    (path / "lib" / "libpython-fake.dylib").write_bytes(b"fake dylib")
    return path


def build_venv(root: Path, shape: str, prefix: Path, scratch: Path) -> Path:
    """A fresh, pip-less venv at ``root`` whose ``bin/python`` is a SYMLINK into the fake ``prefix``, with one of three ``pyvenv.cfg`` shapes,
    and a pytest-bearing ``.pth`` (the pattern of ``pytest_venv`` in test_benchmark_gate_trace.py) written BEFORE the caller snapshots it.
    homebrew: ``home`` is a symlink path to the prefix's ``bin``. uv: ``version_info`` only, ``home`` a minor-version symlink directory.
    clt: ``home`` is a shim directory holding a symlink to the interpreter. Returns the venv's ``bin`` directory."""
    venv.create(root, with_pip=False, symlinks=True)
    bin_dir = root / "bin"
    real_bin = prefix / "bin"
    if shape == "homebrew":
        home = scratch / "opt" / "python" / "libexec" / "bin"
        home.parent.mkdir(parents=True)
        home.symlink_to(real_bin)
        cfg = f"home = {home}\ninclude-system-site-packages = false\nversion = {sys.version_info.major}.{sys.version_info.minor}.0\n"
    elif shape == "uv":
        parent = scratch / "uv" / "python"
        parent.mkdir(parents=True)
        (parent / f"cpython-{sys.version_info.major}.{sys.version_info.minor}").symlink_to(real_bin)
        home = parent / f"cpython-{sys.version_info.major}.{sys.version_info.minor}"
        cfg = f"home = {home}\nimplementation = CPython\nuv = 0.0.0\nversion_info = {sys.version_info.major}.{sys.version_info.minor}.0\n" \
              "include-system-site-packages = false\n"
    elif shape == "clt":
        home = scratch / "clt" / "usr" / "bin"
        home.mkdir(parents=True)
        (home / PYX).symlink_to(real_bin / PYX)
        cfg = f"home = {home}\ninclude-system-site-packages = false\nversion = {sys.version_info.major}.{sys.version_info.minor}.0\n"
    else:
        raise ValueError(shape)
    (root / "pyvenv.cfg").write_text(cfg)
    for entry in list(bin_dir.iterdir()):
        if entry.is_symlink() and entry.name.startswith("python"):
            entry.unlink()
    (bin_dir / PYX).symlink_to(home / PYX)
    (bin_dir / "python").symlink_to(PYX)
    (bin_dir / "python3").symlink_to(PYX)
    sites = {os.path.dirname(os.path.dirname(sys.modules[name].__file__)) for name in ("pytest", "_pytest", "pluggy", "iniconfig", "packaging")
             if name in sys.modules}
    site = next((root / "lib").glob("python3*/site-packages"))
    (site / "zz_pytest.pth").write_text("\n".join(sorted(sites)) + "\n")
    return bin_dir


class World(types.SimpleNamespace):
    """``repo base head`` (commits) ``prefix`` (fake interpreter) ``dispatch`` (the dispatch root) ``sides`` (name -> SimpleNamespace(commit,
    export, bin, snapshot, shape)) ``interpreter_of`` (a callable for the seam: a bin dir to the fake interpreter path)."""


def build_world(tmp_path: Path, monkeypatch, shapes=("homebrew", "uv")) -> World:
    """Rebuild everything under ``tmp_path``: the fixed parent is redirected there, so nothing touches the real temp directory."""
    temp = tmp_path / "tmp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    try:
        bg._require_modern_git()
    except bg.BenchmarkGateError as exc:
        if exc.code != "GIT_TOO_OLD":
            raise
        pytest.skip(f"git >= 2.43 is needed: {exc.detail}")
    repo, base, head = build_repo(tmp_path)
    prefix = build_fake_prefix(tmp_path / "interp")
    dispatch = bg.fixed_parent() / DISPATCH_ROOT
    sides = {}
    for name, commit, shape in (("base", base, shapes[0]), ("head", head, shapes[1])):
        export = bg.export_tree(repo, commit, dispatch / name)
        bin_dir = build_venv(dispatch / f"venv-{name}", shape, prefix, tmp_path / f"{name}-{shape}")
        snapshot = tmp_path / f"{name}-venv.json"
        bg.snapshot_venv(bin_dir, snapshot)
        sides[name] = types.SimpleNamespace(commit=commit, export=export, bin=bin_dir, snapshot=snapshot, shape=shape)
    return World(repo=repo, base=base, head=head, prefix=prefix, dispatch=dispatch, sides=sides,
                 interpreter_of=lambda bin_dir: str(prefix / "bin" / PYX))


@pytest.fixture(params=[("homebrew", "uv"), ("clt", "homebrew")], ids=lambda p: "+".join(p))
def world(tmp_path, monkeypatch, request):
    return build_world(tmp_path, monkeypatch, request.param)


def test_fixture_world_is_consistent(world):
    # (The plan says "exports verify against their commits": ``verify_export_against_commit`` arrives in T2b2, so this checks them against
    # ``git ls-tree`` directly: names, modes and bytes.)
    for name, side in world.sides.items():
        listing = git(world.repo, "ls-tree", "-r", "-z", side.commit).split("\0")
        seen = {}
        for record in filter(None, listing):
            meta, path = record.split("\t", 1)
            mode, kind, _ = meta.split()
            seen[path] = mode
            target = side.export / path
            if mode == "160000":
                assert target.is_dir() and not target.is_symlink() and not list(target.iterdir())
            elif mode == "120000":
                assert target.is_symlink() and os.readlink(target) == git(world.repo, "show", f"{side.commit}:{path}")
            else:
                assert target.read_bytes() == subprocess.run(["git", "show", f"{side.commit}:{path}"], cwd=world.repo, env=GIT_ENV,
                                                             capture_output=True, check=True, timeout=60).stdout
                assert bool(target.stat().st_mode & stat.S_IXUSR) == (mode == "100755")
        assert {"README.md", "link", "tools/run.sh", "vendor/sub"} <= set(seen) and seen["link"] == "120000" and seen["vendor/sub"] == "160000"
        on_disk = {str(p.relative_to(side.export)) for p in side.export.rglob("*") if p.is_file() or p.is_symlink()}
        assert on_disk == {p for p, m in seen.items() if m != "160000"}
        marker = json.loads((side.export.parent / bg._MARKER_NAME).read_text())
        assert marker["kind"] == bg._MARKER_KIND and marker["root"] == DISPATCH_ROOT
        assert json.loads(side.export.parent.joinpath(f"{name}.export.json").read_text())["commit"] == side.commit
        # the venv: a symlinked python that resolves into the fake prefix, and a snapshot that check_venv accepts
        python = side.bin / "python"
        assert python.is_symlink() and os.path.realpath(python) == os.path.realpath(world.prefix / "bin" / PYX)
        assert world.interpreter_of(side.bin) == str(world.prefix / "bin" / PYX)
        other = world.sides["head" if name == "base" else "base"]
        assert bg.check_venv(side.bin, side.snapshot, side.export, (str(other.export),)) == os.path.realpath(side.bin.parent)
    base, head = world.sides["base"], world.sides["head"]
    assert (base.export / "src/app/core.py").read_text() != (head.export / "src/app/core.py").read_text()
    assert not (base.export / "src/app/extra.py").exists() and (head.export / "src/app/extra.py").exists()


def test_fixture_venv_shapes_and_pth(world):
    for side in world.sides.values():
        cfg = (side.bin.parent / "pyvenv.cfg").read_text()
        keys = {line.partition("=")[0].strip() for line in cfg.splitlines() if "=" in line}
        home = Path(re.search(r"^home = (.*)$", cfg, re.M)[1])
        if side.shape == "uv":
            assert "version_info" in keys and "version" not in keys and home.is_symlink() and home.name.startswith("cpython-")
        elif side.shape == "homebrew":
            assert "version" in keys and home.is_symlink()
        else:
            assert "version" in keys and not home.is_symlink() and (home / PYX).is_symlink()
        assert os.path.realpath(home / PYX) == os.path.realpath(side.bin / "python")
        pth = next((side.bin.parent / "lib").glob("python3*/site-packages/zz_pytest.pth"))
        assert pth.read_text().strip() and json.loads(side.snapshot.read_text())["entries"][os.path.relpath(pth, side.bin.parent)]["kind"] == "file"


def test_fixture_fake_prefix_has_the_pin_shapes(world):
    prefix = world.prefix
    names = {str(p.relative_to(prefix)) for p in prefix.rglob("*")}
    assert {f"bin/{PYX}", f"lib/{PYX}/os.py", f"lib/{PYX}/lib-dynload", f"lib/{PYX}/__pycache__", f"lib/{PYXY}.zip",
            "lib/libpython-fake.dylib"} <= names


# --- fake_trace_builder (T2c) ---
# A shared argv_builder (the C4d-1/2 seam) for children that must speak both protocols: every run prints the result digest (what a measure
# run needs), and the trace result line is written only when the harness put BENCH_TRACE_* in the child's environment (what only a trace run
# does), with the run's own nonce. Used by the pipeline rows of T4a2; ``fake_sides`` is the tiny two-directory world of the measure tests.

FAKE_DIGEST = "ab" * 32
FAKE_TRACE_LINES = 7
_FAKE_TRACE_CHILD = """
import os, sys
print("BENCH_RESULT_DIGEST: " + sys.argv[1])
out, nonce = os.environ.get("BENCH_TRACE_OUT"), os.environ.get("BENCH_TRACE_NONCE")
if out and nonce and os.environ.get("BENCH_TRACE_FILE"):
    v = sys.version_info
    with open(out, "w") as f:
        f.write("BENCH_TRACE_LINES: %s %d.%d.%d %s %s\\n" % (sys.argv[2], v[0], v[1], v[2], sys.implementation.name, nonce))
"""


def fake_trace_builder(side, bin_dir, root, target, *, digest=FAKE_DIGEST, lines=FAKE_TRACE_LINES):
    """argv for a tiny real child: prints ``BENCH_RESULT_DIGEST: <digest>`` always; writes the nonce-bearing trace result only when
    ``BENCH_TRACE_*`` is in its environment. Pass as ``argv_builder=fake_trace_builder`` (or a ``functools.partial`` for other values)."""
    return [sys.executable, "-c", _FAKE_TRACE_CHILD, digest, str(lines)]


def _fake_pair(tmp_path):
    roots, bins = {}, {}
    for side in ("base", "head"):
        roots[side] = tmp_path / f"{side}-root"
        bins[side] = tmp_path / f"{side}-venv" / "bin"
        roots[side].mkdir()
        bins[side].mkdir(parents=True)
    return roots, bins


@posix_only
def test_fake_trace_builder_emits_digest_always_and_trace_result_only_with_trace_env(tmp_path):
    roots, bins = _fake_pair(tmp_path)
    args = (str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), "bench.py::test_b")
    traced = bg.trace_paired(*args, timeout_seconds=30, argv_builder=fake_trace_builder)
    assert traced["base"] == traced["head"] == FAKE_TRACE_LINES and traced["argv"]["base"][0] == sys.executable
    measured = bg.measure_paired(*args, repeats=4, timeout_seconds=30, base_commit="a" * 40, head_commit="b" * 40, benchmark_sha256="c" * 64,
                                 min_base_ns=0, argv_builder=fake_trace_builder)
    assert measured["digest"] == FAKE_DIGEST and len(measured["base_ns"]) == 4
    # the child itself: no BENCH_TRACE_* means no result file, with them it writes exactly the one line for the given nonce
    out = tmp_path / "trace.out"
    env = {k: v for k, v in os.environ.items() if not k.startswith("BENCH_TRACE_")}
    argv = fake_trace_builder("base", "", "", "")
    done = subprocess.run(argv, env=env, capture_output=True, text=True, check=True)
    assert done.stdout == f"BENCH_RESULT_DIGEST: {FAKE_DIGEST}\n" and not out.exists()
    env.update(BENCH_TRACE_FILE="bench.py", BENCH_TRACE_OUT=str(out), BENCH_TRACE_NONCE="f" * 32)
    done = subprocess.run(argv, env=env, capture_output=True, text=True, check=True)
    assert done.stdout == f"BENCH_RESULT_DIGEST: {FAKE_DIGEST}\n"
    assert bg._trace_result(out.read_bytes(), "f" * 32) == bg._TraceResult("lines", FAKE_TRACE_LINES, f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]} {sys.implementation.name}")


# --- fingerprint_tree (T2b1a) ---

def _fp_tree(tmp_path: Path) -> Path:
    root = tmp_path / "fp"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("alpha")
    (root / "sub" / "b.txt").write_text("bravo")
    return root


def _fp(root: Path) -> str:
    return bg.fingerprint_tree(root, limit=1000)


@posix_only
def test_fingerprint_changes_for_each_input(tmp_path):
    root = _fp_tree(tmp_path)
    first = _fp(root)
    assert first == _fp(root) and len(first) == 64  # untouched: stable

    def changed(label, mutate):
        before = _fp(root)
        mutate()
        after = _fp(root)
        assert after != before, label
        return after

    target = root / "a.txt"

    def same_size_edit_restored_mtime():
        st = target.stat()
        target.write_text("ALPHA")  # same size; only ctime (not restorable) and content differ
        os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns))
    changed("content edit with restored mtime", same_size_edit_restored_mtime)
    changed("chmod", lambda: os.chmod(target, 0o600))
    changed("size", lambda: target.write_text("alpha-longer"))
    changed("new entry", lambda: (root / "new.txt").write_text("x"))
    changed("renamed entry", lambda: os.rename(root / "new.txt", root / "renamed.txt"))
    changed("removed entry", lambda: os.unlink(root / "renamed.txt"))
    changed("hard link count", lambda: os.link(target, tmp_path / "outside-link"))
    # The root triple alone: a replacement root with identical content differs in (dev, ino, ctime_ns).
    twin = tmp_path / "twin"
    shutil.copytree(root, twin, symlinks=True)
    moved = tmp_path / "old-root"
    os.rename(root, moved)
    os.rename(twin, root)
    assert _fp(root) != _fp(moved)
    empty_a, empty_b = tmp_path / "ea", tmp_path / "eb"
    empty_a.mkdir()
    empty_b.mkdir()
    assert _fp(empty_a) != _fp(empty_b)  # both empty: only the root triple differs
    before = _fp(empty_a)
    os.chmod(empty_a, 0o700)
    os.utime(empty_a, ns=(1, 1))
    (empty_a / "t").write_text("")
    os.unlink(empty_a / "t")  # the root's ctime moves although its listing is the same
    assert _fp(empty_a) != before


@posix_only
def test_fingerprint_follows_no_links(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f.txt").write_text("one")
    root = tmp_path / "r"
    root.mkdir()
    os.symlink(outside, root / "link")
    os.symlink(outside / "f.txt", root / "flink")
    first = _fp(root)
    (outside / "f.txt").write_text("two-changed")
    (outside / "new").write_text("n")
    assert _fp(root) == first
    assert bg.fingerprint_tree(root, limit=2) == first  # the link is one entry, not its target's contents


@posix_only
def test_fingerprint_limits_are_errors_not_skips(tmp_path):
    root = _fp_tree(tmp_path)  # a.txt, sub, sub/b.txt = 3 entries
    assert bg.fingerprint_tree(root, limit=3)
    with pytest.raises(bg.BenchmarkGateError) as e:
        bg.fingerprint_tree(root, limit=2)
    assert e.value.code == "TREE_TOO_LARGE"

    deep = tmp_path / "deep"
    deep.mkdir()
    at = deep
    for _ in range(bg._MAX_HASH_DEPTH):
        at = at / "d"
        at.mkdir()
    assert bg.fingerprint_tree(deep, limit=10_000)  # exactly at the depth limit is fine
    (at / "d").mkdir()
    with pytest.raises(bg.BenchmarkGateError) as e:
        bg.fingerprint_tree(deep, limit=10_000)
    assert e.value.code == "TREE_TOO_LARGE"

    locked = root / "sub"
    os.chmod(locked, 0)
    try:
        if os.access(locked, os.R_OK):
            pytest.skip("directory permissions are not enforced for this user")
        with pytest.raises(bg.BenchmarkGateError) as e:
            _fp(root)
        assert e.value.code == "TREE_UNREADABLE"
    finally:
        os.chmod(locked, 0o700)
    with pytest.raises(bg.BenchmarkGateError) as e:
        bg.fingerprint_tree(tmp_path / "missing", limit=10)
    assert e.value.code == "TREE_UNREADABLE"


# --- interpreter_pin and the pyvenv.cfg parser (T2b1b) ---
# The fixture interpreter is a fake shell script, so most rows pass ``probe=`` (the injectable start-up probe). The default probe runs
# ``<bin>/python -I -S`` and is exercised against the machine's real python in a real venv created in the test.

def _stub_probe(prefix: Path, base_prefix=None, os_file=None):
    real = os.path.realpath(prefix)

    def probe(python, env):
        assert python.endswith(os.sep + "bin" + os.sep + "python") and env["PYTHONNOUSERSITE"] == "1"
        return "\n".join([str(base_prefix or real), str(os_file or os.path.join(real, "lib", PYX, "os.py")), str(base_prefix or real)]) + "\n"
    return probe


def _pin(env, **kw):
    kw.setdefault("probe", _stub_probe(env.prefix))
    return bg.interpreter_pin(env.bin, **kw)


@pytest.fixture
def pin_env(tmp_path):
    """A fake prefix and one Homebrew-shaped venv (``bin`` and ``cfg``), without the git world."""
    prefix = build_fake_prefix(tmp_path / "interp")
    bin_dir = build_venv(tmp_path / "venv", "homebrew", prefix, tmp_path / "side")
    return types.SimpleNamespace(prefix=prefix, bin=bin_dir, root=bin_dir.parent, cfg=bin_dir.parent / "pyvenv.cfg", tmp=tmp_path)


def _code(exc_info) -> str:
    return exc_info.value.code


@posix_only
def test_pin_accepts_homebrew_uv_and_clt_layouts(world):
    pins = {}
    for name, side in world.sides.items():
        pin = bg.interpreter_pin(side.bin, probe=_stub_probe(world.prefix))
        assert isinstance(pin, bg.InterpreterPin) and len(pin.sha256) == 64 and pin.real_python == os.path.realpath(world.prefix / "bin" / PYX)
        pins[name] = pin
    assert pins["base"] == pins["head"] or pins["base"].sha256 == pins["head"].sha256  # same interpreter, same pin


@posix_only
def test_pin_rejects_cfg_faults(pin_env):
    original = pin_env.cfg.read_text()
    minor = sys.version_info.minor

    def rows():
        yield "dup home", lambda t: t + f"home = {pin_env.prefix / 'bin'}\n"
        yield "dup version", lambda t: t + f"version = 3.{minor}.1\n"
        yield "version and version_info", lambda t: t + f"version_info = 3.{minor}.0\n"
        yield "dup include", lambda t: t + "include-system-site-packages = false\n"
        yield "dup executable", lambda t: t + "executable = /a\nexecutable = /b\n"
        yield "include true", lambda t: t.replace("include-system-site-packages = false", "include-system-site-packages = true")
        yield "include True", lambda t: t.replace("include-system-site-packages = false", "include-system-site-packages = True")
        yield "version mismatch", lambda t: t.replace(f"version = 3.{minor}.0", f"version = 3.{minor + 1}.0")
        yield "no version", lambda t: t.replace(f"version = 3.{minor}.0\n", "")
        yield "garbled version", lambda t: t.replace(f"version = 3.{minor}.0", "version = three")
        yield "home elsewhere", lambda t: re.sub(r"(?m)^home = .*$", f"home = {pin_env.tmp / 'decoy'}", t)
        yield "no home", lambda t: re.sub(r"(?m)^home = .*\n", "", t)
        yield "relative home", lambda t: re.sub(r"(?m)^home = .*$", "home = bin", t)
        yield "non-utf8", lambda t: b"\xff\xfe" + t.encode()

    (pin_env.tmp / "decoy").mkdir()  # exists, but holds no python
    for label, mutate in rows():
        mutated = mutate(original)
        pin_env.cfg.write_bytes(mutated if isinstance(mutated, bytes) else mutated.encode())
        with pytest.raises(bg.BenchmarkGateError) as e:
            _pin(pin_env)
        assert _code(e) == "VENV_NOT_ISOLATED", label
    pin_env.cfg.write_text(original)
    assert _pin(pin_env)


@posix_only
def test_pin_ignores_command_and_unknown_keys_and_accepts_a_non_ascii_home(pin_env):
    text = pin_env.cfg.read_text()
    unicode_home = pin_env.tmp / "höme-ü"
    unicode_home.symlink_to(pin_env.prefix / "bin")
    text = re.sub(r"(?m)^home = .*$", f"home = {unicode_home}", text)
    pin_env.cfg.write_text(text + "command = /Users/ü/python -m venv --home home=x version=9.9\nunknown = 1\nimplementation = CPython\n", encoding="utf-8")
    assert _pin(pin_env).real_python == os.path.realpath(pin_env.prefix / "bin" / PYX)


@posix_only
def test_pin_rejects_copies_venv_and_interpreters_inside_the_venv_or_export(pin_env):
    assert _pin(pin_env)
    # an interpreter outside the export passes; the same interpreter reported inside a protected root does not
    with pytest.raises(bg.BenchmarkGateError) as e:
        _pin(pin_env, outside=(str(pin_env.prefix.parent),))
    assert _code(e) == "VENV_NOT_ISOLATED"
    assert _pin(pin_env, outside=(str(pin_env.tmp / "elsewhere"),))
    # a --copies venv: bin/python is a regular file inside the venv
    python = pin_env.bin / "python"
    python.unlink()
    shutil.copy2(pin_env.prefix / "bin" / PYX, python)
    with pytest.raises(bg.BenchmarkGateError) as e:
        _pin(pin_env)
    assert _code(e) == "VENV_NOT_ISOLATED"
    # a symlinked interpreter whose whole prefix lives inside the venv, with a cfg that is otherwise consistent
    inner = build_fake_prefix(pin_env.root / "inner")
    python.unlink()
    python.symlink_to(inner / "bin" / PYX)
    cfg = re.sub(r"(?m)^home = .*$", f"home = {inner / 'bin'}", pin_env.cfg.read_text())
    pin_env.cfg.write_text(cfg)
    with pytest.raises(bg.BenchmarkGateError) as e:
        bg.interpreter_pin(pin_env.bin, probe=_stub_probe(inner))
    assert _code(e) == "VENV_NOT_ISOLATED"


@posix_only
def test_startup_probe_stub_mismatches_are_rejected(pin_env):
    assert _pin(pin_env)
    decoy = pin_env.tmp / "decoy-prefix"
    for label, probe in (
            ("base_prefix", _stub_probe(pin_env.prefix, base_prefix=decoy)),
            ("os.__file__", _stub_probe(pin_env.prefix, os_file=decoy / "lib" / PYX / "os.py")),
            ("os.__file__ in site-packages", _stub_probe(pin_env.prefix, os_file=pin_env.prefix / "lib" / PYX / "site-packages" / "os.py")),
            ("garbage", lambda python, env: "nonsense"),
            ("not a string", lambda python, env: None),
            ("raises", lambda python, env: 1 / 0)):
        with pytest.raises(bg.BenchmarkGateError) as e:
            bg.interpreter_pin(pin_env.bin, probe=probe)
        assert _code(e) == "VENV_NOT_ISOLATED", label


def _real_venv(tmp_path: Path) -> Path:
    root = tmp_path / "realvenv"
    venv.create(root, with_pip=False, symlinks=True)
    python = root / "bin" / "python"
    if not python.is_symlink():
        pytest.skip("this platform's venv does not symlink its python")
    return root


@posix_only
def test_default_probe_runs_the_real_interpreter_isolated(tmp_path):
    root = _real_venv(tmp_path)
    marker = tmp_path / "pth-ran"
    site = next((root / "lib").glob("python3*/site-packages"))
    (site / "zz_marker.pth").write_text(f"import os; open({str(marker)!r}, 'w').write('x')\n")
    (site / "sitecustomize.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n")
    pin = bg.interpreter_pin(root / "bin")
    assert pin.real_python == os.path.realpath(root / "bin" / "python") and len(pin.sha256) == 64
    assert not marker.exists(), "the probe must run with -I -S: no .pth, no sitecustomize"
    assert pin.sha256 == bg.interpreter_pin(root / "bin").sha256


def _script_interpreter(env, *, lines, body=""):
    """Make the fake interpreter a script that answers the start-up probe: it insists on `-I -S -c` and on a clean environment, then prints
    ``lines`` (the three probe values) after the optional shell ``body``."""
    exe = env.prefix / "bin" / PYX
    exe.write_text('#!/bin/sh\n[ "$1" = -I ] && [ "$2" = -S ] && [ "$3" = -c ] && [ -n "$4" ] || exit 3\n[ -z "${SB_PROBE_SECRET+x}" ] || exit 4\n'
                   + body + "".join(f"printf '%s\\n' '{line}'\n" for line in lines))
    exe.chmod(0o755)


@posix_only
def test_default_probe_plumbing_with_a_script_interpreter(pin_env, monkeypatch):
    monkeypatch.setenv("SB_PROBE_SECRET", "x")  # must not reach the probe
    real = os.path.realpath(pin_env.prefix)
    good = [real, f"{real}/lib/{PYX}/os.py", real]
    _script_interpreter(pin_env, lines=good)
    assert bg.interpreter_pin(pin_env.bin).real_python == os.path.realpath(pin_env.prefix / "bin" / PYX)
    decoy = str(pin_env.tmp / "decoy")
    for label, kwargs in (("redirected prefix", dict(lines=[decoy, f"{decoy}/lib/{PYX}/os.py", decoy])),
                          ("redirected os", dict(lines=[real, f"{decoy}/lib/{PYX}/os.py", real])),
                          ("nonzero exit", dict(lines=good, body="exit 1\n")),
                          ("too much output", dict(lines=good, body="yes aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa | head -c 100000\n")),
                          ("two lines", dict(lines=good[:2])),
                          ("not a program", dict(lines=good, body="exec /nonexistent-binary\n"))):
        _script_interpreter(pin_env, **kwargs)
        with pytest.raises(bg.BenchmarkGateError) as e:
            bg.interpreter_pin(pin_env.bin)
        assert _code(e) == "VENV_NOT_ISOLATED", label
    monkeypatch.setattr(bg, "_PROBE_TIMEOUT", 0.5)
    _script_interpreter(pin_env, lines=good, body="exec sleep 30\n")
    with pytest.raises(bg.BenchmarkGateError) as e:
        bg.interpreter_pin(pin_env.bin)
    assert _code(e) == "VENV_NOT_ISOLATED"


@posix_only
def test_startup_probe_catches_a_redirected_home(tmp_path):
    root = _real_venv(tmp_path)
    real_python = Path(os.path.realpath(root / "bin" / "python"))
    real_stdlib = real_python.parent.parent / "lib" / real_python.name
    if not real_stdlib.is_dir():
        pytest.skip("the real interpreter's layout is not <prefix>/lib/pythonX.Y")
    # A decoy prefix whose bin holds a symlink to the real binary (so the by-file `home` check passes) and whose stdlib is the real one
    # with its own os.py: only what CPython actually loads can tell.
    decoy = tmp_path / "decoy"
    (decoy / "bin").mkdir(parents=True)
    (decoy / "bin" / real_python.name).symlink_to(real_python)
    (decoy / "lib" / real_python.name).mkdir(parents=True)
    for entry in real_stdlib.iterdir():
        if entry.name not in ("os.py", "site-packages"):
            (decoy / "lib" / real_python.name / entry.name).symlink_to(entry)
    shutil.copyfile(real_stdlib / "os.py", decoy / "lib" / real_python.name / "os.py")
    cfg = root / "pyvenv.cfg"
    cfg.write_text(re.sub(r"(?m)^home = .*$", f"home = {decoy / 'bin'}", cfg.read_text()))
    seen = subprocess.run([str(root / "bin" / "python"), "-I", "-S", "-c", "import os,sys;print(os.path.realpath(sys.base_prefix))"],
                          capture_output=True, text=True, timeout=60).stdout.strip()
    if seen != os.path.realpath(decoy):
        # macOS framework builds find their stdlib from the loaded dylib and ignore `home`: there is nothing to redirect on such a build
        # (and the pin's probe then correctly sees the real prefix). The probe's rejection logic is covered by the script rows above.
        pytest.skip(f"this CPython build ignores a redirected `home` (it reports {seen})")
    with pytest.raises(bg.BenchmarkGateError) as e:
        bg.interpreter_pin(root / "bin")
    assert _code(e) == "VENV_NOT_ISOLATED" and "probe" in e.value.detail


def _touch_and_compare(label, path: Path, pin_env, *, changes: bool, mutate=None):
    before = _pin(pin_env).sha256
    stat_before = path.stat() if path.exists() else None
    if mutate:
        mutate()
    else:
        path.chmod(0o644)
        path.write_bytes(path.read_bytes() + b"!")
        if stat_before:
            os.chmod(path, stat_before.st_mode & 0o7777)
    after = _pin(pin_env).sha256
    assert (after != before) == changes, label


@posix_only
def test_pin_hash_covers_binary_stdlib_pycache_lib_dynload_prefix_and_lib_files(pin_env):
    prefix = pin_env.prefix
    std = prefix / "lib" / PYX
    (prefix / "Python").write_bytes(b"framework dylib")  # directly under <prefix>
    (prefix / "lib" / "x").mkdir()
    (prefix / "lib" / "x" / "deep.so").write_bytes(b"deep")  # a deep directory under lib: not the stdlib
    (std / "site-packages").mkdir()
    (std / "site-packages" / "mod.py").write_text("x = 1\n")
    for label, path in (("binary", prefix / "bin" / PYX), ("stdlib file", std / "os.py"), ("__pycache__ file", std / "__pycache__" / "os.cpython-fake.pyc"),
                        ("lib-dynload file", std / "lib-dynload" / "_fake.so"), ("file under prefix", prefix / "Python"),
                        ("libpython under lib", prefix / "lib" / "libpython-fake.dylib"), ("python3XY.zip", prefix / "lib" / f"{PYXY}.zip")):
        _touch_and_compare(label, path, pin_env, changes=True)
    for label, path in (("site-packages file", std / "site-packages" / "mod.py"), ("deep dir under lib", prefix / "lib" / "x" / "deep.so")):
        _touch_and_compare(label, path, pin_env, changes=False)
    # timestamps are not hashed
    target = std / "os.py"
    before = _pin(pin_env).sha256
    os.utime(target, (1, 1))
    os.utime(prefix / "bin" / PYX, (2, 2))
    assert _pin(pin_env).sha256 == before
    # structure is: an added, removed or renamed stdlib file, an added __pycache__ file, a new file under <prefix>
    for label, mutate in (("add", lambda: (std / "new.py").write_text("")), ("rename", lambda: os.rename(std / "new.py", std / "renamed.py")),
                          ("pycache add", lambda: (std / "__pycache__" / "new.pyc").write_bytes(b"")),
                          ("prefix add", lambda: (prefix / "Python2").write_bytes(b"")), ("remove", lambda: os.unlink(std / "renamed.py"))):
        _touch_and_compare(label, std, pin_env, changes=True, mutate=mutate)


@posix_only
def test_stdlib_lookup_prefers_lib_then_lib64(pin_env):
    prefix = pin_env.prefix
    only_lib = _pin(pin_env).sha256
    (prefix / "lib64" / PYX).mkdir(parents=True)
    (prefix / "lib64" / PYX / "os.py").write_text("# other\n")
    assert _pin(pin_env).sha256 == only_lib  # lib wins; lib64 is not read
    os.rename(prefix / "lib" / PYX, prefix / "lib" / "moved")  # now only lib64 holds the stdlib
    via_lib64 = bg.interpreter_pin(pin_env.bin, probe=_stub_probe(prefix, os_file=prefix / "lib64" / PYX / "os.py"))
    assert via_lib64.sha256 != only_lib


@posix_only
def test_missing_stdlib_is_dest_rejected(pin_env):
    # (compare maps DEST_REJECTED, TREE_TOO_LARGE and TREE_UNREADABLE to NOT_PROVISIONED in T3a; here only the raise is pinned.)
    shutil.rmtree(pin_env.prefix / "lib" / PYX)
    with pytest.raises(bg.BenchmarkGateError) as e:
        _pin(pin_env)
    assert _code(e) == "DEST_REJECTED"


@posix_only
def test_over_limit_is_tree_too_large(pin_env, monkeypatch):
    # the entries counted: the binary, the stdlib's entries (os.py, lib-dynload, _fake.so, __pycache__, the pyc) and the two files directly
    # under <prefix>/lib (the zip, the dylib) = 8; <prefix> itself holds none
    monkeypatch.setattr(bg, "_INTERPRETER_LIMIT", 8)
    assert _pin(pin_env)
    monkeypatch.setattr(bg, "_INTERPRETER_LIMIT", 7)
    with pytest.raises(bg.BenchmarkGateError) as e:
        _pin(pin_env)
    assert _code(e) == "TREE_TOO_LARGE"
    monkeypatch.setattr(bg, "_INTERPRETER_LIMIT", 20_000)
    total = sum(p.stat().st_size for p in [pin_env.prefix / "bin" / PYX, pin_env.prefix / "lib" / PYX / "os.py",
                                           pin_env.prefix / "lib" / PYX / "lib-dynload" / "_fake.so",
                                           pin_env.prefix / "lib" / PYX / "__pycache__" / "os.cpython-fake.pyc",
                                           pin_env.prefix / "lib" / f"{PYXY}.zip", pin_env.prefix / "lib" / "libpython-fake.dylib"])
    monkeypatch.setattr(bg, "_INTERPRETER_BYTES", total)
    assert _pin(pin_env)
    monkeypatch.setattr(bg, "_INTERPRETER_BYTES", total - 1)
    with pytest.raises(bg.BenchmarkGateError) as e:
        _pin(pin_env)
    assert _code(e) == "TREE_TOO_LARGE"
    monkeypatch.setattr(bg, "_INTERPRETER_BYTES", 1 << 30)
    deep = pin_env.prefix / "lib" / PYX
    for _ in range(bg._MAX_HASH_DEPTH + 1):
        deep = deep / "d"
        deep.mkdir()
    with pytest.raises(bg.BenchmarkGateError) as e:
        _pin(pin_env)
    assert _code(e) == "TREE_TOO_LARGE"


@posix_only
def test_writable_flag(pin_env, monkeypatch):
    if os.geteuid() == 0:
        pytest.skip("root can write everything")
    prefix, std = pin_env.prefix, pin_env.prefix / "lib" / PYX
    assert _pin(pin_env).writable is True  # everything here is owned by the euid
    monkeypatch.setattr(os, "geteuid", lambda: os.getuid() + 12345)  # as if another user owned the files: only os.access decides

    def lock(read_only: bool):
        for path in [prefix, *prefix.rglob("*")]:
            if not path.is_symlink():
                path.chmod((0o555 if path.is_dir() else 0o444) if read_only else (0o755 if path.is_dir() else 0o644))
    # the exe must stay executable only for realism; the pin does not run it
    lock(True)
    try:
        assert _pin(pin_env).writable is False  # a read-only copy
        for label, path in (("pinned file", std / "os.py"), ("directory containing a pinned entry", std / "lib-dynload"),
                            ("stdlib root", std), ("prefix", prefix), ("prefix/lib", prefix / "lib"), ("binary", prefix / "bin" / PYX),
                            ("binary's directory", prefix / "bin"), ("__pycache__ file", std / "__pycache__" / "os.cpython-fake.pyc"),
                            ("lib file", prefix / "lib" / "libpython-fake.dylib")):
            mode = path.stat().st_mode & 0o7777
            path.chmod(mode | 0o200)
            try:
                assert _pin(pin_env).writable is True, label
            finally:
                path.chmod(mode)
            assert _pin(pin_env).writable is False, label
    finally:
        lock(False)


@posix_only
def test_pin_error_mapping_names(pin_env, monkeypatch):
    std = pin_env.prefix / "lib" / PYX
    pin_env.cfg.write_text(pin_env.cfg.read_text() + "version = 3.0\n")
    with pytest.raises(bg.BenchmarkGateError) as e:
        _pin(pin_env)
    assert _code(e) == "VENV_NOT_ISOLATED"
    pin_env.cfg.write_text(pin_env.cfg.read_text().replace("version = 3.0\n", ""))
    monkeypatch.setattr(bg, "_INTERPRETER_LIMIT", 1)
    with pytest.raises(bg.BenchmarkGateError) as e:
        _pin(pin_env)
    assert _code(e) == "TREE_TOO_LARGE"
    monkeypatch.setattr(bg, "_INTERPRETER_LIMIT", 20_000)
    locked = std / "os.py"
    locked.chmod(0)
    try:
        if os.access(locked, os.R_OK):
            pytest.skip("file permissions are not enforced for this user")
        with pytest.raises(bg.BenchmarkGateError) as e:
            _pin(pin_env)
        assert _code(e) == "TREE_UNREADABLE"
    finally:
        locked.chmod(0o644)
    os.unlink(std / "os.py")
    shutil.rmtree(std)
    with pytest.raises(bg.BenchmarkGateError) as e:
        _pin(pin_env)
    assert _code(e) == "DEST_REJECTED"


# --- dependency_parity (T2b1c) ---

def _b64(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def _mk_side(tmp_path: Path, name: str) -> types.SimpleNamespace:
    """A bare venv shape (``bin``, ``pyvenv.cfg``, ``lib/python3.X/site-packages``) and an export directory: enough for ``_venv_layout``."""
    root = tmp_path / f"dp-{name}"
    site = root / "lib" / PYX / "site-packages"
    site.mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "pyvenv.cfg").write_text("home = /nowhere\ninclude-system-site-packages = false\n")
    export = tmp_path / f"dp-export-{name}"
    (export / "src" / "proj").mkdir(parents=True)
    return types.SimpleNamespace(root=root, bin=root / "bin", site=site, export=export)


def _add_dist(side, dist: str, files: dict[str, bytes], *, rows=(), direct_url=None, record=True, version="1.0") -> Path:
    """Write ``files`` under site-packages and an honest ``<dist>-<version>.dist-info`` (METADATA, INSTALLER, RECORD) for them."""
    info = f"{dist}-{version}.dist-info"
    table = dict(files)
    table[f"{info}/METADATA"] = f"Name: {dist}\n".encode()
    for rel, data in table.items():
        path = side.site / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (side.site / info / "INSTALLER").write_text("pip\n")
    if direct_url is not None:
        (side.site / info / "direct_url.json").write_text(json.dumps(direct_url))
    if record:
        import csv
        with open(side.site / info / "RECORD", "w", newline="") as handle:
            writer = csv.writer(handle)
            for rel, data in table.items():
                writer.writerow([rel, "sha256=" + _b64(data), len(data)])
            for row in rows:
                writer.writerow(row)
            writer.writerow([f"{info}/RECORD", "", ""])
    return side.site / info


def _honest_pair(tmp_path: Path):
    sides = []
    for name in ("base", "head"):
        side = _mk_side(tmp_path, name)
        # A pip-style dist: its console-script row points out of site-packages and hashes differently per venv path.
        _add_dist(side, "pip", {"pip/__init__.py": b"v = 1\n", "pip/_x.py": b"x = 2\n"},
                  rows=[["../../../bin/pip", "sha256=" + _b64(f"#!{side.root}/bin/python\n".encode()), "30"]])
        _add_dist(side, "dep", {"dep.py": b"d = 3\n", "dep_data/a.txt": b"hello"})
        sides.append(side)
    return sides


def _parity(a, b):
    return bg.dependency_parity(a.bin, b.bin, a.export, b.export)


def _details(findings):
    return {detail for detail, _ in findings}


@posix_only
def test_console_scripts_at_different_paths_pass(tmp_path):
    base, head = _honest_pair(tmp_path)
    assert (base.site / "pip-1.0.dist-info" / "RECORD").read_bytes() != (head.site / "pip-1.0.dist-info" / "RECORD").read_bytes()
    assert _parity(base, head) == []


@posix_only
def test_two_real_pip_venvs_pass(tmp_path):
    sides = []
    for name in ("base", "head"):
        root = tmp_path / f"real-{name}"
        venv.create(root, with_pip=True, symlinks=True)
        for cache in list(root.rglob("__pycache__")):  # the provisioning contract removes bytecode before pinning
            shutil.rmtree(cache)
        export = tmp_path / f"real-export-{name}"
        export.mkdir()
        sides.append(types.SimpleNamespace(bin=root / "bin", export=export, root=root))
    base, head = sides
    assert _parity(base, head) == []
    # the pip console scripts' RECORD rows differ per venv path, and the comparison still passes (a raw RECORD comparison would not)
    records = [next((s.root / "lib").glob("python3*/site-packages/pip-*.dist-info/RECORD")).read_text() for s in sides]
    assert records[0] != records[1]
    # an edit to an installed file with RECORD intact is caught on the real tree too
    target = next((head.root / "lib").glob("python3*/site-packages/pip/__init__.py"))
    target.write_text(target.read_text() + "\n# edited\n")
    assert _details(_parity(base, head)) == {"DEPENDENCY_PARITY"}


@posix_only
def test_edited_dependency_file_with_intact_record_fails(tmp_path):
    base, head = _honest_pair(tmp_path)
    (head.site / "dep.py").write_bytes(b"d = 4\n")
    findings = _parity(base, head)
    assert _details(findings) == {"DEPENDENCY_PARITY"} and any("dep.py" in text for _, text in findings)
    # the same edit on BOTH sides is caught too: the RECORD no longer matches the disk
    (base.site / "dep.py").write_bytes(b"d = 4\n")
    assert _details(_parity(base, head)) == {"DEPENDENCY_PARITY"}


@posix_only
@pytest.mark.parametrize("name", ["bare.py", "ext.cpython-3-x.so", "ext.pyd", "evil.pth", "x.egg-link", "dep_data/new.py", "newdir/inner.py"])
def test_bare_module_so_pth_egg_link_and_unlisted_py_fail(tmp_path, name):
    base, head = _honest_pair(tmp_path)
    for side in (base, head):  # the same file on both sides: the inventories agree, the ownership rule alone must refuse it
        path = side.site / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x = 1\n")
    findings = _parity(base, head)
    assert _details(findings) == {"DEPENDENCY_PARITY"} and any(name in text for _, text in findings)


@posix_only
def test_symlink_device_fifo_pyc_and_pycache_fail(tmp_path):
    cases = {
        "symlink": lambda s: (s.site / "dep_data" / "l").symlink_to("a.txt"),
        "dirlink": lambda s: (s.site / "dl").symlink_to(s.export),
        "fifo": lambda s: os.mkfifo(s.site / "dep_data" / "f"),
        "pyc": lambda s: (s.site / "dep_data" / "m.pyc").write_bytes(b"\0"),
        "pycache": lambda s: (s.site / "dep_data" / "__pycache__").mkdir(),
        "pycache_with_file": lambda s: ((s.site / "pip" / "__pycache__").mkdir(), (s.site / "pip" / "__pycache__" / "x.txt").write_text("")),
    }
    for label, make in cases.items():
        base, head = _honest_pair(tmp_path / label)
        for side in (base, head):
            make(side)
        findings = _parity(base, head)
        assert _details(findings) == {"DEPENDENCY_PARITY"}, label
    # a symlink is a finding even where its own target would be fine, and it is not followed (the export target is not walked)
    assert not any("proj" in text for _, text in findings)


@posix_only
def test_record_row_path_rules(tmp_path):
    base, head = _honest_pair(tmp_path / "ok")
    # a leading ../ run is dropped, whatever it points at, and nothing is read from it
    for side in (base, head):
        info = side.site / "dep-1.0.dist-info" / "RECORD"
        info.write_text(info.read_text() + "../../../../bin/x,sha256=AAAA,1\n../../etc/y,,\n")
    assert _parity(base, head) == []

    def run(row, tag):
        b, h = _honest_pair(tmp_path / tag)
        record = h.site / "dep-1.0.dist-info" / "RECORD"
        record.write_text(record.read_text() + row)
        return _parity(b, h)

    outside = tmp_path / "abs-target"
    outside.write_text("secret")
    for tag, row in (("abs", f"{outside},sha256={_b64(b'secret')},6\n"), ("mid", "a/../dep.py,,\n"), ("trail", "dep_data/,,\n"),
                     ("dot", "./dep.py,,\n"), ("back", "dep_data\\a.txt,,\n"), ("nul", "dep\0.py,,\n"), ("empty", ",,\n"),
                     ("lead_then_mid", "../a/../b,,\n"), ("algo", "dep_data/a.txt,md5=abc,5\n"), ("missing", "gone.py,sha256=AAAA,1\n"),
                     ("wrong", "dep_data/a.txt,sha256=AAAA,5\n")):
        assert _details(run(row, tag)) == {"DEPENDENCY_PARITY"}, tag
    # a row without a hash owns nothing: the file it names is unowned
    b, h = _honest_pair(tmp_path / "nohash")
    (h.site / "stray.py").write_text("x")
    record = h.site / "dep-1.0.dist-info" / "RECORD"
    record.write_text(record.read_text() + "stray.py,,\n")
    assert _details(_parity(b, h)) == {"DEPENDENCY_PARITY"}
    # a RECORD-less dist
    b, h = _honest_pair(tmp_path / "norecord")
    (h.site / "dep-1.0.dist-info" / "RECORD").unlink()
    assert _details(_parity(b, h)) == {"DEPENDENCY_PARITY"}
    # a RECORD that is not valid UTF-8 or not CSV-parsable
    b, h = _honest_pair(tmp_path / "badrecord")
    (h.site / "dep-1.0.dist-info" / "RECORD").write_bytes(b"\xff\xfe\n")
    assert _details(_parity(b, h)) == {"DEPENDENCY_PARITY"}


@posix_only
def test_allowed_dist_info_files(tmp_path):
    base, head = _honest_pair(tmp_path / "ok")
    for side in (base, head):
        info = side.site / "dep-1.0.dist-info"
        (info / "REQUESTED").write_text("")
        (info / "direct_url.json").write_text(json.dumps({"url": "https://example.invalid/x.whl", "archive_info": {}}))
        (side.site / "distutils-precedence.pth").write_text("import os\n")
        (side.site / "_virtualenv.py").write_text("x = 1\n")
        (side.site / "_virtualenv.pth").write_text("import _virtualenv\n")
    assert _parity(base, head) == []
    for tag, rel in (("meta", "dep-1.0.dist-info/other.txt"), ("nested", "dep-1.0.dist-info/sub/INSTALLER"), ("subvirt", "x/_virtualenv.py"),
                     ("lookalike", "_virtualenvx.py"), ("subdp", "x/distutils-precedence.pth")):
        b, h = _honest_pair(tmp_path / tag)
        for side in (b, h):
            path = side.site / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x")
        assert _details(_parity(b, h)) == {"DEPENDENCY_PARITY"}, tag
    # the free names are free only at the dist-info of a dist: a top-level INSTALLER is not
    b, h = _honest_pair(tmp_path / "top")
    for side in (b, h):
        (side.site / "INSTALLER").write_text("x")
    assert _details(_parity(b, h)) == {"DEPENDENCY_PARITY"}


def _editable(side, *, name="proj", url=None, extra_rows=(), extra_files=None, mapping=None, namespaces="{}", finder=True, editable=True):
    export_proj = side.export / "src" / name
    export_proj.mkdir(parents=True, exist_ok=True)
    url = url if url is not None else side.export.as_uri()
    files = {f"__editable__.{name}-1.0.pth": f"import __editable___{name}_1_0_finder; __editable___{name}_1_0_finder.install()\n".encode()}
    if finder:
        mapping = mapping if mapping is not None else repr({name: str(export_proj)})
        files[f"__editable___{name}_1_0_finder.py"] = f"MAPPING: dict[str, str] = {mapping}\nNAMESPACES: dict[str, list[str]] = {namespaces}\n".encode()
    files.update(extra_files or {})
    return _add_dist(side, name, files, rows=extra_rows, version="1.0", direct_url={"url": url, "dir_info": {"editable": editable}})


@posix_only
def test_one_exempt_editable_dist_per_side(tmp_path):
    base, head = _honest_pair(tmp_path / "ok")
    _editable(base, name="proj")
    _editable(head, name="proj")
    # the exempt dist differs between the sides (another export path in its files) and still passes
    (head.site / "__editable___proj_1_0_finder.py").write_text(
        "MAPPING: dict[str, str] = " + repr({"proj": str(head.export / "src" / "proj")}) + "\nNAMESPACES: dict[str, list[str]] = {}\n# extra\n")
    rewrite = head.site / "proj-1.0.dist-info" / "RECORD"
    import csv
    rows = list(csv.reader(open(rewrite, newline="")))
    data = (head.site / "__editable___proj_1_0_finder.py").read_bytes()
    for row in rows:
        if row[0] == "__editable___proj_1_0_finder.py":
            row[1], row[2] = "sha256=" + _b64(data), str(len(data))
    with open(rewrite, "w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    assert _parity(base, head) == []
    # one side without any editable dist is fine as long as the other's exempt dist is clean
    b2, h2 = _honest_pair(tmp_path / "head-only")
    _editable(h2)
    assert _parity(b2, h2) == []

    def fails(tag, mutate):
        b, h = _honest_pair(tmp_path / tag)
        _editable(b)
        _editable(h)
        mutate(b, h)
        findings = _parity(b, h)
        assert _details(findings) == {"DEPENDENCY_PARITY"}, tag
        return findings

    fails("two_exempt", lambda b, h: _editable(h, name="other"))
    fails("forged_extra_head", lambda b, h: _add_dist(h, "forged", {"forged.py": b"x = 1\n"}, direct_url={"url": h.export.as_uri(), "dir_info": {"editable": True}}))
    fails("forged_extra_outside", lambda b, h: _add_dist(h, "forged", {"forged.py": b"x = 1\n"},
                                                         direct_url={"url": (tmp_path / "elsewhere").as_uri(), "dir_info": {"editable": True}}))
    fails("non_editable_project", lambda b, h: _add_dist(h, "plain", {"plain.py": b"x = 1\n"},
                                                         direct_url={"url": h.export.as_uri(), "dir_info": {}}))
    fails("other_side_export", lambda b, h: _add_dist(h, "oth", {"oth.py": b"x = 1\n"}, direct_url={"url": b.export.as_uri(), "dir_info": {"editable": True}}))

    def owns_other(b, h):
        (h.site / "extra.py").write_text("x = 1\n")
        record = h.site / "proj-1.0.dist-info" / "RECORD"
        record.write_text(record.read_text() + f"extra.py,sha256={_b64(b'x = 1' + chr(10).encode())},6\n")
    fails("owns_other_file", owns_other)

    def owns_nested(b, h):
        (h.site / "dep_data" / "n.pth").write_text("x\n")
        record = h.site / "proj-1.0.dist-info" / "RECORD"
        record.write_text(record.read_text() + "dep_data/n.pth,,\n")
    fails("owns_nested_pth", owns_nested)
    fails("bad_url_scheme", lambda b, h: (h.site / "proj-1.0.dist-info" / "direct_url.json").write_text(
        json.dumps({"url": "https://example.invalid/", "dir_info": {"editable": True}})))
    fails("malformed_direct_url", lambda b, h: (h.site / "proj-1.0.dist-info" / "direct_url.json").write_text("{not json"))
    fails("url_remote_host", lambda b, h: (h.site / "proj-1.0.dist-info" / "direct_url.json").write_text(
        json.dumps({"url": "file://example.invalid" + str(h.export), "dir_info": {"editable": True}})))
    # an editable dist on one side only with an edited non-exempt dist is still caught
    fails("edited_dep", lambda b, h: (h.site / "dep.py").write_bytes(b"d = 9\n"))


@posix_only
def test_editable_finder_mapping_is_parsed_with_literal_eval_and_confined(tmp_path):
    outside = tmp_path / "outside-target"
    outside.mkdir()

    def run(tag, **kw):
        """Each keyword is a template: ``{E}`` is the head export, ``{O}`` the directory outside it."""
        b, h = _honest_pair(tmp_path / tag)
        (h.export / "src" / "esc").symlink_to(outside)
        _editable(b)
        _editable(h, **{k: v.format(E=h.export, O=outside) for k, v in kw.items()})
        return _parity(b, h)

    assert run("literal") == []
    assert run("namespaces_inside", namespaces="{{'ns': ['{E}/src']}}") == []
    for tag, kw in (("computed", dict(mapping="{{'proj': __import__('os').getcwd()}}")),
                    ("call", dict(mapping="dict(proj='/x')")),
                    ("outside", dict(mapping="{{'proj': '{O}'}}")),
                    ("outside_ns", dict(namespaces="{{'ns': ['{O}']}}")),
                    ("dotdot", dict(mapping="{{'proj': '{E}/src/../../outside-target'}}")),
                    ("relative", dict(mapping="{{'proj': 'src/proj'}}")),
                    ("non_str", dict(mapping="{{'proj': 3}}")),
                    ("syntax", dict(mapping="{{")),
                    ("symlink_escape", dict(mapping="{{'proj': '{E}/src/esc'}}")),
                    ("missing_namespaces", dict(namespaces="__import__('os')"))):
        assert _details(run(tag, **kw)) == {"DEPENDENCY_PARITY"}, tag


@posix_only
def test_over_the_hash_budget_is_not_provisioned(tmp_path, monkeypatch):
    base, head = _honest_pair(tmp_path)
    assert bg._VENV_HASH_BYTES == 1 << 30
    monkeypatch.setattr(bg, "_VENV_HASH_BYTES", 20)
    findings = _parity(base, head)
    assert _details(findings) == {"NOT_PROVISIONED"}
    # exactly at the budget passes: the bound is "more than"
    total = sum(p.stat().st_size for p in base.site.rglob("*") if p.is_file())
    monkeypatch.setattr(bg, "_VENV_HASH_BYTES", total)
    assert _parity(base, head) == []
    monkeypatch.setattr(bg, "_VENV_HASH_BYTES", total - 1)
    assert _details(_parity(base, head)) == {"NOT_PROVISIONED"}


@posix_only
def test_untrusted_text_names_the_differences(tmp_path):
    base, head = _honest_pair(tmp_path)
    nasty = "evil`\n#name|x.py"
    (head.site / "dep_data" / nasty).write_text("x")
    (head.site / "dep.py").write_bytes(b"changed")
    (base.site / "dep_data" / "only_base.txt").write_text("b")
    findings = _parity(head, base)
    assert findings and all(type(d) is str and type(t) is str for d, t in findings)
    text = "\n".join(t for _, t in findings)
    for needle in ("only_base.txt", "dep.py", "evil"):
        assert needle in text, needle
    for _, t in findings:
        assert "\n" not in t and "`" not in t and "|" not in t and len(t) <= 400
    assert all(c.isprintable() and ord(c) < 127 for c in text.replace("\n", ""))


@posix_only
def test_parity_inventory_differences_and_bounds(tmp_path, monkeypatch):
    # an extra, RECORD-consistent dist on one side only is a difference, a differing owned file too
    base, head = _honest_pair(tmp_path / "extra")
    _add_dist(head, "added", {"added.py": b"a = 1\n"})
    findings = _parity(base, head)
    assert _details(findings) == {"DEPENDENCY_PARITY"} and any("added.py" in t for _, t in findings)
    base, head = _honest_pair(tmp_path / "differ")
    for side, data in ((base, b"one\n"), (head, b"two\n")):
        _add_dist(side, "same", {"same.py": data})
    assert any("same.py" in t for _, t in _parity(base, head))
    # the walk is bounded: entries and depth are errors, never a skip
    base, head = _honest_pair(tmp_path / "bounds")
    monkeypatch.setattr(bg, "_VENV_FINGERPRINT_LIMIT", 3)
    with pytest.raises(bg.BenchmarkGateError) as e:
        _parity(base, head)
    assert _code(e) == "TREE_TOO_LARGE"
    monkeypatch.setattr(bg, "_VENV_FINGERPRINT_LIMIT", 200_000)
    deep = base.site / "d"
    for _ in range(bg._MAX_HASH_DEPTH + 2):
        deep = deep / "d"
    try:
        deep.mkdir(parents=True)
    except OSError:
        pytest.skip("path too long for this filesystem")
    with pytest.raises(bg.BenchmarkGateError) as e:
        _parity(base, head)
    assert _code(e) == "TREE_TOO_LARGE"
    # a venv that is not a venv is the layout's own refusal
    with pytest.raises(bg.BenchmarkGateError) as e:
        bg.dependency_parity(tmp_path / "nope" / "bin", head.bin, base.export, head.export)
    assert _code(e) == "VENV_NOT_ISOLATED"


# --- T2b2 _parse_listing_oids and verify_export_against_commit ----------------------------------------------------------------------------

def _vrepo(tmp_path: Path, fmt: str, files: dict, *, attrs: str | None = None) -> tuple[Path, str]:
    """A repository of the given object format (``sha1``/``sha256``) with ``files`` (as ``make_commit``), a gitlink ``vendor/sub`` and one
    commit; ``attrs`` becomes a committed ``.gitattributes``."""
    repo = tmp_path / f"repo-{fmt}"
    repo.mkdir()
    git(repo, "init", "-q", f"--object-format={fmt}")
    make_commit(repo, files, "c")
    if attrs is not None:  # staged AFTER the files: the blobs are stored as written, so the export is what must not convert them
        (repo / ".gitattributes").write_text(attrs)
        git(repo, "add", "--", ".gitattributes")
    git(repo, "update-index", "--add", "--cacheinfo", "160000," + "ab" * (20 if fmt == "sha1" else 32) + ",vendor/sub")
    git(repo, "commit", "-q", "-m", "c")
    return repo, git(repo, "rev-parse", "HEAD")


BASIC = {"src/app/__init__.py": "", "src/app/core.py": "def f():\n    return 1\n", "tools/run.sh": ("exec", "#!/bin/sh\n"),
         "link": ("link", "src/app/core.py"), "README.md": "r\n"}


def _vexport(tmp_path, monkeypatch, fmt="sha1", files=BASIC, attrs=None):
    temp = tmp_path / "tmp"
    temp.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    try:
        bg._require_modern_git()
    except bg.BenchmarkGateError as exc:
        if exc.code != "GIT_TOO_OLD":
            raise
        pytest.skip(f"git >= 2.43 is needed: {exc.detail}")
    repo, commit = _vrepo(tmp_path, fmt, files, attrs=attrs)
    export = bg.export_tree(repo, commit, bg.fixed_parent() / DISPATCH_ROOT / "head")
    return types.SimpleNamespace(repo=repo, commit=commit, export=export,
                                 verify=lambda **kw: bg.verify_export_against_commit(repo, commit, export, **kw))


def _vd(findings):
    return sorted((d, p) for d, p in findings)


def test_parse_listing_oids_keeps_the_id_for_both_hash_widths_and_listing_is_unchanged():
    sha1, sha256 = "a1" * 20, "b2" * 32
    raw = (f"100644 blob {sha1}      12\tsrc/a.py\x00100755 blob {sha256}      3\ttools/run\x00"
           f"120000 blob {sha1}      4\tlink\x00160000 commit {sha256}       -\tvendor/sub\x00").encode()
    assert bg._parse_listing_oids(raw) == {"src/a.py": sha1, "tools/run": sha256, "link": sha1, "vendor/sub": sha256}
    # the same bytes through the untouched parser: the base's tuple shape
    assert bg._parse_listing(raw) == {"src/a.py": ("F", 12, False), "tools/run": ("F", 3, True), "link": ("L", 4, False),
                                      "vendor/sub": ("G", 0, False)}
    assert bg._parse_listing_oids(f"100644 blob {sha1}\tplain\x00".encode()) == {"plain": sha1}  # no -l: three fields
    assert bg._parse_listing_oids(b"") == {}
    for bad in (f"100644 blob {'A' * 40}      1\tx\0", f"100644 blob {'a' * 41}      1\tx\0", f"100644 blob {'a' * 63}      1\tx\0",
                "100644 blob abc      1\tx\0", f"100644 blob {sha1} 1 2\tx\0", f"100644 blob {sha1}      1 x\0", f"100644 blob {sha1}      1\tx",
                f"100644 blob é{'a' * 39}      1\tx\0"):
        with pytest.raises(bg.BenchmarkGateError) as e:
            bg._parse_listing_oids(bad.encode())
        assert e.value.code == "GIT_FAILED", bad


def _add_honest_install(root: Path):
    for rel, data in (("app.egg-info/PKG-INFO", b"Name: app\n"), ("app.egg-info/SOURCES.txt", b"x\n"), ("src/pkg.egg-info/PKG-INFO", b"Name: p\n"),
                      ("build/lib/app/core.py", b"x = 1\n"), ("build/lib/app/ext.cpython-312-darwin.so", b"\x7fELF"),
                      ("build/lib/app/__pycache__/core.cpython-312.pyc", b"\0"), ("build/bdist.x/y.pth", b"p\n"),
                      ("dist/app-1.0-py3-none-any.whl", b"PK"), ("dist/app-1.0.tar.gz", b"gz"), (".eggs/setuptools-1.egg", b"PK"),
                      (".eggs/__pycache__/m.pyc", b"\0"), (".eggs/sitecustomize.py", b"x\n"), ("app.egg-info/hashlib.py", b"x\n")):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def test_honest_exports_pass(world):
    for side in world.sides.values():
        assert bg.verify_export_against_commit(world.repo, side.commit, side.export) == []
        _add_honest_install(side.export)
        assert bg.verify_export_against_commit(world.repo, side.commit, side.export) == []
    # the fixture really holds the shapes the row names
    head = world.sides["head"].export
    assert (head / "link").is_symlink() and (head / "vendor/sub").is_dir() and not any((head / "vendor/sub").iterdir())
    assert os.access(head / "tools/run.sh", os.X_OK)


@pytest.mark.parametrize("fmt", ["sha1", "sha256"])
def test_tracked_file_differences(tmp_path, monkeypatch, fmt):
    w = _vexport(tmp_path, monkeypatch, fmt)
    assert w.verify() == []
    ex = w.export

    def differs(rel, mutate):
        path = ex / rel
        backup = path.read_bytes() if path.is_file() and not path.is_symlink() else None
        link_target = os.readlink(path) if path.is_symlink() else None
        mutate(path)
        try:
            assert _vd(w.verify()) == [("TRACKED_FILE_DIFFERS", rel)], rel
        finally:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            elif path.is_symlink() or path.exists():
                path.unlink()
            if backup is not None:
                path.write_bytes(backup)
                path.chmod(0o755 if rel == "tools/run.sh" else 0o644)
            elif link_target is not None:
                path.symlink_to(link_target)
            elif rel == "vendor/sub":
                path.mkdir()
        assert w.verify() == []

    differs("src/app/core.py", lambda p: p.write_text("def f():\n    return 9\n"))  # same size, other byte
    differs("src/app/core.py", lambda p: p.write_text("def f():\n    return 1\n# more\n"))
    differs("src/app/core.py", lambda p: p.chmod(0o755))
    differs("tools/run.sh", lambda p: p.chmod(0o644))
    differs("README.md", lambda p: (p.unlink(), p.symlink_to("src/app/core.py")))
    differs("README.md", lambda p: p.unlink())  # missing
    differs("README.md", lambda p: (p.unlink(), p.mkdir()))  # a directory where a file is tracked
    # tracked symlink: other target, escaping target, replaced by a file, a directory
    differs("link", lambda p: (p.unlink(), p.symlink_to("README.md")))
    differs("link", lambda p: (p.unlink(), p.symlink_to("../../outside")))
    differs("link", lambda p: (p.unlink(), p.write_text("src/app/core.py")))
    differs("link", lambda p: p.unlink())
    # an escaping target keeps its bytes only if the export itself was built so: export_tree refuses that, so the case is a swapped ancestor
    # directory (a tracked directory replaced by a symlink out of the export) -- the link, the file below it and the symlink all fail closed
    outside = tmp_path / "outside"
    outside.mkdir()
    shutil.rmtree(ex / "tools")
    (ex / "tools").symlink_to(outside)
    assert _vd(w.verify()) == [("TRACKED_FILE_DIFFERS", "tools/run.sh"), ("UNTRACKED_PYTHON_FILE", "tools")]
    (ex / "tools").unlink()
    (ex / "tools").mkdir()
    (ex / "tools/run.sh").write_text("#!/bin/sh\n")
    (ex / "tools/run.sh").chmod(0o755)
    assert w.verify() == []
    # gitlink: non-empty, a file, a symlink, missing
    differs("vendor/sub", lambda p: (p / "x").write_text("x"))
    differs("vendor/sub", lambda p: (p / "d").mkdir())
    differs("vendor/sub", lambda p: (shutil.rmtree(p), p.write_text("x")))
    differs("vendor/sub", lambda p: (shutil.rmtree(p), p.symlink_to("src")))
    differs("vendor/sub", lambda p: shutil.rmtree(p))


@pytest.mark.parametrize("fmt", ["sha1", "sha256"])
def test_tracked_link_resolving_out_of_the_export_differs(tmp_path, monkeypatch, fmt):
    """The link's bytes still match the listing, but its target name became a symlink out of the export."""
    w = _vexport(tmp_path, monkeypatch, fmt, {"a/l": ("link", "../b"), "b": "x\n"})
    assert w.verify() == []
    outside = tmp_path / "outside"
    outside.mkdir()
    (w.export / "b").unlink()
    (w.export / "b").symlink_to(outside)
    assert _vd(w.verify()) == sorted([("TRACKED_FILE_DIFFERS", "b"), ("TRACKED_FILE_DIFFERS", "a/l")])


UNTRACKED_BAD = ("hashlib.py", "mod.pyc", "ext.so", "ext.cpython-312-darwin.so", "x.pth", "x.zip", "x.egg", "x.whl", "sitecustomize.py",
                 "usercustomize.py", "sitecustomize.txt", "m.pyd", "conftest.py", "UPPER.PY")


def test_untracked_entries(tmp_path, monkeypatch):
    w = _vexport(tmp_path, monkeypatch)
    ex = w.export
    for where in ("", "src/app/", "newdir/deep/", "vendor/", "src/pkg.egg-info/"):  # not exempt: a root file, tracked dirs, new dirs, a src egg-info
        for name in UNTRACKED_BAD:
            (ex / where).mkdir(parents=True, exist_ok=True)
            path = ex / where / name
            path.write_bytes(b"x")
            assert _vd(w.verify()) == [("UNTRACKED_PYTHON_FILE", f"{where}{name}")], (where, name, w.verify())
            path.unlink()
        assert w.verify() == []
    shutil.rmtree(ex / "newdir")
    shutil.rmtree(ex / "src/pkg.egg-info")
    # a __pycache__ directory (empty or not), a symlink, a fifo, a socket
    (ex / "src/__pycache__").mkdir()
    assert _vd(w.verify()) == [("UNTRACKED_PYTHON_FILE", "src/__pycache__")]
    (ex / "src/__pycache__").rmdir()
    (ex / "newlink").symlink_to("README.md")
    assert _vd(w.verify()) == [("UNTRACKED_PYTHON_FILE", "newlink")]
    (ex / "newlink").unlink()
    os.mkfifo(ex / "fifo")
    assert _vd(w.verify()) == [("UNTRACKED_PYTHON_FILE", "fifo")]
    (ex / "fifo").unlink()
    short = tmp_path / "s"  # AF_UNIX paths are short
    short.mkdir()
    import socket
    sock = socket.socket(socket.AF_UNIX)
    try:
        os.chdir(ex)
        sock.bind("sock")
        assert _vd(w.verify()) == [("UNTRACKED_PYTHON_FILE", "sock")]
    finally:
        sock.close()
        os.chdir(tmp_path)
        (ex / "sock").unlink(missing_ok=True)
    # root-level build/, dist/, .eggs/, <root>/*.egg-info: module suffixes and __pycache__ pass; links and special files still do not
    for top in ("build", "dist", ".eggs", "x.egg-info"):
        for name in UNTRACKED_BAD:
            (ex / top / "sub").mkdir(parents=True, exist_ok=True)
            (ex / top / "sub" / name).write_bytes(b"x")
        (ex / top / "__pycache__").mkdir()
        assert w.verify() == [], top
        (ex / top / "link").symlink_to("../README.md")
        assert _vd(w.verify()) == [("UNTRACKED_PYTHON_FILE", f"{top}/link")], top
        shutil.rmtree(ex / top)
    # the exemption is the root-level one only: a nested build/ is not exempt
    (ex / "src/build").mkdir()
    (ex / "src/build/x.py").write_bytes(b"x")
    assert _vd(w.verify()) == [("UNTRACKED_PYTHON_FILE", "src/build/x.py")]
    shutil.rmtree(ex / "src/build")
    # non-code untracked inputs are not findings (disclosed)
    for name in (".env", "data.json", "setup.cfg", "notes.txt"):
        (ex / name).write_text("x")
    assert w.verify() == []


def test_overlay_allowance(tmp_path, monkeypatch):
    w = _vexport(tmp_path, monkeypatch)
    ex = w.export
    body = b"def bench():\n    pass\n"
    rel = "benchmarks/bench_new.py"
    (ex / "benchmarks").mkdir()
    (ex / rel).write_bytes(body)
    allow = {rel: hashlib.sha256(body).hexdigest()}
    assert _vd(w.verify()) == [("UNTRACKED_PYTHON_FILE", rel)]  # no allowance (the head)
    assert w.verify(allow=allow) == [] and w.verify(allow={}) != [] and w.verify(allow=None) != []
    (ex / rel).write_bytes(body + b" ")  # a changed byte
    assert _vd(w.verify(allow=allow)) == [("UNTRACKED_PYTHON_FILE", rel)]
    (ex / rel).unlink()
    (ex / rel).symlink_to("../README.md")  # a symlink
    assert _vd(w.verify(allow=allow)) == [("UNTRACKED_PYTHON_FILE", rel)]
    (ex / rel).unlink()
    (ex / rel).write_bytes(body)
    (ex / "benchmarks/other.py").write_bytes(b"x")  # nothing else new in the directory the overlay created
    assert _vd(w.verify(allow=allow)) == [("UNTRACKED_PYTHON_FILE", "benchmarks/other.py")]
    (ex / "benchmarks/other.py").unlink()
    (ex / "benchmarks/__pycache__").mkdir()
    assert _vd(w.verify(allow=allow)) == [("UNTRACKED_PYTHON_FILE", "benchmarks/__pycache__")]
    (ex / "benchmarks/__pycache__").rmdir()
    (ex / "elsewhere.py").write_bytes(body)  # the same bytes at another path are not allowed
    assert _vd(w.verify(allow=allow)) == [("UNTRACKED_PYTHON_FILE", "elsewhere.py")]
    (ex / "elsewhere.py").unlink()
    # the allowance is permission, not a requirement, and it does not excuse a tracked file
    (ex / rel).unlink()
    assert w.verify(allow=allow) == []
    (ex / "README.md").write_text("changed\n")
    assert _vd(w.verify(allow={"README.md": hashlib.sha256(b"changed\n").hexdigest()})) == [("TRACKED_FILE_DIFFERS", "README.md")]


@pytest.mark.parametrize("fmt", ["sha1", "sha256"])
def test_export_applies_no_filters(tmp_path, monkeypatch, fmt):
    attrs = "*.txt ident\n*.crlf text eol=crlf\n*.enc text working-tree-encoding=UTF-16\n"
    files = {"a.txt": "$Id$ x\n", "b.crlf": "one\ntwo\n", "c.enc": "café\n", "plain.txt": "no keyword\n"}
    w = _vexport(tmp_path, monkeypatch, fmt, files, attrs=attrs)
    blob = lambda rel: subprocess.run(["git", "show", f"{w.commit}:{rel}"], cwd=w.repo, env=GIT_ENV, capture_output=True, check=True).stdout
    for rel in files:  # the export holds the blob bytes, so the check agrees with the listing
        assert (w.export / rel).read_bytes() == blob(rel)
    assert (w.export / "a.txt").read_bytes() == b"$Id$ x\n" and b"\r" not in (w.export / "b.crlf").read_bytes()
    assert w.verify() == []
    # the blob id is computed with the commit's hash width over the exact bytes
    algo = hashlib.sha1 if fmt == "sha1" else hashlib.sha256
    data = (w.export / "b.crlf").read_bytes()
    assert git(w.repo, "rev-parse", f"{w.commit}:b.crlf") == algo(b"blob %d\0" % len(data) + data).hexdigest()


def test_honest_install_limits_fail_closed(tmp_path, monkeypatch):
    """A build that rewrites a tracked file, writes an untracked ``_version.py`` (setuptools_scm, hatch-vcs: exports have no ``.git``) or
    builds an extension in place fails closed. The workaround is committed generated files or out-of-tree builds."""
    w = _vexport(tmp_path, monkeypatch)
    ex = w.export
    (ex / "src/app/core.py").write_text("# generated by a build\ndef f():\n    return 1\n")
    assert _vd(w.verify()) == [("TRACKED_FILE_DIFFERS", "src/app/core.py")]
    (ex / "src/app/core.py").write_text("def f():\n    return 1\n")
    assert w.verify() == []
    (ex / "src/app/_version.py").write_text("version = '1'\n")
    assert _vd(w.verify()) == [("UNTRACKED_PYTHON_FILE", "src/app/_version.py")]
    (ex / "src/app/_version.py").unlink()
    (ex / "src/app/_speedups.cpython-312-darwin.so").write_bytes(b"\xcf\xfa")
    assert _vd(w.verify()) == [("UNTRACKED_PYTHON_FILE", "src/app/_speedups.cpython-312-darwin.so")]


def test_error_mappings(tmp_path, monkeypatch):
    w = _vexport(tmp_path, monkeypatch)
    # findings are returned, never raised
    (w.export / "hashlib.py").write_text("x")
    assert w.verify() != []
    (w.export / "hashlib.py").unlink()
    # a commit that is not valid or not present
    for commit, code in (("zz", "COMMIT_INVALID"), ("0" * 40, "COMMIT_NOT_FOUND")):
        with pytest.raises(bg.BenchmarkGateError) as e:
            bg.verify_export_against_commit(w.repo, commit, w.export)
        assert e.value.code == code
    # an export root that is not one of ours
    with pytest.raises(bg.BenchmarkGateError) as e:
        bg.verify_export_against_commit(w.repo, w.commit, tmp_path)
    assert e.value.code == "DEST_REJECTED"
    # a listing that is oversize / hostile: EXPORT_*; git output over the cap: GIT_OUTPUT_TOO_LARGE
    monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", 3)
    with pytest.raises(bg.BenchmarkGateError) as e:
        w.verify()
    assert e.value.code == "EXPORT_TOO_LARGE"
    monkeypatch.undo()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    monkeypatch.setitem(bg._PrivateGit.run.__kwdefaults__, "cap", 10)  # the default is bound at definition time
    with pytest.raises(bg.BenchmarkGateError) as e:
        w.verify()
    assert e.value.code == "GIT_OUTPUT_TOO_LARGE"
    monkeypatch.undo()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    # the walk's own bounds: entries and depth are TREE_TOO_LARGE, an unreadable directory TREE_UNREADABLE
    for i in range(6):
        (w.export / f"n{i}.txt").write_text("x")
    monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", 12)  # the listing (about 11 with directories) fits, the walk's 6 extra entries do not
    with pytest.raises(bg.BenchmarkGateError) as e:
        w.verify()
    assert e.value.code in ("TREE_TOO_LARGE", "EXPORT_TOO_LARGE")
    monkeypatch.undo()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    for i in range(6):
        (w.export / f"n{i}.txt").unlink()
    deep = w.export / "d"
    for _ in range(bg._MAX_HASH_DEPTH + 2):
        deep = deep / "d"
    try:
        deep.mkdir(parents=True)
    except OSError:
        pytest.skip("path too long for this filesystem")
    with pytest.raises(bg.BenchmarkGateError) as e:
        w.verify()
    assert e.value.code == "TREE_TOO_LARGE"
    shutil.rmtree(w.export / "d")
    (w.export / "locked").mkdir()
    (w.export / "locked").chmod(0)
    try:
        if os.geteuid() != 0:
            with pytest.raises(bg.BenchmarkGateError) as e:
                w.verify()
            assert e.value.code == "TREE_UNREADABLE"
    finally:
        (w.export / "locked").chmod(0o755)
    (w.export / "locked").rmdir()
    # attacker text in a finding is escaped
    (w.export / "ev\x1b[31mil.py").write_text("x")
    findings = w.verify()
    assert len(findings) == 1 and findings[0][0] == "UNTRACKED_PYTHON_FILE" and "\x1b" not in findings[0][1]


# --- _compare_checks: steps 1 to 6 (T3a) ---
# ``_compare_checks`` is driven directly for passing paths (it returns the context the later steps use); ``_compare_impl`` for the paths that
# end with a result.

BENCH = "benchmarks/bench_x.py"
GATE = {"command": f"pytest -q --no-header {BENCH}", "benchmark_paths": [BENCH], "benchmark_symbol": "build"}
QUIET = lambda: (0.1, 4)  # noqa: E731
NO_GATE = object()  # "use the case's gate" (None is a gate value the tests pass on purpose)


class Case:
    """One compare call over a ``world``: sides, seams and options, all adjustable before ``checks()`` / ``impl()``."""

    def __init__(self, world, tmp_path, monkeypatch):
        self.world, self.mp, self.tmp = world, monkeypatch, tmp_path
        self.n = 0
        self.spy: list[str] = []
        self.allow = True
        self.pin_mods = {}  # side name -> fn(pin) -> pin
        self.probe = QUIET
        self.gate = dict(GATE)
        self.attempt = 1
        self.salt = "ab12"
        self.out_dir = tmp_path / "out"
        self.out_dir.mkdir(exist_ok=True)
        self.out_dir.chmod(0o700)
        self.roots = (str(world.sides["base"].export), str(world.sides["head"].export))
        for side in world.sides.values():  # the fixture's pytest .pth is not installed by any dist: give it an owner, as an honest install has
            site = next((side.bin.parent / "lib").glob("python3*/site-packages"))
            pth = (site / "zz_pytest.pth").read_bytes()
            _add_dist(types.SimpleNamespace(site=site), "zzpytest", {}, rows=[["zz_pytest.pth", "sha256=" + _b64(pth), str(len(pth))]])
        self.base = self._side("base")
        self.head = self._side("head")

    def interp(self, bin_dir):
        self.spy.append("interpreter_of")
        pin = bg.interpreter_pin(bin_dir, outside=self.roots, probe=_stub_probe(self.world.prefix))
        for name, mod in self.pin_mods.items():
            if os.path.realpath(bin_dir) == os.path.realpath(self.world.sides[name].bin):
                pin = mod(pin)
        return pin

    def _side(self, name):
        s = self.world.sides[name]
        pin = bg.interpreter_pin(s.bin, outside=self.roots, probe=_stub_probe(self.world.prefix))
        return bg.Side(str(s.export), s.commit, str(s.bin), str(s.snapshot), hashlib.sha256(s.snapshot.read_bytes()).hexdigest(), pin.sha256)

    def out(self):
        self.n += 1
        return str(self.out_dir / f"result-{self.n}.json")

    def kwargs(self, **over):
        kw = dict(attempt=self.attempt, out_path=self.out(), allow_writable_interpreter=self.allow, load_probe=self.probe,
                  order_salt=self.salt, interpreter_of=self.interp)
        kw.update(over)
        return kw

    def checks(self, gate=NO_GATE, base=None, head=None, **over):
        run = bg._Run()
        self.common = run.common
        return bg._compare_checks(self.gate if gate is NO_GATE else gate, str(self.world.repo), base or self.base, head or self.head, run=run, **self.kwargs(**over))

    def impl(self, gate=NO_GATE, base=None, head=None, **over):
        kw = self.kwargs(**over)
        self.last_out = kw["out_path"]
        return bg._compare_impl(self.gate if gate is NO_GATE else gate, str(self.world.repo), base or self.base, head or self.head, **kw)

    def prepare(self, mutate=None, at9=None, gate=NO_GATE, **over):
        """Steps 1 to 6 and then 7 to 9. `mutate`, if given, runs between 6 and 7 (the exports are still writable); `at9` runs at the
        start of step 9, after the seal and the hash."""
        if at9 is not None:
            real_snapshots = bg._check_snapshots

            def hooked(base, head, stage):
                if stage == "overlaid":
                    self.mp.setattr(bg, "_check_snapshots", real_snapshots)
                    at9(self)
                return real_snapshots(base, head, stage)
            self.mp.setattr(bg, "_check_snapshots", hooked)
        run = bg._Run()
        self.common = run.common
        kw = self.kwargs(**over)
        gate = self.gate if gate is NO_GATE else gate
        checked = bg._compare_checks(gate, str(self.world.repo), self.base, self.head, run=run, **kw)
        self.checked, self.run = checked, run
        if mutate is not None:
            mutate(self)
        return bg._compare_prepare(str(self.world.repo), self.base, self.head, checked, interpreter_of=kw["interpreter_of"], run=run)

    def spies(self, *names):
        for name in names:
            real = getattr(bg, name)

            def wrap(*a, _real=real, _name=name, **k):
                self.spy.append(_name)
                return _real(*a, **k)
            self.mp.setattr(bg, name, wrap)


@pytest.fixture
def case(world, tmp_path, monkeypatch):
    return Case(world, tmp_path, monkeypatch)


def _ends(result, reason, detail=None, stage="pre_overlay"):
    assert result["reason"] == reason and result["result"] == bg.COMPARE_RESULT_OF_REASON[reason], result
    assert result["stage"] == stage
    if detail is not None:
        assert result["detail"] == detail, result


BAD_ARGS = {
    "side-not-a-side": lambda c: dict(base=tuple(c.base)),
    "side-int-root": lambda c: dict(base=c.base._replace(root=5)),
    "side-relative-root": lambda c: dict(base=c.base._replace(root="rel/dir")),
    "side-nul-bin": lambda c: dict(head=c.head._replace(bin_dir="/a\0b")),
    "side-empty-snapshot": lambda c: dict(head=c.head._replace(snapshot="")),
    "snapshot-pin-short": lambda c: dict(base=c.base._replace(snapshot_sha256="ab")),
    "snapshot-pin-upper": lambda c: dict(base=c.base._replace(snapshot_sha256="A" * 64)),
    "interpreter-pin-int": lambda c: dict(head=c.head._replace(interpreter_sha256=7)),
    "commit-non-str": lambda c: dict(head=c.head._replace(commit=None)),
    "attempt-0": lambda c: dict(attempt=0),
    "attempt-3": lambda c: dict(attempt=3),
    "attempt-bool": lambda c: dict(attempt=True),
    "attempt-float": lambda c: dict(attempt=1.0),
    "salt-empty": lambda c: dict(order_salt=""),
    "salt-upper": lambda c: dict(order_salt="AB"),
    "salt-65": lambda c: dict(order_salt="a" * 65),
    "salt-non-str": lambda c: dict(order_salt=12),
    "out-relative": lambda c: dict(out_path="result.json"),
    "out-none": lambda c: dict(out_path=None),
    "out-exists": lambda c: dict(out_path=str(c.tmp / "exists.json")),
}


@posix_only
@pytest.mark.parametrize("name", sorted(BAD_ARGS))
def test_bad_arguments_raise_before_any_child_or_touch(case, name):
    (case.tmp / "exists.json").write_text("x")
    case.spies("_run_once", "seal_export", "export_commit", "validate_benchmark_gate", "is_ancestor", "interpreter_pin")
    before = sorted(os.listdir(case.out_dir))
    with pytest.raises(bg.BenchmarkGateError) as e:
        case.impl(**BAD_ARGS[name](case))
    assert e.value.code == "MEASURE_ARGS_INVALID"
    assert case.spy == [] and sorted(os.listdir(case.out_dir)) == before


@posix_only
def test_bad_or_unknown_commits(case):
    case.spies("_run_once", "seal_export", "export_commit")
    for commit in ("xyz", "A" * 40, "a" * 39, "a" * 64):  # a 64-hex commit next to a 40-hex one is a length mismatch
        with pytest.raises(bg.BenchmarkGateError) as e:
            case.impl(head=case.head._replace(commit=commit))
        assert e.value.code == "COMMIT_INVALID"
    with pytest.raises(bg.BenchmarkGateError) as e:  # unknown, well formed: git says so at step 3
        case.impl(base=case.base._replace(commit="0" * 40))
    assert e.value.code == "COMMIT_NOT_FOUND"
    assert case.spy == []


@posix_only
def test_bad_arguments_still_raise_first_when_the_platform_is_unsupported(case, monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    with pytest.raises(bg.BenchmarkGateError) as e:
        case.impl(attempt=0)
    assert e.value.code == "MEASURE_ARGS_INVALID"


@posix_only
def test_unsupported_platform_is_a_result_after_arguments_are_validated(case, monkeypatch):
    case.spies("validate_benchmark_gate", "is_ancestor", "export_commit")
    monkeypatch.setattr(os, "name", "nt")
    result = case.impl()
    monkeypatch.undo()
    _ends(result, "UNSUPPORTED_PLATFORM", stage="pre_overlay")
    assert case.spy == [] and result["order_salt"] == "ab12" and result["attempt"] == 1 and result["interpreter_writable"] is None
    assert json.loads(Path(case.last_out).read_text()) == result  # the file is written for every ending


@posix_only
@pytest.mark.parametrize("change,code", [
    (lambda g: {**g, "warmup_runs": 0}, "BOUNDS_REJECTED"),
    (lambda g: {**g, "benchmark_paths": ["../x.py"]}, "PATH_REJECTED"),
    (lambda g: {**g, "command": "make bench"}, "COMMAND_REJECTED"),
    (lambda g: None, "GATE_MISSING"),
    (lambda g: {**g, "surprise": 1}, "KEY_UNKNOWN"),
])
def test_gate_rejected_maps_the_gate_code(case, change, code):
    case.spies("is_ancestor", "export_commit")
    result = case.impl(gate=change(case.gate))
    _ends(result, "GATE_REJECTED", code)
    assert result["harness_sha256"] == bg.harness_sha256() and result["gate_sha256"] is None
    assert case.spy == [] and result["base_commit"] == case.base.commit and result["head_commit"] == case.head.commit


@posix_only
def test_a_good_gate_fills_target_hashes_and_the_gate_fields(case):
    checked = case.checks()
    normalized, _ = bg.validate_benchmark_gate(case.gate)
    assert checked.gate == normalized and checked.target == bg.benchmark_target(normalized) == BENCH
    assert case.common["gate_sha256"] == bg.gate_sha256(normalized) and case.common["harness_sha256"] == bg.harness_sha256()
    assert (case.common["repeats"], case.common["min_improvement"], case.common["max_noise"]) == (6, 0.1, 0.1)
    assert case.common["order_salt"] == "ab12" and checked.order_salt == "ab12"


@posix_only
def test_a_missing_salt_is_generated_and_recorded(case):
    seen = set()
    for _ in range(3):
        checked = case.checks(order_salt=None)
        assert re.fullmatch("[0-9a-f]{16}", checked.order_salt) and case.common["order_salt"] == checked.order_salt
        seen.add(checked.order_salt)
    assert len(seen) == 3


@posix_only
def test_gate_validation_precedes_the_ancestry_check_and_ancestry_raises(case):
    swapped_base, swapped_head = case.base._replace(commit=case.head.commit), case.head._replace(commit=case.base.commit)
    case.spies("export_commit", "_export_root")
    with pytest.raises(bg.BenchmarkGateError) as e:
        case.impl(base=swapped_base, head=swapped_head)
    assert e.value.code == "BASE_NOT_ANCESTOR" and case.spy == []
    _ends(case.impl(gate={**case.gate, "warmup_runs": 0}, base=swapped_base, head=swapped_head), "GATE_REJECTED", "BOUNDS_REJECTED")


def _iso(result, detail, text=None):
    _ends(result, "ISOLATION_REJECTED", detail)
    if text is not None:
        assert any(text in t for t in result["untrusted_text"]), result["untrusted_text"]


@posix_only
def test_step4_roots_must_be_distinct_siblings_of_ours(case, tmp_path):
    for head in (case.head._replace(root=case.base.root), case.head._replace(root=case.base.root + "/src"),
                 case.head._replace(root=str(tmp_path / "elsewhere"))):
        with pytest.raises(bg.BenchmarkGateError) as e:
            case.impl(head=head)
        assert e.value.code == "DEST_REJECTED"
    other = bg.fixed_parent() / "bench-c4d3other"
    bg.export_tree(case.world.repo, case.world.head, other / "head")
    with pytest.raises(bg.BenchmarkGateError) as e:  # ours, but not a sibling
        case.impl(head=case.head._replace(root=str(other / "head")))
    assert e.value.code == "DEST_REJECTED"


@posix_only
def test_step4_commit_must_match_the_export(case):
    with pytest.raises(bg.BenchmarkGateError) as e:
        case.impl(base=case.base._replace(commit=case.head.commit))  # an ancestor of itself, so step 3 passes
    assert e.value.code == "OVERLAY_COMMIT_MISMATCH"


def _git_dir(c):
    (c.world.sides["head"].export / ".git").mkdir()


def _bins_shared(c):
    c.head = c.head._replace(bin_dir=c.base.bin_dir)


def _bin_inside_root(c):
    inner = c.world.sides["head"].export / "bin"
    inner.mkdir()
    c.head = c.head._replace(bin_dir=str(inner))


def _differs(c):
    c.pin_mods["head"] = lambda pin: pin._replace(real_python=pin.real_python + "-other")


def _changed(c):
    c.base = c.base._replace(interpreter_sha256="0" * 64)


def _writable(c):
    c.allow = False


def _harness_under_root(c):
    c.mp.setattr(bg, "__file__", str(c.world.sides["base"].export / "benchmark_gate.py"))


def _snapshot_changed(c):
    c.head = c.head._replace(snapshot_sha256="1" * 64)


def _hook(c):
    site = next((c.world.sides["head"].bin.parent / "lib").glob("python3*/site-packages"))
    (site / "evil.pth").write_text("import evil_hook\n")


def _fault_parity(c):
    site = next((c.world.sides["head"].bin.parent / "lib").glob("python3*/site-packages"))
    (site / "bare_module.py").write_text("x = 1\n")


def _tracked(c):
    (c.world.sides["base"].export / "src/app/core.py").write_text("tampered\n")


def _untracked(c):
    (c.world.sides["head"].export / "hashlib.py").write_text("x = 1\n")


# (detail, applier) in the order step 4 checks them; an earlier fault must win over any later one.
FAULTS = [
    ("ROOT_HAS_GIT", _git_dir), ("BIN_NOT_ISOLATED", _bins_shared), ("INTERPRETER_DIFFERS", _differs),
    ("INTERPRETER_CHANGED", _changed), ("INTERPRETER_WRITABLE", _writable), ("HARNESS_FILE_UNDER_ROOT", _harness_under_root),
    ("SNAPSHOT_CHANGED", _snapshot_changed), ("VENV_HOOK_REJECTED", _hook), ("DEPENDENCY_PARITY", _fault_parity),
    ("TRACKED_FILE_DIFFERS", _tracked),
]
FAULT_TEXT = {"VENV_HOOK_REJECTED": "evil.pth", "DEPENDENCY_PARITY": "bare_module.py", "TRACKED_FILE_DIFFERS": "src/app/core.py"}


@posix_only
@pytest.mark.parametrize("detail,apply", FAULTS, ids=[f[0] for f in FAULTS])
def test_step4_isolation_rows(case, detail, apply):
    case.spies("diff_checks", "check_venv", "dependency_parity", "verify_export_against_commit")
    apply(case)
    case.spy.clear()
    result = case.impl()
    _iso(result, detail, FAULT_TEXT.get(detail))
    assert result["python"] is not None or detail in ("ROOT_HAS_GIT", "BIN_NOT_ISOLATED", "INTERPRETER_DIFFERS")
    assert "diff_checks" not in case.spy  # step 5 never ran
    assert json.loads(Path(case.last_out).read_text()) == result


@posix_only
def test_untracked_python_file_is_isolation_rejected(case):
    _untracked(case)
    _iso(case.impl(), "UNTRACKED_PYTHON_FILE", "hashlib.py")


@posix_only
@pytest.mark.parametrize("later", range(1, len(FAULTS)))
def test_step4_order_an_earlier_fault_beats_the_next_one(case, later):
    FAULTS[later - 1][1](case)
    FAULTS[later][1](case)
    _iso(case.impl(), FAULTS[later - 1][0])


@posix_only
def test_step4_writable_interpreter_needs_the_flag_and_the_result_says_so(case):
    case.allow = False
    result = case.impl()
    _iso(result, "INTERPRETER_WRITABLE")
    assert result["interpreter_writable"] is True
    case.pin_mods.update(base=lambda p: p._replace(writable=False), head=lambda p: p._replace(writable=False))
    assert case.checks().writable is False  # a non-writable interpreter passes without the flag
    case.pin_mods.clear()
    case.allow = True
    assert case.checks().writable is True and case.common["interpreter_writable"] is True  # the flag lets it through, and the fact is recorded


@posix_only
def test_step4_interpreter_cross_checks(case):
    # different real interpreters on the sides
    case.pin_mods["base"] = lambda p: p._replace(real_python=p.real_python + "-other")
    _iso(case.impl(), "INTERPRETER_DIFFERS")
    case.pin_mods.clear()
    # a real interpreter inside a venv or an export (the seam is not trusted to say otherwise)
    for inside in (case.world.sides["head"].bin.parent / "python3", case.world.sides["base"].export / "python3"):
        case.pin_mods.update(base=lambda p, i=str(inside): p._replace(real_python=i), head=lambda p, i=str(inside): p._replace(real_python=i))
        _iso(case.impl(), "INTERPRETER_DIFFERS")
    case.pin_mods.clear()
    # a --copies venv / a probe mismatch surface as VENV_NOT_ISOLATED from the helper; a missing stdlib or an oversized one as NOT_PROVISIONED
    for code, detail in (("VENV_NOT_ISOLATED", "INTERPRETER_DIFFERS"), ("TREE_TOO_LARGE", "NOT_PROVISIONED"), ("DEST_REJECTED", "NOT_PROVISIONED"),
                         ("TREE_UNREADABLE", "NOT_PROVISIONED")):
        def boom(bin_dir, code=code):
            raise bg.BenchmarkGateError(code, "x")
        _iso(case.impl(interpreter_of=boom), detail)


@posix_only
def test_step4_a_bin_inside_a_root_is_not_isolated(case):
    _bin_inside_root(case)
    _iso(case.impl(), "BIN_NOT_ISOLATED")


@posix_only
def test_step4_no_python_is_not_provisioned(case):
    os.unlink(case.world.sides["head"].bin / "python")
    _iso(case.impl(), "NOT_PROVISIONED")


@posix_only
def test_step4_pin_is_compared_per_side(case):
    case.head = case.head._replace(interpreter_sha256="f" * 64)
    _iso(case.impl(), "INTERPRETER_CHANGED")


@posix_only
def test_step4_check_venv_errors_map(case):
    for code, detail in (("VENV_NOT_ISOLATED", "VENV_NOT_ISOLATED"), ("VENV_HOOK_REJECTED", "VENV_HOOK_REJECTED"),
                         ("TREE_UNREADABLE", "VENV_NOT_ISOLATED"), ("DEST_REJECTED", "VENV_NOT_ISOLATED")):
        def boom(*a, code=code, **k):
            error = bg.BenchmarkGateError(code, "x")
            error.hits = [{"path": "lib/x\x1b[31m.pth", "reason": "r"}]
            raise error
        case.mp.setattr(bg, "check_venv", boom)
        result = case.impl()
        _iso(result, detail)
        assert all("\x1b" not in t for t in result["untrusted_text"])
    case.mp.setattr(bg, "check_venv", lambda *a, **k: (_ for _ in ()).throw(bg.BenchmarkGateError("VENV_SNAPSHOT_INVALID", "x")))
    with pytest.raises(bg.BenchmarkGateError) as e:
        case.impl()
    assert e.value.code == "VENV_SNAPSHOT_INVALID"
    case.mp.setattr(bg, "check_venv", lambda *a, **k: "/same/venv")  # two sides, one venv root
    _iso(case.impl(), "VENV_NOT_ISOLATED")


@posix_only
def test_step4_a_missing_or_unreadable_snapshot_raises(case):
    os.unlink(case.world.sides["base"].snapshot)
    with pytest.raises(bg.BenchmarkGateError) as e:
        case.impl()
    assert e.value.code == "VENV_SNAPSHOT_INVALID"


@posix_only
def test_step4_dependency_parity_findings_and_errors(case):
    case.mp.setattr(bg, "dependency_parity", lambda *a: [("NOT_PROVISIONED", "venv over budget")])
    _iso(case.impl(), "NOT_PROVISIONED", "over budget")
    case.mp.setattr(bg, "dependency_parity", lambda *a: [("DEPENDENCY_PARITY", "only in head (1): a.py"), ("DEPENDENCY_PARITY", "b")])
    result = case.impl()
    _iso(result, "DEPENDENCY_PARITY")
    assert len(result["untrusted_text"]) == 2
    for code, detail in (("VENV_NOT_ISOLATED", "VENV_NOT_ISOLATED"), ("TREE_TOO_LARGE", "NOT_PROVISIONED"), ("TREE_UNREADABLE", "VENV_NOT_ISOLATED")):
        def boom(*a, code=code):
            raise bg.BenchmarkGateError(code, "x")
        case.mp.setattr(bg, "dependency_parity", boom)
        _iso(case.impl(), detail)


@posix_only
def test_step4_hostile_tree_errors_are_export_rejected_and_host_faults_raise(case):
    for code in ("EXPORT_TOO_LARGE", "EXPORT_PATH_REJECTED", "TREE_TOO_LARGE", "TREE_UNREADABLE", "SEAL_FAILED", "GIT_OUTPUT_TOO_LARGE"):
        def boom(*a, code=code, **k):
            raise bg.BenchmarkGateError(code, "x")
        case.mp.setattr(bg, "verify_export_against_commit", boom)
        _ends(case.impl(), "EXPORT_REJECTED", code)
    for code in ("GIT_TIMEOUT", "GIT_FAILED", "REPO_UNREADABLE"):
        def boom(*a, code=code, **k):
            raise bg.BenchmarkGateError(code, "x")
        case.mp.setattr(bg, "verify_export_against_commit", boom)
        with pytest.raises(bg.BenchmarkGateError) as e:
            case.impl()
        assert e.value.code == code


@posix_only
def test_step4_verification_runs_per_side_with_an_empty_allowance(case):
    calls = []
    real = bg.verify_export_against_commit

    def spy(repo, commit, root, **kw):
        calls.append((commit, str(root), kw))
        return real(repo, commit, root, **kw)
    case.mp.setattr(bg, "verify_export_against_commit", spy)
    case.checks()
    assert [(c[0], c[1]) for c in calls] == [(case.base.commit, case.base.root), (case.head.commit, case.head.root)]
    assert all(not (c[2].get("allow") or {}) for c in calls)


@posix_only
def test_step_order_on_a_passing_path(case):
    case.spies("validate_benchmark_gate", "is_ancestor", "export_commit", "check_venv", "dependency_parity", "verify_export_against_commit",
               "diff_checks")
    probes = []
    case.probe = lambda: probes.append("load_probe") or QUIET()
    case.checks()
    order = case.spy + probes
    assert order == ["validate_benchmark_gate", "is_ancestor", "export_commit", "export_commit", "interpreter_of", "interpreter_of",
                     "check_venv", "check_venv", "dependency_parity", "verify_export_against_commit", "verify_export_against_commit",
                     "diff_checks", "load_probe"]


@posix_only
def test_diff_checks_results(case):
    seen = []

    def raising(code, hits=()):
        def fn(repo, base, head, path):
            seen.append((base, head, path))
            error = bg.BenchmarkGateError(code, "x")
            error.hits = list(hits)
            raise error
        return fn

    hit = {"path": "a.py", "token": "sys.argv", "line_number": 3, "line": "x = sys.argv"}
    for code, reason in (("PROTECTED_PATH_CHANGED", "PROTECTED_PATH_CHANGED"), ("BENCHMARK_AWARE_CODE", "BENCHMARK_AWARE_CODE"),
                         ("GIT_OUTPUT_TOO_LARGE", "DIFF_UNCHECKABLE"), ("TREE_TOO_LARGE", "DIFF_UNCHECKABLE")):
        case.mp.setattr(bg, "diff_checks", raising(code, [hit] if reason != "DIFF_UNCHECKABLE" else []))
        result = case.impl()
        _ends(result, reason, code)
        if reason != "DIFF_UNCHECKABLE":
            assert any("sys.argv" in t and "a.py" in t for t in result["untrusted_text"])
        assert result["interpreter_writable"] is True  # step 4 had passed
    assert seen[0] == (case.base.commit, case.head.commit, BENCH)
    for code in ("GIT_TIMEOUT", "GIT_FAILED", "REPO_UNREADABLE"):
        case.mp.setattr(bg, "diff_checks", raising(code))
        with pytest.raises(bg.BenchmarkGateError) as e:
            case.impl()
        assert e.value.code == code


@posix_only
def test_host_busy_start_leaves_nothing_sealed_and_a_retry_succeeds_on_the_same_exports(case):
    case.spies("seal_export", "overlay_benchmark_file", "_run_once")
    fingerprints = [bg.fingerprint_tree(case.base.root, limit=10_000), bg.fingerprint_tree(case.head.root, limit=10_000)]
    case.probe = lambda: (0.71, 1)
    result = case.impl()
    _ends(result, "HOST_BUSY_START", stage="pre_overlay")
    assert result["host_check"] == "start_only" and result["loadavg"] == {"start": 0.71, "end": None}
    assert result["cpu_count"] == {"start": 1, "end": None}
    assert case.spy == ["interpreter_of", "interpreter_of"] or "seal_export" not in case.spy
    assert [bg.fingerprint_tree(case.base.root, limit=10_000), bg.fingerprint_tree(case.head.root, limit=10_000)] == fingerprints
    assert os.stat(case.base.root).st_mode & stat.S_IWUSR and os.stat(os.path.join(case.head.root, "README.md")).st_mode & stat.S_IWUSR
    case.probe = QUIET
    checked = case.checks()  # a new out_path, the same exports: past step 6
    assert checked.load == (0.1, 4) and case.common["host_check"] == "start_only"
    # this world's head has no benchmark file: step 7 refuses it, and a refusal leaves the exports unsealed
    _ends(case.impl(), "OVERLAY_REJECTED", "OVERLAY_PATH_REJECTED", stage="pre_overlay")
    assert "seal_export" not in case.spy and "_run_once" not in case.spy


@posix_only
def test_host_check_edges_and_bad_probes(case):
    case.probe = lambda: (0.70, 1)  # 0.70 * 10 > 7 * 1 is false: not busy
    assert case.checks().load == (0.70, 1)
    case.probe = lambda: (0.7, 2)
    assert case.checks()
    case.probe = lambda: (1.41, 2)
    _ends(case.impl(), "HOST_BUSY_START")
    case.probe = lambda: (1.4, 2)
    assert case.checks()
    case.probe = lambda: (7, 10)
    assert case.checks()
    case.probe = lambda: (8, 10)
    _ends(case.impl(), "HOST_BUSY_START")
    def boom():
        raise OSError("no loadavg")
    for probe in (boom, lambda: (True, 4), lambda: (float("nan"), 4), lambda: (float("inf"), 4), lambda: (-1.0, 4), lambda: ("1", 4),
                  lambda: (1.0, 0), lambda: (1.0, True), lambda: (1.0, 2.5), lambda: (1.0,), lambda: None, lambda: (50.0, -1)):
        case.probe = probe
        checked = case.checks()  # skipped, not busy and not an error
        assert case.common["host_check"] == "skipped_probe_failed" and checked.load is None
    assert case.common["loadavg"] == {"start": None, "end": None}


@posix_only
def test_default_load_probe_returns_a_load_and_a_cpu_count():
    load, cpus = bg._default_load_probe()
    assert isinstance(load, float) and load >= 0 and isinstance(cpus, int) and cpus >= 1


@posix_only
def test_compare_is_a_thin_wrapper_over_the_default_seams(world, tmp_path, monkeypatch):
    case = Case(world, tmp_path, monkeypatch)
    seen = {}

    def fake_impl(gate, repo, base, head, **kw):
        seen.update(kw)
        return {"ok": True}
    monkeypatch.setattr(bg, "_compare_impl", fake_impl)
    out = case.out()
    assert bg.compare(case.gate, str(world.repo), case.base, case.head, attempt=2, out_path=out, allow_writable_interpreter=True) == {"ok": True}
    assert seen == {"attempt": 2, "out_path": out, "allow_writable_interpreter": True}  # no seam is passed: the defaults apply
    with pytest.raises(TypeError):
        bg.compare(case.gate, str(world.repo), case.base, case.head, out_path=out, load_probe=QUIET)


# --- T3b: steps 7 to 9 (_compare_prepare) ---

BENCH_OK = (b"import hashlib\n\nfrom app.core import f as build\n\n\ndef test_bench():\n    out = build()\n"
            b"    print('BENCH_RESULT_DIGEST: ' + hashlib.sha256(str(out).encode()).hexdigest())\n")
BENCH_BAD = b"class Bad:\n    pass\n"


_ORIGINAL_BUILD_REPO = build_repo


def _bench_repo(mode: str, body: bytes):
    """``new``: the benchmark is added by the head (overlay-origin). ``pre``: the base already has it."""
    def build(tmp_path: Path):
        repo, base, head = _ORIGINAL_BUILD_REPO(tmp_path)
        (repo / "benchmarks").mkdir()
        (repo / BENCH).write_bytes(body)
        git(repo, "add", "-f", "--", BENCH)
        git(repo, "commit", "-q", "-m", "bench")
        with_bench = git(repo, "rev-parse", "HEAD")
        if mode == "new":
            return repo, head, with_bench
        make_commit(repo, {"src/app/core.py": "def f():\n    return 3\n"}, "head3")
        git(repo, "commit", "-q", "-m", "head3")
        return repo, with_bench, git(repo, "rev-parse", "HEAD")
    return build


def _bench_case(tmp_path, monkeypatch, mode="new", body=BENCH_OK):
    monkeypatch.setitem(globals(), "build_repo", _bench_repo(mode, body))
    return Case(build_world(tmp_path, monkeypatch), tmp_path, monkeypatch)


@pytest.fixture
def bcase(tmp_path, monkeypatch):
    return _bench_case(tmp_path, monkeypatch)


@pytest.fixture
def pcase(tmp_path, monkeypatch):
    return _bench_case(tmp_path, monkeypatch, "pre")


def _fp_both(c):
    return [bg.fingerprint_tree(r, limit=100_000) for r in c.roots]


@posix_only
def test_overlay_origin_pass_through(bcase):
    c = bcase
    c.spies("overlay_benchmark_file")
    real = bg.overlay_benchmark_file
    c.mp.setattr(bg, "overlay_benchmark_file", lambda *a, **k: (real(*a, **k), "PRE_EXISTING")[1])  # a lying return value is not trusted
    prepared = c.prepare()
    assert prepared.origin == "BUILDER_AUTHORED" and c.common["benchmark_origin"] == "BUILDER_AUTHORED"
    assert prepared.benchmark == BENCH and prepared.target == bg.benchmark_target(prepared.gate) and prepared.roots == c.roots
    assert prepared.benchmark_sha256 == hashlib.sha256(BENCH_OK).hexdigest() == c.common["benchmark_sha256"]
    assert prepared.h0 == (bg.hash_export(c.roots[0]), bg.hash_export(c.roots[1]))
    assert prepared.harness_sha256 == c.common["harness_sha256"] and prepared.gate_sha256 == c.common["gate_sha256"]
    base_bench = Path(c.roots[0]) / BENCH  # overlaid, and both exports are sealed
    assert base_bench.read_bytes() == BENCH_OK and not os.stat(base_bench).st_mode & 0o222 and not os.stat(c.roots[0]).st_mode & 0o200
    assert not os.stat(c.roots[1]).st_mode & 0o200


@posix_only
def test_overlay_origin_through_the_pipeline_reaches_step_13(bcase):
    result = bcase.impl(argv_builder=fake_trace_builder, min_base_ns=0)  # steps 7 to 12 passed with honest fake children; the timings decide the rest
    assert result["stage"] == "ran" and result["benchmark_origin"] == "BUILDER_AUTHORED" and result["reason"] != "ISOLATION_REJECTED"
    assert result["trace"]["base"]["value"] == FAKE_TRACE_LINES and result["digest"] in (FAKE_DIGEST, None)


@posix_only
def test_pre_existing_origin_has_no_allowance_at_all(pcase):
    c = pcase
    calls = []
    real = bg.verify_export_against_commit

    def spy(repo, commit, root, **kw):
        calls.append((commit, str(root), dict(kw.get("allow") or {})))
        return real(repo, commit, root, **kw)
    c.mp.setattr(bg, "verify_export_against_commit", spy)
    prepared = c.prepare()
    assert prepared.origin == "PRE_EXISTING" and c.common["benchmark_origin"] == "PRE_EXISTING"
    assert calls[2:] == [(c.base.commit, c.base.root, {}), (c.head.commit, c.head.root, {})]  # the step 9 pair; the step 4 pair came first
    assert (Path(c.roots[0]) / BENCH).read_bytes() == BENCH_OK


@posix_only
def test_step9_allowance_is_the_overlaid_file_on_the_base_only(bcase):
    c = bcase
    calls = []
    real = bg.verify_export_against_commit

    def spy(repo, commit, root, **kw):
        calls.append((commit, str(root), dict(kw.get("allow") or {})))
        return real(repo, commit, root, **kw)
    c.mp.setattr(bg, "verify_export_against_commit", spy)
    c.prepare()
    sha = hashlib.sha256(BENCH_OK).hexdigest()
    assert calls[2:] == [(c.base.commit, c.base.root, {BENCH: sha}), (c.head.commit, c.head.root, {})]


@posix_only
@pytest.mark.parametrize("code,reason", [("BENCHMARK_MODIFIED", "BENCHMARK_MODIFIED"), ("OVERLAY_PATH_REJECTED", "OVERLAY_REJECTED"),
                                         ("OVERLAY_NOT_REGULAR", "OVERLAY_REJECTED"), ("OVERLAY_PATH_CONFLICT", "OVERLAY_REJECTED"),
                                         ("TREE_TOO_LARGE", "EXPORT_REJECTED"), ("TREE_UNREADABLE", "EXPORT_REJECTED"),
                                         ("SEAL_FAILED", "EXPORT_REJECTED")])
def test_step7_refusals_map_and_leave_nothing_sealed_or_created(bcase, code, reason):
    c = bcase
    c.spies("seal_export")
    before = _fp_both(c)

    def refuse(*a, **k):
        raise bg.BenchmarkGateError(code, "x\x1b[31m")
    c.mp.setattr(bg, "overlay_benchmark_file", refuse)
    result = c.impl()
    _ends(result, reason, code, stage="pre_overlay")
    assert all("\x1b" not in t for t in result["untrusted_text"])
    assert "seal_export" not in c.spy and _fp_both(c) == before and os.stat(c.roots[0]).st_mode & stat.S_IWUSR
    assert json.loads(Path(c.last_out).read_text()) == result


@posix_only
@pytest.mark.parametrize("code", ["OVERLAY_COMMIT_MISMATCH", "OVERLAY_BASE_SEALED", "OVERLAY_FAILED", "DEST_REJECTED"])
def test_step7_caller_and_harness_faults_raise(bcase, code):
    def refuse(*a, **k):
        raise bg.BenchmarkGateError(code, "x")
    bcase.mp.setattr(bg, "overlay_benchmark_file", refuse)
    with pytest.raises(bg.BenchmarkGateError) as e:
        bcase.impl()
    assert e.value.code == code


@posix_only
def test_step7_real_benchmark_modified_leaves_the_exports_unsealed(pcase):
    def edit(c):  # present at base with other bytes than the head's (made between steps 6 and 7: step 4 would see it)
        (Path(c.roots[0]) / BENCH).write_bytes(BENCH_OK + b"# edited\n")
    with pytest.raises(bg._Verdict) as e:
        pcase.prepare(edit)
    assert (e.value.reason, e.value.detail, e.value.stage) == ("BENCHMARK_MODIFIED", "BENCHMARK_MODIFIED", "pre_overlay")
    assert os.stat(pcase.roots[0]).st_mode & stat.S_IWUSR and os.stat(pcase.roots[1]).st_mode & stat.S_IWUSR


@posix_only
def test_step7_a_path_the_head_does_not_have_is_overlay_rejected(bcase):
    other = "benchmarks/bench_missing.py"
    gate = {**GATE, "command": f"pytest -q --no-header {other}", "benchmark_paths": [other]}
    bcase.mp.setattr(bg, "diff_checks", lambda *a: None)  # step 5 would trip on the path token first; this row is about step 7
    _ends(bcase.impl(gate=gate), "OVERLAY_REJECTED", "OVERLAY_PATH_REJECTED", stage="pre_overlay")


@posix_only
def test_step7_top_levels_are_taken_after_the_install_and_before_the_overlay(bcase):
    c = bcase
    (Path(c.roots[0]) / "build").mkdir()  # what an install leaves behind
    seen = {}
    c.spies("repo_top_levels", "overlay_benchmark_file")
    real = bg.validate_benchmark_content

    def spy(source, symbol, top):
        seen["top"] = top
        return real(source, symbol, top)
    c.mp.setattr(bg, "validate_benchmark_content", spy)
    c.prepare()
    assert c.spy.index("repo_top_levels") < c.spy.index("overlay_benchmark_file")
    assert "app" in seen["top"] and "build" in seen["top"] and "benchmarks" not in seen["top"]  # the overlay's own directory is not importable


@posix_only
def test_step8_unequal_benchmark_bytes(bcase):
    c = bcase
    real = bg.overlay_benchmark_file

    def overlay_then_diverge(*a, **k):
        out = real(*a, **k)
        path = Path(c.roots[0]) / BENCH
        path.chmod(0o644)
        path.write_bytes(BENCH_OK + b"# diverged\n")
        return out
    c.mp.setattr(bg, "overlay_benchmark_file", overlay_then_diverge)
    result = c.impl()
    _ends(result, "ISOLATION_REJECTED", "BENCHMARK_BYTES_DIFFER", stage="overlaid")
    assert result["benchmark_origin"] == "BUILDER_AUTHORED"


@posix_only
def test_step8_lint_rejected_detail_is_the_first_violation_and_the_list_is_untrusted_text(tmp_path, monkeypatch):
    c = _bench_case(tmp_path, monkeypatch, body=BENCH_BAD)
    top = frozenset({"app"})
    expected = bg.validate_benchmark_content(BENCH_BAD, "build", top)
    assert len(expected) > 1 and expected == sorted(expected, key=bg.VIOLATION_CODES.index)
    result = c.impl()
    _ends(result, "LINT_REJECTED", expected[0], stage="overlaid")
    assert result["untrusted_text"] == expected
    assert result["benchmark_sha256"] == hashlib.sha256(BENCH_BAD).hexdigest()


@posix_only
def test_step8_order_is_seal_read_hash_reread(bcase):
    c = bcase
    c.spies("seal_export", "read_benchmark", "validate_benchmark_content", "hash_export", "overlay_benchmark_file", "repo_top_levels")
    c.prepare()
    step = [n for n in c.spy if n != "interpreter_of"]
    assert step == ["repo_top_levels", "overlay_benchmark_file", "seal_export", "seal_export", "read_benchmark", "read_benchmark",
                    "validate_benchmark_content", "hash_export", "hash_export", "read_benchmark", "read_benchmark"]


@posix_only
@pytest.mark.parametrize("which", [0, 1])
def test_step8_a_changed_reread_is_export_changed(bcase, which):
    c = bcase
    real = bg.read_benchmark
    calls = []

    def read(root, path):
        calls.append(root)
        data = real(root, path)
        return data + b"#" if len(calls) == 3 + which else data  # one of the two re-reads after the hash
    c.mp.setattr(bg, "read_benchmark", read)
    _ends(c.impl(), "ISOLATION_REJECTED", "EXPORT_CHANGED", stage="overlaid")


@posix_only
@pytest.mark.parametrize("name,code", [("read_benchmark", "OVERLAY_NOT_REGULAR"), ("read_benchmark", "OVERLAY_PATH_REJECTED"),
                                       ("read_benchmark", "TREE_UNREADABLE"), ("seal_export", "SEAL_FAILED"), ("seal_export", "TREE_UNREADABLE"),
                                       ("hash_export", "TREE_UNREADABLE"), ("hash_export", "TREE_TOO_LARGE")])
def test_step8_hostile_tree_errors_are_export_rejected(bcase, name, code):
    def boom(*a, **k):
        raise bg.BenchmarkGateError(code, "x")
    bcase.mp.setattr(bg, name, boom)
    _ends(bcase.impl(), "EXPORT_REJECTED", code, stage="overlaid")


def _extra_head_py(c):
    os.chmod(c.roots[1], 0o755)
    Path(c.roots[1], "hashlib.py").write_text("x = 1\n")


def _extra_base_py_beside(c):
    d = Path(c.roots[0]) / "benchmarks"
    d.chmod(0o755)
    (d / "other.py").write_text("x = 1\n")


def _overlaid_changed(c):
    path = Path(c.roots[0]) / BENCH
    Path(c.roots[0], "benchmarks").chmod(0o755)
    path.chmod(0o644)
    path.write_bytes(BENCH_OK + b"# late\n")


def _snap(c):
    c.world.sides["head"].snapshot.write_text("{}")


def _hook9(c):
    site = next((c.world.sides["head"].bin.parent / "lib").glob("python3*/site-packages"))
    (site / "evil.pth").write_text("import evil_hook\n")


def _interp9(c):
    c.pin_mods["head"] = lambda pin: pin._replace(sha256="0" * 64)


def _parity9(c):
    site = next((c.world.sides["head"].bin.parent / "lib").glob("python3*/site-packages"))
    (site / "bare_module.py").write_text("x = 1\n")


def _tracked9(c):
    path = Path(c.roots[1]) / "README.md"
    path.chmod(0o644)
    path.write_text("tampered\n")


# in the order step 9 checks them: each earlier fault beats every later one
FAULTS9 = [("SNAPSHOT_CHANGED", _snap), ("VENV_HOOK_REJECTED", _hook9), ("INTERPRETER_CHANGED", _interp9),
           ("DEPENDENCY_PARITY", _parity9), ("TRACKED_FILE_DIFFERS", _tracked9)]


@posix_only
@pytest.mark.parametrize("detail,mutate", [("UNTRACKED_PYTHON_FILE", _extra_head_py), ("UNTRACKED_PYTHON_FILE", _extra_base_py_beside),
                                           ("UNTRACKED_PYTHON_FILE", _overlaid_changed)] + FAULTS9,
                         ids=["second-py-head", "second-py-beside-overlay", "overlaid-file-changed"] + [f[0] for f in FAULTS9])
def test_step9_reruns_the_checks_and_allows_only_the_overlaid_file(bcase, detail, mutate):
    c = bcase
    with pytest.raises(bg._Verdict) as e:
        c.prepare(at9=mutate)
    assert (e.value.reason, e.value.detail, e.value.stage) == ("ISOLATION_REJECTED", detail, "overlaid")
    assert c.common["benchmark_origin"] == "BUILDER_AUTHORED"


@posix_only
@pytest.mark.parametrize("later", range(1, len(FAULTS9)))
def test_step9_an_earlier_fault_beats_the_next_one(tmp_path, monkeypatch, later):
    c = _bench_case(tmp_path, monkeypatch)
    with pytest.raises(bg._Verdict) as e:
        c.prepare(at9=lambda case: (FAULTS9[later][1](case), FAULTS9[later - 1][1](case)))
    assert e.value.detail == FAULTS9[later - 1][0]


@posix_only
def test_step9_check_order_and_that_it_runs_after_step_8(bcase):
    c = bcase
    c.spies("hash_export", "check_venv", "dependency_parity", "verify_export_against_commit")
    c.prepare()
    tail = c.spy[c.spy.index("hash_export", c.spy.index("hash_export") + 1) + 1:]
    assert tail == ["check_venv", "check_venv", "interpreter_of", "interpreter_of", "dependency_parity",
                    "verify_export_against_commit", "verify_export_against_commit"]


@posix_only
@pytest.mark.parametrize("code,detail", [("VENV_NOT_ISOLATED", "INTERPRETER_DIFFERS"), ("TREE_TOO_LARGE", "NOT_PROVISIONED")])
def test_step9_pin_errors_map_with_the_stage_overlaid(bcase, code, detail):
    c = bcase
    calls = []
    real = c.interp

    def seam(bin_dir):
        calls.append(bin_dir)
        if len(calls) > 2:  # step 4 asks twice; the third call is step 9
            raise bg.BenchmarkGateError(code, "x")
        return real(bin_dir)
    c.interp = seam
    with pytest.raises(bg._Verdict) as e:
        c.prepare()
    assert (e.value.reason, e.value.detail, e.value.stage) == ("ISOLATION_REJECTED", detail, "overlaid")


# --- T4a1: step 12 (the post-run check) and the step-9 baseline ---


def _p12(c, prepared):
    return bg._post_run_check(prepared, str(c.world.repo), c.base, c.head, interpreter_of=c.interp)


def _site(c, name="head"):
    return next((c.world.sides[name].bin.parent / "lib").glob("python3*/site-packages"))


def _unseal(*paths):
    for path in paths:
        os.chmod(path, 0o755 if os.path.isdir(path) else 0o644)


def _s12_edit(c):
    _unseal(c.roots[1], Path(c.roots[1]) / "README.md")
    (Path(c.roots[1]) / "README.md").write_text("tampered\n")


def _s12_tamper_restore(c):
    path = Path(c.roots[1]) / "README.md"
    before = os.stat(path)
    original = path.read_bytes()
    _unseal(c.roots[1], path)
    path.write_bytes(b"x" * len(original))
    path.write_bytes(original)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    os.chmod(path, stat.S_IMODE(before.st_mode))
    os.chmod(c.roots[1], 0o555)
    after = os.stat(path)
    assert (path.read_bytes(), after.st_mode, after.st_mtime_ns) == (original, before.st_mode, before.st_mtime_ns)
    assert after.st_ctime_ns != before.st_ctime_ns  # only ctime moved


def _s12_sidecar(c):
    path = c.world.sides["head"].export.parent / "head.export.json"
    data = path.read_bytes()
    path.unlink()
    path.write_bytes(data)  # same bytes, a new inode


def _s12_marker(c):
    path = c.world.sides["head"].export.parent / bg._MARKER_NAME
    path.write_bytes(path.read_bytes() + b" ")


def _s12_new_sibling(c):
    (c.world.sides["head"].export.parent / "extra").write_text("x")


def _s12_removed_sibling(c):
    (c.world.sides["head"].export.parent / "head.export.json").unlink()


def _s12_snapshot(c):
    c.world.sides["head"].snapshot.write_text("{}")


def _s12_hook_and_snapshot(c):
    (_site(c) / "evil.pth").write_text("import evil_hook\n")
    snapshot = c.world.sides["head"].snapshot
    snapshot.unlink()
    bg.snapshot_venv(c.world.sides["head"].bin, snapshot)  # the snapshot now blesses the hook


def _s12_interpreter(c):
    stdlib = next(p for p in (c.world.prefix / "lib").glob("python3*") if p.is_dir())
    (stdlib / "__pycache__").mkdir(exist_ok=True)
    (stdlib / "__pycache__" / "planted.cpython-312.pyc").write_bytes(b"x")


def _s12_hook(c):
    (_site(c) / "evil.pth").write_text("import evil_hook\n")


def _s12_venv_file(c):
    (_site(c) / "data.txt").write_text("x")


def _s12_cfg(c):
    cfg = c.world.sides["head"].bin.parent / "pyvenv.cfg"
    cfg.write_text(cfg.read_text() + "note = x\n")


@posix_only
def test_honest_run_leaves_every_fingerprint_unchanged(bcase):
    c = bcase
    prepared = c.prepare()
    assert _p12(c, prepared) is None
    assert _p12(c, prepared) is None  # and nothing the check did moved anything


@posix_only
@pytest.mark.parametrize("detail,mutate", [
    ("EXPORT_CHANGED", _s12_edit), ("EXPORT_CHANGED", _s12_tamper_restore), ("EXPORT_CHANGED", _s12_sidecar),
    ("EXPORT_CHANGED", _s12_marker), ("EXPORT_CHANGED", _s12_new_sibling), ("EXPORT_CHANGED", _s12_removed_sibling),
    ("SNAPSHOT_CHANGED", _s12_snapshot), ("SNAPSHOT_CHANGED", _s12_hook_and_snapshot), ("INTERPRETER_CHANGED", _s12_interpreter),
    ("VENV_HOOK_REJECTED", _s12_hook), ("VENV_CHANGED", _s12_venv_file), ("VENV_CHANGED", _s12_cfg)],
    ids=["edit", "tamper-restore", "sidecar-swap", "marker-edit", "sibling-added", "sibling-removed", "snapshot", "hook-and-snapshot",
         "interpreter", "venv-hook", "venv-file", "pyvenv-cfg"])
def test_step12_detects_each_tamper(bcase, detail, mutate):
    c = bcase
    prepared = c.prepare()
    mutate(c)
    verdict = _p12(c, prepared)
    assert isinstance(verdict, bg._Verdict)
    assert (verdict.result, verdict.reason, verdict.detail, verdict.stage) == ("REJECTED", "ISOLATION_REJECTED", detail, "ran")


@posix_only
def test_tamper_and_restore_is_invisible_to_the_content_hash_and_caught_by_the_fingerprint(bcase):
    c = bcase
    prepared = c.prepare()
    _s12_tamper_restore(c)
    assert bg.hash_export(c.roots[1]) == prepared.h0[1]  # bytes, mode and names are back
    assert _p12(c, prepared).detail == "EXPORT_CHANGED"


@posix_only
def test_baseline_includes_pyvenv_cfg_and_the_snapshot_files(bcase):
    c = bcase
    prepared = c.prepare()
    b = prepared.baseline
    cfgs = [hashlib.sha256((c.world.sides[n].bin.parent / "pyvenv.cfg").read_bytes()).hexdigest() for n in ("base", "head")]
    assert list(b.cfg_sha256) == cfgs
    assert list(b.exports) == _fp_both(c)
    assert b.exports[0] == bg.fingerprint_tree(c.roots[0], limit=bg._MAX_TREE_ENTRIES)
    assert b.venvs[1] == bg.fingerprint_tree(str(c.world.sides["head"].bin.parent), limit=bg._VENV_FINGERPRINT_LIMIT)
    assert len(b.snapshots) == 2 and b.snapshots[0] != b.snapshots[1]
    cfg = c.world.sides["base"].bin.parent / "pyvenv.cfg"
    cfg.write_text(cfg.read_text() + "note = x\n")
    assert _p12(c, prepared).detail == "VENV_CHANGED"


@posix_only
def test_baseline_dispatch_root_has_names_and_non_export_entries(bcase):
    c = bcase
    b = c.prepare().baseline
    dispatch = Path(c.roots[0]).parent
    names, entries = b.dispatch
    assert list(names) == sorted(os.listdir(dispatch))
    assert os.path.basename(c.roots[0]) not in dict(entries) and os.path.basename(c.roots[1]) not in dict(entries)
    marker = os.lstat(dispatch / bg._MARKER_NAME)
    assert dict(entries)[bg._MARKER_NAME] == (marker.st_dev, marker.st_ino, marker.st_size, marker.st_ctime_ns)


def _stub_finding(name):
    return lambda *a, **k: [("TRACKED_FILE_DIFFERS", "x")] if name == "verify" else [("DEPENDENCY_PARITY", "x")]


@posix_only
def test_step12_check_order(bcase):
    c = bcase
    c.spies("_check_snapshots", "hash_export", "fingerprint_tree", "check_venv", "dependency_parity", "verify_export_against_commit")
    prepared = c.prepare()
    c.spy.clear()
    assert _p12(c, prepared) is None
    kinds = [s for s in c.spy if s != "fingerprint_tree"]
    assert kinds == ["_check_snapshots", "interpreter_of", "interpreter_of", "hash_export", "hash_export", "check_venv", "check_venv",
                     "dependency_parity", "verify_export_against_commit", "verify_export_against_commit"]
    first_fp = c.spy.index("fingerprint_tree")
    assert c.spy.index("hash_export") < first_fp < c.spy.index("check_venv") < len(c.spy) - c.spy[::-1].index("fingerprint_tree") - 1


@posix_only
@pytest.mark.parametrize("later", range(1, 5))
def test_step12_an_earlier_fault_beats_the_next_one(tmp_path, monkeypatch, later):
    c = _bench_case(tmp_path, monkeypatch)
    faults = [("SNAPSHOT_CHANGED", _s12_snapshot), ("INTERPRETER_CHANGED", _s12_interpreter), ("EXPORT_CHANGED", _s12_edit),
              ("VENV_HOOK_REJECTED", _s12_hook), ("VENV_CHANGED", _s12_venv_file)]
    prepared = c.prepare()
    faults[later][1](c)
    faults[later - 1][1](c)
    assert _p12(c, prepared).detail == faults[later - 1][0]


@posix_only
def test_step12_venv_fault_beats_parity_beats_verification(bcase):
    c = bcase
    prepared = c.prepare()
    c.mp.setattr(bg, "dependency_parity", _stub_finding("parity"))
    c.mp.setattr(bg, "verify_export_against_commit", _stub_finding("verify"))
    assert _p12(c, prepared).detail == "DEPENDENCY_PARITY"
    _s12_venv_file(c)
    assert _p12(c, prepared).detail == "VENV_CHANGED"


@posix_only
def test_step12_verification_runs_last_with_the_step9_allowance(bcase):
    c = bcase
    prepared = c.prepare()
    calls = []
    c.mp.setattr(bg, "verify_export_against_commit", lambda repo, commit, root, **kw: calls.append((commit, str(root), dict(kw.get("allow") or {}))) or [])
    assert _p12(c, prepared) is None
    sha = hashlib.sha256(BENCH_OK).hexdigest()
    assert calls == [(c.base.commit, c.base.root, {BENCH: sha}), (c.head.commit, c.head.root, {})]
    c.mp.setattr(bg, "verify_export_against_commit", _stub_finding("verify"))
    assert _p12(c, prepared).detail == "TRACKED_FILE_DIFFERS"


@posix_only
def test_step12_pre_existing_origin_has_no_allowance(pcase):
    c = pcase
    prepared = c.prepare()
    calls = []
    c.mp.setattr(bg, "verify_export_against_commit", lambda repo, commit, root, **kw: calls.append(dict(kw.get("allow") or {})) or [])
    assert _p12(c, prepared) is None
    assert calls == [{}, {}]


@posix_only
@pytest.mark.parametrize("code", ["TREE_UNREADABLE", "DEST_REJECTED", "OVERLAY_FAILED", "TREE_TOO_LARGE"])
def test_step12_hash_errors_are_hash_unreadable(bcase, code):
    c = bcase
    prepared = c.prepare()

    def boom(root):
        raise bg.BenchmarkGateError(code, "x")
    c.mp.setattr(bg, "hash_export", boom)
    v = _p12(c, prepared)
    assert (v.reason, v.detail, v.stage) == ("ISOLATION_REJECTED", "HASH_UNREADABLE", "ran")


@posix_only
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads everything")
def test_step12_a_real_unreadable_entry_is_isolation_rejected(bcase):
    c = bcase
    prepared = c.prepare()
    victim = Path(c.roots[1]) / "tools"
    os.chmod(victim, 0)
    try:
        v = _p12(c, prepared)
    finally:
        os.chmod(victim, 0o555)
    assert (v.reason, v.detail) == ("ISOLATION_REJECTED", "HASH_UNREADABLE")


@posix_only
def test_step12_fingerprint_errors(bcase):
    c = bcase
    prepared = c.prepare()
    real = bg.fingerprint_tree

    def too_big(root, *, limit):
        if limit == bg._VENV_FINGERPRINT_LIMIT:
            raise bg.BenchmarkGateError("TREE_TOO_LARGE", "x")
        return real(root, limit=limit)
    c.mp.setattr(bg, "fingerprint_tree", too_big)
    assert _p12(c, prepared).detail == "FINGERPRINT_FAILED"

    def unreadable(root, *, limit):
        if limit == bg._MAX_TREE_ENTRIES:
            raise bg.BenchmarkGateError("TREE_UNREADABLE", "x")
        return real(root, limit=limit)
    c.mp.setattr(bg, "fingerprint_tree", unreadable)
    v = _p12(c, prepared)
    assert (v.reason, v.detail) == ("ISOLATION_REJECTED", "HASH_UNREADABLE")


@posix_only
def test_step12_a_venv_over_its_limit_is_fingerprint_failed(bcase):
    c = bcase
    prepared = c.prepare()
    c.mp.setattr(bg, "_VENV_FINGERPRINT_LIMIT", 1)
    v = _p12(c, prepared)
    assert (v.reason, v.detail, v.stage) == ("ISOLATION_REJECTED", "FINGERPRINT_FAILED", "ran")


@posix_only
@pytest.mark.parametrize("code", ["GIT_TIMEOUT", "GIT_FAILED", "REPO_UNREADABLE"])
def test_step12_git_and_host_faults_raise(bcase, code):
    c = bcase
    prepared = c.prepare()

    def boom(*a, **k):
        raise bg.BenchmarkGateError(code, "x")
    c.mp.setattr(bg, "verify_export_against_commit", boom)
    with pytest.raises(bg.BenchmarkGateError) as e:
        _p12(c, prepared)
    assert e.value.code == code


@posix_only
def test_step12_verification_too_large_is_export_rejected(bcase):
    c = bcase
    prepared = c.prepare()

    def boom(*a, **k):
        raise bg.BenchmarkGateError("GIT_OUTPUT_TOO_LARGE", "x")
    c.mp.setattr(bg, "verify_export_against_commit", boom)
    v = _p12(c, prepared)
    assert (v.result, v.reason, v.detail, v.stage) == ("REJECTED", "EXPORT_REJECTED", "GIT_OUTPUT_TOO_LARGE", "ran")


@posix_only
def test_step12_pin_and_snapshot_errors_are_integrity_errors(bcase):
    c = bcase
    prepared = c.prepare()
    real = c.interp

    def boom(bin_dir):
        raise bg.BenchmarkGateError("TREE_UNREADABLE", "x")
    c.interp = boom
    assert _p12(c, prepared).detail == "INTERPRETER_CHANGED"
    c.interp = real
    c.world.sides["head"].snapshot.unlink()
    assert _p12(c, prepared).detail == "SNAPSHOT_CHANGED"


@posix_only
def test_step9_baseline_errors_are_isolation_rejected_with_stage_overlaid(bcase):
    c = bcase
    real = bg.fingerprint_tree

    def too_big(root, *, limit):
        if limit == bg._VENV_FINGERPRINT_LIMIT:
            raise bg.BenchmarkGateError("TREE_TOO_LARGE", "x")
        return real(root, limit=limit)
    c.mp.setattr(bg, "fingerprint_tree", too_big)
    with pytest.raises(bg._Verdict) as e:
        c.prepare()
    assert (e.value.reason, e.value.detail, e.value.stage) == ("ISOLATION_REJECTED", "FINGERPRINT_FAILED", "overlaid")


# --- T4a2: steps 10 and 11 and the 2.7 mapping rows ---
# Stubs of ``trace_paired`` / ``measure_paired`` raise the exact errors the real functions build (attributes ``kind``, ``side``, ``phase``,
# ``partial``, ``trace``); the real functions are used for the spawn, the honest child and the step-12 rows. ``_compare_runs`` is called
# directly where the outcome object matters, ``_compare_impl`` where the result file does.

import errno  # noqa: E402

TRACE_OK = {"base": 7, "head": 7, "interpreter": "3.12.0 cpython", "argv": {"base": ["b"], "head": ["h"]}, "body_has_control_flow": False}
MEASURE_OK = {"order": ["base_first"] * 6, "base_ns": [10] * 6, "head_ns": [5] * 6, "digest": FAKE_DIGEST, "argv": {"base": ["b"], "head": ["h"]}}


def _err(code, kind=None, side=None, phase=None, trace=None, partial=None, detail="boom"):
    error = bg.BenchmarkGateError(code, detail)
    error.kind, error.side, error.phase, error.trace, error.partial = kind, side, phase, trace, partial
    return error


def _seen(bk="lines", bv=7, hk="lines", hv=8, bi="3.12.0 cpython", hi="3.12.0 cpython"):
    return {"base": {"kind": bk, "value": bv, "interpreter": bi}, "head": {"kind": hk, "value": hv, "interpreter": hi},
            "argv": {"base": ["b"], "head": ["h"]}, "body_has_control_flow": True}


def _stub(c, name, outcome, hook=None):
    """Replace ``bg.<name>``; ``outcome`` is an exception (raised) or a value (returned). Returns the list of calls' keyword arguments."""
    calls = []

    def fn(*args, **kwargs):
        calls.append(kwargs)
        if hook is not None:
            hook(c)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome
    c.mp.setattr(bg, name, fn)
    return calls


def _runs(c, builder=fake_trace_builder, **over):
    if not hasattr(c, "prepared"):  # steps 1 to 9 once per case: a second prepare would find sealed exports
        c.prepared = c.prepare()
    prepared = c.prepared
    kw = dict(run=c.run, argv_builder=builder, min_base_ns=0, interpreter_of=c.interp)
    kw.update(over)
    return bg._compare_runs(prepared, str(c.world.repo), c.base, c.head, c.checked, **kw)


def _ran(result, reason, detail=None):
    _ends(result, reason, detail, stage="ran")


def _probe_counter(c):
    calls = []
    c.probe = lambda: (calls.append(1), (0.1, 4))[1]
    return calls


def _post12(c):
    return c.spy.count("_post_run_check")


@posix_only
@pytest.mark.parametrize("where,code,kind", [("trace_paired", "MEASURE_FAILED", "harness"), ("trace_paired", "MEASURE_ARGS_INVALID", None),
                                             ("measure_paired", "MEASURE_FAILED", None), ("measure_paired", "MEASURE_ARGS_INVALID", None),
                                             ("measure_paired", "MEASURE_FAILED", "spawn"), ("trace_paired", "MEASURE_FAILED", "spawn")])
def test_row_T1_and_M4_raise(bcase, where, code, kind):
    c = bcase
    c.spies("_post_run_check")
    if where == "measure_paired":
        _stub(c, "trace_paired", TRACE_OK)
    _stub(c, where, _err(code, kind), hook=_s12_edit)  # the child "edited an export", and still a raise beats the step-12 result
    with pytest.raises(bg.BenchmarkGateError) as e:
        c.impl(argv_builder=fake_trace_builder, min_base_ns=0)
    assert e.value.code == code
    assert _post12(c) == 0 and not Path(c.last_out).exists()


@posix_only
def test_row_T2_trace_unavailable(bcase):
    c = bcase
    calls = _probe_counter(c)
    c.spies("_post_run_check")
    measured = _stub(c, "measure_paired", MEASURE_OK)
    _stub(c, "trace_paired", _err("TRACE_UNAVAILABLE", "unavailable", trace=_seen("unavailable", "no_monitoring", "unavailable", "no_monitoring"),
                                  phase="trace"))
    result = c.impl(argv_builder=fake_trace_builder, min_base_ns=0)
    _ran(result, "TRACE_UNAVAILABLE")
    assert result["result"] == "INCONCLUSIVE" and result["kind"] == "unavailable" and result["trace_mismatch_seen"] is False
    assert result["trace"]["base"] == {"kind": "unavailable", "value": "no_monitoring", "interpreter": "3.12.0 cpython"}
    assert result["trace"]["head"]["value"] == "no_monitoring" and result["trace"]["argv_note"] == "harness-only: temporary ini and plugin directory"
    assert result["trace"]["argv"] == {"base": ["b"], "head": ["h"]} and result["trace"]["body_has_control_flow"] is True
    assert measured == [] and len(calls) == 1 and _post12(c) == 1  # step 11 not run, only the start probe, step 12 ran
    assert json.loads(Path(c.last_out).read_text()) == result


def _bad_exe(side, bin_dir, root, target):
    return ["/nonexistent-c4d3/python", "-c", "pass"]


@posix_only
def test_row_T3_spawn_from_trace_paired_through_a_real_spawn_failure(bcase):
    c = bcase
    c.spies("_post_run_check")
    measured = _stub(c, "measure_paired", MEASURE_OK)
    result = c.impl(argv_builder=_bad_exe, min_base_ns=0)  # a missing <bin>/python is caught at step 4; a failing spawn after it is this row
    _ran(result, "ISOLATION_REJECTED", "NOT_PROVISIONED")
    assert result["kind"] == "spawn" and result["side"] == "base" and result["trace"] is None
    assert measured == [] and _post12(c) == 1


@posix_only
def test_row_T3_spawn_from_measure_paired_through_a_real_spawn_failure(bcase):
    c = bcase
    c.spies("_post_run_check")
    _stub(c, "trace_paired", TRACE_OK)
    result = c.impl(argv_builder=_bad_exe, min_base_ns=0)
    _ran(result, "ISOLATION_REJECTED", "NOT_PROVISIONED")
    assert result["kind"] == "spawn" and result["side"] == "base" and result["phase"] == "warmup" and result["trace"]["base"]["value"] == 7
    assert _post12(c) == 1


@posix_only
@pytest.mark.parametrize("stage", ["trace", "measure"])
@pytest.mark.parametrize("number,raises", [(errno.EAGAIN, True), (None, True), (errno.ENOMEM, True), (errno.ENOENT, False), (errno.EACCES, False)])
def test_spawn_errno_split(bcase, stage, number, raises):
    c = bcase
    if stage == "measure":
        _stub(c, "trace_paired", TRACE_OK)

    def refuse(*a, **k):
        raise bg._SpawnFailed("no", number)
    c.mp.setattr(bg, "_run_once", refuse)
    if raises:
        with pytest.raises(bg.BenchmarkGateError) as e:
            c.impl(argv_builder=fake_trace_builder, min_base_ns=0)
        assert e.value.code == "MEASURE_FAILED"
    else:
        _ran(c.impl(argv_builder=fake_trace_builder, min_base_ns=0), "ISOLATION_REJECTED", "NOT_PROVISIONED")


T4_ROWS = [("head", "nonzero", "HEAD_NONZERO_EXIT"), ("head", "timeout", "HEAD_TIMEOUT"), ("head", "oversize", "HEAD_OUTPUT_TOO_LARGE"),
           ("base", "nonzero", "BASE_NONZERO_EXIT"), ("base", "timeout", "BASE_TIMEOUT"), ("base", "oversize", "BASE_OUTPUT_TOO_LARGE")]


@posix_only
@pytest.mark.parametrize("side,kind,reason", T4_ROWS)
def test_row_T4_by_side_and_trace_fault(bcase, side, kind, reason):
    c = bcase
    calls = _probe_counter(c)
    c.spies("_post_run_check")
    measured = _stub(c, "measure_paired", MEASURE_OK)
    _stub(c, "trace_paired", _err("TRACE_MISMATCH", kind, side, "trace", detail=f"{kind}: x\x1b[31m"))
    result = c.impl(argv_builder=fake_trace_builder, min_base_ns=0)
    _ran(result, reason, kind)
    assert result["trace_fault"] == side and result["kind"] == kind and result["side"] == side and result["phase"] == "trace"
    assert result["trace"] is None and result["trace_mismatch_seen"] is False
    assert all("\x1b" not in t for t in result["untrusted_text"]) and result["untrusted_text"]
    assert measured == [] and len(calls) == 1 and _post12(c) == 1
    assert result["result"] == ("REJECTED" if (side, kind) == ("base", "nonzero") else "NOT_IMPROVED" if side == "head" else "INCONCLUSIVE")


@posix_only
def test_row_T5_counts_differ_is_pending_and_measure_still_runs(bcase):
    c = bcase
    measured = _stub(c, "measure_paired", MEASURE_OK)
    _stub(c, "trace_paired", _err("TRACE_MISMATCH", "counts_differ", phase="trace", trace=_seen()))
    c.spies("_post_run_check")
    outcome = _runs(c)
    assert len(measured) == 1 and outcome.measured == MEASURE_OK and outcome.measure_verdict is None
    assert (outcome.pending.result, outcome.pending.reason, outcome.pending.detail, outcome.pending.stage, outcome.pending.kind) == \
        ("REJECTED", "TRACE_MISMATCH", "counts_differ", "ran", "counts_differ")
    assert outcome.trace["base"]["value"] == 7 and outcome.trace["head"]["value"] == 8 and outcome.trace["argv_note"]
    assert c.run.common["trace"] == outcome.trace and _post12(c) == 1


@posix_only
def test_row_T5_real_children_with_differing_counts(bcase):
    c = bcase

    def builder(side, bin_dir, root, target):
        return fake_trace_builder(side, bin_dir, root, target, lines=7 if side == "base" else 9)
    outcome = _runs(c, builder)
    assert outcome.pending.reason == "TRACE_MISMATCH" and outcome.measured["digest"] == FAKE_DIGEST and len(outcome.measured["base_ns"]) == 6
    assert (outcome.trace["base"]["value"], outcome.trace["head"]["value"]) == (7, 9)


@posix_only
@pytest.mark.parametrize("code,kind,reason", [("HEAD_NONZERO_EXIT", "nonzero", "HEAD_NONZERO_EXIT"), ("DIGEST_MISMATCH", None, "DIGEST_MISMATCH"),
                                              ("BASE_NONZERO_EXIT", "nonzero", "BASE_NONZERO_EXIT")])
def test_row_T5_trace_mismatch_seen_when_measure_raises_rejected_or_not_improved(bcase, code, kind, reason):
    c = bcase
    _stub(c, "trace_paired", _err("TRACE_MISMATCH", "counts_differ", phase="trace", trace=_seen()))
    _stub(c, "measure_paired", _err(code, kind, "head" if code.startswith("HEAD") else None, "timed"))
    result = c.impl(argv_builder=fake_trace_builder, min_base_ns=0)
    _ran(result, reason)
    assert result["trace_mismatch_seen"] is True and result["trace"]["head"]["value"] == 8 and result["trace_fault"] is None


@posix_only
def test_row_T5_pending_meets_a_measure_inconclusive_and_both_are_kept_for_step_13(bcase):
    c = bcase
    _stub(c, "trace_paired", _err("TRACE_MISMATCH", "counts_differ", phase="trace", trace=_seen()))
    partial = {"order": ["base_first"], "base_ns": [3], "head_ns": [2]}
    _stub(c, "measure_paired", _err("BASE_TIMEOUT", "timeout", "base", "timed", partial=partial))
    outcome = _runs(c)
    assert outcome.pending.reason == "TRACE_MISMATCH" and outcome.measured is None
    assert (outcome.measure_verdict.result, outcome.measure_verdict.reason, outcome.measure_verdict.extra["partial"]) == ("INCONCLUSIVE", "BASE_TIMEOUT", partial)


@posix_only
@pytest.mark.parametrize("kind", ["plugin_failed", "no_result", "unavailable_one_side", "unavailable_tokens_differ",
                                  "unavailable_interpreters_differ", "interpreters_differ"])
def test_row_T6_at_once(bcase, kind):
    c = bcase
    calls = _probe_counter(c)
    c.spies("_post_run_check")
    measured = _stub(c, "measure_paired", MEASURE_OK)
    after = kind not in ("plugin_failed", "no_result")
    side = "head" if kind in ("plugin_failed", "no_result", "unavailable_one_side") else None
    _stub(c, "trace_paired", _err("TRACE_MISMATCH", kind, side, "trace", trace=_seen("unavailable", "no_monitoring", "lines", 3) if after else None))
    result = c.impl(argv_builder=fake_trace_builder, min_base_ns=0)
    _ran(result, "TRACE_MISMATCH", kind)
    assert result["result"] == "REJECTED" and result["kind"] == kind and (result["trace"] is not None) == after
    assert result["trace_mismatch_seen"] is False and result["trace_fault"] is None
    assert measured == [] and len(calls) == 1 and _post12(c) == 1


M_ROWS = [("BASE_NONZERO_EXIT", "nonzero", "base", "BASE_NONZERO_EXIT", "REJECTED"), ("DIGEST_MISSING", None, None, "DIGEST_MISSING", "REJECTED"),
          ("DIGEST_UNSTABLE", None, "head", "DIGEST_UNSTABLE", "REJECTED"), ("WORKLOAD_TOO_SHORT", None, "base", "WORKLOAD_TOO_SHORT", "REJECTED"),
          ("HEAD_NONZERO_EXIT", "nonzero", "head", "HEAD_NONZERO_EXIT", "NOT_IMPROVED"), ("HEAD_TIMEOUT", "timeout", "head", "HEAD_TIMEOUT", "NOT_IMPROVED"),
          ("DIGEST_MISMATCH", None, None, "DIGEST_MISMATCH", "NOT_IMPROVED"),
          ("OUTPUT_TOO_LARGE", "oversize", "head", "HEAD_OUTPUT_TOO_LARGE", "NOT_IMPROVED"),
          ("BASE_TIMEOUT", "timeout", "base", "BASE_TIMEOUT", "INCONCLUSIVE"), ("OUTPUT_TOO_LARGE", "oversize", "base", "BASE_OUTPUT_TOO_LARGE", "INCONCLUSIVE")]


@posix_only
@pytest.mark.parametrize("code,kind,side,reason,result", M_ROWS)
def test_rows_M1_M2_M3(bcase, code, kind, side, reason, result):
    c = bcase
    c.spies("_post_run_check")
    partial = {"order": ["base_first"], "base_ns": [3], "head_ns": [2]}
    _stub(c, "trace_paired", TRACE_OK)
    _stub(c, "measure_paired", _err(code, kind, side, "timed", partial=partial, detail="tail text"))
    if result == "INCONCLUSIVE":  # M3 is step 13's item 5: the outcome carries the mapped verdict, nothing is raised
        outcome = _runs(c)
        verdict = outcome.measure_verdict
        assert outcome.pending is None and outcome.measured is None and outcome.trace["base"]["value"] == 7
    else:
        with pytest.raises(bg._Verdict) as e:
            _runs(c)
        verdict = e.value
    assert (verdict.result, verdict.reason, verdict.stage, verdict.kind) == (result, reason, "ran", kind)
    assert verdict.detail == (kind or "") and verdict.extra["side"] == side and verdict.extra["phase"] == "timed"
    assert verdict.extra["partial"] == partial and verdict.extra["untrusted_text"] == ["tail text"]
    assert _post12(c) == 1


@posix_only
@pytest.mark.parametrize("code,kind,side,reason,result", [row for row in M_ROWS if row[4] != "INCONCLUSIVE"])
def test_rows_M1_M2_through_the_result(bcase, code, kind, side, reason, result):
    c = bcase
    partial = {"order": ["base_first"], "base_ns": [3], "head_ns": [2]}
    _stub(c, "trace_paired", TRACE_OK)
    _stub(c, "measure_paired", _err(code, kind, side, "timed", partial=partial, detail="tail"))
    full = c.impl(argv_builder=fake_trace_builder, min_base_ns=0)
    _ran(full, reason)
    assert full["trace_mismatch_seen"] is False and full["side"] == side and full["phase"] == "timed" and full["partial"] == partial
    assert full["trace"]["base"]["value"] == 7 and full["untrusted_text"] == ["tail"] and full["trace_fault"] is None


@posix_only
def test_dispatch_order(bcase):
    c = bcase
    _stub(c, "trace_paired", TRACE_OK)
    # code first for the raising rows, even when the kind says spawn; kind == "spawn" before the NONZERO_EXIT code; unknown codes fail closed
    _stub(c, "measure_paired", _err("MEASURE_FAILED", "spawn", "head", "timed"))
    with pytest.raises(bg.BenchmarkGateError):
        _runs(c)
    c2 = c
    _stub(c2, "measure_paired", _err("HEAD_NONZERO_EXIT", "spawn", "head", "warmup"))
    with pytest.raises(bg._Verdict) as e:
        _runs(c2)
    assert (e.value.reason, e.value.detail, e.value.kind) == ("ISOLATION_REJECTED", "NOT_PROVISIONED", "spawn")  # T3, not M2
    _stub(c2, "measure_paired", _err("HEAD_NONZERO_EXIT", "nonzero", "head", "warmup"))
    with pytest.raises(bg._Verdict) as e:
        _runs(c2)
    assert (e.value.reason, e.value.detail) == ("HEAD_NONZERO_EXIT", "nonzero")
    for code, kind in (("SOMETHING_NEW", None), ("UNSUPPORTED_PLATFORM", None)):
        _stub(c2, "measure_paired", _err(code, kind, None, "timed"))
        with pytest.raises(bg.BenchmarkGateError):
            _runs(c2)
    _stub(c2, "measure_paired", MEASURE_OK)
    # trace_paired: code first for MEASURE_*, then spawn before the kind table, then TRACE_UNAVAILABLE by code; a harness kind or an unknown kind raises
    for error in (_err("MEASURE_FAILED", "spawn", "base", "trace"), _err("TRACE_MISMATCH", "harness", None, "trace"),
                  _err("TRACE_MISMATCH", "no_such_kind", None, "trace"), _err("SOMETHING_NEW", "nonzero", "head", "trace")):
        _stub(c2, "trace_paired", error)
        with pytest.raises(bg.BenchmarkGateError):
            _runs(c2)
    _stub(c2, "trace_paired", _err("TRACE_MISMATCH", "spawn", "head", "trace"))
    with pytest.raises(bg._Verdict) as e:
        _runs(c2)
    assert (e.value.reason, e.value.detail) == ("ISOLATION_REJECTED", "NOT_PROVISIONED")
    _stub(c2, "trace_paired", _err("TRACE_UNAVAILABLE", "unavailable", None, "trace", trace=_seen("unavailable", "tool_in_use", "unavailable", "tool_in_use")))
    with pytest.raises(bg._Verdict) as e:
        _runs(c2)
    assert e.value.reason == "TRACE_UNAVAILABLE"


def _edit_in_child(side, bin_dir, root, target):
    """A real tiny child that prints its digest and trace result, and the head's also edits a file of its own export (chmod first)."""
    edit = ("import os\nif sys.argv[3]:\n    d = sys.argv[3]; os.chmod(d, 0o755); p = os.path.join(d, 'README.md'); os.chmod(p, 0o644)\n"
            "    open(p, 'a').write('tampered')\n")
    return [sys.executable, "-c", _FAKE_TRACE_CHILD + edit, FAKE_DIGEST, str(FAKE_TRACE_LINES), root if side == "head" else ""]


@posix_only
def test_step12_through_a_real_child(bcase):
    c = bcase
    c.spies("_post_run_check")
    result = c.impl(argv_builder=_edit_in_child, min_base_ns=0)
    _ran(result, "ISOLATION_REJECTED", "EXPORT_CHANGED")
    assert result["trace"]["head"]["value"] == FAKE_TRACE_LINES and _post12(c) == 1  # both runs went through; step 12 beat the later result


@posix_only
def test_an_honest_real_child_leaves_step_12_silent(bcase):
    c = bcase
    c.spies("_post_run_check")
    outcome = _runs(c)
    assert outcome.pending is None and outcome.measure_verdict is None and len(outcome.measured["base_ns"]) == 6 and _post12(c) == 1
    assert outcome.measured["digest"] == FAKE_DIGEST and outcome.trace["base"] == {"kind": "lines", "value": FAKE_TRACE_LINES,
                                                                                   "interpreter": outcome.trace["head"]["interpreter"]}
    assert outcome.trace["argv_note"] and set(outcome.trace) == {"base", "head", "body_has_control_flow", "argv", "argv_note"}


ENDINGS = {
    "T2": ("trace", _err("TRACE_UNAVAILABLE", "unavailable", None, "trace", trace=_seen("unavailable", "no_monitoring", "unavailable", "no_monitoring")),
           "TRACE_UNAVAILABLE"),
    "T3-trace": ("trace", _err("TRACE_MISMATCH", "spawn", "base", "trace"), "ISOLATION_REJECTED"),
    "T4": ("trace", _err("TRACE_MISMATCH", "nonzero", "head", "trace"), "HEAD_NONZERO_EXIT"),
    "T6": ("trace", _err("TRACE_MISMATCH", "no_result", "base", "trace"), "TRACE_MISMATCH"),
    "M1": ("measure", _err("DIGEST_MISSING", None, None, "warmup"), "DIGEST_MISSING"),
    "M2": ("measure", _err("HEAD_TIMEOUT", "timeout", "head", "timed"), "HEAD_TIMEOUT"),
    "M3": ("measure", _err("BASE_TIMEOUT", "timeout", "base", "timed"), "BASE_TIMEOUT"),
    "T3-measure": ("measure", _err("BASE_NONZERO_EXIT", "spawn", "base", "warmup"), "ISOLATION_REJECTED"),
    "success": ("measure", MEASURE_OK, "reaches-step-13"),
}


@posix_only
@pytest.mark.parametrize("name", sorted(ENDINGS))
def test_step12_runs_after_every_path_that_started_a_child(bcase, name):
    c = bcase
    c.spies("_post_run_check")
    where, outcome, _ = ENDINGS[name]
    if where == "trace":
        _stub(c, "trace_paired", outcome, hook=_s12_edit)
        _stub(c, "measure_paired", MEASURE_OK)
    else:
        _stub(c, "trace_paired", TRACE_OK)
        _stub(c, "measure_paired", outcome, hook=_s12_edit)
    result = c.impl(argv_builder=fake_trace_builder, min_base_ns=0)  # step 12 beats the success path too
    _ran(result, "ISOLATION_REJECTED", "EXPORT_CHANGED")
    assert _post12(c) == 1
    assert result["kind"] is None  # step 12's verdict is its own, not the ending it beat


@posix_only
def test_step12_beats_a_pending_trace_mismatch_and_a_measure_failure(bcase):
    c = bcase
    _stub(c, "trace_paired", _err("TRACE_MISMATCH", "counts_differ", phase="trace", trace=_seen()))
    _stub(c, "measure_paired", _err("HEAD_NONZERO_EXIT", "nonzero", "head", "timed"), hook=_s12_edit)
    result = c.impl(argv_builder=fake_trace_builder, min_base_ns=0)
    _ran(result, "ISOLATION_REJECTED", "EXPORT_CHANGED")
    assert result["trace"]["head"]["value"] == 8  # what the trace saw stays in the file


# --- T4b: step 13 (the precedence list, HOST_BUSY_END, statistics) and the coverage of the vocabularies ---
# The stubs above stand in for ``trace_paired`` / ``measure_paired``; steps 1 to 9 and the step-12 check are real, so a ``hook`` that edits an
# export is a real tamper. ``_probes`` scripts the load probe: the first call is the start probe (step 6), the second the end probe (step 13).

def _meas(base_ns, head_ns):
    return {**MEASURE_OK, "base_ns": list(base_ns), "head_ns": list(head_ns)}


def _go(c, trace=TRACE_OK, measure=MEASURE_OK, hook=None, hook_on="measure", **over):
    """Stub both library calls and run ``_compare_impl``; the stubs' recorded calls are ``c.calls = (trace, measure)``."""
    c.calls = (_stub(c, "trace_paired", trace, hook=hook if hook_on == "trace" else None),
               _stub(c, "measure_paired", measure, hook=hook if hook_on == "measure" else None))
    return c.impl(argv_builder=fake_trace_builder, min_base_ns=0, **over)


def _probes(c, *values):
    """The n-th call returns ``values[n-1]`` (the last repeats); an exception instance is raised. Returns the list of calls."""
    calls = []

    def probe():
        calls.append(1)
        value = values[min(len(calls), len(values)) - 1]
        if isinstance(value, BaseException):
            raise value
        return value
    c.probe = probe
    return calls


BUSY_END = (4.0, 4)  # (4.0 - 1) * 10 = 30 > 7 * 4 = 28
START_OK = (0.1, 4)
PENDING = _err("TRACE_MISMATCH", "counts_differ", phase="trace", trace=_seen())
HALVED = _meas([100, 200, 400, 100, 200, 400], [50, 100, 200, 50, 100, 200])


@posix_only
def test_precedence_0_a_raise_beats_a_step12_finding(bcase):
    c = bcase
    c.spies("_post_run_check")
    with pytest.raises(bg.BenchmarkGateError) as e:
        _go(c, measure=_err("MEASURE_FAILED", None, None, "timed"), hook=_s12_edit)  # the export was edited, and the raise still wins
    assert e.value.code == "MEASURE_FAILED" and _post12(c) == 0 and not Path(c.last_out).exists()


TRACE_AT_ONCE = {
    "T2": _err("TRACE_UNAVAILABLE", "unavailable", None, "trace", trace=_seen("unavailable", "no_monitoring", "unavailable", "no_monitoring")),
    "T3": _err("TRACE_MISMATCH", "spawn", "base", "trace"),
    "T4": _err("TRACE_MISMATCH", "nonzero", "head", "trace"),
    "T6": _err("TRACE_MISMATCH", "no_result", "head", "trace"),
}
T_REASON = {"T2": "TRACE_UNAVAILABLE", "T3": "ISOLATION_REJECTED", "T4": "HEAD_NONZERO_EXIT", "T6": "TRACE_MISMATCH"}


@posix_only
@pytest.mark.parametrize("name", sorted(TRACE_AT_ONCE))
def test_precedence_1_step12_beats_an_at_once_trace_result_and_its_detail_wins(bcase, name):
    c = bcase
    result = _go(c, trace=TRACE_AT_ONCE[name], hook=_s12_edit, hook_on="trace")
    _ran(result, "ISOLATION_REJECTED", "EXPORT_CHANGED")  # also over the T3 spawn's NOT_PROVISIONED
    assert result["kind"] is None and result["trace_fault"] is None


@posix_only
@pytest.mark.parametrize("name", sorted(TRACE_AT_ONCE))
def test_precedence_2_an_at_once_trace_result_beats_a_measure_refusal_and_is_not_probed(bcase, name):
    c = bcase
    calls = _probes(c, START_OK, BUSY_END)
    result = _go(c, trace=TRACE_AT_ONCE[name], measure=_err("BASE_NONZERO_EXIT", "nonzero", "base", "warmup"))
    _ran(result, T_REASON[name])
    assert c.calls[1] == [] and len(calls) == 1 and result["host_check"] == "start_only" and result["ratios"] is None  # step 11 did not run


@posix_only
@pytest.mark.parametrize("code,kind,side,reason", [("BASE_NONZERO_EXIT", "nonzero", "base", "BASE_NONZERO_EXIT"), ("DIGEST_MISSING", None, None, "DIGEST_MISSING"),
                                                   ("HEAD_NONZERO_EXIT", "nonzero", "head", "HEAD_NONZERO_EXIT"), ("DIGEST_MISMATCH", None, None, "DIGEST_MISMATCH"),
                                                   ("BASE_NONZERO_EXIT", "spawn", "base", "ISOLATION_REJECTED")])
def test_precedence_3_a_measure_rejection_beats_a_pending_trace_mismatch_and_marks_it_seen(bcase, code, kind, side, reason):
    c = bcase
    calls = _probes(c, START_OK, BUSY_END)
    result = _go(c, trace=PENDING, measure=_err(code, kind, side, "timed"))
    _ran(result, reason)
    assert result["trace_mismatch_seen"] is True and result["ratios"] is None and len(calls) == 1 and result["host_check"] == "start_only"


@posix_only
def test_precedence_4_a_pending_trace_mismatch_beats_a_measure_inconclusive_and_keeps_the_partial_data(bcase):
    c = bcase
    calls = _probes(c, START_OK, BUSY_END)
    partial = {"order": ["base_first"], "base_ns": [3], "head_ns": [2]}
    result = _go(c, trace=PENDING, measure=_err("BASE_TIMEOUT", "timeout", "base", "timed", partial=partial))
    _ran(result, "TRACE_MISMATCH", "counts_differ")
    assert result["partial"] == partial and result["trace"]["head"]["value"] == 8 and result["ratios"] is None and result["improvement"] is None
    assert len(calls) == 1 and result["host_check"] == "start_only" and result["trace_mismatch_seen"] is False  # the result itself is the mismatch


@posix_only
def test_precedence_4_a_pending_trace_mismatch_beats_the_statistics_and_a_busy_host_and_keeps_the_measured_data(bcase):
    c = bcase
    calls = _probes(c, START_OK, BUSY_END)
    evaluated = []
    real = bg.evaluate_paired_samples
    c.mp.setattr(bg, "evaluate_paired_samples", lambda *a, **k: (evaluated.append(1), real(*a, **k))[1])
    result = _go(c, trace=PENDING, measure=HALVED)
    _ran(result, "TRACE_MISMATCH", "counts_differ")
    assert result["ratios"] == [0.5] * 6 and result["improvement"] == 0.5 and result["mad_over_median"] == 0.0 and result["n"] == 6
    assert result["base_ns"] == HALVED["base_ns"] and result["head_ns"] == HALVED["head_ns"] and result["digest"] == FAKE_DIGEST
    assert result["base_median_ns"] == 200.0 and result["head_median_ns"] == 100.0 and result["order"] == HALVED["order"]
    assert len(calls) == 1 and result["host_check"] == "start_only" and result["loadavg"]["end"] is None
    assert result["trace_mismatch_seen"] is False and evaluated == []  # the mismatch stands; evaluate is not consulted


@posix_only
def test_precedence_5_a_measure_inconclusive_with_no_pending_beats_the_statistics_and_is_not_probed(bcase):
    c = bcase
    calls = _probes(c, START_OK, BUSY_END)
    evaluated = []
    c.mp.setattr(bg, "evaluate_paired_samples", lambda *a, **k: evaluated.append(1))
    partial = {"order": ["base_first"], "base_ns": [3], "head_ns": [2]}
    result = _go(c, measure=_err("BASE_TIMEOUT", "timeout", "base", "timed", partial=partial))
    _ran(result, "BASE_TIMEOUT", "timeout")
    assert result["partial"] == partial and result["ratios"] is None and result["trace"]["base"]["value"] == 7
    assert len(calls) == 1 and result["host_check"] == "start_only" and evaluated == []


@posix_only
@pytest.mark.parametrize("name", ["digest", "trace", "tamper", "pending"])
def test_a_forced_busy_host_cannot_hide_a_digest_trace_or_tamper_verdict(bcase, name):
    c = bcase
    calls = _probes(c, START_OK, (50.0, 4))
    if name == "digest":
        result, reason = _go(c, measure=_err("DIGEST_MISMATCH", None, None, "warmup")), "DIGEST_MISMATCH"
    elif name == "trace":
        result, reason = _go(c, trace=TRACE_AT_ONCE["T6"]), "TRACE_MISMATCH"
    elif name == "tamper":
        result, reason = _go(c, hook=_s12_edit), "ISOLATION_REJECTED"
    else:
        result, reason = _go(c, trace=PENDING), "TRACE_MISMATCH"
    _ran(result, reason)
    assert len(calls) == 1 and result["host_check"] == "start_only" and result["loadavg"]["end"] is None


ACCEPTANCE_TRACE_ROWS = {  # one compare per case: the overlay seals the exports, so a second run on them would be a different (rejected) call
    "counts-differ-digests-match": (dict(trace=PENDING), "TRACE_MISMATCH", "counts_differ", False, None),
    "counts-differ-digests-differ": (dict(trace=PENDING, measure=_err("DIGEST_MISMATCH", None, None, "warmup")), "DIGEST_MISMATCH", None, True, None),
    "counts-differ-base-times-out": (dict(trace=PENDING, measure=_err("BASE_TIMEOUT", "timeout", "base", "timed")), "TRACE_MISMATCH", "counts_differ", False, None),
    "head-nonzero-in-the-trace-run": (dict(trace=_err("TRACE_MISMATCH", "nonzero", "head", "trace")), "HEAD_NONZERO_EXIT", "nonzero", False, "head"),
    "both-sides-unavailable": (dict(trace=TRACE_AT_ONCE["T2"]), "TRACE_UNAVAILABLE", None, False, None),
}


@posix_only
@pytest.mark.parametrize("name", sorted(ACCEPTANCE_TRACE_ROWS))
def test_acceptance_trace_rows(bcase, name):
    kwargs, reason, detail, seen, fault = ACCEPTANCE_TRACE_ROWS[name]
    result = _go(bcase, **kwargs)
    _ran(result, reason, detail)
    assert result["trace_mismatch_seen"] is seen and result["trace_fault"] == fault


@posix_only
def test_acceptance_trace_mismatch_through_real_children(bcase):
    c = bcase

    def builder(side, bin_dir, root, target):
        return fake_trace_builder(side, bin_dir, root, target, lines=7 if side == "base" else 9)
    result = c.impl(argv_builder=builder, min_base_ns=0)  # counts differ, digests match: real children for both runs
    _ran(result, "TRACE_MISMATCH", "counts_differ")
    assert result["trace"]["head"]["value"] == 9 and len(result["ratios"]) == 6 and result["digest"] == FAKE_DIGEST


def _stat_row(c, base, head):
    return _go(c, measure=_meas(base, head))


@posix_only
def test_statistics_fix_halves_the_work(bcase):
    c = bcase
    calls = _probes(c, START_OK, (0.2, 4))
    result = _go(c, measure=HALVED)
    _ran(result, "IMPROVED_CLEAR")
    assert result["result"] == "IMPROVED" and result["kind"] is None and result["benchmark_origin"] == "BUILDER_AUTHORED"
    assert result["ratios"] == [0.5] * 6 and result["improvement"] == 0.5 and result["mad_over_median"] == 0.0
    assert result["base_ns"] == [100, 200, 400, 100, 200, 400] and result["head_ns"] == [50, 100, 200, 50, 100, 200] and result["n"] == 6
    assert result["base_median_ns"] == 200.0 and result["head_median_ns"] == 100.0 and result["repeats"] == 6
    assert (result["min_improvement"], result["max_noise"]) == (0.1, 0.1) and result["digest"] == FAKE_DIGEST and result["order"] == HALVED["order"]
    assert result["argv"] == HALVED["argv"] and result["order_salt"] == "ab12"
    assert result["host_check"] == "checked" and result["loadavg"] == {"start": 0.1, "end": 0.2} and result["cpu_count"] == {"start": 4, "end": 4}
    assert len(calls) == 2 and json.loads(Path(c.last_out).read_text()) == result


@posix_only
@pytest.mark.parametrize("base,head,reason,improvement", [
    ([100] * 6, [120] * 6, "BELOW_HALF_THRESHOLD", -0.2),  # head slower
    ([100] * 6, [100] * 6, "BELOW_HALF_THRESHOLD", 0.0),
    ([100] * 6, [50, 100, 50, 100, 50, 100], "NOISY", 0.25),
    ([100] * 6, [85, 85, 85, 85, 95, 95], "INCONSISTENT", 0.15),
    ([100] * 6, [93] * 6, "BORDERLINE", 0.07),
])
def test_statistics_verdict_rows(bcase, base, head, reason, improvement):
    result = _stat_row(bcase, base, head)
    _ran(result, reason)
    ratios = [Fraction(h, b) for b, h in zip(base, head)]
    assert result["ratios"] == [float(r) for r in ratios] and result["improvement"] == pytest.approx(improvement)
    median = bg._median(ratios)
    assert result["improvement"] == float(1 - median) and result["mad_over_median"] == float(bg._ratio_stats(base, head)[2] / median)
    assert result["base_ns"] == base and result["head_ns"] == head and result["host_check"] == "checked"


@posix_only
def test_invalid_input_via_monkeypatched_evaluate_is_never_replaced_by_host_busy_end(bcase):
    c = bcase
    c.mp.setattr(bg, "evaluate_paired_samples", lambda *a, **k: ("INCONCLUSIVE", "INVALID_INPUT"))
    _probes(c, START_OK, BUSY_END)
    result = _go(c, measure=HALVED)
    _ran(result, "INVALID_INPUT")
    assert result["result"] == "INCONCLUSIVE" and result["ratios"] == [0.5] * 6


@posix_only
@pytest.mark.parametrize("base,head", [([100] * 6, [50] * 6), ([100] * 6, [120] * 6), ([100] * 6, [50, 100, 50, 100, 50, 100]), ([100] * 6, [93] * 6)],
                         ids=["improved", "not-improved", "noisy", "borderline"])
def test_host_busy_end_replaces_improved_not_improved_and_inconclusive(bcase, base, head):
    c = bcase
    _probes(c, START_OK, BUSY_END)
    result = _stat_row(c, base, head)
    _ran(result, "HOST_BUSY_END", "")
    ratios = [Fraction(h, b) for b, h in zip(base, head)]
    assert result["result"] == "INCONCLUSIVE" and result["host_check"] == "checked" and result["loadavg"]["end"] == 4.0
    assert result["ratios"] == [float(r) for r in ratios] and result["improvement"] == float(1 - bg._median(ratios)) and result["base_ns"] == base  # data stays


ONE_CALL = {  # one call per case, as above: (kwargs of _go, expected reason)
    "pending-with-success": (dict(trace=PENDING, measure=HALVED), "TRACE_MISMATCH"),
    "T2": (dict(trace=TRACE_AT_ONCE["T2"]), "TRACE_UNAVAILABLE"), "T3": (dict(trace=TRACE_AT_ONCE["T3"]), "ISOLATION_REJECTED"),
    "T4": (dict(trace=TRACE_AT_ONCE["T4"]), "HEAD_NONZERO_EXIT"), "T6": (dict(trace=TRACE_AT_ONCE["T6"]), "TRACE_MISMATCH"),
    "M2-head-timeout": (dict(measure=_err("HEAD_TIMEOUT", "timeout", "head", "timed")), "HEAD_TIMEOUT"),
    "M3-base-timeout": (dict(measure=_err("BASE_TIMEOUT", "timeout", "base", "timed")), "BASE_TIMEOUT"),
    "M1-digest-unstable": (dict(measure=_err("DIGEST_UNSTABLE", None, None, "timed")), "DIGEST_UNSTABLE"),
}


@posix_only
@pytest.mark.parametrize("name", sorted(ONE_CALL))
def test_host_busy_end_with_a_pending_mismatch_the_mismatch_stands_and_other_endings_are_not_probed(bcase, name):
    c = bcase
    calls = _probes(c, START_OK, BUSY_END)
    kwargs, reason = ONE_CALL[name]
    _ran(_go(c, **kwargs), reason)
    assert len(calls) == 1  # the start probe only, never an end probe


def _end_row(c, start, end, cpus_note=None):
    calls = _probes(c, start, end)
    result = _go(c, measure=HALVED)
    return result, calls


@posix_only
@pytest.mark.parametrize("cpus,load,busy", [(3, 3.1, False), (3, 3.11, True), (4, 3.8, False), (4, 3.81, True), (10, 8.0, False), (10, 8.01, True)])
def test_host_busy_arithmetic_subtracts_the_gates_own_load_exactly(bcase, cpus, load, busy):
    c = bcase
    result, calls = _end_row(c, (0.1, cpus), (load, cpus))  # (load - 1) * 10 > 7 * cpus, with Fraction(str(load)): no float error at the edge
    _ran(result, "HOST_BUSY_END" if busy else "IMPROVED_CLEAR")
    assert result["host_check"] == "checked" and result["loadavg"]["end"] == load and result["cpu_count"]["end"] == cpus and len(calls) == 2
    if cpus == 4 and load == 3.8:
        assert load * 10 > 7 * cpus and result["reason"] == "IMPROVED_CLEAR"


@posix_only
@pytest.mark.parametrize("load,reason", [(0.70, "IMPROVED_CLEAR"), (0.71, "HOST_BUSY_START")])
def test_host_busy_start_edge_is_exact_at_one_cpu(bcase, load, reason):
    c = bcase
    c.probe = lambda: (load, 1)  # 0.70 * 10 > 7 is false, 0.71 * 10 > 7 true; the end check is skipped for 1 cpu
    result = c.impl(argv_builder=fake_trace_builder, min_base_ns=0) if reason == "HOST_BUSY_START" else _go(c)
    _ends(result, reason, stage="pre_overlay" if reason == "HOST_BUSY_START" else "ran")


@posix_only
@pytest.mark.parametrize("cpus", [1, 2])
def test_host_end_check_is_skipped_below_three_cpus(bcase, cpus):
    c = bcase
    result, calls = _end_row(c, (0.1, cpus), (50.0, cpus))
    _ran(result, "IMPROVED_CLEAR")
    assert result["host_check"] == "end_skipped_few_cpus" and result["loadavg"] == {"start": 0.1, "end": 50.0} and len(calls) == 2


def _boom():
    return OSError("no loadavg")


BAD_PROBES = [_boom(), (True, 4), (float("nan"), 4), (float("inf"), 4), (-1.0, 4), ("1", 4), (1.0, 0), (1.0, True), (1.0, 2.5), (1.0,), None, (50.0, -1)]


@posix_only
@pytest.mark.parametrize("bad", range(len(BAD_PROBES)))
def test_a_bad_end_probe_skips_the_end_check(bcase, bad):
    c = bcase
    result, calls = _end_row(c, START_OK, BAD_PROBES[bad])
    _ran(result, "IMPROVED_CLEAR")
    assert result["host_check"] == "skipped_probe_failed" and result["loadavg"] == {"start": 0.1, "end": None}
    assert result["cpu_count"] == {"start": 4, "end": None} and len(calls) == 2


@posix_only
def test_a_failed_start_probe_skips_both_checks_and_the_end_probe_does_not_run(bcase):
    c = bcase
    result, calls = _end_row(c, None, BUSY_END)
    _ran(result, "IMPROVED_CLEAR")
    assert result["host_check"] == "skipped_probe_failed" and result["loadavg"] == {"start": None, "end": None} and len(calls) == 1


@posix_only
def test_the_default_end_probe_is_the_default_load_probe(bcase):
    c = bcase
    c.probe = None  # no seam: the default probe answers (a real load on a real host)
    calls = []
    real = bg._default_load_probe
    c.mp.setattr(bg, "_default_load_probe", lambda: (calls.append(1), (0.1, 4))[1])
    c.probe = None
    result = _go(c)
    _ran(result, "IMPROVED_CLEAR")
    assert len(calls) == 2 and real is not bg._default_load_probe and result["host_check"] == "checked"


# --- the coverage of the vocabularies ---

def _mapped(fn, code, kind=None, side=None):
    """The reason ``fn`` maps an error to, or "RAISES"."""
    try:
        verdict = fn(_err(code, kind, side, "timed"))
    except bg.BenchmarkGateError:
        return "RAISES"
    assert bg.COMPARE_RESULT_OF_REASON[verdict.reason] == verdict.result
    return verdict.reason


MEASURE_CASES = {
    "UNSUPPORTED_PLATFORM": [(None, None, "RAISES")],
    "BASE_NONZERO_EXIT": [("nonzero", "base", "BASE_NONZERO_EXIT"), ("spawn", "base", "ISOLATION_REJECTED")],
    "HEAD_NONZERO_EXIT": [("nonzero", "head", "HEAD_NONZERO_EXIT"), ("spawn", "head", "ISOLATION_REJECTED")],
    "BASE_TIMEOUT": [("timeout", "base", "BASE_TIMEOUT")],
    "HEAD_TIMEOUT": [("timeout", "head", "HEAD_TIMEOUT")],
    "OUTPUT_TOO_LARGE": [("oversize", "base", "BASE_OUTPUT_TOO_LARGE"), ("oversize", "head", "HEAD_OUTPUT_TOO_LARGE")],
    "DIGEST_MISSING": [(None, None, "DIGEST_MISSING")],
    "DIGEST_UNSTABLE": [(None, "head", "DIGEST_UNSTABLE")],
    "DIGEST_MISMATCH": [(None, None, "DIGEST_MISMATCH")],
    "WORKLOAD_TOO_SHORT": [(None, "base", "WORKLOAD_TOO_SHORT")],
    "MEASURE_ARGS_INVALID": [(None, None, "RAISES")],  # the two codes `measure_paired` raises for a caller or harness fault: item 0
    "MEASURE_FAILED": [("harness", None, "RAISES"), ("spawn", "base", "RAISES")],
}
TRACE_CASES = {  # by kind: (code the trace run raises it with, side, mapped reason)
    "spawn": ("TRACE_MISMATCH", "base", "ISOLATION_REJECTED"),
    "oversize": ("TRACE_MISMATCH", "head", "HEAD_OUTPUT_TOO_LARGE"),
    "timeout": ("TRACE_MISMATCH", "base", "BASE_TIMEOUT"),
    "nonzero": ("TRACE_MISMATCH", "head", "HEAD_NONZERO_EXIT"),
    "plugin_failed": ("TRACE_MISMATCH", "head", "TRACE_MISMATCH"),
    "no_result": ("TRACE_MISMATCH", "head", "TRACE_MISMATCH"),
    "unavailable_one_side": ("TRACE_MISMATCH", "head", "TRACE_MISMATCH"),
    "unavailable_tokens_differ": ("TRACE_MISMATCH", None, "TRACE_MISMATCH"),
    "unavailable_interpreters_differ": ("TRACE_MISMATCH", None, "TRACE_MISMATCH"),
    "interpreters_differ": ("TRACE_MISMATCH", None, "TRACE_MISMATCH"),
    "counts_differ": ("TRACE_MISMATCH", None, "TRACE_MISMATCH"),  # pending: the caller keeps it for item 4
    "unavailable": ("TRACE_UNAVAILABLE", None, "TRACE_UNAVAILABLE"),
    "harness": ("MEASURE_FAILED", None, "RAISES"),
}


def test_coverage_every_measure_code_is_mapped_or_deliberately_raised():
    assert set(MEASURE_CASES) == set(bg.MEASURE_REFUSAL_CODES) | {"MEASURE_ARGS_INVALID", "MEASURE_FAILED"}  # kills a forgotten code
    for code, rows in MEASURE_CASES.items():
        for kind, side, expected in rows:
            assert _mapped(bg._map_measure_error, code, kind, side) == expected, (code, kind, side)


def test_coverage_every_trace_kind_and_code_is_mapped_or_deliberately_raised():
    assert set(TRACE_CASES) == set(bg.TRACE_FAILURE_KINDS)  # includes `harness`
    assert {code for code, _, _ in TRACE_CASES.values()} >= set(bg.TRACE_REFUSAL_CODES)
    for kind, (code, side, expected) in TRACE_CASES.items():
        assert _mapped(bg._map_trace_error, code, kind, side) == expected, kind
    for code in ("MEASURE_ARGS_INVALID", "MEASURE_FAILED"):
        assert _mapped(bg._map_trace_error, code, "harness", None) == "RAISES"
    assert _mapped(bg._map_trace_error, "SOMETHING_NEW", "nonzero", "head") == "RAISES"


def test_coverage_every_evaluate_reason_has_a_result_that_agrees():
    import inspect
    reasons = set(re.findall(r'"([A-Z_]+)"', inspect.getsource(bg._evaluate))) - bg.COMPARE_RESULTS
    assert reasons == {"INVALID_INPUT", "IMPROVED_CLEAR", "NOISY", "INCONSISTENT", "BORDERLINE", "BELOW_HALF_THRESHOLD"}
    seen = set()
    for base, head in (([100] * 6, [50] * 6), ([100] * 6, [120] * 6), ([100] * 6, [50, 100] * 3), ([100] * 6, [85, 85, 85, 85, 95, 95]),
                       ([100] * 6, [93] * 6), ([100] * 6, [])):
        result, reason = bg.evaluate_paired_samples(base, head, repeats=6, min_improvement=0.1, max_noise=0.1)
        assert bg.COMPARE_RESULT_OF_REASON[reason] == result
        seen.add(reason)
    assert seen == reasons


# --- one row per reason, the stage of every step-ending, the schema ---

def _diff_raises(code):
    def run(c):
        def fn(repo, base, head, path):
            error = bg.BenchmarkGateError(code, "x")
            error.hits = [{"path": "a.py", "token": "sys.argv", "line_number": 3, "line": "x"}] if code != "GIT_OUTPUT_TOO_LARGE" else []
            raise error
        c.mp.setattr(bg, "diff_checks", fn)
        return c.impl()
    return run


def _raises_in(name, code):
    def run(c):
        def fn(*a, **k):
            raise bg.BenchmarkGateError(code, "x")
        c.mp.setattr(bg, name, fn)
        return c.impl()
    return run


def _unsupported(c):
    c.mp.setattr(os, "name", "nt")
    result = c.impl()
    c.mp.undo()
    return result


def _root_has_git(c):
    (Path(c.roots[0]) / ".git").mkdir()
    return c.impl()


def _writable(c):
    c.allow = False
    return c.impl()


def _busy_start(c):
    c.probe = lambda: (0.71, 1)
    return c.impl()


def _diverge(c):
    real = bg.overlay_benchmark_file

    def overlay_then_diverge(*a, **k):
        out = real(*a, **k)
        path = Path(c.roots[0]) / BENCH
        path.chmod(0o644)
        path.write_bytes(BENCH_OK + b"# diverged\n")
        return out
    c.mp.setattr(bg, "overlay_benchmark_file", overlay_then_diverge)
    return c.impl()


def _step9_pin(c):
    calls, real = [], c.interp

    def seam(bin_dir):
        calls.append(bin_dir)
        if len(calls) > 2:  # step 4 asks twice; the third call is step 9
            raise bg.BenchmarkGateError("VENV_NOT_ISOLATED", "x")
        return real(bin_dir)
    c.interp = seam
    return c.impl()


def _measure_raises(code, kind=None, side=None, trace=TRACE_OK):
    return lambda c: _go(c, trace=trace, measure=_err(code, kind, side, "timed"))


def _stats(base, head):
    return lambda c: _go(c, measure=_meas(base, head))


def _invalid(c):
    c.mp.setattr(bg, "evaluate_paired_samples", lambda *a, **k: ("INCONCLUSIVE", "INVALID_INPUT"))
    return _go(c)


def _busy_end(c):
    _probes(c, START_OK, BUSY_END)
    return _go(c)


def _real_spawn(c):
    return c.impl(argv_builder=_bad_exe, min_base_ns=0)


def _lint_body(c):
    return c.impl()


# id: (case body, runner, reason, detail (None: any token), stage)
ENDING_ROWS = {
    "s1-unsupported-platform": (BENCH_OK, _unsupported, "UNSUPPORTED_PLATFORM", "", "pre_overlay"),
    "s2-gate-rejected": (BENCH_OK, lambda c: c.impl(gate={**c.gate, "warmup_runs": 0}), "GATE_REJECTED", "BOUNDS_REJECTED", "pre_overlay"),
    "s4-root-has-git": (BENCH_OK, _root_has_git, "ISOLATION_REJECTED", "ROOT_HAS_GIT", "pre_overlay"),
    "s4-interpreter-writable": (BENCH_OK, _writable, "ISOLATION_REJECTED", "INTERPRETER_WRITABLE", "pre_overlay"),
    "s4-export-rejected": (BENCH_OK, _raises_in("verify_export_against_commit", "TREE_UNREADABLE"), "EXPORT_REJECTED", "TREE_UNREADABLE", "pre_overlay"),
    "s5-protected-path": (BENCH_OK, _diff_raises("PROTECTED_PATH_CHANGED"), "PROTECTED_PATH_CHANGED", "PROTECTED_PATH_CHANGED", "pre_overlay"),
    "s5-benchmark-aware": (BENCH_OK, _diff_raises("BENCHMARK_AWARE_CODE"), "BENCHMARK_AWARE_CODE", "BENCHMARK_AWARE_CODE", "pre_overlay"),
    "s5-diff-uncheckable": (BENCH_OK, _diff_raises("GIT_OUTPUT_TOO_LARGE"), "DIFF_UNCHECKABLE", "GIT_OUTPUT_TOO_LARGE", "pre_overlay"),
    "s6-host-busy-start": (BENCH_OK, _busy_start, "HOST_BUSY_START", "", "pre_overlay"),
    "s7-overlay-rejected": (BENCH_OK, _raises_in("overlay_benchmark_file", "OVERLAY_PATH_REJECTED"), "OVERLAY_REJECTED", "OVERLAY_PATH_REJECTED", "pre_overlay"),
    "s7-benchmark-modified": (BENCH_OK, _raises_in("overlay_benchmark_file", "BENCHMARK_MODIFIED"), "BENCHMARK_MODIFIED", "BENCHMARK_MODIFIED", "pre_overlay"),
    "s7-export-rejected": (BENCH_OK, _raises_in("overlay_benchmark_file", "SEAL_FAILED"), "EXPORT_REJECTED", "SEAL_FAILED", "pre_overlay"),
    "s8-bytes-differ": (BENCH_OK, _diverge, "ISOLATION_REJECTED", "BENCHMARK_BYTES_DIFFER", "overlaid"),
    "s8-lint-rejected": (BENCH_BAD, _lint_body, "LINT_REJECTED", None, "overlaid"),
    "s8-export-rejected": (BENCH_OK, _raises_in("hash_export", "TREE_TOO_LARGE"), "EXPORT_REJECTED", "TREE_TOO_LARGE", "overlaid"),
    "s9-interpreter-differs": (BENCH_OK, _step9_pin, "ISOLATION_REJECTED", "INTERPRETER_DIFFERS", "overlaid"),
    "s10-trace-unavailable": (BENCH_OK, lambda c: _go(c, trace=TRACE_AT_ONCE["T2"]), "TRACE_UNAVAILABLE", "unavailable", "ran"),
    "s10-spawn-without-a-child": (BENCH_OK, _real_spawn, "ISOLATION_REJECTED", "NOT_PROVISIONED", "ran"),
    "s10-trace-mismatch": (BENCH_OK, lambda c: _go(c, trace=TRACE_AT_ONCE["T6"]), "TRACE_MISMATCH", "no_result", "ran"),
    "s10-head-nonzero": (BENCH_OK, lambda c: _go(c, trace=TRACE_AT_ONCE["T4"]), "HEAD_NONZERO_EXIT", "nonzero", "ran"),
    "s10-head-timeout": (BENCH_OK, lambda c: _go(c, trace=_err("TRACE_MISMATCH", "timeout", "head", "trace")), "HEAD_TIMEOUT", "timeout", "ran"),
    "s10-head-output": (BENCH_OK, lambda c: _go(c, trace=_err("TRACE_MISMATCH", "oversize", "head", "trace")), "HEAD_OUTPUT_TOO_LARGE", "oversize", "ran"),
    "s10-base-nonzero": (BENCH_OK, lambda c: _go(c, trace=_err("TRACE_MISMATCH", "nonzero", "base", "trace")), "BASE_NONZERO_EXIT", "nonzero", "ran"),
    "s10-base-timeout": (BENCH_OK, lambda c: _go(c, trace=_err("TRACE_MISMATCH", "timeout", "base", "trace")), "BASE_TIMEOUT", "timeout", "ran"),
    "s10-base-output": (BENCH_OK, lambda c: _go(c, trace=_err("TRACE_MISMATCH", "oversize", "base", "trace")), "BASE_OUTPUT_TOO_LARGE", "oversize", "ran"),
    "s11-base-nonzero": (BENCH_OK, _measure_raises("BASE_NONZERO_EXIT", "nonzero", "base"), "BASE_NONZERO_EXIT", "nonzero", "ran"),
    "s11-digest-missing": (BENCH_OK, _measure_raises("DIGEST_MISSING"), "DIGEST_MISSING", "", "ran"),
    "s11-digest-unstable": (BENCH_OK, _measure_raises("DIGEST_UNSTABLE", None, "head"), "DIGEST_UNSTABLE", "", "ran"),
    "s11-too-short": (BENCH_OK, _measure_raises("WORKLOAD_TOO_SHORT", None, "base"), "WORKLOAD_TOO_SHORT", "", "ran"),
    "s11-head-nonzero": (BENCH_OK, _measure_raises("HEAD_NONZERO_EXIT", "nonzero", "head"), "HEAD_NONZERO_EXIT", "nonzero", "ran"),
    "s11-head-timeout": (BENCH_OK, _measure_raises("HEAD_TIMEOUT", "timeout", "head"), "HEAD_TIMEOUT", "timeout", "ran"),
    "s11-head-output": (BENCH_OK, _measure_raises("OUTPUT_TOO_LARGE", "oversize", "head"), "HEAD_OUTPUT_TOO_LARGE", "oversize", "ran"),
    "s11-digest-mismatch": (BENCH_OK, _measure_raises("DIGEST_MISMATCH"), "DIGEST_MISMATCH", "", "ran"),
    "s11-base-timeout": (BENCH_OK, _measure_raises("BASE_TIMEOUT", "timeout", "base"), "BASE_TIMEOUT", "timeout", "ran"),
    "s11-base-output": (BENCH_OK, _measure_raises("OUTPUT_TOO_LARGE", "oversize", "base"), "BASE_OUTPUT_TOO_LARGE", "oversize", "ran"),
    "s11-spawn": (BENCH_OK, _measure_raises("BASE_NONZERO_EXIT", "spawn", "base"), "ISOLATION_REJECTED", "NOT_PROVISIONED", "ran"),
    "s11-pending-mismatch": (BENCH_OK, lambda c: _go(c, trace=PENDING), "TRACE_MISMATCH", "counts_differ", "ran"),
    "s12-export-changed": (BENCH_OK, lambda c: _go(c, hook=_s12_edit), "ISOLATION_REJECTED", "EXPORT_CHANGED", "ran"),
    "s13-improved": (BENCH_OK, _stats([100] * 6, [50] * 6), "IMPROVED_CLEAR", "", "ran"),
    "s13-below-half": (BENCH_OK, _stats([100] * 6, [120] * 6), "BELOW_HALF_THRESHOLD", "", "ran"),
    "s13-noisy": (BENCH_OK, _stats([100] * 6, [50, 100] * 3), "NOISY", "", "ran"),
    "s13-inconsistent": (BENCH_OK, _stats([100] * 6, [85, 85, 85, 85, 95, 95]), "INCONSISTENT", "", "ran"),
    "s13-borderline": (BENCH_OK, _stats([100] * 6, [93] * 6), "BORDERLINE", "", "ran"),
    "s13-invalid-input": (BENCH_OK, _invalid, "INVALID_INPUT", "", "ran"),
    "s13-host-busy-end": (BENCH_OK, _busy_end, "HOST_BUSY_END", "", "ran"),
}


def _row_result(tmp_path, monkeypatch, name):
    body, runner, *_ = ENDING_ROWS[name]
    c = _bench_case(tmp_path, monkeypatch, body=body)
    return c, runner(c)


@posix_only
@pytest.mark.parametrize("name", sorted(ENDING_ROWS))
def test_stage_of_every_step_ending_and_one_row_per_reason(tmp_path, monkeypatch, name):
    _, _, reason, detail, stage = ENDING_ROWS[name]
    c, result = _row_result(tmp_path, monkeypatch, name)
    _ends(result, reason, detail, stage=stage)  # the 2.3 table: the stage, the result of the reason and the detail
    token = result["detail"].split(" ")[0]
    assert token == "" or token in bg.COMPARE_DETAIL_TOKENS, result["detail"]
    assert all(part.isdigit() for part in result["detail"].split(" ")[1:])
    assert result["schema"] == bg.COMPARE_SCHEMA and set(result) == set(bg.COMPARE_RESULT_KEYS)
    assert json.loads(Path(c.last_out).read_text()) == result


def test_every_reason_of_the_vocabulary_has_a_row():
    assert {row[2] for row in ENDING_ROWS.values()} == set(bg.COMPARE_RESULT_OF_REASON)  # kills an unreachable or forgotten reason
    assert {bg.COMPARE_RESULT_OF_REASON[row[2]] for row in ENDING_ROWS.values()} == bg.COMPARE_RESULTS


@posix_only
def test_the_step_to_stage_table_is_asserted_whole():
    by_stage = {}
    for _, _, reason, _, stage in ENDING_ROWS.values():
        by_stage.setdefault(stage, set()).add(reason)
    assert set(by_stage) == set(bg.COMPARE_STAGES)
    assert {"UNSUPPORTED_PLATFORM", "GATE_REJECTED", "HOST_BUSY_START", "PROTECTED_PATH_CHANGED"} <= by_stage["pre_overlay"]
    assert {"LINT_REJECTED"} <= by_stage["overlaid"] and {"HOST_BUSY_END", "TRACE_UNAVAILABLE", "IMPROVED_CLEAR"} <= by_stage["ran"]


@posix_only
def test_the_result_schema_from_compare_impl(bcase):
    c = bcase
    evil = "EVIL\x1b[31mé`|\n" * 3
    hits = [{"path": f"p{i}.py", "token": evil, "line_number": i, "line": evil} for i in range(30)]

    def diff(repo, base, head, path):
        error = bg.BenchmarkGateError("BENCHMARK_AWARE_CODE", evil)
        error.hits = hits
        raise error
    c.mp.setattr(bg, "diff_checks", diff)
    result = c.impl()
    raw = Path(c.last_out).read_bytes()
    assert raw.decode("ascii") and raw.endswith(b"\n") and json.loads(raw) == result  # ASCII only, nothing lost
    assert set(result) == set(bg.COMPARE_RESULT_KEYS) and len(result["untrusted_text"]) == 20
    assert all(len(t) <= 200 and "\x1b" not in t for t in result["untrusted_text"]) and any("EVIL" in t for t in result["untrusted_text"])
    assert "EVIL" not in json.dumps({k: v for k, v in result.items() if k != "untrusted_text"})  # attacker text lives only in untrusted_text
    assert result["detail"] == "BENCHMARK_AWARE_CODE" and result["schema"] == "software-builder-bench-compare-v1"


@posix_only
def test_the_result_of_a_finished_comparison_has_every_key_filled(bcase):
    done = _go(bcase, measure=HALVED)
    assert set(done) == set(bg.COMPARE_RESULT_KEYS) and done["stage"] == "ran" and done["untrusted_text"] == []
    assert [k for k, v in done.items() if v is None] == ["kind", "trace_fault", "side", "phase", "partial"]  # only what does not apply is null


@posix_only
def test_gate_sha256_equals_what_validate_prints_for_the_same_gate(bcase, tmp_path):
    c = bcase
    result = _go(c, measure=HALVED)
    spec = tmp_path / "inputs.json"
    spec.write_text(json.dumps({"benchmark_gate": c.gate, "performance_review_origin": True}))
    done = subprocess.run([sys.executable, str(SCRIPT), "validate", "--specialist-inputs", str(spec)], capture_output=True, text=True, check=True)
    assert done.stdout.splitlines() == ["OK", f"gate_sha256: {result['gate_sha256']}"]
    normalized, _ = bg.validate_benchmark_gate(c.gate)
    assert result["gate_sha256"] == bg.gate_sha256(normalized)


# --- T5b: the CLI (`compare`, `run-once`), the crash contract and the RESULT line ---
# The in-process rows drive ``bg.main`` with ``bg.compare`` replaced by ``_compare_impl`` plus the test seams (a real CLI process has no
# seams); the process rows run the real script. One ``compare`` per fixture: a second call on the same exports meets the step-4 untracked-file check.

def _cli_compare_args(c, gate_path, out, *extra):
    return ["compare", "--gate", str(gate_path), "--repo", str(c.world.repo),
            "--base-root", c.base.root, "--head-root", c.head.root, "--base-commit", c.base.commit, "--head-commit", c.head.commit,
            "--base-bin", c.base.bin_dir, "--head-bin", c.head.bin_dir,
            "--base-snapshot", c.base.snapshot, "--base-snapshot-sha256", c.base.snapshot_sha256, "--base-interpreter-sha256", c.base.interpreter_sha256,
            "--head-snapshot", c.head.snapshot, "--head-snapshot-sha256", c.head.snapshot_sha256, "--head-interpreter-sha256", c.head.interpreter_sha256,
            "--out", str(out), *extra]


def _seamed_compare(c):
    """``bg.compare`` as the CLI calls it, plus the case's seams (the default seams need a real interpreter)."""
    real = bg._compare_impl

    def compare(gate, repo, base, head, **kw):
        return real(gate, repo, base, head, argv_builder=fake_trace_builder, min_base_ns=0, load_probe=c.probe, interpreter_of=c.interp,
                    order_salt=c.salt, **kw)
    c.mp.setattr(bg, "compare", compare)


def _gate_file(c):
    path = c.tmp / "gate.json"
    path.write_text(json.dumps(c.gate))
    return path


RESULT_LINE = re.compile(r"RESULT: ([A-Z_]+) ([A-Z_]+) interpreter_writable=(0|1|n/a) sha256=([0-9a-f]{64})")


def parse_compare_outcome(returncode: int, stdout: str, file_bytes: bytes | None) -> int:
    """The Orchestrator's reading of one ``compare`` run (spec 2.9): the exit code it may act on. An exit 0 or 1 counts only with a RESULT line
    whose sha256 is that of the file's bytes and whose result and reason match the parsed file (and the exit agrees with the result);
    anything else, including Python's own exit 1 for an uncaught exception, is exit 2 (\"ignore the file\")."""
    if returncode not in (0, 1) or file_bytes is None:
        return 2
    lines = [m for m in map(RESULT_LINE.fullmatch, stdout.splitlines()) if m]
    if len(lines) != 1 or lines[0].group(4) != hashlib.sha256(file_bytes).hexdigest():
        return 2
    try:
        parsed = json.loads(file_bytes)
    except ValueError:
        return 2
    if (parsed.get("result"), parsed.get("reason")) != (lines[0].group(1), lines[0].group(2)) or bg.COMPARE_RESULT_OF_REASON.get(parsed["reason"]) != parsed["result"]:
        return 2
    return 0 if parsed["result"] == "IMPROVED" and returncode == 0 else 1 if parsed["result"] != "IMPROVED" and returncode == 1 else 2


def _writable_token(value):
    return {True: "1", False: "0", None: "n/a"}[value]


def _run_main(capsys, argv):
    code = bg.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _stub_both(c, measure):
    _stub(c, "trace_paired", TRACE_OK)
    _stub(c, "measure_paired", measure)


def _read_out(path):
    return Path(path).read_bytes() if os.path.lexists(path) else None


def _bad_gate(c):
    c.gate = {**c.gate, "warmup_runs": 0}


def _no_flag_but_not_writable(c):
    c.allow = False
    c.pin_mods.update(base=lambda p: p._replace(writable=False), head=lambda p: p._replace(writable=False))


def _tampered_pin(c):
    c.base = c.base._replace(interpreter_sha256="0" * 64)


CLI_ROWS = {
    "improved": (HALVED, None, 0, "IMPROVED", "IMPROVED_CLEAR", "1"),
    "improved-not-writable": (HALVED, _no_flag_but_not_writable, 0, "IMPROVED", "IMPROVED_CLEAR", "0"),
    "not-improved": (_meas([100] * 6, [120] * 6), None, 1, "NOT_IMPROVED", "BELOW_HALF_THRESHOLD", "1"),
    "inconclusive": (_meas([100] * 6, [93] * 6), None, 1, "INCONCLUSIVE", "BORDERLINE", "1"),
    "rejected-step4": (HALVED, _tampered_pin, 1, "REJECTED", "ISOLATION_REJECTED", None),
    "rejected-step2-gate": (HALVED, _bad_gate, 1, "REJECTED", "GATE_REJECTED", "n/a"),
}


@posix_only
@pytest.mark.parametrize("name", sorted(CLI_ROWS))
def test_cli_result_line_and_exit_codes(tmp_path, monkeypatch, capsys, name):
    measure, prep, exit_code, result, reason, writable = CLI_ROWS[name]
    c = _bench_case(tmp_path, monkeypatch)
    if prep is not None:
        prep(c)
    _stub_both(c, measure)
    _seamed_compare(c)
    out = c.out()
    code, stdout, stderr = _run_main(capsys, _cli_compare_args(c, _gate_file(c), out, *(["--allow-writable-interpreter"] if c.allow else [])))
    data = Path(out).read_bytes()  # the file exists before (and without) any reading of the line
    assert code == exit_code and stderr == ""
    parsed = json.loads(data)
    assert (parsed["result"], parsed["reason"]) == (result, reason)
    expected = _writable_token(parsed["interpreter_writable"]) if writable is None else writable
    assert stdout == f"RESULT: {result} {reason} interpreter_writable={expected} sha256={hashlib.sha256(data).hexdigest()}\n"  # the closed sets, one line
    assert parse_compare_outcome(code, stdout, data) == exit_code  # a reader that hashes the file bytes agrees


@posix_only
def test_cli_exit_2_for_a_usage_error_prints_no_result_and_a_process_row_matches(tmp_path, monkeypatch, capsys):
    c = _bench_case(tmp_path, monkeypatch)
    out = c.out()
    # an out file that exists is a caller fault: a raised error, exit 2, no RESULT line, and the file is not ours to read
    Path(out).write_text("planted")
    done = subprocess.run([sys.executable, str(SCRIPT), *_cli_compare_args(c, _gate_file(c), out, "--allow-writable-interpreter")],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 2 and done.stdout == "" and re.fullmatch(r"usage error: [A-Z_]+: BenchmarkGateError\n", done.stderr), done
    assert Path(out).read_text() == "planted" and parse_compare_outcome(done.returncode, done.stdout, b"planted") == 2


@posix_only
def test_cli_process_with_default_seams_ends_at_the_gate_with_a_result_line(tmp_path, monkeypatch):
    c = _bench_case(tmp_path, monkeypatch)
    _bad_gate(c)  # ends at step 2, before any interpreter is probed: the default seams are enough
    out = c.out()
    done = subprocess.run([sys.executable, str(SCRIPT), *_cli_compare_args(c, _gate_file(c), out)], capture_output=True, text=True, timeout=300)
    data = Path(out).read_bytes()
    assert done.returncode == 1 and done.stderr == "", done
    assert done.stdout == f"RESULT: REJECTED GATE_REJECTED interpreter_writable=n/a sha256={hashlib.sha256(data).hexdigest()}\n"
    assert parse_compare_outcome(done.returncode, done.stdout, data) == 1
    assert json.loads(data)["stage"] == "pre_overlay"


@posix_only
def test_exit_1_without_a_valid_result_line_is_not_a_result(tmp_path):
    good = (json.dumps({"result": "NOT_IMPROVED", "reason": "BELOW_HALF_THRESHOLD"}) + "\n").encode()
    sha = hashlib.sha256(good).hexdigest()
    line = f"RESULT: NOT_IMPROVED BELOW_HALF_THRESHOLD interpreter_writable=1 sha256={sha}\n"
    assert parse_compare_outcome(1, line, good) == 1
    assert parse_compare_outcome(1, "", good) == 2  # no line
    assert parse_compare_outcome(1, "Traceback (most recent call last):\n", good) == 2  # Python's uncaught exception exits 1
    assert parse_compare_outcome(1, line, good + b" ") == 2  # another sha
    assert parse_compare_outcome(1, line, None) == 2  # no file
    assert parse_compare_outcome(1, line.replace("BELOW_HALF_THRESHOLD", "NOISY"), good) == 2  # the line disagrees with the file
    assert parse_compare_outcome(1, line + line, good) == 2  # two lines
    assert parse_compare_outcome(0, line, good) == 2  # exit 0 only for IMPROVED
    assert parse_compare_outcome(2, line, good) == 2
    improved = (json.dumps({"result": "IMPROVED", "reason": "IMPROVED_CLEAR"}) + "\n").encode()
    line0 = f"RESULT: IMPROVED IMPROVED_CLEAR interpreter_writable=0 sha256={hashlib.sha256(improved).hexdigest()}\n"
    assert parse_compare_outcome(0, line0, improved) == 0 and parse_compare_outcome(1, line0, improved) == 2
    crash = subprocess.run([sys.executable, "-c", "raise RuntimeError('boom')"], capture_output=True, text=True, timeout=60)
    assert crash.returncode == 1 and parse_compare_outcome(crash.returncode, crash.stdout, good) == 2


INJECTED = [(RuntimeError("EVIL\x1b[31m secret"), "INTERNAL", "RuntimeError"), (OSError(13, "EVIL\x1b[31m denied"), "INTERNAL", "PermissionError"),
            (ValueError("EVIL"), "INTERNAL", "ValueError"), (RecursionError("EVIL"), "INTERNAL", "RecursionError"),
            (Exception("EVIL"), "INTERNAL", "Exception"), (KeyboardInterrupt(), "INTERNAL", "KeyboardInterrupt"),
            (bg.BenchmarkGateError("MEASURE_FAILED", "EVIL\x1b[31m"), "MEASURE_FAILED", "BenchmarkGateError"),
            (bg.BenchmarkGateError("EVIL_CODE", "EVIL"), "INTERNAL", "BenchmarkGateError")]


@posix_only
@pytest.mark.parametrize("error,code_name,type_name", INJECTED, ids=lambda v: type(v).__name__ if isinstance(v, BaseException) else None)
def test_injected_runtime_error_is_exit_2_with_no_json(tmp_path, monkeypatch, capsys, error, code_name, type_name):
    c = _bench_case(tmp_path, monkeypatch)
    _seamed_compare(c)

    def boom(*args, **kwargs):
        raise error
    monkeypatch.setattr(bg, "_compare_runs", boom)  # steps 1 to 9 are real: the exports are sealed when the injected error arrives
    before = [signal.getsignal(n) for n in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)]
    out = c.out()
    code, stdout, stderr = _run_main(capsys, _cli_compare_args(c, _gate_file(c), out, "--allow-writable-interpreter"))
    assert code == 2 and stdout == "" and stderr == f"usage error: {code_name}: {type_name}\n"  # never the attacker's text
    assert not os.path.lexists(out) and os.listdir(c.out_dir) == []  # writes nothing
    assert [signal.getsignal(n) for n in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)] == before
    assert all(not os.stat(root).st_mode & 0o200 for root in c.roots)  # sealed stays sealed
    monkeypatch.undo()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    monkeypatch.setattr(bg, "_pid_alive", lambda pid: False)  # the exporting process has exited, as it has when the Orchestrator cleans up
    assert bg.cleanup_root(str(c.world.dispatch)) == "REMOVED"  # cleanup restores the sealed exports and removes the root


@posix_only
def test_a_missing_or_bad_gate_file_is_exit_2_not_a_traceback(tmp_path, monkeypatch, capsys):
    c = _bench_case(tmp_path, monkeypatch)
    _seamed_compare(c)
    out = c.out()
    code, stdout, stderr = _run_main(capsys, _cli_compare_args(c, tmp_path / "nope.json", out))
    assert (code, stdout, stderr) == (2, "", "usage error: INTERNAL: FileNotFoundError\n")
    (tmp_path / "bad.json").write_text("{not json")
    code, stdout, stderr = _run_main(capsys, _cli_compare_args(c, tmp_path / "bad.json", out))
    assert (code, stdout) == (2, "") and stderr.startswith("usage error: INTERNAL: ") and not os.path.lexists(out)
    (tmp_path / "big.json").write_text(" " * (bg._MAX_INPUT_BYTES + 1))
    code, stdout, stderr = _run_main(capsys, _cli_compare_args(c, tmp_path / "big.json", out))
    assert (code, stdout) == (2, "") and not os.path.lexists(out)


_SIGTERM_DRIVER = r'''
import importlib.util, json, os, sys
script, prefix, roots_json, pidfile, *argv = sys.argv[1:]
spec = importlib.util.spec_from_file_location("bg_driver", script)
bg = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bg
spec.loader.exec_module(bg)
real_prefix = os.path.realpath(prefix)
pyx = "python%d.%d" % sys.version_info[:2]
roots = json.loads(roots_json)
CHILD = ("import os, subprocess, time\n"
         "p = subprocess.Popen(['sleep', '300'])\n"
         "open(%r + '.tmp', 'w').write(str(p.pid)); os.replace(%r + '.tmp', %r)\n"
         "time.sleep(300)\n") % (pidfile, pidfile, pidfile)


def probe(python, env):
    return "\n".join([real_prefix, os.path.join(real_prefix, "lib", pyx, "os.py"), real_prefix]) + "\n"


def interpreter_of(bin_dir):
    return bg.interpreter_pin(bin_dir, outside=roots, probe=probe)


real = bg._compare_impl


def compare(gate, repo, base, head, **kw):
    return real(gate, repo, base, head, argv_builder=lambda side, bin_dir, root, target: [sys.executable, "-c", CHILD], min_base_ns=0,
                load_probe=lambda: (0.1, 4), interpreter_of=interpreter_of, order_salt="ab12", **kw)


bg.compare = compare
sys.exit(bg.main(argv))
'''

_SLEEPING_BENCH = """import os, subprocess


def test_bench():
    p = subprocess.Popen([{sleep!r}, "300"])
    open({pid!r} + ".tmp", "w").write(str(p.pid))
    os.replace({pid!r} + ".tmp", {pid!r})
    p.wait()
"""


def _wait_for_pid(pidfile: Path, proc, deadline=240.0) -> int:
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        if pidfile.exists() and pidfile.read_text().strip():
            return int(pidfile.read_text())
        if proc.poll() is not None:
            raise AssertionError(f"the CLI exited early: {proc.communicate()}")
        time.sleep(0.05)
    raise AssertionError("the child never wrote its grandchild's pid")


def _pid_is_gone(pid: int, deadline=15.0) -> bool:
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def _real_pytest_bin(tmp_path: Path) -> Path:
    """A real, pip-less venv whose ``.pth`` makes this interpreter's pytest importable (the pattern of ``pytest_venv`` in test_benchmark_gate_trace.py)."""
    root = tmp_path / "pyvenv"
    venv.create(root, with_pip=False, symlinks=True)
    sites = {os.path.dirname(os.path.dirname(sys.modules[name].__file__)) for name in ("pytest", "_pytest", "pluggy", "iniconfig", "packaging")
             if name in sys.modules}
    site = next((root / "lib").glob("python3*/site-packages"))
    (site / "zz_pytest.pth").write_text("\n".join(sorted(sites)) + "\n")
    return root / "bin"


def _once_world(tmp_path: Path, source: str, gate: dict | None = None):
    root = tmp_path / "once-root"
    (root / "benchmarks").mkdir(parents=True)
    (root / BENCH).write_text(source)
    gate_path = tmp_path / "once-gate.json"
    gate_path.write_text(json.dumps(gate or GATE))
    return root, _real_pytest_bin(tmp_path), gate_path


@posix_only
@pytest.mark.parametrize("which", ["compare", "run-once"])
def test_sigterm_kills_the_childs_group_and_exits_2(tmp_path, monkeypatch, which):
    pidfile = tmp_path / "grandchild.pid"
    if which == "compare":
        c = _bench_case(tmp_path, monkeypatch)
        out = Path(c.out())
        driver = tmp_path / "driver.py"
        driver.write_text(_SIGTERM_DRIVER)
        argv = [sys.executable, str(driver), str(SCRIPT), str(c.world.prefix), json.dumps(list(c.roots)), str(pidfile),
                *_cli_compare_args(c, _gate_file(c), out, "--allow-writable-interpreter")]
    else:
        out = tmp_path / "never.json"
        root, bin_dir, gate_path = _once_world(tmp_path, _SLEEPING_BENCH.format(sleep=shutil.which("sleep") or "/bin/sleep", pid=str(pidfile)))
        argv = [sys.executable, str(SCRIPT), "run-once", "--gate", str(gate_path), "--root", str(root), "--bin", str(bin_dir)]
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
                            env={**os.environ, "TMPDIR": str(tmp_path / "tmp")})  # the exports live under the redirected fixed parent
    try:
        grandchild = _wait_for_pid(pidfile, proc)
        proc.send_signal(signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
    assert proc.returncode == 2, (proc.returncode, stdout, stderr)  # not -15: the handler ran, the cleanup finished
    assert stdout == "" and stderr == "usage error: INTERNAL: KeyboardInterrupt\n"
    assert not out.exists()  # no JSON
    assert _pid_is_gone(grandchild)  # the child's group is gone


DIGEST_BENCH = "import hashlib\n\n\ndef test_bench():\n    print('BENCH_RESULT_DIGEST: ' + hashlib.sha256(b'x').hexdigest())\n"
X_DIGEST = hashlib.sha256(b"x").hexdigest()


def _cli(*argv, timeout=300):
    return subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, timeout=timeout)


@posix_only
def test_run_once_cli(tmp_path, monkeypatch, capsys):
    root, bin_dir, gate = _once_world(tmp_path, DIGEST_BENCH)
    base_args = ["run-once", "--gate", str(gate), "--root", str(root), "--bin", str(bin_dir)]
    done = _cli(*base_args)  # --side defaults to head; exit 0 prints the digest the child printed
    assert (done.returncode, done.stdout, done.stderr) == (0, f"digest: {X_DIGEST}\n", ""), done
    assert _cli(*base_args, "--side", "base").stdout == f"digest: {X_DIGEST}\n"
    # exit 1 prints the reason and the escaped detail on stderr
    (root / BENCH).write_text("def test_bench():\n    raise SystemExit(3)\n")
    for extra, reason in (([], "HEAD_NONZERO_EXIT"), (["--side", "head"], "HEAD_NONZERO_EXIT"), (["--side", "base"], "BASE_NONZERO_EXIT")):
        done = _cli(*base_args, *extra)
        assert (done.returncode, done.stdout) == (1, f"{reason}\n") and done.stderr.startswith("detail: "), done
    (root / BENCH).write_text("def test_bench():\n    pass\n")
    done = _cli(*base_args)
    assert (done.returncode, done.stdout) == (1, "DIGEST_MISSING\n") and done.stderr.startswith("detail: ")
    # a gate that the validator rejects: REJECT:<code>, nothing run (warmup_runs 0 is BOUNDS_REJECTED)
    bad = tmp_path / "bad-gate.json"
    bad.write_text(json.dumps({**GATE, "warmup_runs": 0}))
    done = _cli("run-once", "--gate", str(bad), "--root", str(root), "--bin", str(bin_dir))
    assert (done.returncode, done.stdout) == (1, "REJECT:BOUNDS_REJECTED\n")
    # exit 2: usage or a caller fault, nothing on stdout
    missing = _cli("run-once", "--gate", str(gate), "--root", str(tmp_path / "no-such-root"), "--bin", str(bin_dir))
    assert missing.returncode == 2 and missing.stdout == "" and re.fullmatch(r"usage error: MEASURE_ARGS_INVALID: BenchmarkGateError\n", missing.stderr), missing
    nogate = _cli("run-once", "--gate", str(tmp_path / "none.json"), "--root", str(root), "--bin", str(bin_dir))
    assert (nogate.returncode, nogate.stdout, nogate.stderr) == (2, "", "usage error: INTERNAL: FileNotFoundError\n")
    # injected library outcomes (the real ones need a 10 s timeout or a 1 GiB file): the code on stdout, the escaped detail on stderr, exit 1
    for code in ("HEAD_TIMEOUT", "BASE_TIMEOUT", "OUTPUT_TOO_LARGE", "DIGEST_MISSING"):
        def raising(*a, _code=code, **k):
            raise bg.BenchmarkGateError(_code, "child said \x1b[31mEVIL\nline")
        monkeypatch.setattr(bg, "run_benchmark_once", raising)
        got = _run_main(capsys, base_args)
        assert got[:2] == (1, f"{code}\n") and got[2] == "detail: child said ?[31mEVIL line\n", (code, got)
    for code in ("MEASURE_FAILED", "MEASURE_ARGS_INVALID", "UNSUPPORTED_PLATFORM"):  # a harness fault is not a verdict
        monkeypatch.setattr(bg, "run_benchmark_once", lambda *a, _code=code, **k: (_ for _ in ()).throw(bg.BenchmarkGateError(_code, "EVIL")))
        assert _run_main(capsys, base_args) == (2, "", f"usage error: {code}: BenchmarkGateError\n")
    monkeypatch.setattr(bg, "run_benchmark_once", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("EVIL")))
    assert _run_main(capsys, base_args) == (2, "", "usage error: INTERNAL: RuntimeError\n")
    monkeypatch.setattr(bg, "run_benchmark_once", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert _run_main(capsys, base_args) == (2, "", "usage error: INTERNAL: KeyboardInterrupt\n")


COMPARE_FLAGS = ["--gate", "--repo", "--base-root", "--head-root", "--base-commit", "--head-commit", "--base-bin", "--head-bin", "--base-snapshot",
                 "--base-snapshot-sha256", "--base-interpreter-sha256", "--head-snapshot", "--head-snapshot-sha256", "--head-interpreter-sha256", "--out"]


@posix_only
def test_cli_arguments_are_the_spec_ones(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(bg, "_cmd_compare", lambda args: seen.append(args) or 0)
    monkeypatch.setattr(bg, "_cmd_run_once", lambda args: seen.append(args) or 0)
    full = [part for flag in COMPARE_FLAGS for part in (flag, f"v{flag[2:]}")]
    assert bg.main(["compare", *full]) == 0
    args = seen.pop()
    assert sorted(vars(args)) == sorted(["command", "func", "attempt", "allow_writable_interpreter"] + [f[2:].replace("-", "_") for f in COMPARE_FLAGS])
    assert args.attempt == 1 and args.allow_writable_interpreter is False and args.out == "vout" and args.gate == "vgate"
    assert bg.main(["compare", *full, "--attempt", "2", "--allow-writable-interpreter"]) == 0
    args = seen.pop()
    assert args.attempt == 2 and args.allow_writable_interpreter is True
    capsys.readouterr()
    for flag in COMPARE_FLAGS:  # each required
        rest = list(full)
        index = rest.index(flag)
        del rest[index:index + 2]
        assert bg.main(["compare", *rest]) == 2 and seen == [], flag
    for bad in (["--attempt", "x"], ["--allow-writable-interpreter", "yes"], ["--ini", "x.ini"], ["--side", "head"]):
        assert bg.main(["compare", *full, *bad]) == 2 and seen == [], bad
    assert bg.main(["run-once", "--gate", "g", "--root", "r", "--bin", "b"]) == 0
    args = seen.pop()
    assert sorted(vars(args)) == ["bin", "command", "func", "gate", "root", "side"] and args.side == "head"  # no ini option
    assert bg.main(["run-once", "--gate", "g", "--root", "r", "--bin", "b", "--side", "base"]) == 0 and seen.pop().side == "base"
    for rest in (["--root", "r", "--bin", "b"], ["--gate", "g", "--bin", "b"], ["--gate", "g", "--root", "r"],
                 ["--gate", "g", "--root", "r", "--bin", "b", "--side", "both"], ["--gate", "g", "--root", "r", "--bin", "b", "--ini", "i"]):
        assert bg.main(["run-once", *rest]) == 2 and seen == [], rest


# --- T6: real pytest children and real-child tamper rows (spec 3, 4 rows 6 and 17) ---
# The two real rows run the whole pipeline with the default argv (a real ``python -P -m pytest`` child, a real trace plugin) in two real,
# pip-less venvs whose project is installed as an editable dist (the one exempt dist of the parity check). The interpreter is the machine's own,
# so ``allow_writable_interpreter`` is on (a Homebrew or runner interpreter is writable) and the interpreter seam is the default probe.
# The tamper rows use tiny real child processes in the fixture world, whose interpreter is the FAKE prefix: no row ever writes to a real interpreter.

REAL_LOOP = 40_000_000  # iterations of one pass of the workload; sized so one pass takes about a second (see the T6 calibration figures)
_REAL_WORK = ("def _work():\n    x = 0\n    for i in range(%d):\n        x = (x * 31 + i) %% 1000003\n    return x\n\n\n" % REAL_LOOP)
REAL_CORE_SLOW = _REAL_WORK + "def f():\n    _work()\n    return _work()\n"  # the redundant first pass is the "fix" the head removes
REAL_CORE_FAST = _REAL_WORK + "def f():\n    return _work()\n"  # the same value, half the work
REAL_CORE_UNCHANGED = REAL_CORE_SLOW + "\n# a comment: the work done is the same\n"
REAL_MIN_BASE_NS = 500_000_000 # lowered from the production floor so a fast machine still measures; the pipeline, not the floor, is under test

_REAL_FINDER = '''MAPPING: dict[str, str] = {{"app": {target!r}}}
NAMESPACES: dict[str, list[str]] = {{}}

import sys
from importlib.util import spec_from_file_location


class _Finder:
    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        if fullname in MAPPING:
            return spec_from_file_location(fullname, MAPPING[fullname] + "/__init__.py", submodule_search_locations=[MAPPING[fullname]])
        return None


def install():
    if _Finder not in sys.meta_path:
        sys.meta_path.append(_Finder)
'''


def _real_repo(mode: str):
    """``new``: the base has the slow code and no benchmark, the head has the fast code and adds the benchmark (overlay-origin). ``pre``:
    the base already has the benchmark and the head changes nothing but a comment."""
    def build(tmp_path: Path):
        repo, _, _ = _ORIGINAL_BUILD_REPO(tmp_path)
        files = {"src/app/core.py": REAL_CORE_SLOW}
        if mode == "pre":
            files[BENCH] = BENCH_OK.decode()
        make_commit(repo, files, "slow")
        git(repo, "commit", "-q", "-m", "slow")
        base = git(repo, "rev-parse", "HEAD")
        if mode == "new":
            make_commit(repo, {"src/app/core.py": REAL_CORE_FAST, BENCH: BENCH_OK.decode()}, "fast")
        else:
            make_commit(repo, {"src/app/core.py": REAL_CORE_UNCHANGED}, "same")
        git(repo, "commit", "-q", "-m", "head")
        return repo, base, git(repo, "rev-parse", "HEAD")
    return build


def _real_pytest_venv(root: Path, export: Path) -> Path:
    """A real, pip-less venv: this interpreter's pytest through a ``.pth`` (the pattern of ``build_venv``), and the project installed as the
    one editable dist the parity check exempts, so ``import app`` finds the export's ``src/app``. All of it exists before the snapshot."""
    venv.create(root, with_pip=False, symlinks=True)
    sites = {os.path.dirname(os.path.dirname(sys.modules[name].__file__)) for name in ("pytest", "_pytest", "pluggy", "iniconfig", "packaging")
             if name in sys.modules}
    site = next((root / "lib").glob("python3*/site-packages"))
    (site / "zz_pytest.pth").write_text("\n".join(sorted(sites)) + "\n")
    finder = _REAL_FINDER.format(target=str(export / "src" / "app")).encode()
    _editable(types.SimpleNamespace(site=site, export=export), name="app", extra_files={"__editable___app_1_0_finder.py": finder})
    return root / "bin"


def build_real_world(tmp_path: Path, monkeypatch, mode: str) -> World:
    temp = tmp_path / "tmp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    try:
        bg._require_modern_git()
    except bg.BenchmarkGateError as exc:
        if exc.code != "GIT_TOO_OLD":
            raise
        pytest.skip(f"git >= 2.43 is needed: {exc.detail}")
    repo, base, head = _real_repo(mode)(tmp_path)
    dispatch = bg.fixed_parent() / DISPATCH_ROOT
    sides = {}
    for name, commit in (("base", base), ("head", head)):
        export = bg.export_tree(repo, commit, dispatch / name)
        bin_dir = _real_pytest_venv(dispatch / f"venv-{name}", export)
        snapshot = tmp_path / f"{name}-venv.json"
        bg.snapshot_venv(bin_dir, snapshot)
        sides[name] = types.SimpleNamespace(commit=commit, export=export, bin=bin_dir, snapshot=snapshot, shape="real")
    return World(repo=repo, base=base, head=head, prefix=None, dispatch=dispatch, sides=sides, interpreter_of=None)


class RealCase(Case):
    """``Case`` with the real interpreter probe instead of the fake-prefix stub."""

    def interp(self, bin_dir):
        self.spy.append("interpreter_of")
        return bg.interpreter_pin(bin_dir, outside=self.roots)

    def _side(self, name):
        s = self.world.sides[name]
        pin = bg.interpreter_pin(s.bin, outside=self.roots)
        return bg.Side(str(s.export), s.commit, str(s.bin), str(s.snapshot), hashlib.sha256(s.snapshot.read_bytes()).hexdigest(), pin.sha256)


def _real_compare(tmp_path: Path, monkeypatch, mode: str):
    """One whole real comparison (steps 1 to 13) on fresh fixtures. Returns ``(case, result, seen)``; ``seen`` holds what steps 9 and 12 returned."""
    c = RealCase(build_real_world(tmp_path, monkeypatch, mode), tmp_path, monkeypatch)
    seen = {"post": []}
    real_prepare, real_post = bg._compare_prepare, bg._post_run_check

    def prepare(*a, **k):
        seen["prepared"] = real_prepare(*a, **k)
        return seen["prepared"]

    def post(*a, **k):
        seen["post"].append(real_post(*a, **k))
        return seen["post"][-1]
    monkeypatch.setattr(bg, "_compare_prepare", prepare)
    monkeypatch.setattr(bg, "_post_run_check", post)
    result = c.impl(min_base_ns=REAL_MIN_BASE_NS)  # default argv_builder: real pytest children
    return c, result, seen


@posix_only
def test_real_improved_overlay_origin(tmp_path, monkeypatch):
    c, result, seen = _real_compare(tmp_path, monkeypatch, "new")
    _ran(result, "IMPROVED_CLEAR")
    assert result["result"] == "IMPROVED" and result["kind"] is None and result["benchmark_origin"] == "BUILDER_AUTHORED"  # exit-0 class: IMPROVED
    # a lower bound, not equality: removing half the work cannot give more than 0.5, and a quiet machine gave 0.45 to 0.49 (T6 calibration); 0.25 is
    # about half of that, above the gate's own 0.10 (never loosened) and far from anything noise alone would make
    assert result["improvement"] >= 0.25 and len(result["ratios"]) == 6 and result["n"] == 6
    assert result["host_check"] == "checked" and result["interpreter_writable"] is True and result["order_salt"] == "ab12"
    # JSON with every 2.8 key, equal to what was returned
    assert set(result) == set(bg.COMPARE_RESULT_KEYS) and json.loads(Path(c.last_out).read_text()) == result
    assert [k for k, v in result.items() if v is None] == ["kind", "trace_fault", "side", "phase", "partial"]
    assert re.fullmatch(r"[0-9a-f]{64}", result["digest"]) and result["benchmark_sha256"] == hashlib.sha256(BENCH_OK).hexdigest()
    assert result["trace"]["base"]["kind"] == result["trace"]["head"]["kind"] == "lines" and result["trace"]["base"]["value"] > 0
    assert result["trace"]["base"]["value"] == result["trace"]["head"]["value"]
    # steps 9 and 12 passed with the overlaid file: the base export holds the head's benchmark, sealed, and step 12 found nothing
    prepared = seen["prepared"]
    assert prepared.origin == "BUILDER_AUTHORED" and seen["post"] == [None]
    base_bench = Path(c.roots[0]) / BENCH
    assert base_bench.read_bytes() == BENCH_OK and not os.stat(base_bench).st_mode & 0o222
    # every fingerprint is unchanged after the children ran (recomputed here, independently of step 12)
    assert bg._baseline_fingerprints(c.base, c.head, c.roots, prepared.baseline.real_python, "ran") == prepared.baseline
    assert bg.hash_export(c.roots[0]) == prepared.h0[0] and bg.hash_export(c.roots[1]) == prepared.h0[1]


@posix_only
def test_real_not_improved_pre_existing_benchmark(tmp_path, monkeypatch):
    c, result, seen = _real_compare(tmp_path, monkeypatch, "pre")
    _ran(result, "BELOW_HALF_THRESHOLD")
    assert result["result"] == "NOT_IMPROVED" and result["benchmark_origin"] == "PRE_EXISTING"
    assert result["improvement"] < c.gate.get("min_improvement", 0.10) / 2 and len(result["ratios"]) == 6
    assert set(result) == set(bg.COMPARE_RESULT_KEYS) and json.loads(Path(c.last_out).read_text()) == result
    assert seen["post"] == [None] and re.fullmatch(r"[0-9a-f]{64}", result["digest"])
    assert result["trace"]["base"]["value"] == result["trace"]["head"]["value"] > 0


def _child_with(extra: str, payload):
    """A builder for tiny real children that speak both protocols (``_FAKE_TRACE_CHILD``) and then run ``extra`` on the HEAD side only.
    ``payload(side, bin_dir, root)`` is the JSON the child gets as ``sys.argv[3]`` (``{}`` for the base side)."""
    def builder(side, bin_dir, root, target):
        arg = json.dumps(payload(bin_dir, root) if side == "head" else {})
        return [sys.executable, "-c", _FAKE_TRACE_CHILD + extra, FAKE_DIGEST, str(FAKE_TRACE_LINES), arg]
    return builder


_CHILD_HOOK_AND_SNAPSHOT = """
import importlib.util, json
a = json.loads(sys.argv[3])
if a:
    spec = importlib.util.spec_from_file_location("bg_in_child", a["script"])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bg_in_child"] = mod
    spec.loader.exec_module(mod)
    open(os.path.join(a["site"], "evil.pth"), "w").write("import evil_hook\\n")
    if os.path.exists(a["snapshot"]):
        os.unlink(a["snapshot"])
    mod.snapshot_venv(a["bin"], a["snapshot"])  # the snapshot now blesses the hook
"""

_CHILD_EDIT_INTERPRETER = """
import json
a = json.loads(sys.argv[3])
if a:
    os.makedirs(os.path.join(a["stdlib"], "__pycache__"), exist_ok=True)
    open(os.path.join(a["stdlib"], "__pycache__", "planted.cpython-312.pyc"), "wb").write(b"x")
"""

_CHILD_EDIT_AND_RESTORE = """
import json, stat
a = json.loads(sys.argv[3])
if a:
    root, path = a["root"], os.path.join(a["root"], "README.md")
    dir_mode, before = stat.S_IMODE(os.stat(root).st_mode), os.stat(path)
    data = open(path, "rb").read()
    os.chmod(root, 0o755)
    os.chmod(path, 0o644)
    open(path, "wb").write(b"x" * len(data))
    open(path, "wb").write(data)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    os.chmod(path, stat.S_IMODE(before.st_mode))
    os.chmod(root, dir_mode)
"""


def _hook_payload(c):
    side = c.world.sides["head"]
    return lambda bin_dir, root: {"script": str(SCRIPT), "site": str(_site(c)), "snapshot": str(side.snapshot), "bin": str(side.bin)}


def _interp_payload(c):
    stdlib = next(p for p in (c.world.prefix / "lib").glob("python3*") if p.is_dir())
    return lambda bin_dir, root: {"stdlib": str(stdlib)}


def _restore_payload(c):
    return lambda bin_dir, root: {"root": root}


REAL_CHILD_TAMPERS = {
    "hook-and-snapshot": ("SNAPSHOT_CHANGED", _CHILD_HOOK_AND_SNAPSHOT, _hook_payload),
    "interpreter": ("INTERPRETER_CHANGED", _CHILD_EDIT_INTERPRETER, _interp_payload),
    "edit-and-restore": ("EXPORT_CHANGED", _CHILD_EDIT_AND_RESTORE, _restore_payload),
}


@posix_only
@pytest.mark.parametrize("name", sorted(REAL_CHILD_TAMPERS))
def test_real_child_tamper_is_isolation_rejected_and_beats_the_other_results(bcase, name):
    c = bcase
    detail, extra, payload = REAL_CHILD_TAMPERS[name]
    c.spies("_post_run_check")
    seen = {}
    real_prepare = bg._compare_prepare
    c.mp.setattr(bg, "_compare_prepare", lambda *a, **k: seen.setdefault("prepared", real_prepare(*a, **k)))
    result = c.impl(argv_builder=_child_with(extra, payload(c)), min_base_ns=0)
    _ran(result, "ISOLATION_REJECTED", detail)
    assert result["result"] == "REJECTED" and result["kind"] is None and _post12(c) == 1
    assert result["trace"]["head"]["value"] == FAKE_TRACE_LINES  # both paired runs completed; step 12 then beat what they said
    if name == "edit-and-restore":  # the bytes, modes and names are all back, so the content hash is blind to it: only the fingerprint saw it
        assert bg.hash_export(c.roots[1]) == seen["prepared"].h0[1]
        assert bg.verify_export_against_commit(c.world.repo, c.head.commit, c.roots[1], allow={}) == []


_CHILD_REWRITES_INI_AND_PLANTS = """
import json
log = json.loads(sys.argv[3])["log"]
home = os.environ["HOME"]
scratch = os.path.dirname(home)
work = os.path.dirname(scratch)
ini = os.path.join(scratch, "empty.ini")
row = {"ini": open(ini).read(), "scratch": sorted(os.listdir(scratch)), "work_has_planted": "planted" in os.listdir(work)}
open(log, "a").write(json.dumps(row) + "\\n")
open(ini, "w").write("[pytest]\\naddopts = --tampered\\n")
open(os.path.join(work, "planted"), "w").write("x")
"""


@posix_only
def test_a_real_child_that_rewrites_its_ini_or_plants_a_file_under_work_changes_nothing(bcase, tmp_path):
    c = bcase
    log = tmp_path / "ini-log.jsonl"

    def builder(side, bin_dir, root, target):  # BOTH sides tamper with their own scratch and work
        return [sys.executable, "-c", _FAKE_TRACE_CHILD + _CHILD_REWRITES_INI_AND_PLANTS, FAKE_DIGEST, str(FAKE_TRACE_LINES), json.dumps({"log": str(log)})]
    result = c.impl(argv_builder=builder, min_base_ns=0)
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    gate = bg.validate_benchmark_gate(c.gate)[0]
    assert len(rows) == 2 + 2 * (gate["warmup_runs"] + gate["repeats"])  # the trace pair, then every warmup and timed run of both sides
    # every run saw the pristine ini and a scratch holding only its own three entries, however much the earlier children rewrote and planted
    assert all(row["ini"] == bg._EMPTY_INI and row["scratch"] == ["empty.ini", "home", "tmp"] for row in rows)
    assert any(row["work_has_planted"] for row in rows)  # the plant did land under work for the measure runs: the row is not vacuous
    assert result["stage"] == "ran" and result["reason"] != "ISOLATION_REJECTED" and len(result["ratios"]) == 6 and result["trace"]["head"]["value"] == FAKE_TRACE_LINES


# --- T7 pins (spec 4 row 18): the CLI registers both commands, the CLI path uses the default seams, the generated salt is random ---

@posix_only
def test_main_registers_compare_and_run_once(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(bg, "_cmd_compare", lambda args: seen.append("compare") or 0)
    monkeypatch.setattr(bg, "_cmd_run_once", lambda args: seen.append("run-once") or 0)
    assert bg.main(["--help"]) == 0  # argparse prints the subcommand list and exits 0
    helptext = capsys.readouterr().out
    assert "compare" in helptext and "run-once" in helptext
    full = [part for flag in COMPARE_FLAGS for part in (flag, f"v{flag[2:]}")]
    assert bg.main(["compare", *full]) == 0 and seen == ["compare"]
    assert bg.main(["run-once", "--gate", "g", "--root", "r", "--bin", "b"]) == 0 and seen == ["compare", "run-once"]
    assert bg.main(["no-such-command"]) == 2 and seen == ["compare", "run-once"]


@posix_only
def test_cli_path_uses_default_seams(monkeypatch, tmp_path):
    """``main`` -> ``_cmd_compare`` -> ``compare`` -> ``_compare_impl`` passes only the five spec arguments: no ``argv_builder``,
    ``load_probe``, ``order_salt``, ``interpreter_of`` (or ``min_base_ns``): a real CLI process has no seams."""
    calls = []

    def impl(*args, **kwargs):
        calls.append((args, kwargs))
        raise bg.BenchmarkGateError("MEASURE_FAILED", "stop here")
    monkeypatch.setattr(bg, "_compare_impl", impl)
    gate = tmp_path / "gate.json"
    gate.write_text(json.dumps(GATE))
    full = [part for flag in COMPARE_FLAGS for part in (flag, f"v{flag[2:]}")]
    full[full.index("--gate") + 1] = str(gate)
    assert bg.main(["compare", *full, "--attempt", "2", "--allow-writable-interpreter"]) == 2  # the stub's raise: exit 2, nothing else ran
    (args, kwargs), = calls
    assert kwargs == {"attempt": 2, "out_path": "vout", "allow_writable_interpreter": True}
    assert args[0] == GATE and args[1] == "vrepo"
    assert args[2] == bg.Side("vbase-root", "vbase-commit", "vbase-bin", "vbase-snapshot", "vbase-snapshot-sha256", "vbase-interpreter-sha256")
    assert args[3] == bg.Side("vhead-root", "vhead-commit", "vhead-bin", "vhead-snapshot", "vhead-snapshot-sha256", "vhead-interpreter-sha256")
    calls.clear()
    with pytest.raises(bg.BenchmarkGateError):  # the library entry point too
        bg.compare(GATE, "r", args[2], args[3], out_path="o")
    (_, kwargs), = calls
    assert set(kwargs) == {"attempt", "out_path", "allow_writable_interpreter"}


@posix_only
def test_generated_salt_is_random_and_recorded(bcase, tmp_path, monkeypatch):
    recorded = []

    def run_one(case):
        seen = {}

        def measure(*a, **kw):
            seen.update(kw)
            order = bg.run_order(kw["base_commit"], kw["head_commit"], kw["benchmark_sha256"], kw["attempt"], kw["repeats"], salt=kw["order_salt"])
            return {**MEASURE_OK, "order": order}
        case.mp.setattr(bg, "trace_paired", lambda *a, **k: TRACE_OK)
        case.mp.setattr(bg, "measure_paired", measure)
        result = case.impl(argv_builder=fake_trace_builder, min_base_ns=0, order_salt=None)  # no salt: _compare_impl generates one
        recorded.append((result, seen))
        return result
    first = run_one(bcase)
    second_dir = tmp_path / "second"  # one compare per world: the second needs fresh exports
    second_dir.mkdir()
    second = run_one(_bench_case(second_dir, monkeypatch))
    assert first["order_salt"] != second["order_salt"]
    for result, seen in recorded:
        assert re.fullmatch("[0-9a-f]{16}", result["order_salt"]) and seen["order_salt"] == result["order_salt"]  # what ran is what was recorded
        again = bg.run_order(result["base_commit"], result["head_commit"], result["benchmark_sha256"], result["attempt"], result["repeats"],
                             salt=result["order_salt"])
        assert result["order"] == again  # the recorded salt reproduces the order
