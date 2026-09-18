"""Tests for scripts/install_engine.py's CLI layer -- _cli_install/_cli_uninstall,
_lock_timing_from_env/_env_float, main()'s catch-all, and _sigterm_as_system_exit's signal
registration/delivery/restoration. install_skill()/uninstall_skill()'s own behavior is
covered by test_install_engine_install.py/test_install_engine_uninstall.py; this file is
about the thin CLI wrapper around them."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from scripts import install_engine
from scripts.install_engine import (
    DEFAULT_LOCK_STALE_SECONDS,
    DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS,
    InstallOutcome,
    UninstallOutcome,
    _cli_install,
    _cli_uninstall,
    _env_float,
    _lock_timing_from_env,
    main,
)


def test_env_float_falls_back_to_default_when_unset() -> None:
    assert _env_float("NOT_SET_ANYWHERE", 30.0) == 30.0


def test_env_float_falls_back_to_default_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """bash's ${VAR:-default} treats an empty value the same as unset -- Python's
    os.environ.get(name, default) does not, so this must be handled explicitly."""
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_SECONDS", "")
    assert _env_float("LOCK_WAIT_TIMEOUT_SECONDS", 30.0) == 30.0


def test_env_float_parses_a_real_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_SECONDS", "7.5")
    assert _env_float("LOCK_WAIT_TIMEOUT_SECONDS", 30.0) == 7.5


def test_env_float_raises_on_a_non_empty_non_numeric_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unlike the empty-string case, a genuinely garbled value (not unset, not empty) is not
    silently defaulted -- bash's own `((age > LOCK_STALE_SECONDS))` would fail on it too, just
    with a different error shape. This is only indirectly covered by the main()-level
    catch-all test below; this asserts _env_float's own behavior directly."""
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_SECONDS", "not-a-number")
    with pytest.raises(ValueError):
        _env_float("LOCK_WAIT_TIMEOUT_SECONDS", 30.0)


def test_lock_timing_from_env_uses_defaults_when_both_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOCK_WAIT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LOCK_STALE_SECONDS", raising=False)
    assert _lock_timing_from_env() == (DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS, DEFAULT_LOCK_STALE_SECONDS)


def test_cli_install_returns_130_when_install_skill_raises_system_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_sigterm_as_system_exit() converts SIGTERM into SystemExit(130) inside install_skill();
    _cli_install must catch that alongside KeyboardInterrupt, not just KeyboardInterrupt alone,
    or a SIGTERM-triggered SystemExit would propagate uncaught out of main()."""

    def _raise_system_exit(*_args: object, **_kwargs: object) -> InstallOutcome:
        raise SystemExit(130)

    monkeypatch.setattr(install_engine, "install_skill", _raise_system_exit)
    args = argparse.Namespace(
        skill_id="demo-skill",
        repo_root=Path("/repo"),
        dest_root=Path("/dest"),
        host_label="cursor",
        dry_run=False,
    )

    assert _cli_install(args) == 130


def test_cli_uninstall_returns_130_when_uninstall_skill_raises_system_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_system_exit(*_args: object, **_kwargs: object) -> UninstallOutcome:
        raise SystemExit(130)

    monkeypatch.setattr(install_engine, "uninstall_skill", _raise_system_exit)
    args = argparse.Namespace(skill_id="demo-skill", dest_root=Path("/dest"), dry_run=False)

    assert _cli_uninstall(args) == 130


def test_main_prints_a_clean_error_instead_of_a_traceback_on_a_malformed_env_var(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A garbled (non-empty, non-numeric) LOCK_WAIT_TIMEOUT_SECONDS crashes _env_float's
    float() call before install_skill() is ever reached -- main()'s catch-all around CLI
    dispatch must turn that into a clean "error: ..." + exit 1, not a raw traceback."""
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_SECONDS", "not-a-number")
    exit_code = main(
        ["install", "demo-skill", str(tmp_path / "dest"), "cursor", "--repo-root", str(tmp_path)]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err


@pytest.mark.skipif(sys.platform == "win32", reason="os.kill(pid, SIGTERM) bypasses Python's signal module on Windows")
def test_sigterm_as_system_exit_converts_a_real_signal_to_exit_130() -> None:
    with pytest.raises(SystemExit) as exc_info:
        with install_engine._sigterm_as_system_exit():
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(1)  # give the signal a chance to be delivered

    assert exc_info.value.code == 130


def test_sigterm_as_system_exit_restores_the_previous_handler_on_exit() -> None:
    original_handler = signal.getsignal(signal.SIGTERM)
    try:
        with install_engine._sigterm_as_system_exit():
            assert signal.getsignal(signal.SIGTERM) != original_handler
        assert signal.getsignal(signal.SIGTERM) == original_handler
    finally:
        signal.signal(signal.SIGTERM, original_handler)


def test_sigterm_as_system_exit_restores_the_previous_handler_even_on_exception() -> None:
    original_handler = signal.getsignal(signal.SIGTERM)
    try:
        with pytest.raises(ValueError):
            with install_engine._sigterm_as_system_exit():
                raise ValueError("boom")
        assert signal.getsignal(signal.SIGTERM) == original_handler
    finally:
        signal.signal(signal.SIGTERM, original_handler)


def test_sigterm_as_system_exit_skips_restore_when_previous_handler_was_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """signal.signal() returns None when the previous handler was installed outside Python's
    signal module (e.g. native/embedding-host code) -- passing that back to signal.signal()
    raises TypeError, which would mask whatever exception is already propagating through the
    `finally`. Simulate that case by faking the registration call to report no previous
    handler, and confirm no second (restoring) call is attempted."""
    calls: list[object] = []

    def fake_signal(sig: int, handler: object) -> None:
        calls.append(handler)
        return None  # simulate: no Python-tracked previous handler to report back

    monkeypatch.setattr(install_engine.signal, "signal", fake_signal)

    with install_engine._sigterm_as_system_exit():
        pass

    assert len(calls) == 1  # only the registration call; the restore was correctly skipped
