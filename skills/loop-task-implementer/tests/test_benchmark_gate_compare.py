"""C4d-3 ``compare``: vocabularies, ``Side``, result assembly and the dir-fd result writer (task T2a).

Pure tests only: no child process, no git. The pipeline rows arrive with later tasks and extend this module.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
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
