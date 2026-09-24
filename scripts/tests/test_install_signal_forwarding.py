"""install.sh must forward a signal aimed at *its own* PID to the install engine child.

`kill <install.sh pid>` is the usual way a supervisor stops it. With the engine run as a plain
foreground child, bash died immediately and the engine was orphaned to init: it kept running,
holding the lock and a staging directory, with nothing left to roll it back if it was later
killed hard. The engine's own SIGTERM cleanup (test_install_engine_install.py) only helps if the
signal actually reaches it -- these tests send it to the bash process only, not the process
group, which is the case a group-signalling test can't distinguish.
"""

from __future__ import annotations

import contextlib
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="install.sh is POSIX-only")

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts" / "install.sh"
SKILL = "pr-review"

# A stand-in `python3` that slows only the install engine's packaging step, so the signal lands
# while an install is genuinely in flight. Every other python3 call install.sh makes passes
# straight through.
_FAKE_PYTHON = """#!/usr/bin/env bash
if [[ "$1" == *install_engine.py ]]; then
  shift
  exec "{real}" -c '
import sys, time
import scripts.install_engine as engine
real_package_skill = engine.package_skill
def slow_package_skill(**kwargs):
    time.sleep(4)
    return real_package_skill(**kwargs)
engine.package_skill = slow_package_skill
sys.exit(engine.main(sys.argv[1:]))
' "$@"
fi
exec "{real}" "$@"
"""


def _spawn(cmd: list[str], env: dict[str, str]) -> subprocess.Popen[str]:
    """install.sh in its own session, so the fake engines it spawns can be reaped by group.

    SIGINT is reset to its default: a runner that ignores it (nohup, a backgrounded job) would
    otherwise pass that on, and bash cannot trap a signal it inherited as ignored."""
    return subprocess.Popen(
        cmd,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL),
    )


def _reap(proc: subprocess.Popen[str]) -> None:
    """Kill the whole group: killing only bash leaves a fake engine's `sleep` loop running."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)
    proc.wait(timeout=10)


def _start_slow_install(tmp_path: Path) -> tuple[subprocess.Popen[str], Path]:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "python3"
    fake.write_text(_FAKE_PYTHON.format(real=sys.executable), encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    proc = _spawn(["bash", str(INSTALLER), "--agent", "cursor", SKILL], env)
    return proc, home / ".cursor" / "skills"


def _wait_until_staging(skills_dir: Path, proc: subprocess.Popen[str], timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if list(skills_dir.glob(f".{SKILL}.staging.*")):
            return
        if proc.poll() is not None:
            pytest.fail(f"install.sh exited before staging began: {proc.communicate()}")
        time.sleep(0.05)
    _reap(proc)
    pytest.fail("install never reached staging")


@pytest.mark.parametrize(
    "sig", [signal.SIGTERM, signal.SIGINT, signal.SIGHUP], ids=["SIGTERM", "SIGINT", "SIGHUP"]
)
def test_signal_to_install_sh_alone_reaches_the_engine_and_rolls_back(
    tmp_path: Path, sig: signal.Signals
) -> None:
    proc, skills_dir = _start_slow_install(tmp_path)
    try:
        _wait_until_staging(skills_dir, proc)
        os.kill(proc.pid, sig)  # bash's PID only -- not the process group
        stdout, stderr = proc.communicate(timeout=30)
    finally:
        _reap(proc)

    assert proc.returncode == 130, (stdout, stderr)
    # Long enough for an orphaned engine (the old behavior) to have finished the 4s-slow install.
    time.sleep(6)
    assert not (skills_dir / SKILL).exists(), "an orphaned engine completed the install"
    assert list(skills_dir.glob(f".{SKILL}.*")) == [], "staging/backup/lock directories left behind"


# An engine that finishes cleanly (exit 0) as the stop request lands: the run must still stop, and
# must report 130 -- not the 143 of the interrupted `wait`, and not carry on to the next skill.
_FAKE_PYTHON_EXITS_0_ON_TERM = """#!/usr/bin/env bash
if [[ "$1" == *install_engine.py ]]; then
  echo "$@" >> "{log}"
  trap 'exit 0' TERM
  while :; do sleep 0.05; done
fi
exec "{real}" "$@"
"""


def test_a_stop_request_ends_a_multi_skill_run_even_if_the_engine_exits_cleanly_first(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "engine.log"
    fake = bin_dir / "python3"
    fake.write_text(_FAKE_PYTHON_EXITS_0_ON_TERM.format(real=sys.executable, log=log), encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    proc = _spawn(["bash", str(INSTALLER), "--agent", "cursor", SKILL, "api-design-review"], env)
    try:
        deadline = time.monotonic() + 30
        while not log.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert log.exists(), "engine was never started"
        os.kill(proc.pid, signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=30)
    finally:
        _reap(proc)

    assert proc.returncode == 130, (stdout, stderr)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1, "the next skill was started after the stop"


# An engine killed by the forwarded TERM before it could install its own handler dies with 143.
# That is still a stop request, not an ordinary failure: reading it as one made install_skill
# `return 1` and the loop carry on installing the remaining skills.
_FAKE_PYTHON_DIES_ON_TERM = """#!/usr/bin/env bash
if [[ "$1" == *install_engine.py ]]; then
  echo "$@" >> "{log}"
  exec sleep 30
