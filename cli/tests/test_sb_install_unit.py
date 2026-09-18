"""In-process unit tests for cli/sb/__main__.py's _cmd_install/_cmd_uninstall status tallying
-- everything else in this directory shells out to a real `python -m sb` subprocess, which
can never produce an outcome.status the real install_skill()/uninstall_skill() wouldn't. These
tests monkeypatch install_skill()/uninstall_skill() directly to exercise the fail-loud
AssertionError branch, which no subprocess-level test can reach."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pytest

import sb.__main__ as sb_main


# _cmd_install/_cmd_uninstall only ever read .status/.message (plus .dest, but only on the
# "installed" branch neither test below reaches) -- a minimal stand-in avoids the ambiguity of
# importing InstallOutcome/UninstallOutcome from whichever of the two `scripts.install_engine`
# modules (root checkout vs. cli/sb/_vendored/) happens to already be in sys.modules.
@dataclass(frozen=True)
class _FakeOutcome:
    skill_id: str
    dest: Path
    status: str
    message: str


def _fake_destinations(dest_root: Path) -> tuple[object, list[tuple[Path, str]]]:
    return object(), [(dest_root, "cursor")]


def test_cmd_install_raises_on_an_unrecognized_outcome_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sb_main, "_resolve_destinations", lambda *_a, **_kw: _fake_destinations(tmp_path))
    monkeypatch.setattr(
        sb_main,
        "install_skill",
        lambda *_a, **_kw: _FakeOutcome("demo", tmp_path / "demo", "something_new", "?"),
    )
    args = argparse.Namespace(skill_ids=["demo"], host="cursor", target_dir=None, dry_run=False)

    with pytest.raises(AssertionError, match="unhandled install outcome status"):
        sb_main._cmd_install(args)


def test_cmd_uninstall_raises_on_an_unrecognized_outcome_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sb_main, "_resolve_destinations", lambda *_a, **_kw: _fake_destinations(tmp_path))
    monkeypatch.setattr(
        sb_main,
        "uninstall_skill",
        lambda *_a, **_kw: _FakeOutcome("demo", tmp_path / "demo", "something_new", "?"),
    )
    args = argparse.Namespace(skill_ids=["demo"], host="cursor", target_dir=None, dry_run=False)

    with pytest.raises(AssertionError, match="unhandled uninstall outcome status"):
        sb_main._cmd_uninstall(args)


def test_cmd_uninstall_does_not_raise_on_the_absent_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """"absent" is a valid, intentionally-untallied status (a no-op uninstall) -- must not
    trip the same fail-loud branch that catches a genuinely unrecognized status."""
    monkeypatch.setattr(sb_main, "_resolve_destinations", lambda *_a, **_kw: _fake_destinations(tmp_path))
    monkeypatch.setattr(
        sb_main,
        "uninstall_skill",
        lambda *_a, **_kw: _FakeOutcome("demo", tmp_path / "demo", "absent", "not installed"),
    )
    args = argparse.Namespace(skill_ids=["demo"], host="cursor", target_dir=None, dry_run=False)

    assert sb_main._cmd_uninstall(args) == 0
