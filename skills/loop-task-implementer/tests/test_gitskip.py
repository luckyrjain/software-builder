"""Self-tests of the shared skip helpers (``_gitskip.py``)."""

from __future__ import annotations

import pytest

from _gitskip import skip_losing_coverage, skip_old_git


def test_skip_old_git_fails_under_ci_and_skips_elsewhere(monkeypatch):
    monkeypatch.setenv("CI", "true")
    with pytest.raises(pytest.fail.Exception, match="needed"):
        skip_old_git("git >= 2.43 is needed")
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(pytest.skip.Exception, match="needed"):
        skip_old_git("git >= 2.43 is needed")


def test_skip_losing_coverage_skips_everywhere_and_warns_loudly_under_ci(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(pytest.skip.Exception, match="COVERAGE LOST: the home redirect"):
        skip_losing_coverage("this build ignores a redirected home", "the home redirect")
    monkeypatch.setenv("CI", "true")
    with pytest.warns(UserWarning, match="COVERAGE LOST: the home redirect"):
        with pytest.raises(pytest.skip.Exception, match="the home redirect"):  # the skip itself is not turned into a failure
            skip_losing_coverage("this build ignores a redirected home", "the home redirect")


def test_both_skip_messages_name_the_running_test(monkeypatch):
    """pytest shows the skip at `_gitskip.py:<line>`; the message must say which test raised it."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_x.py::test_row (call)")
    with pytest.raises(pytest.skip.Exception, match=r"test_x\.py::test_row"):
        skip_old_git("git >= 2.43 is needed")
    with pytest.raises(pytest.skip.Exception, match=r"COVERAGE LOST: the home redirect \[tests/test_x\.py::test_row"):
        skip_losing_coverage("this build ignores a redirected home", "the home redirect")
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    with pytest.raises(pytest.skip.Exception) as caught:
        skip_old_git("plain")
    assert str(caught.value) == "plain"