fi
exec "{real}" "$@"
"""


def test_an_engine_killed_by_the_forwarded_term_still_ends_a_multi_skill_run(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "engine.log"
    fake = bin_dir / "python3"
    fake.write_text(_FAKE_PYTHON_DIES_ON_TERM.format(real=sys.executable, log=log), encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    proc = _spawn(["bash", str(INSTALLER), "--agent", "cursor", SKILL, "api-design-review"], env)
    try:
        deadline = time.monotonic() + 30
        while not log.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert log.exists(), "engine was never started"
        os.kill(proc.pid, signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=30)
    finally:
        _reap(proc)

    assert proc.returncode == 130, (stdout, stderr)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1, "the next skill was started after the stop"


# Records that the install engine was started, and otherwise behaves as the real python3.
_FAKE_PYTHON_ENGINE_LOGS_ONLY = """#!/usr/bin/env bash
if [[ "$1" == *install_engine.py ]]; then
  echo "$@" >> "{log}"
fi
exec "{real}" "$@"
"""


def test_an_empty_skill_name_and_a_missing_option_value_are_usage_errors(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "engine.log"
    fake = bin_dir / "python3"
    fake.write_text(_FAKE_PYTHON_ENGINE_LOGS_ONLY.format(real=sys.executable, log=log), encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "HOME": str(tmp_path), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    empty = subprocess.run(
        ["bash", str(INSTALLER), "--agent", "cursor", "--uninstall", ""],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    assert empty.returncode == 1
    assert "invalid skill name ''" in empty.stderr
    assert not log.exists(), "install.sh's own name check must reject an empty name before the engine runs"

    missing = subprocess.run(
        ["bash", str(INSTALLER), "--agent"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    assert missing.returncode == 2
    assert "--agent requires a value" in missing.stderr
    assert "unbound variable" not in missing.stderr


# A stop request that lands while bash is between engine runs -- in a read-only python3 probe for
# the next skill -- must still end the run with 130 and not start that skill.
_FAKE_PYTHON_SLOW_PROBES = """#!/usr/bin/env bash
if [[ "$1" == *install_engine.py ]]; then
  echo "$@" >> "{log}"
  exit 0
fi
if [[ -e "{log}" ]]; then sleep 1; fi
exec "{real}" "$@"
"""


def test_a_stop_request_between_skills_exits_130_without_starting_the_next_skill(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "engine.log"
    fake = bin_dir / "python3"
    fake.write_text(_FAKE_PYTHON_SLOW_PROBES.format(real=sys.executable, log=log), encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    proc = _spawn(["bash", str(INSTALLER), "--agent", "cursor", SKILL, "api-design-review"], env)
    try:
        deadline = time.monotonic() + 30
        while not log.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert log.exists(), "engine was never started"
        time.sleep(0.3)  # the probes after the first engine run now sleep 1s each
        os.kill(proc.pid, signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=30)
    finally:
        _reap(proc)

    assert proc.returncode == 130, (stdout, stderr)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1, "the next skill was started after the stop"


# `--uninstall` goes through a different install.sh function than install, and nothing above
# signalled it: it must forward a stop to the engine and stop the run just the same.
_FAKE_PYTHON_ENGINE_EXITS_130_ON_TERM = """#!/usr/bin/env bash
if [[ "$1" == *install_engine.py ]]; then
  echo "$@" >> "{log}"
  trap 'exit 130' TERM
  while :; do sleep 0.05; done
