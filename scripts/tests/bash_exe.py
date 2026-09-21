"""Which `bash` the install.sh tests launch.

On a Windows runner `subprocess` searches C:\\Windows\\System32 before PATH, so a bare "bash"
resolves to the WSL launcher (which prints a UTF-16 "no installed distributions" message and
exits 1) rather than the Git Bash that `shell: bash` steps use. Resolve Git Bash explicitly
there; everywhere else the bare name is right.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _find() -> str:
    if sys.platform != "win32":
        return "bash"
    for root in filter(None, (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), r"C:\Program Files")):
        candidate = Path(root) / "Git" / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    return shutil.which("bash") or "bash"


BASH = _find()
