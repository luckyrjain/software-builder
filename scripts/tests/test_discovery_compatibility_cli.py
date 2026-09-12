"""Regression tests for registry discovery commands and host compatibility output."""

from __future__ import annotations

import subprocess
import sys

import pytest

from scripts.registry import cli
from scripts.registry.generate_compatibility import (
    _cell,
    _host_profiles,
    render_compatibility_matrix,
)


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
    assert "Version: 1.2.0" in output
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
    pr_review = next(line for line in matrix.splitlines() if "| pr-review |" in line)
    assert "codex_plugin \\(full/degraded\\)" in pr_review
    assert "codex_plugin_portable_package \\(full/degraded/unsupported\\)" in pr_review
    assert "unsupported | unsupported" not in pr_review
    assert "full" in matrix
    assert "degraded" in matrix
    assert "unsupported" in matrix


def test_dynamic_output_escapes_terminal_and_markdown_controls() -> None:
    assert "\x1b" not in cli._display_text("\x1b[31mRED")
    assert "\\x1b" in cli._display_text("\x1b[31mRED")
    assert _cell("skill`|[name](url)<https://evil>\n") == "skill\\`\\|\\[name\\]\\(url\\)\\<https://evil\\>\\x0a"


def test_canonical_output_requires_host_contracts(tmp_path) -> None:
    with pytest.raises(ValueError, match="host contracts required"):
        _host_profiles(tmp_path, canonical=True)


def test_compatibility_prints_status_for_known_host_and_skill() -> None:
    result = _run_cli("compatibility", "--host", "claude", "--skill", "pr-review")

    assert result.returncode == 0
    assert "claude pr-review:" in result.stdout


def test_compatibility_defaults_to_every_skill_when_skill_omitted() -> None:
    result = _run_cli("compatibility", "--host", "claude")

    assert result.returncode == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) > 1
    assert any("pr-review" in line for line in lines)


def test_compatibility_rejects_unknown_host() -> None:
    result = _run_cli("compatibility", "--host", "does-not-exist")

    assert result.returncode == 2
    assert "unknown host" in result.stderr


def test_compatibility_rejects_unknown_skill() -> None:
    result = _run_cli("compatibility", "--host", "claude", "--skill", "does-not-exist")

    assert result.returncode == 1
    assert "unknown skill" in result.stderr


def test_compatibility_surface_flag_matches_default_for_claude_local_surface() -> None:
    # The real "claude" host's only surface is LOCAL with no per-surface overrides today, so
    # --surface LOCAL must resolve identically to omitting --surface entirely.
    with_surface = _run_cli("compatibility", "--host", "claude", "--skill", "pr-review", "--surface", "LOCAL")
    without_surface = _run_cli("compatibility", "--host", "claude", "--skill", "pr-review")

    assert with_surface.returncode == without_surface.returncode == 0
    assert with_surface.stdout == without_surface.stdout


def test_compatibility_rejects_unknown_surface() -> None:
    result = _run_cli("compatibility", "--host", "claude", "--surface", "NOT_A_REAL_SURFACE")

    assert result.returncode == 2
    assert "NOT_A_REAL_SURFACE" in result.stderr


def test_compatibility_surface_differentiates_per_surface_capability_overrides(tmp_path, capsys) -> None:
    """Direct-call test (not subprocess): cmd_compatibility itself has no --repo-root flag
    (unlike doctor.py), so a synthetic multi-surface registry can only be exercised by calling
    the function directly against a tmp_path root, not via _run_cli. Modeled on
    scripts/tests/test_doctor.py's _write_surface_fixture: a "claude" host with a LOCAL surface
    where host.repository.read_write is AVAILABLE and a CLOUD surface where it's UNAVAILABLE,
    plus one skill (demo-skill) requiring it.

    Expected status strings, traced (not guessed) through compatibility_resolver.py's
    _combine_status: the fixture's host verification is "UNVERIFIED". On LOCAL, the capability
    is AVAILABLE so capability_status is "READY", but _combine_status still downgrades a READY
    capability result on an UNVERIFIED host to "UNVERIFIED" (see
    scripts/tests/test_compatibility_resolver.py's own ("READY", "UNVERIFIED", "UNVERIFIED")
    case). On CLOUD, the capability is UNAVAILABLE so capability_status is "BLOCKED", and
    "BLOCKED" always wins regardless of host verification.
    """
    import yaml

    from scripts.registry.cli import cmd_compatibility

    agent_hosts = {
        "schema_version": 1,
        "targets": [
            {"id": "claude-project", "scope": "project", "path": "{project_root}/.claude/skills"},
        ],
        "hosts": [
            {
                "id": "claude",
                "surfaces": [
                    {
                        "kind": "LOCAL",
                        "discovery": [
                            {"target": "claude-project", "mode": "NATIVE", "precedence": 10},
                        ],
                        "capabilities": {"host.repository.read_write": "AVAILABLE"},
                    },
                    {
                        "kind": "CLOUD",
                        "discovery": [
                            {"target": "claude-project", "mode": "NATIVE", "precedence": 10},
                        ],
                        "capabilities": {"host.repository.read_write": "UNAVAILABLE"},
                    },
                ],
                "capabilities": {"host.repository.read_write": "UNKNOWN"},
                "isolation": {"mode": "UNKNOWN"},
                "constraints": [],
                "verification": "UNVERIFIED",
                "evidence": [],
                "maintainer_support": "BEST_EFFORT",
            },
        ],
    }
    (tmp_path / "agent-hosts.yaml").write_text(
        yaml.safe_dump(agent_hosts, sort_keys=False), encoding="utf-8"
    )

    skills = {
        "schema_version": 1,
        "skills": {
            "demo-skill": {
                "path": "demo-skill",
                "category": "test",
                "invocation": "ambient",
                "hosts": {"claude": {"install": True}},
                "install": {"requires": []},
                "lint": {"skill_md_max_lines": 180, "target": "demo-skill"},
                "composition": {"invokes": []},
                "capabilities": {"required": ["host.repository.read_write"], "optional": []},
                "risk_class": ["repository-write"],
            },
        },
    }
    (tmp_path / "skills.yaml").write_text(yaml.safe_dump(skills, sort_keys=False), encoding="utf-8")

    (tmp_path / "VERSION").write_text("1.0.0\n", encoding="utf-8")

    exit_code_local = cmd_compatibility(tmp_path, "claude", "demo-skill", "LOCAL")
    local_out = capsys.readouterr().out
    exit_code_cloud = cmd_compatibility(tmp_path, "claude", "demo-skill", "CLOUD")
    cloud_out = capsys.readouterr().out

    assert exit_code_local == 0
    assert exit_code_cloud == 0  # cmd_compatibility always returns 0 for a resolved (not unknown) host/skill --
    # the differentiation is in the printed status line, not the exit code.
    assert "claude demo-skill: UNVERIFIED" in local_out
    assert "claude demo-skill: BLOCKED" in cloud_out
    assert "missing required: host.repository.read_write" in cloud_out
