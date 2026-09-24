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
import threading
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
    sig = install_engine._terminate_signal()  # SIGTERM on POSIX, SIGBREAK on Windows
    original_handler = signal.getsignal(sig)
    try:
        with install_engine._sigterm_as_system_exit():
            assert signal.getsignal(sig) != original_handler
        assert signal.getsignal(sig) == original_handler
    finally:
        signal.signal(sig, original_handler)


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
    """signal.getsignal() returns None when the previous handler was installed outside Python's
    signal module (e.g. native/embedding-host code) -- passing that back to signal.signal()
    raises TypeError, which would mask whatever exception is already propagating through the
    `finally`. Simulate that case by faking getsignal to report no previous handler, and
    confirm no second (restoring) call is attempted."""
    calls: list[object] = []

    def fake_signal(sig: int, handler: object) -> None:
        calls.append(handler)
        return None  # simulate: no Python-tracked previous handler to report back

    monkeypatch.setattr(install_engine.signal, "signal", fake_signal)
    monkeypatch.setattr(install_engine.signal, "getsignal", lambda sig: None)

    with install_engine._sigterm_as_system_exit():
        pass

    assert len(calls) == len(install_engine._stop_signals()) + 1  # SIGINT + stops: registrations only; no restore


# --- _terminate_signal / _defer_interrupts ---------------------------------------------------

posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="os.kill(pid, SIGTERM) bypasses Python's signal module on Windows"
)


def test_terminate_signal_is_sigterm_on_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install_engine.sys, "platform", "linux")
    assert install_engine._terminate_signal() == signal.SIGTERM


def test_terminate_signal_uses_sigbreak_on_windows_and_none_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(install_engine.sys, "platform", "win32")
    monkeypatch.setattr(signal, "SIGBREAK", 21, raising=False)
    assert install_engine._terminate_signal() == 21
    monkeypatch.delattr(signal, "SIGBREAK")
    assert install_engine._terminate_signal() is None


def test_terminate_signal_is_none_off_the_main_thread() -> None:
    result: list[object] = []
    worker = threading.Thread(target=lambda: result.append(install_engine._terminate_signal()))
    worker.start()
    worker.join()
    assert result == [None]


def test_context_managers_are_no_ops_off_the_main_thread() -> None:
    """signal.signal() raises ValueError anywhere but the main thread. A direct held_lock()
    user on a worker thread worked before signals were involved in the release path; it must
    still work (unprotected), not crash and strand the lock."""
    errors: list[BaseException] = []

    def _run() -> None:
        try:
            with install_engine._sigterm_as_system_exit():
                with install_engine._defer_interrupts():
                    pass
        except BaseException as exc:  # noqa: BLE001 - reporting whatever escaped the worker
            errors.append(exc)

    worker = threading.Thread(target=_run)
    worker.start()
    worker.join()
    assert errors == []


def test_held_lock_works_and_releases_from_a_worker_thread(tmp_path: Path) -> None:
    errors: list[BaseException] = []

    def _run() -> None:
        try:
            with install_engine.held_lock(tmp_path, "demo-skill"):
                pass
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    worker = threading.Thread(target=_run)
    worker.start()
    worker.join()
    assert errors == []
    assert not (tmp_path / ".demo-skill.lock").exists()


def test_defer_interrupts_restores_both_handlers_on_exit(signal_sentinels: object) -> None:
    terminate = install_engine._terminate_signal()  # SIGTERM on POSIX, SIGBREAK on Windows
    before = (signal.getsignal(signal.SIGINT), signal.getsignal(terminate))
    with install_engine._defer_interrupts():
        assert signal.getsignal(signal.SIGINT) != before[0]
        assert signal.getsignal(terminate) != before[1]
    assert (signal.getsignal(signal.SIGINT), signal.getsignal(terminate)) == before


def test_defer_interrupts_restores_both_handlers_on_exception(signal_sentinels: object) -> None:
    before = (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM))
    with pytest.raises(ValueError):
        with install_engine._defer_interrupts():
            raise ValueError("boom")
    assert (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)) == before


