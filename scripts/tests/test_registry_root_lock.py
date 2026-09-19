"""Both pytest suites must serialize on the same lock file (see registry_root_lock.py)."""

from __future__ import annotations

from pathlib import Path

from scripts.tests.registry_root_lock import LOCK_PATH, ROOT

_CONFTESTS = [ROOT / "scripts" / "tests" / "conftest.py", ROOT / "cli" / "tests" / "conftest.py"]


def test_both_conftests_take_the_lock_path_from_the_shared_module() -> None:
    for conftest in _CONFTESTS:
        source = conftest.read_text(encoding="utf-8")
        assert "from scripts.tests.registry_root_lock import LOCK_PATH" in source, conftest
        assert "software-builder-pytest-registry-root" not in source, f"{conftest} hardcodes its own lock name"


def test_the_lock_path_is_keyed_on_this_checkout() -> None:
    assert LOCK_PATH.name.startswith("software-builder-pytest-registry-root-")
    assert LOCK_PATH.name.endswith(".lock")
    assert LOCK_PATH.parent == Path(LOCK_PATH.parent)  # under the system temp dir, not the repo
    assert ROOT not in LOCK_PATH.parents
