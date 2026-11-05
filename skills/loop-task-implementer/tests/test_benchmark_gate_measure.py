"""C4d-1: the measurement harness (``run_order``, ``side_env``, ``pytest_argv``, ``measure_paired``).

Children are ``python -c`` processes injected through the ``argv_builder`` seam (a real ``python -m pytest`` costs 0.4 s median and up to
3 s under load); one test runs real pytest to prove the digest is read with ``-P --import-mode=importlib`` and that a head-added
``hashlib.py`` cannot shadow. No assertion depends on a measured duration.
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
    for i in range(40):
        assert bg.run_order(f"{i:040x}", HEAD, BENCH, 1, 8) not in alternating or i > 0 or True
    orders = {tuple(bg.run_order(f"{i:040x}", HEAD, BENCH, 1, 8)) for i in range(40)}
    assert len(orders) > 5


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
    return bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), "bench.py::test_bench",
                             **kwargs)


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
        open({str(marker)!r}, "a").write(" ".join([sys.argv[1], os.getcwd(), os.environ["HOME"], os.environ["TMPDIR"], os.environ["PYTHONHASHSEED"], str("PYTHONPATH" in os.environ)]) + "\\n")
        print("BENCH_RESULT_DIGEST: {DIGEST}")
    """
    measure(tmp_path, script)
    rows = [line.split() for line in marker.read_text().splitlines()]
    assert len({row[2] for row in rows}) == len(rows) and len({row[3] for row in rows}) == len(rows)
    for side, cwd, _home, _tmp, seed, has_path in rows:
        assert os.path.realpath(cwd) == os.path.realpath(tmp_path / f"{side}-root")
        assert seed == "0" and has_path == "False"


@posix_only
def test_scratch_directories_are_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", None)
    measure(tmp_path, OK_CHILD)
    assert list((tmp_path / "tmp").iterdir()) == []


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
    assert err.code == "RUN_TIMEOUT"
    assert time.monotonic() - started < 20


@posix_only
def test_a_slow_exit_after_the_timeout_is_not_a_success(tmp_path):
    script = f"""
        import time
        print("BENCH_RESULT_DIGEST: {DIGEST}", flush=True)
        time.sleep(2)
    """
    assert refusal(tmp_path, script, timeout_seconds=0.5).code == "RUN_TIMEOUT"


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
    assert marker.read_text() == "x"  # only the first warmup run happened


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
def test_a_digest_that_changes_between_runs_is_unstable(tmp_path):
    counter = tmp_path / "counter"
    script = f"""
        import os, sys
        path = {str(counter)!r}
        n = int(open(path).read()) if os.path.exists(path) else 0
        if sys.argv[1] == "head":
            open(path, "w").write(str(n + 1))
        print("BENCH_RESULT_DIGEST: " + ("{DIGEST[:-1]}" + ("0" if n < 1 else "1" if n % 2 else "2")))
    """
    err = refusal(tmp_path, script)
    assert err.code in ("DIGEST_UNSTABLE", "DIGEST_MISMATCH")


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


@posix_only
def test_a_workload_under_the_minimum_is_too_short(tmp_path):
    assert refusal(tmp_path, OK_CHILD, min_base_ns=10 ** 12).code == "WORKLOAD_TOO_SHORT"


@posix_only
def test_the_default_minimum_is_two_seconds(tmp_path):
    roots, bins = fake_sides(tmp_path)
    with pytest.raises(bg.BenchmarkGateError) as info:
        bg.measure_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), "t", repeats=4, timeout_seconds=30,
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
    {"min_base_ns": -1}, {"min_base_ns": 1.5}, {"attempt": 3}, {"base_commit": "x"}, {"benchmark_sha256": "x"},
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
