"""C4d-1: the measurement harness (``run_order``, ``side_env``, ``pytest_argv``, ``measure_paired``).

Children are ``python -c`` processes injected through the ``argv_builder`` seam (a real ``python -m pytest`` costs 0.4 s median and up to
3 s under load); one test runs real pytest to prove the digest is read with ``-P --import-mode=importlib`` and that a head-added
``hashlib.py`` cannot shadow (that is the only real-pytest test in this file; the trace's real-pytest rows are in test_benchmark_gate_trace.py).
No assertion depends on a measured duration.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import textwrap
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_gate.py"
spec = importlib.util.spec_from_file_location("benchmark_gate_measure_under_test", SCRIPT)
bg = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bg
spec.loader.exec_module(bg)

BASE = "a" * 40
HEAD = "b" * 40
BENCH = "c" * 64
DIGEST = "d" * 64

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX harness")


# --- run_order ------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("repeats", [4, 6, 8])
@pytest.mark.parametrize("attempt", [1, 2])
def test_run_order_is_balanced_and_deterministic(repeats, attempt):
    order = bg.run_order(BASE, HEAD, BENCH, attempt, repeats)
    assert len(order) == repeats
    assert order.count("head_first") == repeats // 2
    assert order.count("base_first") == repeats // 2
    assert order == bg.run_order(BASE, HEAD, BENCH, attempt, repeats)


def test_run_order_depends_on_every_seed_input():
    seen = {tuple(bg.run_order(base, head, bench, attempt, 8))
            for base in (BASE, "e" * 40) for head in (HEAD, "f" * 40) for bench in (BENCH, "0" * 64) for attempt in (1, 2)}
    assert len(seen) > 8  # 16 combinations, 70 balanced orders: most differ


def test_run_order_is_not_strict_alternation_for_any_commit_pair():
    alternating = [["head_first", "base_first"] * 4, ["base_first", "head_first"] * 4]
    orders = [bg.run_order(f"{i:040x}", HEAD, BENCH, 1, 8) for i in range(40)]
    assert len({tuple(o) for o in orders}) > 5
    assert sum(o in alternating for o in orders) < 10  # 2 of 70 balanced orders alternate; a fixed alternation would make all 40 do


@pytest.mark.parametrize("args", [
    ("short", HEAD, BENCH, 1, 4), (BASE, "G" * 40, BENCH, 1, 4), (BASE, HEAD, "c" * 63, 1, 4), (BASE, HEAD, BENCH, 0, 4),
    (BASE, HEAD, BENCH, 3, 4), (BASE, HEAD, BENCH, True, 4), (BASE, HEAD, BENCH, 1, 5), (BASE, HEAD, BENCH, 1, True),
    (None, HEAD, BENCH, 1, 4), (BASE, HEAD, BENCH, "1", 4), (BASE.upper(), HEAD, BENCH, 1, 4),
])
def test_run_order_rejects_bad_arguments(args):
    with pytest.raises(bg.BenchmarkGateError) as info:
        bg.run_order(*args)
    assert info.value.code == "MEASURE_ARGS_INVALID"


def test_run_order_accepts_sha256_commits():
    assert len(bg.run_order("a" * 64, "b" * 64, BENCH, 1, 4)) == 4


# --- side_env / pytest_argv -----------------------------------------------------------------------------------------------

def test_side_env_is_an_allowlist(tmp_path):
    env = bg.side_env(str(tmp_path / "venv" / "bin"), str(tmp_path / "scratch"))
    assert set(env) == {"PATH", "VIRTUAL_ENV", "PYTHONNOUSERSITE", "PYTHONHASHSEED", "PYTHONPYCACHEPREFIX",
                        "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "LANG", "HOME", "TMPDIR"}
    assert env["PATH"] == f"{tmp_path / 'venv' / 'bin'}:/usr/bin:/bin"
    assert env["VIRTUAL_ENV"] == str(tmp_path / "venv")
    assert env["PYTHONNOUSERSITE"] == "1" and env["PYTHONHASHSEED"] == "0" and env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert "PYTHONPATH" not in env
    assert Path(env["HOME"]).is_dir() and Path(env["TMPDIR"]).is_dir()
    assert Path(env["HOME"]).parent == tmp_path / "scratch"


def test_side_env_ignores_the_callers_environment(tmp_path, monkeypatch):
    for name in ("GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "ANTHROPIC_API_KEY", "PYTHONPATH", "GIT_DIR"):
        monkeypatch.setenv(name, "x")
    env = bg.side_env(str(tmp_path / "bin"), str(tmp_path / "s"))
    assert not {"GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "ANTHROPIC_API_KEY", "PYTHONPATH", "GIT_DIR"} & set(env)


def test_pytest_argv_is_the_designed_argv():
    argv = bg.pytest_argv("/v/bin", "/r", "benchmarks/test_b.py::test_b", "/w/empty.ini")
    assert argv == ["/v/bin/python", "-P", "-m", "pytest", "-q", "--no-header", "-s", "--noconftest", "--import-mode=importlib",
                    "-c", "/w/empty.ini", "--rootdir", "/r", "-p", "no:cacheprovider", "benchmarks/test_b.py::test_b"]


def test_trace_env_is_a_copy_with_four_keys():
    env = {"PATH": "/x", "HOME": "/h"}
    out = bg.trace_env(env, "/plug", "benchmarks/b.py", "/out/trace.json", "n0nce")
    assert out is not env and env == {"PATH": "/x", "HOME": "/h"}
    assert out == {**env, "PYTHONPATH": "/plug", "BENCH_TRACE_FILE": "benchmarks/b.py", "BENCH_TRACE_OUT": "/out/trace.json",
                   "BENCH_TRACE_NONCE": "n0nce"}


def test_pytest_argv_plugins_keyword_only_validated_and_placed_before_the_target():
    base = bg.pytest_argv("/v/bin", "/r", "t.py::t", "/w/e.ini")
    for plugins in (("bench_trace_plugin",), ["bench_trace_plugin"]):
        argv = bg.pytest_argv("/v/bin", "/r", "t.py::t", "/w/e.ini", plugins=plugins)
        assert argv[-5:] == ["-p", "no:cacheprovider", "-p", "bench_trace_plugin", "t.py::t"]
        assert argv[:-3] == base[:-1]
    assert bg.pytest_argv("/v/bin", "/r", "t.py::t", "/w/e.ini", plugins=()) == base
    with pytest.raises(TypeError):
        bg.pytest_argv("/v/bin", "/r", "t.py::t", "/w/e.ini", ("bench_trace_plugin",))
    for bad in ("abc", "bench_trace_plugin", ("os",), ["x;y"], ("bench_trace_plugin", "os"), 5, None):
        with pytest.raises(ValueError):
            bg.pytest_argv("/v/bin", "/r", "t.py::t", "/w/e.ini", plugins=bad)


# --- measure_paired with injected children --------------------------------------------------------------------------------

def fake_sides(tmp_path):
    roots, bins = {}, {}
    for side in ("base", "head"):
        roots[side] = tmp_path / f"{side}-root"
        bins[side] = tmp_path / f"{side}-venv" / "bin"
        roots[side].mkdir()
        bins[side].mkdir(parents=True)
    return roots, bins


def builder(script: str, *extra: str):
    """argv_builder running ``python -c script <side> <root> <extra...>``."""
    def build(side, bin_dir, root, target):
        return [sys.executable, "-c", textwrap.dedent(script), side, root, target, *extra]
    return build


def measure(tmp_path, script, **overrides):
    roots, bins = fake_sides(tmp_path)
    kwargs = dict(repeats=4, timeout_seconds=30, base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH,
                  min_base_ns=0, argv_builder=builder(script))
    kwargs.update(overrides)
    target = kwargs.pop("target", "bench.py::test_bench")
    return bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), target, **kwargs)


def refusal(tmp_path, script, **overrides):
    with pytest.raises(bg.BenchmarkGateError) as info:
        measure(tmp_path, script, **overrides)
    return info.value


OK_CHILD = f"""
    import sys
    print("BENCH_RESULT_DIGEST: {DIGEST}")
