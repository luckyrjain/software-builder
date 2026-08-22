"""Regression tests for registry discovery commands and host compatibility output."""

from __future__ import annotations

import subprocess
import sys

from scripts.registry import cli
from scripts.registry.generate_compatibility import render_compatibility_matrix


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.registry", *args],
        cwd=cli.ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_list_prints_canonical_skill_summary() -> None:
    result = _run_cli("list")

    assert result.returncode == 0
    output = result.stdout
    assert "api-test-creator" in output
    assert "domain-comprehension" in output
    assert "orchestrator" in output
    assert "1.1.0" in output
    rows = [line for line in output.splitlines() if line and not line.startswith("Skill") and not line.startswith("-----")]
    assert rows == sorted(rows)


def test_explain_prints_canonical_skill_contract() -> None:
    result = _run_cli("explain", "pr-review")

    assert result.returncode == 0
    output = result.stdout
    assert "Skill: pr-review" in output
    assert "Version: 1.1.0" in output
    assert "Authority:" in output
    assert "Supported hosts:" in output
    assert "Output contract:" in output


def test_explain_rejects_unknown_skill() -> None:
    result = _run_cli("explain", "does-not-exist")

    assert result.returncode == 1
    assert "unknown skill" in result.stderr


def test_compatibility_matrix_covers_all_hosts_and_support_levels() -> None:
    matrix = render_compatibility_matrix(cli.ROOT)

    header = matrix.splitlines()[6]
    assert "Cursor" in header
    assert "Claude" in header
    assert "Codex" in header
    assert "ChatGPT" in header
    assert "Kiro" in header
    assert "Generic" in header
    assert "support envelope" in header
    pr_review = next(line for line in matrix.splitlines() if "`pr-review`" in line)
    assert "codex_plugin (full/degraded)" in pr_review
    assert "codex_plugin_portable_package (full/degraded/unsupported)" in pr_review
    assert "unsupported | unsupported" not in pr_review
    assert "full" in matrix
    assert "degraded" in matrix
    assert "unsupported" in matrix
