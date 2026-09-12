"""Shared fixtures for cli/tests/.

Every test here shells out to `python -m sb ...`, which needs cli/sb/_vendored/ and
cli/sb/_registry_snapshot/ to already exist on disk (see scripts/build_sb_snapshot.py). Build
them once per session before any test runs, so this suite passes from a fresh clone instead of
depending on scripts/tests/test_build_sb_snapshot.py having already populated them earlier.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_sb_snapshot import build_snapshot  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _build_snapshot() -> None:
    build_snapshot(ROOT)
