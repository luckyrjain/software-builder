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