def test_defer_interrupts_falls_back_to_defaults_when_previous_handler_was_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """signal.getsignal() returns None for a handler installed outside Python's signal module.
    Leaving `_record` in place would swallow every later signal for the life of the process, so
    the restore must fall back to the interpreter's own default -- not skip, and not pass None
    (a TypeError)."""
    calls: list[tuple[int, object]] = []

    def fake_signal(sig: int, handler: object) -> None:
        calls.append((sig, handler))
        return None

    monkeypatch.setattr(install_engine.signal, "signal", fake_signal)
    monkeypatch.setattr(install_engine.signal, "getsignal", lambda sig: None)
    with install_engine._defer_interrupts():
        pass

    restores = calls[len(calls) // 2 :]
    assert {sig for sig, _ in restores} == {signal.SIGINT, *install_engine._stop_signals()}
    for sig, handler in restores:
        assert handler is not None
        expected = signal.default_int_handler if sig == signal.SIGINT else signal.SIG_DFL
        assert handler == expected


@posix_only
def test_defer_interrupts_defers_sigterm_until_the_block_finishes(signal_sentinels: object) -> None:
    completed = False
    with pytest.raises(SystemExit) as exc_info:
        with install_engine._defer_interrupts():
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)
            completed = True
    assert exc_info.value.code == 130
    assert completed  # the block ran to the end; the signal did not interrupt it


@posix_only
def test_defer_interrupts_defers_sigint_too_not_a_keyboard_interrupt(signal_sentinels: object) -> None:
    """Ctrl-C mid-rollback would otherwise raise KeyboardInterrupt straight through it."""
    completed = False
    with pytest.raises(SystemExit) as exc_info:
        with install_engine._defer_interrupts():
            os.kill(os.getpid(), signal.SIGINT)
            time.sleep(0.2)
            completed = True
    assert exc_info.value.code == 130
    assert completed


@posix_only
def test_a_deferred_signal_supersedes_an_exception_raised_by_the_block(signal_sentinels: object) -> None:
    """The block raising must not swallow a recorded signal: a failed rollback would otherwise
    let a multi-skill run continue after being told to stop. The original stays visible as
    `__context__`."""
    with pytest.raises(SystemExit) as exc_info:
        with install_engine._defer_interrupts():
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)
            raise ValueError("cleanup failed")
    assert exc_info.value.code == 130
    assert isinstance(exc_info.value.__context__, ValueError)


@posix_only
def test_an_exception_alone_still_propagates_unchanged(signal_sentinels: object) -> None:
    with pytest.raises(ValueError, match="boom"):
        with install_engine._defer_interrupts():
            raise ValueError("boom")


@posix_only
def test_defer_nested_in_sigterm_as_system_exit_restores_handlers_lifo(signal_sentinels: object) -> None:
    sentinel_term = signal.getsignal(signal.SIGTERM)
    with install_engine._sigterm_as_system_exit():
        outer = signal.getsignal(signal.SIGTERM)
        assert outer != sentinel_term
        with install_engine._defer_interrupts():
            assert signal.getsignal(signal.SIGTERM) not in (outer, sentinel_term)
        assert signal.getsignal(signal.SIGTERM) == outer  # back to the converting handler
        with pytest.raises(SystemExit) as exc_info:
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)
        assert exc_info.value.code == 130
    assert signal.getsignal(signal.SIGTERM) == sentinel_term