fi
exec "{real}" "$@"
"""


def test_a_stop_request_during_uninstall_reaches_the_engine_and_ends_the_run(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "engine.log"
    fake = bin_dir / "python3"
    fake.write_text(_FAKE_PYTHON_ENGINE_EXITS_130_ON_TERM.format(real=sys.executable, log=log), encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    proc = _spawn(
        ["bash", str(INSTALLER), "--agent", "cursor", "--uninstall", SKILL, "api-design-review"], env
    )
    try:
        deadline = time.monotonic() + 30
        while not log.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert log.exists(), "the uninstall engine was never started"
        os.kill(proc.pid, signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=30)
    finally:
        _reap(proc)

    assert proc.returncode == 130, (stdout, stderr)
    invocations = log.read_text(encoding="utf-8").splitlines()
    assert len(invocations) == 1, "the next skill was uninstalled after the stop"
    assert " uninstall " in invocations[0]


def test_run_engine_installs_its_signal_trap_before_it_launches_the_engine() -> None:
    """A signal in the gap between launching the engine and trapping would kill bash and orphan
    the engine. That window is microseconds wide, so no behavioural test can hit it on demand;
    the ordering itself is the invariant, so it is asserted directly."""
    body = INSTALLER.read_text(encoding="utf-8").split("run_engine() {", 1)[1].split("\n}\n", 1)[0]
    launch = body.index('python3 "$@" &')
    first_trap = body.index("trap '")
    assert first_trap < launch


# A stop that lands before the first engine has ever run (in a read-only probe) still exits 130
# via the script-level trap, and no engine is started.
_FAKE_PYTHON_ALL_CALLS_SLOW = """#!/usr/bin/env bash
if [[ "$1" == *install_engine.py ]]; then
  echo "$@" >> "{log}"
  exit 0
fi
echo started >> "{probe_log}"
sleep 1
exec "{real}" "$@"
"""


def test_a_stop_request_during_the_first_probe_exits_130_and_starts_no_engine(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "engine.log"
    probe_log = tmp_path / "probe.log"
    fake = bin_dir / "python3"
    fake.write_text(
        _FAKE_PYTHON_ALL_CALLS_SLOW.format(real=sys.executable, log=log, probe_log=probe_log), encoding="utf-8"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    proc = _spawn(["bash", str(INSTALLER), "--agent", "cursor", SKILL], env)
    try:
        deadline = time.monotonic() + 30
        while not probe_log.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert probe_log.exists(), "install.sh never reached its first python3 probe"
        os.kill(proc.pid, signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=30)
    finally:
        _reap(proc)

    assert proc.returncode == 130, (stdout, stderr)
    assert not log.exists(), "an engine was started after the stop"


# The engine takes a moment to clean up after the forwarded TERM. install.sh must still be waiting
# when it finishes: returning as soon as the trapped signal interrupts `wait` would leave the
# cleanup running unsupervised, orphaned, after the run reported it had stopped.
_FAKE_PYTHON_SLOW_CLEANUP_ON_TERM = """#!/usr/bin/env bash
if [[ "$1" == *install_engine.py ]]; then
  echo "$@" >> "{log}"
  # Drop the inherited pipes: otherwise `communicate()` cannot return until this engine exits,
  # which would hide whether install.sh itself waited for it.
  exec >/dev/null 2>&1
  trap 'sleep 1; echo cleaned > "{done}"; exit 130' TERM
  while :; do sleep 0.05; done
fi
exec "{real}" "$@"
"""


def test_install_sh_waits_for_the_engine_to_finish_cleaning_up_before_it_exits(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "engine.log"
    done = tmp_path / "cleanup.done"
    fake = bin_dir / "python3"
    fake.write_text(
        _FAKE_PYTHON_SLOW_CLEANUP_ON_TERM.format(real=sys.executable, log=log, done=done), encoding="utf-8"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    proc = _spawn(["bash", str(INSTALLER), "--agent", "cursor", SKILL], env)
    try:
        deadline = time.monotonic() + 30
        while not log.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert log.exists(), "engine was never started"
        os.kill(proc.pid, signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=30)
        cleanup_finished_before_exit = done.exists()
    finally:
        _reap(proc)

    assert proc.returncode == 130, (stdout, stderr)
    assert cleanup_finished_before_exit, "install.sh exited while the engine was still cleaning up"


# install.sh cannot trap its own SIGKILL, so the engine it starts has to notice the death of its
# parent itself -- but only when install.sh asked it to (a user backgrounding the engine directly
# has not).
_FAKE_PYTHON_RECORDS_PARENT_WATCH_ENV = """#!/usr/bin/env bash
if [[ "$1" == *install_engine.py ]]; then
  echo "${{INSTALL_ENGINE_EXIT_WITH_PARENT:-unset}}" >> "{log}"
  exit 0
fi
exec "{real}" "$@"
"""


def test_install_sh_asks_the_engine_to_exit_with_its_parent(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "engine.env"
    fake = bin_dir / "python3"
    fake.write_text(_FAKE_PYTHON_RECORDS_PARENT_WATCH_ENV.format(real=sys.executable, log=log), encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    env.pop("INSTALL_ENGINE_EXIT_WITH_PARENT", None)
    proc = _spawn(["bash", str(INSTALLER), "--agent", "cursor", SKILL], env)
    try:
        proc.communicate(timeout=60)
    finally:
        _reap(proc)

    # install.sh's own pid ($$), not a placeholder: a kill landing while the engine is still
    # starting up needs the expected parent known up front, not read late from os.getppid().
    assert log.read_text(encoding="utf-8").split() == [str(proc.pid)]
