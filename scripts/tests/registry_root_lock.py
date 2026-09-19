"""The one lock-file path both pytest suites use to serialize against snapshot rebuilds.

scripts/tests/ and cli/tests/ run as separate processes (under `make -j lint-suites`), and some
scripts/tests rebuild cli/sb/_vendored and cli/sb/_registry_snapshot, which cli/tests read. Each
suite's conftest.py takes an flock on this path -- so it must be one definition, not two
literals that can drift apart.

The path is keyed on this checkout: suites run from different worktrees (or another session's
copy) mutate different roots and have nothing to serialize against each other, and sharing one
machine-wide name made an unrelated run's exclusive lock hang them.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_ROOT_KEY = hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]
LOCK_PATH = Path(tempfile.gettempdir()) / f"software-builder-pytest-registry-root-{_ROOT_KEY}.lock"
