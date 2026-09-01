"""Tests for scripts/lint-dangling-md-links.sh.

No test file existed for this script before -- it was only ever exercised transitively via
`make lint-suites`, where a specific failure mode (a real anchor being falsely reported as
dangling) went unnoticed as CI flakiness across many PRs before being root-caused here.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-dangling-md-links.sh"


def run_lint(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *(str(p) for p in paths)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_accepts_a_correctly_slugified_anchor(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("## Decision Confidence (numeric 0–1)\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("[link](target.md#decision-confidence-numeric-01)\n", encoding="utf-8")

    result = run_lint(source)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


def test_rejects_a_genuinely_wrong_anchor(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("## Real Heading\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("[bad link](target.md#does-not-exist)\n", encoding="utf-8")

    result = run_lint(source)

    assert result.returncode == 1
    assert "dangling anchor: target.md#does-not-exist" in result.stderr


def test_rejects_a_missing_target_file(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("[bad link](missing.md)\n", encoding="utf-8")

    result = run_lint(source)

    assert result.returncode == 1
    assert "dangling: missing.md" in result.stderr


def test_matching_anchor_is_not_flaky_under_repeated_runs(tmp_path: Path) -> None:
    """Regression for a real bug: `printf ... | grep -qx "$anchor"` let `grep -q`'s early exit on
    match SIGPIPE the still-writing `printf`; under `set -o pipefail` that made the pipeline's
    exit status reflect printf's SIGPIPE (141) instead of grep's successful match (0), so a
    genuinely present anchor was intermittently reported as dangling in CI.

    Reproduction requires two things at once: the match must be near the *start* of the heading
    list (so grep -q can decide "found it" and close its end of the pipe almost immediately) with
    a *large* amount of data still queued behind it (so printf is still mid-write, past the OS
    pipe buffer, when that close happens) -- confirmed against the pre-fix script: this exact
    shape failed 200/200 runs under background CPU load (`yes > /dev/null &` on every core, which
    widens the race window enough for the write to lose), and the fixed script (pure-bash
    exact-line match, no subprocess/pipe at all) passed 200/200 under the identical load. This
    test reproduces the shape without injecting CPU load, since CI test runners can't reliably do
    that -- it is best-effort/documentation coverage, not a guaranteed catch of a reintroduced bug
    on a quiet machine, but it exercises the same code path.
    """
    target = tmp_path / "target.md"
    headings = ["## The Real Target"] + [f"## Heading Number {i}" for i in range(3000)]
    target.write_text("\n".join(headings) + "\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("[link](target.md#the-real-target)\n", encoding="utf-8")

    for _ in range(20):
        result = run_lint(source)
        assert result.returncode == 0, result.stderr
        assert result.stderr == ""
