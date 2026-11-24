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