"""


@posix_only
def test_a_clean_measurement_returns_paired_positive_ints(tmp_path):
    result = measure(tmp_path, OK_CHILD)
    assert result["digest"] == DIGEST
    assert result["order"] == bg.run_order(BASE, HEAD, BENCH, 1, 4)
    assert len(result["base_ns"]) == len(result["head_ns"]) == 4
    assert all(type(v) is int and v > 0 for v in result["base_ns"] + result["head_ns"])


@posix_only
def test_measurement_output_feeds_evaluate_paired_samples(tmp_path):
    result = measure(tmp_path, OK_CHILD)
    verdict = bg.evaluate_paired_samples(result["base_ns"], result["head_ns"], repeats=4, min_improvement=0.1, max_noise=0.1)
    assert verdict[0] in ("IMPROVED", "NOT_IMPROVED", "INCONCLUSIVE")


@posix_only
def test_rounds_run_in_the_seeded_order_with_one_warmup_round_first(tmp_path):
    marker = tmp_path / "marker"
    script = f"""
        import sys
        with open({str(marker)!r}, "a") as handle:
            handle.write(sys.argv[1] + "\\n")
        print("BENCH_RESULT_DIGEST: {DIGEST}")
    """
    result = measure(tmp_path, script)
    ran = marker.read_text().split()
    assert ran[:2] == ["base", "head"]  # the warmup round
    timed = ran[2:]
    assert len(timed) == 8
    expected = []
    for position in result["order"]:
        expected += ["head", "base"] if position == "head_first" else ["base", "head"]
    assert timed == expected


@posix_only
def test_two_warmup_rounds(tmp_path):
    marker = tmp_path / "marker"
    script = f"""
        import sys
        open({str(marker)!r}, "a").write(sys.argv[1] + "\\n")
        print("BENCH_RESULT_DIGEST: {DIGEST}")
    """
    measure(tmp_path, script, warmup=2)
    assert len(marker.read_text().split()) == 4 + 8


@posix_only
def test_each_run_has_its_own_home_and_tmpdir_and_the_roots_as_cwd(tmp_path):
    marker = tmp_path / "marker"
    script = f"""
        import os, sys
        open({str(marker)!r}, "a").write(" ".join([sys.argv[1], os.getcwd(), os.environ["HOME"], os.environ["TMPDIR"], os.environ["PYTHONHASHSEED"], str("PYTHONPATH" in os.environ), str(any(n in os.environ for n in ("BENCH_TRACE_FILE", "BENCH_TRACE_OUT", "BENCH_TRACE_NONCE")))]) + "\\n")
        print("BENCH_RESULT_DIGEST: {DIGEST}")
    """
    measure(tmp_path, script)
    rows = [line.split() for line in marker.read_text().splitlines()]
    assert len({row[2] for row in rows}) == len(rows) and len({row[3] for row in rows}) == len(rows)
    for side, cwd, _home, _tmp, seed, has_path, has_trace in rows:
        assert os.path.realpath(cwd) == os.path.realpath(tmp_path / f"{side}-root")
        assert seed == "0" and has_path == "False" and has_trace == "False"


@posix_only
def test_scratch_directories_are_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", None)
    measure(tmp_path, OK_CHILD)
    assert list((tmp_path / "tmp").iterdir()) == []


@posix_only
def test_an_unknown_execute_failure_kind_is_an_assertion_error(tmp_path, monkeypatch):
    def execute(side, argv, root, scratch, env, timeout, fail):
        raise fail("mystery", "x")

    monkeypatch.setattr(bg, "_execute", execute)
    with pytest.raises(AssertionError, match="unknown _execute failure kind"):
        measure(tmp_path, OK_CHILD)


@posix_only
def test_a_nonzero_exit_on_each_side_has_its_own_code(tmp_path):
    for side in ("base", "head"):
        script = f"""
            import sys
            print("BENCH_RESULT_DIGEST: {DIGEST}")
            sys.exit(3 if sys.argv[1] == {side!r} else 0)
        """
        err = refusal(tmp_path / side if (tmp_path / side).mkdir() is None else tmp_path, script)
        assert err.code == f"{side.upper()}_NONZERO_EXIT"
        assert "exit 3" in err.detail


@posix_only
def test_a_child_killed_by_a_signal_is_a_nonzero_exit(tmp_path):
    script = """
        import os, signal
        os.kill(os.getpid(), signal.SIGKILL)
    """
    assert refusal(tmp_path, script).code == "BASE_NONZERO_EXIT"


@posix_only
def test_a_run_over_the_timeout_is_killed_and_reported(tmp_path):
    script = f"""
        import time
        print("BENCH_RESULT_DIGEST: {DIGEST}", flush=True)
        time.sleep(30)
    """
    started = time.monotonic()
    err = refusal(tmp_path, script, timeout_seconds=1)
    assert err.code == "BASE_TIMEOUT"
    assert time.monotonic() - started < 20


@posix_only
def test_a_slow_exit_after_the_timeout_is_not_a_success(tmp_path):
    script = f"""
        import time
        print("BENCH_RESULT_DIGEST: {DIGEST}", flush=True)
        time.sleep(2)
    """
    assert refusal(tmp_path, script, timeout_seconds=0.5).code == "BASE_TIMEOUT"


@posix_only
def test_oversize_stdout_is_detected_even_though_python_survives_sigxfsz(tmp_path):
    script = f"""
        import sys
        try:
            sys.stdout.write("x" * (3 << 20))
            sys.stdout.flush()
        except OSError:
            pass
        print("BENCH_RESULT_DIGEST: {DIGEST}")
    """
    assert refusal(tmp_path, script).code == "OUTPUT_TOO_LARGE"


@posix_only
def test_oversize_stderr_is_detected(tmp_path):
    script = f"""
        import sys
        try:
            sys.stderr.write("x" * (3 << 20))
            sys.stderr.flush()
        except OSError:
            pass
        print("BENCH_RESULT_DIGEST: {DIGEST}")
    """
    assert refusal(tmp_path, script).code == "OUTPUT_TOO_LARGE"


OVERSIZE_THEN = """
    import sys
    try:
        sys.stdout.write("x" * (3 << 20))
        sys.stdout.flush()
    except OSError:
        pass
    {after}
