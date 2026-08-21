"""Windows path-boundary regressions for the test-creator write guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import test_creator_write_guard as guard


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def test_windows_alternate_data_stream_component_is_unsafe() -> None:
    assert guard._windows_path_component_is_unsafe("tracked.py:hidden")
    assert guard._windows_path_component_is_unsafe("tracked.py::$DATA")
    assert not guard._windows_path_component_is_unsafe("tracked.py")


def test_planned_path_uses_windows_component_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr(
        guard,
        "_windows_path_component_is_unsafe",
        lambda part: ":" in part,
    )
    monkeypatch.setattr(guard.os, "name", "nt")

    normalised, error = guard._normalise_planned_paths(repo, ["tracked.py:hidden"])

    assert normalised == ()
    assert error is not None
    assert "Windows alternate data stream" in error
