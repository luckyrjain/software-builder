"""Tests for the `make lint-actions-security` target's zizmor fallback logic.

This shell logic (in the Makefile, not a Python script) has twice been the site of a real
bug during this branch's review history: a fatal-vs-transient zizmor failure was originally
treated as an unconditional hard failure, and the fix for that was itself broken by `dash`'s
`echo` interpreting a backslash escape and truncating the captured output before the
fallback-detection `grep` ever saw it. Neither bug had a regression test. These tests stub
`zizmor` on `PATH` to deterministically drive each branch without depending on network access,
a real token, or zizmor actually being installed.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _make_fake_zizmor(bin_dir: Path, script: str) -> None:
    fake = bin_dir / "zizmor"
    fake.write_text(script, encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _run_target(bin_dir: Path, *, token: str | None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        env.pop(key, None)
    if token is not None:
        env["GH_TOKEN"] = token
    return subprocess.run(
        ["make", "lint-actions-security"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_success_with_token_runs_online_audit(tmp_path: Path) -> None:
    _make_fake_zizmor(
        tmp_path,
        "#!/bin/sh\necho 'No findings to report. Good job!'\nexit 0\n",
    )
    result = _run_target(tmp_path, token="a-token")
    assert result.returncode == 0, result.stderr
    assert "No findings" in result.stdout


def test_fatal_online_audit_falls_back_and_succeeds(tmp_path: Path) -> None:
    # Simulates zizmor's own real behavior: the online-audit invocation (no
    # --no-online-audits flag) fails with its exact "fatal: no audit was performed"
    # message; the retry with --no-online-audits (the fallback this target adds) succeeds.
    _make_fake_zizmor(
        tmp_path,
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        "  *' --no-online-audits '*) echo 'No findings to report. Good job!'; exit 0 ;;\n"
        "  *) echo 'fatal: no audit was performed'; exit 1 ;;\n"
        "esac\n",
    )
    result = _run_target(tmp_path, token="a-bad-token")
    assert result.returncode == 0, result.stderr
    assert "falling back to --no-online-audits" in result.stderr
    assert "No findings" in result.stdout


def test_real_finding_with_token_fails_without_fallback(tmp_path: Path) -> None:
    # A genuine finding must still fail loudly — the fallback is only for the specific
    # "fatal: no audit was performed" infrastructure-failure message, not for real findings.
    _make_fake_zizmor(
        tmp_path,
        "#!/bin/sh\n"
        "echo 'error[template-injection]: code injection via template expansion'\n"
        "exit 1\n",
    )
    result = _run_target(tmp_path, token="a-token")
    assert result.returncode != 0
    assert "falling back" not in result.stderr
    assert "template-injection" in result.stderr


def test_no_token_runs_offline_directly(tmp_path: Path) -> None:
    _make_fake_zizmor(
        tmp_path,
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        "  *' --no-online-audits '*) echo 'No findings to report. Good job!'; exit 0 ;;\n"
        "  *) echo 'should not run the online path without a token' >&2; exit 1 ;;\n"
        "esac\n",
    )
    result = _run_target(tmp_path, token=None)
    assert result.returncode == 0, result.stderr
    assert "no GH_TOKEN/GITHUB_TOKEN set" in result.stderr
    assert "No findings" in result.stdout


def test_zizmor_not_installed_skips_without_failing() -> None:
    # Reconstructs PATH from only the bare minimum needed to run `make`/`sh`/coreutils,
    # excluding wherever this environment's own real zizmor happens to be installed (e.g.
    # /usr/local/bin via pip) — prepending an empty stub dir to the *existing* PATH, like the
    # other tests do, wouldn't reliably hit this branch on a machine where zizmor is already
    # on PATH later in the search order.
    env = dict(os.environ)
    env["PATH"] = "/usr/bin:/bin"
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        env.pop(key, None)
    env["GH_TOKEN"] = "a-token"
    result = subprocess.run(
        ["make", "lint-actions-security"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "SKIPPED:" in result.stderr
    assert "zizmor not installed" in result.stderr
