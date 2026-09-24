"""Tests for scripts/lock_safety_patterns.py (the F1 Condition 1 lock-safety classifier).

Three test classes per rule: a clean case that must not trigger, a violating case that must
trigger, and an "only-added-lines" scoping case where the same violating pattern sits only in
*unchanged* lines and must not fire (design doc, "The four rules (v1 scope)" table: "never flags
pre-existing code the PR didn't touch" -- a load-bearing correctness property, not a nice-to-have).

Plus the single most important test class here (change-impact report, required_tests): feeding
this repository's own real, currently-shipped `held_lock`/`_sigterm_as_system_exit` (which
defines and registers `_on_stop`)/`run_if_new` source through `check()` and asserting zero
violations. If any of these fail, the design's central claim -- that the four rules are grounded
in what this codebase's own correct code looks like, not an invented standard -- is falsified,
and the fix is to correct the rule, never to weaken the golden fixture to match a false positive.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import lock_safety_patterns as lsp  # noqa: E402

INSTALL_ENGINE_PATH = ROOT / "scripts" / "install_engine.py"
IDEMPOTENCY_STORE_PATH = ROOT / "skills" / "pr-gatekeeper" / "scripts" / "idempotency_store.py"


def _all_lines(source: str) -> set[int]:
    """Every line number in `source` -- used to test a snippet as if every line were newly
    added, the strictest possible scoping (nothing is excluded by the added-lines filter)."""
    return set(range(1, len(source.splitlines()) + 1))


def _extract_function_source(file_path: Path, function_name: str) -> str:
    """The exact, currently-shipped source text of the top-level or nested function/context
    manager named `function_name` in `file_path`, via `ast.get_source_segment` -- never
    hand-retyped, so this always reflects the real file's actual current content rather than a
    copy that could silently drift out of sync with it."""
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            segment = ast.get_source_segment(source, node)
            assert segment is not None, f"could not extract source for {function_name} in {file_path}"
            return segment
    raise AssertionError(f"{function_name} not found in {file_path}")


# --- Golden fixtures: this repo's own real, currently-shipped clean code -----------------------


def test_golden_fixture_held_lock_zero_violations() -> None:
    """scripts/install_engine.py's held_lock() -- the try/finally-wrapped lock acquire/release
    shape rule `lock-without-tryfinally` is grounded in. Must produce zero violations."""
    source = _extract_function_source(INSTALL_ENGINE_PATH, "held_lock")
    violations = lsp.check({"held_lock.py": source}, {"held_lock.py": _all_lines(source)})
    assert violations == []


def test_golden_fixture_on_stop_zero_violations() -> None:
    """scripts/install_engine.py's `_on_stop` signal handler -- nested inside, and registered by,
    `_sigterm_as_system_exit()`, so that whole function is the fixture (it's what actually
    contains both the handler definition rule `unsafe-signal-handler` inspects and the
    `signal.signal(...)` registration call the rule keys off of). Must produce zero violations."""
    source = _extract_function_source(INSTALL_ENGINE_PATH, "_sigterm_as_system_exit")
    violations = lsp.check({"on_stop.py": source}, {"on_stop.py": _all_lines(source)})
    assert violations == []


def test_golden_fixture_run_if_new_zero_violations() -> None:
    """skills/pr-gatekeeper/scripts/idempotency_store.py's run_if_new() -- should_process (check)
    strictly precedes subprocess.run strictly precedes mark_processed (effect), the shape rule
    `idempotency-check-after-effect` is grounded in. Must produce zero violations."""
    source = _extract_function_source(IDEMPOTENCY_STORE_PATH, "run_if_new")
    violations = lsp.check({"run_if_new.py": source}, {"run_if_new.py": _all_lines(source)})
    assert violations == []


# --- lock-without-tryfinally --------------------------------------------------------------------

_LOCK_CLEAN = """\
import fcntl


