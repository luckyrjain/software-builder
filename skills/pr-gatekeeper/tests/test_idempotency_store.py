"""Tests for pr-gatekeeper/scripts/idempotency_store.py."""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
# scripts/tests/install_lock_test_helpers.py's spawn_lock_holder is this repo's established
# real-subprocess lock-contention harness (see scripts/tests/test_install_concurrency.py). It
# lives under the repository-root "scripts" package, not the pr-gatekeeper skill's own
# "scripts" dir inserted above, so it needs the repo root on sys.path too.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import idempotency_store  # noqa: E402
from idempotency_store import _safe_slug, _store_path  # noqa: E402
from scripts.tests.install_lock_test_helpers import spawn_lock_holder  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "idempotency_store.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_then_mark(tmp_path: Path) -> None:
    base = [
        "--store-root",
        str(tmp_path),
        "--project",
        "group/repo",
        "--merge-request-iid",
        "42",
        "--head-sha",
        "abc123",
    ]
    assert run(*base, "check").returncode == 0
    assert run(*base, "mark").returncode == 0
    assert run(*base, "check").returncode == 1

    base[-1] = "def456"
    assert run(*base, "check").returncode == 0


def test_run_if_new_skips_duplicate(tmp_path: Path) -> None:
    base = [
        "--store-root",
        str(tmp_path),
        "--project",
        "group/repo",
        "--merge-request-iid",
        "42",
        "--head-sha",
        "abc123",
        "run-if-new",
        "--",
        sys.executable,
        "-c",
        "print('ok')",
    ]
    assert run(*base).returncode == 0
    assert run(*base).returncode == 1


def test_safe_slug_rejects_path_traversal() -> None:
    slug = _safe_slug("../../etc/passwd")
    # No path separator survives, so the whole traversal string collapses into
    # a single, harmless path segment rather than escaping into parent dirs.
    assert "/" not in slug
    assert "\\" not in slug


def test_safe_slug_strips_null_bytes_and_traversal_chars() -> None:
    slug = _safe_slug("group/repo\x00../evil")
    assert "\x00" not in slug
    assert "/" not in slug
    assert slug == "group_repo_.._evil"


def test_safe_slug_caps_length() -> None:
    slug = _safe_slug("a" * 500)
    assert len(slug) == 128


def test_safe_slug_collapses_all_dots() -> None:
    assert _safe_slug("..") == "_"
    assert _safe_slug(".") == "_"
    assert _safe_slug("") == "_"


def test_safe_slug_neutralizes_leading_dash() -> None:
    assert not _safe_slug("-rf").startswith("-")


def test_store_path_stays_within_root_for_traversal_project(tmp_path: Path) -> None:
    path = _store_path(tmp_path, "../../etc/passwd", 1)
    assert path.parent.parent == tmp_path
    assert ".." not in path.parts


def test_check_with_unusual_project_identifier(tmp_path: Path) -> None:
    # A null byte can't even survive as a literal subprocess argv element (the
    # OS/Python reject it before the script runs), so the CLI-level regression
    # case here uses traversal segments and an oversized identifier instead;
    # the null-byte case is covered directly against _safe_slug() above.
    base = [
        "--store-root",
        str(tmp_path),
        "--project",
        "../../etc/passwd" + "x" * 200,
        "--merge-request-iid",
        "1",
        "--head-sha",
        "abc123",
    ]
    result = run(*base, "check")
    assert result.returncode == 0
    # The store file must land inside store-root, not escape via traversal.
    created = list(tmp_path.rglob("mr-1.json"))
    assert created == []  # "check" alone does not write a record file
    assert run(*base, "mark").returncode == 0
    created = list(tmp_path.rglob("mr-1.json"))
    assert len(created) == 1
    assert tmp_path in created[0].resolve().parents


# --- F4 hardening: --lock-wait-timeout, signal forwarding, fsync -------------------------------
#
# Everything below is additive-only: no existing test function above was changed. These exercise
# skills/pr-gatekeeper/scripts/idempotency_store.py's new bounded lock-wait, signal-forwarding,
# and fsync behavior per docs/superpowers/specs/2026-09-27-f4-idempotency-hardening-design.md.


def _lock_path(store_root: Path, project: str, merge_request_iid: int) -> Path:
    """Reproduces mr_lock's own lock-file naming so a test can pre-create it and hold the real
    OS lock on it via spawn_lock_holder before the CLI itself ever runs."""
    lock_dir = store_root / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / f"{_safe_slug(project)}-mr-{merge_request_iid}.lock"


