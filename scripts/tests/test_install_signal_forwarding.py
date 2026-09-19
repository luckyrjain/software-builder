"""install.sh must forward a signal aimed at *its own* PID to the install engine child.

`kill <install.sh pid>` is the usual way a supervisor stops it. With the engine run as a plain
foreground child, bash died immediately and the engine was orphaned to init: it kept running,
holding the lock and a staging directory, with nothing left to roll it back if it was later
killed hard. The engine's own SIGTERM cleanup (test_install_engine_install.py) only helps if the
signal actually reaches it -- these tests send it to the bash process only, not the process
group, which is the case a group-signalling test can't distinguish.
"""

from __future__ import annotations

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


def _start_slow_install(tmp_path: Path) -> tuple[subprocess.Popen[str], Path]:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "python3"
    fake.write_text(_FAKE_PYTHON.format(real=sys.executable), encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    proc = subprocess.Popen(
        ["bash", str(INSTALLER), "--agent", "cursor", SKILL],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc, home / ".cursor" / "skills"


def _wait_until_staging(skills_dir: Path, proc: subprocess.Popen[str], timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if list(skills_dir.glob(f".{SKILL}.staging.*")):
            return
        if proc.poll() is not None:
            pytest.fail(f"install.sh exited before staging began: {proc.communicate()}")
        time.sleep(0.05)
    proc.kill()
    pytest.fail("install never reached staging")


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT], ids=["SIGTERM", "SIGINT"])
def test_signal_to_install_sh_alone_reaches_the_engine_and_rolls_back(
    tmp_path: Path, sig: signal.Signals
) -> None:
    proc, skills_dir = _start_slow_install(tmp_path)
    try:
        _wait_until_staging(skills_dir, proc)
        os.kill(proc.pid, sig)  # bash's PID only -- not the process group
        stdout, stderr = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()

    assert proc.returncode == 130, (stdout, stderr)
    # Long enough for an orphaned engine (the old behavior) to have finished the 4s-slow install.
    time.sleep(5)
    assert not (skills_dir / SKILL).exists(), "an orphaned engine completed the install"
    assert list(skills_dir.glob(f".{SKILL}.*")) == [], "staging/backup/lock directories left behind"