@posix_only
def test_defer_interrupts_leaves_an_ignored_signal_ignored(signal_sentinels: object) -> None:
    """An async child of a non-interactive shell (or nohup) has SIGINT ignored on purpose;
    deferring must not turn that ignored signal into an abort (or a 130 exit)."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    with install_engine._defer_interrupts():
        assert signal.getsignal(signal.SIGINT) == signal.SIG_IGN
        os.kill(os.getpid(), signal.SIGINT)
        time.sleep(0.1)
    assert signal.getsignal(signal.SIGINT) == signal.SIG_IGN


@posix_only
def test_sigterm_as_system_exit_leaves_an_ignored_signal_ignored(signal_sentinels: object) -> None:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    with install_engine._sigterm_as_system_exit():
        assert signal.getsignal(signal.SIGTERM) == signal.SIG_IGN
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(0.1)
    assert signal.getsignal(signal.SIGTERM) == signal.SIG_IGN


@posix_only
def test_defer_interrupts_restores_the_first_handler_if_a_signal_lands_between_installs(
    monkeypatch: pytest.MonkeyPatch, signal_sentinels: object
) -> None:
    """A signal arriving after SIGINT's handler is replaced but before SIGTERM's is must not
    leave the SIGINT one installed for the rest of the process."""
    sigint_before = signal.getsignal(signal.SIGINT)
    real_signal = signal.signal
    installs = 0

    def _signal_then_interrupt(sig: int, handler: object) -> object:
        nonlocal installs
        result = real_signal(sig, handler)  # type: ignore[arg-type]
        installs += 1
        if installs == 1:
            raise SystemExit(130)  # what the old SIGTERM handler does when it fires here
        return result

    monkeypatch.setattr(install_engine.signal, "signal", _signal_then_interrupt)
    with pytest.raises(SystemExit):
        with install_engine._defer_interrupts():
            pass  # pragma: no cover
    monkeypatch.undo()
    assert signal.getsignal(signal.SIGINT) == sigint_before


@posix_only
def test_a_failed_cleanup_superseded_by_a_deferred_signal_is_still_reported(
    signal_sentinels: object, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        with install_engine._defer_interrupts():
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.2)
            raise OSError(28, "No space left on device")
    assert exc_info.value.code == 130
    assert "cleanup failed while handling an interrupt" in capsys.readouterr().err


def test_stop_signals_include_sighup_on_posix_and_nothing_off_the_main_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if sys.platform != "win32":
        assert set(install_engine._stop_signals()) == {signal.SIGTERM, signal.SIGHUP}
    result: list[list[int]] = []
    worker = threading.Thread(target=lambda: result.append(install_engine._stop_signals()))
    worker.start()
    worker.join()
    assert result == [[]]


@posix_only
def test_sighup_is_converted_like_sigterm_and_restored(signal_sentinels: object) -> None:
    before = signal.getsignal(signal.SIGHUP)
    with pytest.raises(SystemExit) as exc_info:
        with install_engine._sigterm_as_system_exit():
            os.kill(os.getpid(), signal.SIGHUP)
            time.sleep(0.2)
    assert exc_info.value.code == 130
    assert signal.getsignal(signal.SIGHUP) == before


@posix_only
def test_sighup_is_deferred_during_cleanup(signal_sentinels: object) -> None:
    completed = False
    with pytest.raises(SystemExit) as exc_info:
        with install_engine._defer_interrupts():
            os.kill(os.getpid(), signal.SIGHUP)
            time.sleep(0.2)
            completed = True
    assert exc_info.value.code == 130
    assert completed


@posix_only
def test_an_ignored_sighup_stays_ignored(signal_sentinels: object) -> None:
    """`nohup` sets SIGHUP to ignored on purpose; deferral must not turn it into an abort."""
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    with install_engine._sigterm_as_system_exit():
        assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN
    with install_engine._defer_interrupts():
        assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN


@posix_only
def test_the_second_stop_signal_is_absorbed_while_the_first_is_being_handled(signal_sentinels: object) -> None:
    """Once the first signal has fired, later ones must not raise: the caller's cleanup handler
    runs inside the block and has to finish."""
    cleanup_finished = False
    with pytest.raises(SystemExit) as exc_info:
        with install_engine._sigterm_as_system_exit():
            try:
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(0.2)
            except SystemExit:
                os.kill(os.getpid(), signal.SIGTERM)  # a second signal, during the "cleanup"
                time.sleep(0.2)
                cleanup_finished = True
                raise
    assert exc_info.value.code == 130
    assert cleanup_finished


@posix_only
def test_sigint_is_a_keyboard_interrupt_first_and_absorbed_after(signal_sentinels: object) -> None:
    cleanup_finished = False
    with pytest.raises(KeyboardInterrupt):
        with install_engine._sigterm_as_system_exit():
            try:
                os.kill(os.getpid(), signal.SIGINT)
                time.sleep(0.2)
            except KeyboardInterrupt:
                os.kill(os.getpid(), signal.SIGINT)
                time.sleep(0.2)
                cleanup_finished = True
                raise
    assert cleanup_finished


@posix_only
def test_a_third_signal_calls_os_exit_with_130(monkeypatch: pytest.MonkeyPatch, signal_sentinels: object) -> None:
    calls: list[int] = []
    monkeypatch.setattr(install_engine.os, "_exit", lambda code: (calls.append(code), (_ for _ in ()).throw(SystemExit(code)))[-1])
    with pytest.raises(SystemExit) as exc_info:
        with install_engine._defer_interrupts():
            for _ in range(3):
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(0.1)
    assert calls == [130]
    assert exc_info.value.code == 130