"""


@posix_only
def test_characterize_error_details(tmp_path):
    roots, bins = fake_sides(tmp_path)
    with pytest.raises(bg.BenchmarkGateError) as info:  # no <bin>/python: Popen cannot start the child
        bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), "bench.py::t", repeats=4, timeout_seconds=30,
                          base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH, min_base_ns=0)
    assert info.value.detail.startswith("could not start the run: ")
    for name in ("a", "b", "c", "d"):
        (tmp_path / name).mkdir()
    timeout = refusal(tmp_path / "a", "import time\ntime.sleep(30)", timeout_seconds=1)
    assert timeout.code == "BASE_TIMEOUT" and timeout.detail == "run exceeded 1 s"
    oversize = refusal(tmp_path / "b", OVERSIZE_THEN.format(after="pass"))
    assert oversize.code == "OUTPUT_TOO_LARGE" and oversize.detail == "base run wrote 1048576 bytes"
    nonzero = refusal(tmp_path / "c", 'import sys\nsys.stderr.write("boomtail")\nsys.exit(3)')
    assert nonzero.code == "BASE_NONZERO_EXIT" and re.fullmatch(r"exit 3: .*boomtail", nonzero.detail)


@posix_only
def test_oversize_beats_timeout(tmp_path):
    err = refusal(tmp_path, OVERSIZE_THEN.format(after="import time; time.sleep(30)"), timeout_seconds=1)
    assert err.code == "OUTPUT_TOO_LARGE"


@posix_only
def test_oversize_beats_nonzero_exit(tmp_path):
    err = refusal(tmp_path, OVERSIZE_THEN.format(after="sys.exit(3)"))
    assert err.code == "OUTPUT_TOO_LARGE"


@posix_only
def test_scratch_is_removed_after_spawn_failure_timeout_and_nonzero(tmp_path, monkeypatch):
    real = bg.shutil.rmtree
    removed = []

    def spy(path, *args, **kwargs):
        if re.fullmatch(r"(base|head)-\d+", os.path.basename(str(path))):
            removed.append(os.path.basename(str(path)))
        return real(path, *args, **kwargs)
    monkeypatch.setattr(bg.shutil, "rmtree", spy)
    roots, bins = fake_sides(tmp_path)
    with pytest.raises(bg.BenchmarkGateError):  # spawn failure
        bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), "bench.py::t", repeats=4, timeout_seconds=30,
                          base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH, min_base_ns=0)
    assert removed == ["base-1"]
    for name, script, overrides in (("t", "import time\ntime.sleep(30)", {"timeout_seconds": 1}), ("n", "import sys\nsys.exit(3)", {})):
        removed.clear()
        (tmp_path / name).mkdir()
        refusal(tmp_path / name, script, **overrides)
        assert removed == ["base-1"], name


@posix_only
def test_spawn_failure_cause_is_spawn_failed(tmp_path):
    roots, bins = fake_sides(tmp_path)
    with pytest.raises(bg.BenchmarkGateError) as info:
        bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), "bench.py::t", repeats=4, timeout_seconds=30,
                          base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH, min_base_ns=0)
    assert isinstance(info.value.__cause__, bg._SpawnFailed)


@posix_only
def test_a_missing_digest_fails_after_the_first_warmup_round(tmp_path):
    marker = tmp_path / "marker"
    script = f"""
        import sys
        open({str(marker)!r}, "a").write("x")
        print("no digest here")
    """
    err = refusal(tmp_path, script)
    assert err.code == "DIGEST_MISSING"
    assert marker.read_text() == "xx"  # only the first warmup round happened (both sides)


@posix_only
@pytest.mark.parametrize("line", ["BENCH_RESULT_DIGEST: " + "D" * 64, "BENCH_RESULT_DIGEST: " + "d" * 63, "BENCH_RESULT_DIGEST:" + "d" * 64,
                                  "bench_result_digest: " + "d" * 64])
def test_a_malformed_digest_line_is_a_missing_digest(tmp_path, line):
    script = f"print({line!r})"
    assert refusal(tmp_path, script).code == "DIGEST_MISSING"


@posix_only
def test_the_last_digest_in_the_output_wins_and_pytest_progress_may_share_the_line(tmp_path):
    other = "e" * 64
    script = f"""
        print("BENCH_RESULT_DIGEST: {other}")
        print(".BENCH_RESULT_DIGEST: {DIGEST}")
    """
    assert measure(tmp_path, script)["digest"] == DIGEST


@posix_only
def test_a_digest_that_varies_within_one_side_is_unstable(tmp_path):
    counter = tmp_path / "counter"
    script = f"""
        import os, sys
        path = {str(counter)!r} + sys.argv[1]
        n = int(open(path).read()) if os.path.exists(path) else 0
        open(path, "w").write(str(n + 1))
        digest = "{DIGEST}" if sys.argv[1] == "head" else ("{DIGEST}" if n < 2 else "{'0' * 64}")
        print("BENCH_RESULT_DIGEST: " + digest)
    """
    assert refusal(tmp_path, script).code == "DIGEST_UNSTABLE"


@posix_only
def test_sides_that_print_different_digests_mismatch_in_the_first_warmup_round(tmp_path):
    marker = tmp_path / "marker"
    script = f"""
        import sys
        open({str(marker)!r}, "a").write("x")
        print("BENCH_RESULT_DIGEST: " + ("{DIGEST}" if sys.argv[1] == "base" else "{'0' * 64}"))
    """
    assert refusal(tmp_path, script).code == "DIGEST_MISMATCH"
    assert marker.read_text() == "xx"


def counting_child(tmp_path, digest_expr):
    """A child that knows its side and how many times that side ran before (n), printing ``digest_expr`` (a Python expression)."""
    return f"""
        import os, sys
        path = {str(tmp_path / "count")!r} + sys.argv[1]
        n = int(open(path).read()) if os.path.exists(path) else 0
        open(path, "w").write(str(n + 1))
        side = sys.argv[1]
        value = {digest_expr}
        if value is not None:
            print("BENCH_RESULT_DIGEST: " + value)
    """


OTHER = "0" * 64


@posix_only
@pytest.mark.parametrize("silent_side", ["base", "head"])
def test_a_digest_printed_by_only_one_side_is_a_mismatch_not_a_missing_digest(tmp_path, silent_side):
    script = counting_child(tmp_path, f"None if side == {silent_side!r} else {DIGEST!r}")
    err = refusal(tmp_path, script)
    assert err.code == "DIGEST_MISMATCH" and err.phase == "warmup"


@posix_only
def test_neither_side_printing_a_digest_is_missing_after_both_ran_once(tmp_path):
    err = refusal(tmp_path, counting_child(tmp_path, "None"))
    assert err.code == "DIGEST_MISSING" and err.phase == "warmup" and err.side is None
    assert (tmp_path / "countbase").read_text() == "1" and (tmp_path / "counthead").read_text() == "1"


@posix_only
@pytest.mark.parametrize("side_name", ["base", "head"])
def test_a_digest_that_changes_in_a_timed_round_is_unstable(tmp_path, side_name):
    script = counting_child(tmp_path, f"{OTHER!r} if (side == {side_name!r} and n >= 2) else {DIGEST!r}")
    err = refusal(tmp_path, script)
    assert err.code == "DIGEST_UNSTABLE" and err.side == side_name and err.phase == "timed"


@posix_only
def test_a_digest_that_disappears_after_the_first_round_is_unstable(tmp_path):
    script = counting_child(tmp_path, f"None if (side == 'head' and n >= 1) else {DIGEST!r}")
    err = refusal(tmp_path, script)
    assert err.code == "DIGEST_UNSTABLE" and err.side == "head"


@posix_only
def test_a_digest_that_changes_between_warmup_rounds_is_unstable(tmp_path):
    script = counting_child(tmp_path, f"{OTHER!r} if (side == 'base' and n == 1) else {DIGEST!r}")
    err = refusal(tmp_path, script, warmup=2)
    assert err.code == "DIGEST_UNSTABLE" and err.phase == "warmup"


@posix_only
def test_a_digest_followed_by_more_hex_is_not_a_digest(tmp_path):
    script = f'print("BENCH_RESULT_DIGEST: {DIGEST}ff")'
    assert refusal(tmp_path, script).code == "DIGEST_MISSING"


@posix_only
def test_only_the_head_timing_out_is_a_head_timeout(tmp_path):
    script = f"""
        import sys, time
        print("BENCH_RESULT_DIGEST: {DIGEST}", flush=True)
        if sys.argv[1] == "head":
            time.sleep(30)
    """
    err = refusal(tmp_path, script, timeout_seconds=1)
    assert err.code == "HEAD_TIMEOUT" and err.side == "head" and err.phase == "warmup"


@posix_only
def test_a_missing_python_in_the_bin_directory_is_a_coded_nonzero_exit(tmp_path):
    roots, bins = fake_sides(tmp_path)
    with pytest.raises(bg.BenchmarkGateError) as info:
        bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), "bench.py::t", repeats=4, timeout_seconds=30,
                          base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH, min_base_ns=0)
    assert info.value.code == "BASE_NONZERO_EXIT" and info.value.side == "base"
    assert "could not start" in info.value.detail


@posix_only
def test_a_failure_after_timing_began_carries_the_partial_data(tmp_path):
    script = counting_child(tmp_path, f"{DIGEST!r}") + "\n        sys.exit(3 if (side == 'head' and n >= 3) else 0)\n"
    err = refusal(tmp_path, script)
    assert err.code == "HEAD_NONZERO_EXIT" and err.phase == "timed"
    assert err.partial["order"] == bg.run_order(BASE, HEAD, BENCH, 1, 4)
    assert 0 < len(err.partial["base_ns"]) < 4 and len(err.partial["head_ns"]) == len(err.partial["base_ns"])


@posix_only
def test_too_short_a_workload_names_the_measured_median_and_keeps_the_timings(tmp_path):
    err = refusal(tmp_path, OK_CHILD, min_base_ns=10 ** 12)
    assert re.search(r"base median \d+ ns is under 1000000000000 ns", err.detail)
    assert len(err.partial["base_ns"]) == len(err.partial["head_ns"]) == 4


@posix_only
def test_the_result_echoes_the_argv_of_each_side(tmp_path):
    result = measure(tmp_path, OK_CHILD)
    assert set(result["argv"]) == {"base", "head"}
    assert result["argv"]["base"][-3] == "base" and result["argv"]["head"][-3] == "head"


@posix_only
def test_the_default_argv_uses_a_caller_owned_ini_when_given(tmp_path):
    roots, bins = fake_sides(tmp_path)
    ini = tmp_path / "mine.ini"
    ini.write_text("[pytest]\n")
    for side in ("base", "head"):
        (bins[side] / "python").symlink_to(sys.executable)
    with pytest.raises(bg.BenchmarkGateError) as info:  # the child is not pytest: it fails, but the argv was built
        bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), "bench.py::t", repeats=4, timeout_seconds=30,
                          base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH, min_base_ns=0, ini_path=str(ini))
    assert info.value.code in ("BASE_NONZERO_EXIT", "DIGEST_MISSING")


@posix_only
def test_children_get_devnull_as_stdin_even_when_the_parent_has_a_pipe(tmp_path):
    script = f"""
        import os
        assert os.path.samestat(os.fstat(0), os.stat("/dev/null")), "stdin is not /dev/null"
        print("BENCH_RESULT_DIGEST: {DIGEST}")
    """
    read_end, write_end = os.pipe()
    saved = os.dup(0)
    os.dup2(read_end, 0)
    try:
        assert measure(tmp_path, script)["digest"] == DIGEST
    finally:
        os.dup2(saved, 0)
        for fd in (saved, read_end, write_end):
            os.close(fd)


@posix_only
def test_every_refusal_carries_side_phase_and_partial_attributes(tmp_path, monkeypatch):
    for index, override in enumerate(({"repeats": 5}, {"target": "-x"})):
        (tmp_path / str(index)).mkdir()
        err = refusal(tmp_path / str(index), OK_CHILD, **override)
        assert (err.side, err.phase, err.partial) == (None, None, None)
    (tmp_path / "nt").mkdir()
    monkeypatch.setattr(bg.os, "name", "nt")
    err = refusal(tmp_path / "nt", OK_CHILD)
    assert (err.side, err.phase, err.partial) == (None, None, None)


@posix_only
def test_a_harness_fault_in_a_timed_round_keeps_the_phase_and_the_finished_rounds(tmp_path, monkeypatch):
    real = bg.os.makedirs
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] > 12:  # a few runs in: the second timed round
            raise OSError(28, "No space left on device")
        return real(*args, **kwargs)
    monkeypatch.setattr(bg.os, "makedirs", flaky)
    err = refusal(tmp_path, OK_CHILD)
    assert err.code == "MEASURE_FAILED" and err.phase == "timed"
    assert set(err.partial) == {"order", "base_ns", "head_ns"} and len(err.partial["base_ns"]) >= 1


@posix_only
def test_a_failure_in_the_first_timed_round_still_carries_partial(tmp_path):
    script = counting_child(tmp_path, f"{DIGEST!r}") + "\n        sys.exit(3 if (side == 'head' and n >= 1) else 0)\n"
    err = refusal(tmp_path, script)
    assert err.phase == "timed" and err.code == "HEAD_NONZERO_EXIT"
    assert err.partial == {"order": bg.run_order(BASE, HEAD, BENCH, 1, 4), "base_ns": [], "head_ns": []}


@posix_only
def test_an_unstable_digest_in_a_timed_round_carries_partial(tmp_path):
    err = refusal(tmp_path, counting_child(tmp_path, f"{OTHER!r} if (side == 'base' and n >= 2) else {DIGEST!r}"))
    assert err.code == "DIGEST_UNSTABLE" and set(err.partial) == {"order", "base_ns", "head_ns"}


@posix_only
def test_a_warmup_failure_has_no_partial(tmp_path):
    assert refusal(tmp_path, counting_child(tmp_path, "None")).partial is None


@posix_only
def test_a_missing_digest_in_a_later_warmup_round_is_unstable(tmp_path):
    err = refusal(tmp_path, counting_child(tmp_path, f"None if (side == 'head' and n == 1) else {DIGEST!r}"), warmup=2)
    assert err.code == "DIGEST_UNSTABLE" and err.phase == "warmup"


@posix_only
def test_the_end_of_stderr_is_kept_in_the_detail(tmp_path):
    script = """
        import sys
        sys.stderr.write("x" * 3000 + "LASTLINE")
        sys.exit(1)
    """
    assert "LASTLINE" in refusal(tmp_path, script).detail


@posix_only
def test_the_file_size_limit_is_applied_to_the_child(tmp_path):
    marker = tmp_path / "limit"
    script = f"""
        import resource
        open({str(marker)!r}, "a").write(repr(resource.getrlimit(resource.RLIMIT_FSIZE)) + "\\n")
        print("BENCH_RESULT_DIGEST: {DIGEST}")
    """
    measure(tmp_path, script)
    assert set(marker.read_text().split("\n")) - {""} == {f"({1 << 20}, {1 << 20})"}


@posix_only
def test_the_pycache_prefix_is_per_side_and_shared_across_that_sides_runs(tmp_path):
    marker = tmp_path / "prefix"
    script = f"""
        import os, sys
        open({str(marker)!r}, "a").write(sys.argv[1] + " " + os.environ["PYTHONPYCACHEPREFIX"] + "\\n")
        print("BENCH_RESULT_DIGEST: {DIGEST}")
    """
    measure(tmp_path, script)
    rows = [line.split() for line in marker.read_text().splitlines()]
    by_side = {side: {prefix for s, prefix in rows if s == side} for side in ("base", "head")}
    assert len(by_side["base"]) == 1 and len(by_side["head"]) == 1 and by_side["base"] != by_side["head"]


@posix_only
def test_a_harness_fault_while_preparing_a_run_is_a_coded_measure_failure(tmp_path, monkeypatch):
    def full_disk(*args, **kwargs):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(bg.os, "makedirs", full_disk)
    err = refusal(tmp_path, OK_CHILD)
    assert err.code == "MEASURE_FAILED" and "No space" in err.detail


@posix_only
def test_a_watchdog_that_cannot_start_kills_the_child_and_is_a_coded_failure(tmp_path, monkeypatch):
    pidfile = tmp_path / "pid"
    script = f"""
        import os, time
        open({str(pidfile)!r}, "w").write(str(os.getpid()))
        time.sleep(60)
    """

    def no_thread(self):
        raise RuntimeError("can't start new thread")
    monkeypatch.setattr(bg.threading.Timer, "start", no_thread)
    err = refusal(tmp_path, script)
    assert err.code == "MEASURE_FAILED"
    pid = int(pidfile.read_text()) if pidfile.exists() else None
    deadline = time.monotonic() + 10
    while pid is not None and time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        if pid is not None:
            pytest.fail("the child survived")


@posix_only
def test_a_workload_under_the_minimum_is_too_short(tmp_path):
    assert refusal(tmp_path, OK_CHILD, min_base_ns=10 ** 12).code == "WORKLOAD_TOO_SHORT"


@posix_only
def test_the_default_minimum_is_two_seconds(tmp_path):
    roots, bins = fake_sides(tmp_path)
    with pytest.raises(bg.BenchmarkGateError) as info:
        bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), "bench.py::t", repeats=4, timeout_seconds=30,
                          base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH, argv_builder=builder(OK_CHILD))
    assert info.value.code == "WORKLOAD_TOO_SHORT"


@posix_only
def test_the_process_group_is_killed_after_every_run(tmp_path):
    pidfile = tmp_path / "pids"
    script = f"""
        import subprocess, sys
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        open({str(pidfile)!r}, "a").write(str(child.pid) + "\\n")
        print("BENCH_RESULT_DIGEST: {DIGEST}")
    """
    measure(tmp_path, script)
    deadline = time.monotonic() + 10
    for pid in map(int, pidfile.read_text().split()):
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            try:  # a zombie still answers kill(0); it is dead for our purposes
                if Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z":
                    break
            except OSError:
                pass
            time.sleep(0.05)
        else:
            pytest.fail(f"grandchild {pid} survived the run")


@posix_only
def test_stderr_tail_in_a_refusal_is_escaped(tmp_path):
    script = """
        import sys
        sys.stderr.write("# boom `rm -rf` | x\\n\\x1b[31mred\\n")
        sys.exit(1)
    """
    err = refusal(tmp_path, script)
    assert "`" not in err.detail and "\n" not in err.detail and "\x1b" not in err.detail and "|" not in err.detail


@pytest.mark.parametrize("override", [
    {"repeats": 5}, {"repeats": True}, {"warmup": 0}, {"warmup": 4}, {"warmup": True}, {"timeout_seconds": 0}, {"timeout_seconds": -1},
    {"timeout_seconds": float("nan")}, {"timeout_seconds": True}, {"timeout_seconds": "5"}, {"timeout_seconds": 3601},
    {"target": "-pfoo"}, {"target": ""}, {"target": "a\0b"}, {"ini_path": "relative.ini"}, {"ini_path": 5}, {"min_base_ns": -1}, {"min_base_ns": 1.5}, {"attempt": 3}, {"base_commit": "x"}, {"benchmark_sha256": "x"},
])
def test_bad_arguments_are_a_caller_error_before_anything_runs(tmp_path, override):
    marker = tmp_path / "marker"
    script = f"open({str(marker)!r}, 'a').write('x')"
    assert refusal(tmp_path, script, **override).code == "MEASURE_ARGS_INVALID"
    assert not marker.exists()


@posix_only
def test_roots_and_bins_must_be_distinct_existing_absolute_directories(tmp_path):
    roots, bins = fake_sides(tmp_path)
    good = [str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"])]
    common = dict(repeats=4, timeout_seconds=30, base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH, min_base_ns=0,
                  argv_builder=builder(OK_CHILD))
    bad = [
        [good[0], good[0], good[2], good[3]], [good[0], good[1], good[2], good[2]], [good[0], str(tmp_path / "missing"), good[2], good[3]],
        ["relative", good[1], good[2], good[3]], [good[0], good[1], "", good[3]], [good[0], good[1], good[2], good[3] + "\0"],
        [good[0], good[1], 5, good[3]],
    ]
    for args in bad:
        with pytest.raises(bg.BenchmarkGateError) as info:
            bg.measure_paired(*args, "t", **common)
        assert info.value.code == "MEASURE_ARGS_INVALID", args


@posix_only
def test_nested_roots_are_rejected(tmp_path):
    roots, bins = fake_sides(tmp_path)
    inner = roots["base"] / "inner"
    inner.mkdir()
    with pytest.raises(bg.BenchmarkGateError) as info:
        bg.measure_paired(str(roots["base"]), str(inner), str(bins["base"]), str(bins["head"]), "t", repeats=4, timeout_seconds=30,
                          base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH, min_base_ns=0, argv_builder=builder(OK_CHILD))
    assert info.value.code == "MEASURE_ARGS_INVALID"


GOOD_TARGETS = (("bench.py::t", "bench.py"), ("a/b/test_x.py", "a/b/test_x.py"), ("x.py::T::m", "x.py"), ("bench.py::t[a\\b]", "bench.py"))
BAD_TARGETS = (5, None, b"x.py", "", "a\0.py", "a\\b.py", "/abs/x.py", "./x.py", "a/./x.py", "../x.py", "a/../x.py", "a//x.py", "a/", "-x.py",
               "x.txt", "x.py2", "dir", "b\ud800.py::t", "b\u00e9.py", "bench.py::\ud800", "\nbench.py", "a\tb.py", "a\x7fb.py", "a\x1fb.py::t",
               "bench.py::t\0")


def test_benchmark_file_of_accepts_and_rejects_targets():
    for target, expected in GOOD_TARGETS:
        assert bg._benchmark_file_of(target) == expected
    for target in BAD_TARGETS:
        with pytest.raises(bg.BenchmarkGateError) as info:
            bg._benchmark_file_of(target)
        assert info.value.code == "MEASURE_ARGS_INVALID", target
        assert info.value.detail == "target must be a .py path under the root, without '..' or a leading '-'", target


def test_check_timeout_accepts_and_rejects_values():
    for good in (1, 0.5, 30, 3600, 3600.0):
        bg._check_timeout(good)
    for bad in (True, False, float("nan"), 0, 0.0, -1, 3601, "30", None):
        with pytest.raises(bg.BenchmarkGateError) as info:
            bg._check_timeout(bad)
        assert info.value.code == "MEASURE_ARGS_INVALID", bad


@posix_only
def test_measure_paired_rejects_bad_targets_and_timeouts(tmp_path):
    roots, bins = fake_sides(tmp_path)
    common = dict(repeats=4, timeout_seconds=30, base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH, min_base_ns=0,
                  argv_builder=builder(OK_CHILD))
    for target in BAD_TARGETS:
        with pytest.raises(bg.BenchmarkGateError) as info:
            bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), target, **common)
        assert info.value.code == "MEASURE_ARGS_INVALID", target
    for bad in (True, float("nan"), 0, 3601, "30", None):
        with pytest.raises(bg.BenchmarkGateError) as info:
            bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), "bench.py::t",
                              **{**common, "timeout_seconds": bad})
        assert info.value.code == "MEASURE_ARGS_INVALID", bad


@posix_only
def test_sides_checks_run_before_the_target_check(tmp_path):
    roots, bins = fake_sides(tmp_path)
    inner = roots["base"] / "inner"
    inner.mkdir()
    common = dict(repeats=4, timeout_seconds=30, base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH, min_base_ns=0,
                  argv_builder=builder(OK_CHILD))
    cases = (
        ((str(roots["base"]), str(roots["head"]), "", str(bins["head"])), "base bin must be an existing absolute directory"),
        (("relative", str(roots["head"]), str(bins["base"]), str(bins["head"])), "base root must be an existing absolute directory"),
        ((str(roots["base"]), str(roots["base"]), str(bins["base"]), str(bins["head"])), "the two sides must not share a root or a bin directory"),
        ((str(roots["base"]), str(inner), str(bins["base"]), str(bins["head"])), "neither root may contain the other"),
    )
    for args, message in cases:
        with pytest.raises(bg.BenchmarkGateError) as info:
            bg.measure_paired(*args, "../bad", **common)
        assert info.value.code == "MEASURE_ARGS_INVALID"
        assert info.value.detail == message, (args, info.value.detail)


@posix_only
def test_symlinked_twin_roots_are_one_root(tmp_path):
    roots, bins = fake_sides(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(roots["base"])
    with pytest.raises(bg.BenchmarkGateError) as info:
        bg.measure_paired(str(roots["base"]), str(alias), str(bins["base"]), str(bins["head"]), "t", repeats=4, timeout_seconds=30,
                          base_commit=BASE, head_commit=HEAD, benchmark_sha256=BENCH, min_base_ns=0, argv_builder=builder(OK_CHILD))
    assert info.value.code == "MEASURE_ARGS_INVALID"


def test_a_non_posix_platform_is_unsupported(tmp_path, monkeypatch):
    monkeypatch.setattr(bg.os, "name", "nt")
    assert refusal(tmp_path, OK_CHILD).code == "UNSUPPORTED_PLATFORM"


def test_the_codes_are_in_the_error_vocabulary():
    for code in bg.MEASURE_REFUSAL_CODES + ("MEASURE_ARGS_INVALID",):
        assert code in bg.ERROR_CODES
        assert re.fullmatch(r"[A-Z_]+", code)


# --- one real pytest run --------------------------------------------------------------------------------------------------

BENCH_SOURCE = """
import hashlib