def test_lock_wait_timeout_names_holder_pid_for_check(tmp_path: Path) -> None:
    """`check` already calls mr_lock today (main()'s bare `with mr_lock(...):` block) -- this is
    exactly the gap round 3's Software Architect review caught in the design doc (check's own
    exit-3 case was undocumented despite the code already acquiring the lock), so it gets its
    own dedicated real-subprocess coverage rather than relying on mark's test alone."""
    lock_path = _lock_path(tmp_path, "group/repo", 42)
    holder = spawn_lock_holder(lock_path)
    try:
        result = run(
            "--store-root", str(tmp_path),
            "--project", "group/repo",
            "--merge-request-iid", "42",
            "--head-sha", "abc123",
            "--lock-wait-timeout", "1",
            "check",
        )
        assert result.returncode == 3
        assert str(holder.pid) in result.stderr
    finally:
        holder.kill()
        holder.wait()


def test_lock_wait_timeout_names_holder_pid_for_mark(tmp_path: Path) -> None:
    lock_path = _lock_path(tmp_path, "group/repo", 43)
    holder = spawn_lock_holder(lock_path)
    try:
        result = run(
            "--store-root", str(tmp_path),
            "--project", "group/repo",
            "--merge-request-iid", "43",
            "--head-sha", "abc123",
            "--lock-wait-timeout", "1",
            "mark",
        )
        assert result.returncode == 3
        assert str(holder.pid) in result.stderr
    finally:
        holder.kill()
        holder.wait()


def test_lock_wait_timeout_names_holder_pid_for_run_if_new(tmp_path: Path) -> None:
    """run-if-new's lock acquisition happens inside run_if_new() itself -- a separate code path
    from the bare `with mr_lock(...):` block main() uses for check/mark -- so exercising it too
    (not just mark) matters: a bug scoped to only one of those two call sites would not show up
    in the other test."""
    lock_path = _lock_path(tmp_path, "group/repo", 44)
    holder = spawn_lock_holder(lock_path)
    try:
        result = run(
            "--store-root", str(tmp_path),
            "--project", "group/repo",
            "--merge-request-iid", "44",
            "--head-sha", "abc123",
            "--lock-wait-timeout", "1",
            "run-if-new", "--", sys.executable, "-c", "print('should not run')",
        )
        assert result.returncode == 3
        assert str(holder.pid) in result.stderr
    finally:
        holder.kill()
        holder.wait()


def test_lock_wait_timeout_rejects_nan(tmp_path: Path) -> None:
    result = run(
        "--store-root", str(tmp_path),
        "--project", "group/repo",
        "--merge-request-iid", "1",
        "--head-sha", "abc123",
        "--lock-wait-timeout", "nan",
        "check",
    )
    assert result.returncode == 2


def test_lock_wait_timeout_rejects_negative(tmp_path: Path) -> None:
    result = run(
        "--store-root", str(tmp_path),
        "--project", "group/repo",
        "--merge-request-iid", "1",
        "--head-sha", "abc123",
        "--lock-wait-timeout", "-1",
        "check",
    )
    assert result.returncode == 2


def test_lock_wait_timeout_rejects_infinity(tmp_path: Path) -> None:
    result = run(
        "--store-root", str(tmp_path),
        "--project", "group/repo",
        "--merge-request-iid", "1",
        "--head-sha", "abc123",
        "--lock-wait-timeout", "inf",
        "check",
    )
    assert result.returncode == 2


