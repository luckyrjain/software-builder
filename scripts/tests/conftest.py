"""Shared fixtures for scripts/tests/.

Most of this suite's tests read the real repository's live registry/manifest state directly
from ROOT (``parse_registry(ROOT / "skills.yaml")``, ``load_canonical_manifest(ROOT)``, and
friends) by design -- an isolated tmp_path fixture would need to mirror the entire skill tree
(every registered skill's SKILL.md/reference files, every declared host) for checks like
``validate_canonical_manifest`` to mean anything, which is far more than most of these tests
need. One test (test_platform_manifest.py's
``test_validate_manifest_reports_new_fragment_missing_from_composition_contracts_cleanly``)
exploits that same real-tree requirement in the other direction: it briefly writes a throwaway
skill fragment onto the *real* repository root to exercise a real-tree code path, and removes it
in a ``finally``. Under pytest-xdist's parallel workers, a reader on another worker can observe
that fragment mid-window -- seen in CI as a stray ``orphan-test-skill`` entry leaking into a
sibling test's expected skill list.

Rather than harden every one of those ~40 call sites against a transient extra registry entry,
route every test through one shared/exclusive file lock: a test marked
``@pytest.mark.mutates_repository_root`` holds it exclusively for its whole run (so nothing else
in the suite can be mid-test while the real tree is mutated); every other test holds it
non-exclusively (readers never block each other, only the one mutator). The lock file lives
outside the repository so it never needs a .gitignore entry or shows up in `git status`.
"""

from __future__ import annotations

import fcntl
import tempfile
from pathlib import Path

import pytest

_LOCK_PATH = Path(tempfile.gettempdir()) / "software-builder-pytest-registry-root.lock"


@pytest.fixture(autouse=True)
def _serialize_against_repository_root_mutation(request: pytest.FixtureRequest):
    exclusive = request.node.get_closest_marker("mutates_repository_root") is not None
    _LOCK_PATH.touch(exist_ok=True)
    with open(_LOCK_PATH) as handle:
        fcntl.flock(handle, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