def acquire(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
"""

_LOCK_VIOLATING = """\
import fcntl


def acquire(fd):
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd
"""


def test_lock_without_tryfinally_clean_case_not_flagged() -> None:
    violations = lsp.check({"f.py": _LOCK_CLEAN}, {"f.py": _all_lines(_LOCK_CLEAN)})
    assert violations == []


def test_lock_without_tryfinally_violating_case_flagged() -> None:
    violations = lsp.check({"f.py": _LOCK_VIOLATING}, {"f.py": _all_lines(_LOCK_VIOLATING)})
    assert len(violations) == 1
    assert violations[0].rule == lsp.RULE_LOCK_WITHOUT_TRYFINALLY
    assert violations[0].line == 5


def test_lock_without_tryfinally_scoped_to_added_lines_only() -> None:
    """The exact same violating pattern, but the diff didn't touch that line -- must not fire."""
    changed = _all_lines(_LOCK_VIOLATING) - {5}
    violations = lsp.check({"f.py": _LOCK_VIOLATING}, {"f.py": changed})
    assert violations == []


# --- lock-without-tryfinally: function/lambda scope boundary (LENS-A-1) ------------------------

_LOCK_LAMBDA_IN_OUTER_TRYFINALLY = """\
import fcntl


def outer(fd, executor):
    try:
        executor.submit(lambda: fcntl.flock(fd, fcntl.LOCK_EX))
    finally:
        cleanup()
"""

_LOCK_THREAD_WORKER_IN_OUTER_TRYFINALLY = """\
import fcntl
import threading


def start_worker(fd):
    try:
        def worker():
            fcntl.flock(fd, fcntl.LOCK_EX)
            process(fd)
        t = threading.Thread(target=worker)
        t.start()
    finally:
        release_other_resource()
"""

_LOCK_NESTED_FUNCTION_WITH_OWN_TRYFINALLY = """\
import fcntl


def outer(fd):
    def worker():
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    worker()
"""


def test_lock_without_tryfinally_lambda_in_outer_tryfinally_still_flagged() -> None:
    """A lock call inside a lambda passed to `executor.submit` runs on the executor's own
    schedule, possibly after the outer try/finally (which merely contains the lambda's
    *definition*) has already exited -- the outer `finally` is not a real release guarantee and
    must not suppress the violation (LENS-A-1)."""
    source = _LOCK_LAMBDA_IN_OUTER_TRYFINALLY
    violations = lsp.check({"f.py": source}, {"f.py": _all_lines(source)})
    assert len(violations) == 1
    assert violations[0].rule == lsp.RULE_LOCK_WITHOUT_TRYFINALLY
    assert violations[0].line == 6


def test_lock_without_tryfinally_thread_worker_in_outer_tryfinally_still_flagged() -> None:
    """Same false negative, via a nested `worker()` function definition run on a separate thread
    rather than a lambda -- the lock call's own function scope (`worker`) has no try/finally of
    its own, so it must be flagged regardless of `start_worker`'s outer try/finally (LENS-A-1)."""
    source = _LOCK_THREAD_WORKER_IN_OUTER_TRYFINALLY
    violations = lsp.check({"f.py": source}, {"f.py": _all_lines(source)})
    assert len(violations) == 1
    assert violations[0].rule == lsp.RULE_LOCK_WITHOUT_TRYFINALLY
    assert violations[0].line == 8


def test_lock_without_tryfinally_nested_function_with_own_tryfinally_not_flagged() -> None:
    """The legitimate case: a lock call inside a nested function that itself has its own
    enclosing try/finally, at the *same* function scope as the call, must still be recognized as
    protected -- the fix is "protection must be in the same function scope as the call", not
    "any nested function is always unprotected" (LENS-A-1)."""
    source = _LOCK_NESTED_FUNCTION_WITH_OWN_TRYFINALLY
    violations = lsp.check({"f.py": source}, {"f.py": _all_lines(source)})
    assert violations == []


# --- lock-without-tryfinally: keyword fd/handle argument (LENS-A-2) ----------------------------

_LOCK_KEYWORD_FD_VIOLATING = """\
def acquire_lock(fd, operation):
    pass


def acquire(fd):
    acquire_lock(fd=fd, operation=1)
    return fd
"""


def test_lock_without_tryfinally_keyword_fd_argument_flagged() -> None:
    """`_has_fd_like_argument` must also inspect keyword arguments, not just positional ones --
    a lock-acquisition-shaped call whose fd is passed as `fd=fd` is just as real a bypass as the
    already-flagged positional form (LENS-A-2)."""
    source = _LOCK_KEYWORD_FD_VIOLATING
    violations = lsp.check({"f.py": source}, {"f.py": _all_lines(source)})
    assert len(violations) == 1
    assert violations[0].rule == lsp.RULE_LOCK_WITHOUT_TRYFINALLY
    assert violations[0].line == 6


# --- bare-except-added -------------------------------------------------------------------------

_EXCEPT_CLEAN = """\
def read_file(path):
    try:
        return path.read_text()
    except OSError:
        return ""
"""

_EXCEPT_VIOLATING = """\
def read_file(path):
    try:
        return path.read_text()
    except:
        return ""
"""


def test_bare_except_clean_case_not_flagged() -> None:
    violations = lsp.check({"f.py": _EXCEPT_CLEAN}, {"f.py": _all_lines(_EXCEPT_CLEAN)})
    assert violations == []


def test_bare_except_violating_case_flagged() -> None:
    violations = lsp.check({"f.py": _EXCEPT_VIOLATING}, {"f.py": _all_lines(_EXCEPT_VIOLATING)})
    assert len(violations) == 1
    assert violations[0].rule == lsp.RULE_BARE_EXCEPT_ADDED
    assert violations[0].line == 4


def test_bare_except_scoped_to_added_lines_only() -> None:
    changed = _all_lines(_EXCEPT_VIOLATING) - {4}
    violations = lsp.check({"f.py": _EXCEPT_VIOLATING}, {"f.py": changed})
    assert violations == []


def test_bare_except_base_exception_with_pass_body_also_flagged() -> None:
    source = "def f():\n    try:\n        g()\n    except BaseException:\n        pass\n"
    violations = lsp.check({"f.py": source}, {"f.py": _all_lines(source)})
    assert len(violations) == 1
    assert violations[0].rule == lsp.RULE_BARE_EXCEPT_ADDED


# --- unsafe-signal-handler ----------------------------------------------------------------------

_SIGNAL_CLEAN = """\
import signal
import sys


def _on_stop(signum, frame):
    if signum == signal.SIGINT:
        raise KeyboardInterrupt
    sys.exit(130)


def install():
    signal.signal(signal.SIGTERM, _on_stop)
"""

_SIGNAL_VIOLATING = """\
import signal
import subprocess


def _on_stop(signum, frame):
    subprocess.run(["cleanup"])


def install():
    signal.signal(signal.SIGTERM, _on_stop)
"""


def test_unsafe_signal_handler_clean_case_not_flagged() -> None:
    violations = lsp.check({"f.py": _SIGNAL_CLEAN}, {"f.py": _all_lines(_SIGNAL_CLEAN)})
    assert violations == []


def test_unsafe_signal_handler_violating_case_flagged() -> None:
    violations = lsp.check({"f.py": _SIGNAL_VIOLATING}, {"f.py": _all_lines(_SIGNAL_VIOLATING)})
    assert len(violations) == 1
    assert violations[0].rule == lsp.RULE_UNSAFE_SIGNAL_HANDLER
    assert violations[0].line == 6  # the subprocess.run(...) statement inside _on_stop


def test_unsafe_signal_handler_scoped_to_added_lines_only() -> None:
    """The registering signal.signal(...) call itself (line 10) must be an added line for this
    rule to fire -- an untouched registration of an (also untouched) unsafe handler isn't new PR
    content to flag."""
    changed = _all_lines(_SIGNAL_VIOLATING) - {10}
    violations = lsp.check({"f.py": _SIGNAL_VIOLATING}, {"f.py": changed})
    assert violations == []


# --- idempotency-check-after-effect ---------------------------------------------------------

_IDEMPOTENCY_CLEAN = """\
def run_if_new(store, key):
    if not should_process(store, key):
        return 1
    mark_processed(store, key)
    return 0
"""

_IDEMPOTENCY_VIOLATING = """\
def run_if_new(store, key):
    mark_processed(store, key)
    if not should_process(store, key):
        return 1
    return 0
"""


def test_idempotency_check_after_effect_clean_case_not_flagged() -> None:
    violations = lsp.check({"f.py": _IDEMPOTENCY_CLEAN}, {"f.py": _all_lines(_IDEMPOTENCY_CLEAN)})
    assert violations == []


def test_idempotency_check_after_effect_violating_case_flagged() -> None:
    violations = lsp.check({"f.py": _IDEMPOTENCY_VIOLATING}, {"f.py": _all_lines(_IDEMPOTENCY_VIOLATING)})
    assert len(violations) == 1
    assert violations[0].rule == lsp.RULE_IDEMPOTENCY_CHECK_AFTER_EFFECT
    assert violations[0].line == 2  # mark_processed(...), which precedes should_process(...)


def test_idempotency_check_after_effect_scoped_to_added_lines_only() -> None:
    """Neither the effect call's line (2) nor the check call's line (3) is an added line -- the
    inverted ordering already existed before this (hypothetical) PR touched anything else in the
    function, so it must not fire."""
    changed = _all_lines(_IDEMPOTENCY_VIOLATING) - {2, 3}
    violations = lsp.check({"f.py": _IDEMPOTENCY_VIOLATING}, {"f.py": changed})
    assert violations == []


# --- check(): cross-cutting behavior -------------------------------------------------------------


def test_check_unparseable_file_produces_its_own_violation() -> None:
    """Fail-closed, never silently skipped (design doc, Failure strategy table)."""
    violations = lsp.check({"broken.py": "def f(:\n    pass\n"}, {"broken.py": {1}})
    assert len(violations) == 1
    assert violations[0].rule == lsp.RULE_UNPARSEABLE
    assert violations[0].file == "broken.py"


def test_check_non_python_file_skipped_not_flagged() -> None:
    violations = lsp.check({"notes.md": "flock(fd)\n"}, {"notes.md": {1}})
    assert violations == []


def test_check_evaluates_every_rule_not_just_the_first_violation() -> None:
    """The state machine's `checking_patterns` state always fully evaluates all 4 rules on every
    changed file, even after the first violation is found (design doc, State machines table)."""
    source = _LOCK_VIOLATING + "\n" + _EXCEPT_VIOLATING.replace("def read_file", "def read_file2")
    violations = lsp.check({"f.py": source}, {"f.py": _all_lines(source)})
    rules_hit = {v.rule for v in violations}
    assert lsp.RULE_LOCK_WITHOUT_TRYFINALLY in rules_hit
    assert lsp.RULE_BARE_EXCEPT_ADDED in rules_hit