def _spawn_run_if_new(base: list[str], child_code: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, str(SCRIPT), *base, "run-if-new", "--", sys.executable, "-c", child_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_run_if_new_cooperative_child_exits_on_sigterm(tmp_path: Path) -> None:
    """A child that catches SIGTERM and exits cleanly: the wrapper should forward the signal,
    return exit 4 promptly, and skip mark_processed (a subsequent check for the same head still
    reports "unprocessed")."""
    base = [
        "--store-root", str(tmp_path),
        "--project", "group/repo",
        "--merge-request-iid", "50",
        "--head-sha", "shaC",
    ]
    child_code = (
        "import signal, sys, time\n"
        "signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))\n"
        "print('ready', flush=True)\n"
        "time.sleep(30)\n"
    )
    proc = _spawn_run_if_new(base, child_code)
    assert proc.stdout is not None
    line = proc.stdout.readline()
    assert line.strip() == "ready", f"child did not start: {line!r}"
    proc.send_signal(signal.SIGTERM)
    _, stderr = proc.communicate(timeout=10)
    assert proc.returncode == 4, stderr

    assert run(*base, "check").returncode == 0  # still unprocessed: mark_processed was skipped


def test_run_if_new_forwards_sigint_and_terminates_child(tmp_path: Path) -> None:
    """Explicit SIGINT case (not just SIGTERM): asserts the child is actually terminated by the
    forwarded signal, not silently orphaned by an uncaught KeyboardInterrupt escaping the
    subprocess.run()->Popen()/wait() migration -- if that happened, proc.wait() below would
    time out waiting the full 30s the child sleeps for."""
    base = [
        "--store-root", str(tmp_path),
        "--project", "group/repo",
        "--merge-request-iid", "51",
        "--head-sha", "shaI",
    ]
    child_code = (
        "import signal, sys, time\n"
        "signal.signal(signal.SIGINT, lambda *a: sys.exit(0))\n"
        "print('ready', flush=True)\n"
        "time.sleep(30)\n"
    )
    proc = _spawn_run_if_new(base, child_code)
    assert proc.stdout is not None
    line = proc.stdout.readline()
    assert line.strip() == "ready", f"child did not start: {line!r}"
    proc.send_signal(signal.SIGINT)
    _, stderr = proc.communicate(timeout=10)
    assert proc.returncode == 4, stderr

    assert run(*base, "check").returncode == 0


def test_run_if_new_uncooperative_child_blocks_until_it_actually_exits(tmp_path: Path) -> None:
    """A child that ignores the forwarded signal: the design's disclosed trade-off says the
    wrapper must block in .wait() exactly as long as it already would today, not return early.
    This is the one test that would fail loudly if a Builder "improved" the design back toward
    automatic escalation/kill, which the owner explicitly cut in revision 3 (see the design doc's
    Revision history)."""
    base = [
        "--store-root", str(tmp_path),
        "--project", "group/repo",
        "--merge-request-iid", "52",
        "--head-sha", "shaU",
    ]
    child_code = (
        "import signal, sys, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('ready', flush=True)\n"
        "time.sleep(1.5)\n"
        "sys.exit(0)\n"
    )
    proc = _spawn_run_if_new(base, child_code)
    assert proc.stdout is not None
    line = proc.stdout.readline()
    assert line.strip() == "ready", f"child did not start: {line!r}"
    started = time.monotonic()
    proc.send_signal(signal.SIGTERM)
    _, stderr = proc.communicate(timeout=10)
    elapsed = time.monotonic() - started

    assert elapsed >= 1.4, "wrapper returned before the uncooperative child actually exited"
    assert proc.returncode == 4, stderr
    assert run(*base, "check").returncode == 0  # still unprocessed: mark_processed was skipped


def test_default_unbounded_lock_wait_still_honors_sigterm(tmp_path: Path) -> None:
    """Lock-wait-phase signal-scoping: the new signal handler must be installed only from the
    moment Popen() returns onward, never around mr_lock's lock-wait -- bounded or unbounded. If
    it leaked into the lock-wait phase, a waiter blocked in the *default unbounded* wait (no
    --lock-wait-timeout passed) would become uninterruptible except by SIGKILL, exactly the
    regression round 3 of the design's adversarial review caught (see the design doc's Revision
    history, "Revision 3 -> 4"). Uses `mark`, not run-if-new: at the point the signal is sent,
    the waiter is still blocked acquiring the lock -- no child process, and thus no Popen(),
    exists yet -- so this exercises the exact phase run-if-new's own handler must not cover."""
    lock_path = _lock_path(tmp_path, "group/repo", 60)
    holder = spawn_lock_holder(lock_path, duration=30.0)
    try:
        waiter = subprocess.Popen(
            [
                sys.executable, str(SCRIPT),
                "--store-root", str(tmp_path),
                "--project", "group/repo",
                "--merge-request-iid", "60",
                "--head-sha", "abc123",
                "mark",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Give the waiter time to actually enter the blocking flock() call before signalling it.
        time.sleep(0.5)
        waiter.send_signal(signal.SIGTERM)
        waiter.wait(timeout=10)
        # Default SIGTERM disposition (no handler installed): the process is killed by the
        # signal, reported by Popen as a negative returncode -- not our own signal-handling
        # path's exit 4, and not a clean 0/1/2/3 either.
        assert waiter.returncode == -signal.SIGTERM
    finally:
        holder.kill()
        holder.wait()


def test_save_record_fsyncs_temp_file_then_directory(tmp_path: Path, monkeypatch) -> None:
    """Matches run_log.py's own monkeypatch-based test style for its _fsync/_fsync_dir calls
    (see skills/loop-task-implementer/tests/test_run_log.py's
    test_the_directory_entry_is_synced_for_the_first_record_even_after_a_rejected_call and
    test_fsync_asks_for_a_full_flush_where_the_platform_has_one): asserts the temp file's fd is
    fsynced before os.replace(), and the containing directory is fsynced only after."""
    calls: list[str] = []
    monkeypatch.setattr(idempotency_store, "_fsync", lambda fd: calls.append("fsync_file"))
    monkeypatch.setattr(idempotency_store, "_fsync_dir", lambda directory: calls.append("fsync_dir"))
    real_replace = idempotency_store.os.replace

    def _replace_and_record(*args: object, **kwargs: object) -> None:
        calls.append("replace")
        real_replace(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(idempotency_store.os, "replace", _replace_and_record)

    idempotency_store.save_record(tmp_path, "group/repo", 70, {"last_processed_head_sha": "shaX"})

    assert calls == ["fsync_file", "replace", "fsync_dir"]
