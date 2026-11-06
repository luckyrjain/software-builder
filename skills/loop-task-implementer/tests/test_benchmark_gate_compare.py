"""C4d-3 ``compare``: vocabularies, ``Side``, result assembly and the dir-fd result writer (task T2a).

Pure tests only: no child process, no git. The pipeline rows arrive with later tasks and extend this module.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
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