def test_bench():
    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(b"x").hexdigest())
"""


def pytest_venv(path: Path) -> Path:
    """A real, pip-less venv whose ``.pth`` makes the running interpreter's pytest importable, whichever site directory it lives in."""
    import venv

    venv.create(path, with_pip=False, symlinks=True)
    sites = {os.path.dirname(os.path.dirname(sys.modules[name].__file__)) for name in ("pytest", "_pytest", "pluggy", "iniconfig", "packaging")
             if name in sys.modules}
    site = next((path / "lib").glob("python3*/site-packages"))
    (site / "zz_pytest.pth").write_text("\n".join(sorted(sites)) + "\n")
    return path / "bin"


@posix_only
def test_real_pytest_prints_the_digest_with_dash_s_and_a_head_added_hashlib_does_not_shadow(tmp_path):
    roots, _ = fake_sides(tmp_path)
    bins = {side: pytest_venv(tmp_path / f"{side}-real-venv") for side in ("base", "head")}
    for side in ("base", "head"):
        (roots[side] / "test_bench.py").write_text(BENCH_SOURCE)
    (roots["head"] / "hashlib.py").write_text("raise RuntimeError('shadowed')\n")
    (roots["head"] / "conftest.py").write_text("raise RuntimeError('conftest loaded')\n")
    result = bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]),
                               "test_bench.py::test_bench", repeats=4, timeout_seconds=120, base_commit=BASE, head_commit=HEAD,
                               benchmark_sha256=BENCH, min_base_ns=0)
    assert len(result["digest"]) == 64
    assert len(result["base_ns"]) == 4
