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


def test_run_batch_reports_an_interrupted_batch_and_exits_130(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A Ctrl-C between or during skills used to surface as a raw traceback with no summary;
    the engine has already rolled back the interrupted skill, so the batch just needs to say
    what finished and stop."""
    calls: list[str] = []

    def operation(skill_id: str, dest_root: Path, host_label: str) -> _FakeOutcome:
        calls.append(skill_id)
        if skill_id == "b":
            raise KeyboardInterrupt
        return _FakeOutcome(skill_id, dest_root, "installed", f"Installed {skill_id}")

    code = sb_main._run_batch(
        ["a", "b", "c"],
        [(Path("/dest"), "cursor")],
        operation,
        dry_run=False,
        verb="install",
        past_tense="installed",
        success_status="installed",
    )

    assert code == 130
    assert calls == ["a", "b"]  # "c" never started
    assert "interrupted: 1 completed, 0 failed" in capsys.readouterr().err


def test_run_batch_turns_a_terminate_signal_between_skills_into_exit_130(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import os
    import signal
    import sys
    import time

    if sys.platform == "win32":
        pytest.skip("POSIX signal semantics")
    previous = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(AssertionError("unconverted SIGTERM")))
    try:
        def operation(skill_id: str, dest_root: Path, host_label: str) -> _FakeOutcome:
            if skill_id == "a":
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(0.2)
            return _FakeOutcome(skill_id, dest_root, "installed", f"Installed {skill_id}")

        code = sb_main._run_batch(
            ["a", "b"],
            [(Path("/dest"), "cursor")],
            operation,
            dry_run=False,
            verb="install",
            past_tense="installed",
            success_status="installed",
        )
    finally:
        signal.signal(signal.SIGTERM, previous)
    assert code == 130
    assert "interrupted:" in capsys.readouterr().err


def test_run_batch_summary_counts_skills_that_were_not_installed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def operation(skill_id: str, dest_root: Path, host_label: str) -> _FakeOutcome:
        status = "absent" if skill_id == "b" else "uninstalled"
        return _FakeOutcome(skill_id, dest_root, status, f"{status} {skill_id}")

    code = sb_main._run_batch(
        ["a", "b", "c"],
        [(Path("/dest"), "cursor")],
        operation,
        dry_run=False,
        verb="uninstall",
        past_tense="uninstalled",
        success_status="uninstalled",
        extra_ok_statuses=frozenset({"absent"}),
    )

    assert code == 0
    assert "uninstalled: 2, failed: 0, not installed: 1" in capsys.readouterr().err
