"""Shared skip helpers of the benchmark-gate tests (imported by name: the tests directory is on ``sys.path`` under pytest's default import mode)."""

from __future__ import annotations

import os
import warnings

import pytest


def _named(message: str) -> str:
    """Append the running test's id: pytest reports a skip raised here as ``_gitskip.py:<line>``, which hides WHICH test skipped."""
    test = os.environ.get("PYTEST_CURRENT_TEST")
    return f"{message} [{test}]" if test else message


def skip_old_git(message: str):
    """A git older than 2.43 skips these tests on a developer machine and FAILS them under CI (the ``CI`` variable): a skip there would hide a
    whole suite. Production's ``_require_modern_git`` hard-fails either way."""
    message = _named(message)
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


def skip_losing_coverage(reason: str, lost: str):
    """Skip because this platform or build cannot run the check, and say loudly WHAT coverage is lost: locally it is a plain skip; under CI it is also
    a ``UserWarning`` (shown in the warnings summary of the CI log), because a runner whose interpreter keeps skipping these rows has silently
    stopped testing that guard. It does not fail: framework builds and other legitimate interpreters skip these rows on purpose."""
    message = _named(f"{reason}; COVERAGE LOST: {lost}")
    if os.environ.get("CI"):
        warnings.warn(message, UserWarning, stacklevel=2)
    pytest.skip(message)
