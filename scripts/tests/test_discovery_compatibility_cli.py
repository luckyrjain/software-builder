"""Regression tests for registry discovery commands and host compatibility output."""

from __future__ import annotations

from scripts.registry import cli
from scripts.registry.generate_compatibility import render_compatibility_matrix


def test_list_prints_canonical_skill_summary(capsys) -> None:
    assert cli.main(["list"]) == 0

    output = capsys.readouterr().out
    assert "api-test-creator" in output
    assert "domain-comprehension" in output
    assert "orchestrator" in output
    assert "1.1.0" in output


def test_explain_prints_canonical_skill_contract(capsys) -> None:
    assert cli.main(["explain", "pr-review"]) == 0

    output = capsys.readouterr().out
    assert "Skill: pr-review" in output
    assert "Version: 1.1.0" in output
    assert "Authority:" in output
    assert "Supported hosts:" in output
    assert "Output contract:" in output


def test_explain_rejects_unknown_skill(capsys) -> None:
    assert cli.main(["explain", "does-not-exist"]) == 1

    assert "unknown skill" in capsys.readouterr().err


def test_compatibility_matrix_covers_all_hosts_and_support_levels() -> None:
    matrix = render_compatibility_matrix(cli.ROOT)

    header = matrix.splitlines()[6]
    assert "Cursor" in header
    assert "Claude" in header
    assert "Codex" in header
    assert "ChatGPT" in header
    assert "Kiro" in header
    assert "Generic" in header
    assert "Support" in header
    assert "full" in matrix
    assert "degraded" in matrix
    assert "unsupported" in matrix
