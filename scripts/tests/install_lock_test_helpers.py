"""Shared helper for tests that need a real OS-level lock held by another process -- the flock
rewrite means there is no lock-file *content* a test can fake to simulate "held": the only way to
make `held_lock()` actually wait is to have a real process genuinely hold the OS's own lock."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_HOLD_LOCK_CODE = """
import sys, time
from pathlib import Path
sys.path.insert(0, {root!r})
from scripts.install_engine import _open_lock_file, _try_lock, _write_holder_pid

fd = _open_lock_file(Path({lock_path!r}))
while not _try_lock(fd):
    time.sleep(0.01)
_write_holder_pid(fd)
print("locked", flush=True)
time.sleep({duration})
"""


def spawn_lock_holder(lock_path: Path, duration: float = 60.0) -> subprocess.Popen[str]:
    """Start a subprocess that acquires the real OS lock at `lock_path` and holds it for
    `duration` seconds (or until killed). Blocks until the subprocess reports it has actually
    acquired the lock, so the caller's own attempt never races this one still starting up."""
    code = _HOLD_LOCK_CODE.format(root=str(ROOT), lock_path=str(lock_path), duration=duration)
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    line = proc.stdout.readline()
    assert line.strip() == "locked", f"lock holder failed to start: {line!r}"
    return proc
