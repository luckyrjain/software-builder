"""Tests for the registry-driven legacy install destination resolver (Candidate 5).

Every expected value here was cross-checked by hand-tracing scripts/install.sh's actual
dest_roots()/host_label_for_dest() Bash functions for the same inputs, so this pins the exact
behavior those functions must keep producing once install.sh calls into this module instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry.host_registry import parse_host_registry

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def host_registry():
    return parse_host_registry(ROOT / "agent-hosts.yaml")


def test_unknown_agent_raises(host_registry) -> None:
    from scripts.registry.legacy_install_resolver import resolve_legacy_install_destinations

    with pytest.raises(ValueError, match="unknown --agent 'kiro'"):
        resolve_legacy_install_destinations(host_registry, "kiro", home=Path("/home/u"), target_dir=None)


@pytest.mark.parametrize(
    ("agent", "target_dir", "expected"),
    [
        ("cursor", None, [("/home/u/.cursor/skills", "cursor")]),
        ("cursor", "/repo", [("/repo/.cursor/skills", "cursor-project")]),
        ("cursor-project", None, [("/home/u/.cursor/skills", "cursor")]),
        ("cursor-project", "/repo", [("/repo/.cursor/skills", "cursor-project")]),
        ("claude-user", None, [("/home/u/.claude/skills", "claude-user")]),
        # claude-user ignores --target-dir entirely -- this is install.sh's existing behavior,
        # not a bug this migration introduces (see the module's docstring).
        ("claude-user", "/repo", [("/home/u/.claude/skills", "claude-user")]),
        ("claude-project", None, [("/home/u/.claude/skills", "claude-user")]),
        ("claude-project", "/repo", [("/repo/.claude/skills", "claude-project")]),
        (
            "all",
            None,
            [("/home/u/.cursor/skills", "cursor"), ("/home/u/.claude/skills", "claude-user")],
        ),
        (
            "all",
            "/repo",
            [("/repo/.cursor/skills", "cursor-project"), ("/repo/.claude/skills", "claude-project")],
        ),
    ],
)
def test_resolve_legacy_install_destinations(host_registry, agent, target_dir, expected) -> None:
    from scripts.registry.legacy_install_resolver import resolve_legacy_install_destinations

    result = resolve_legacy_install_destinations(
        host_registry,
        agent,
        home=Path("/home/u"),
        target_dir=Path(target_dir) if target_dir else None,
    )
    assert [(str(dest), label) for dest, label in result] == expected


def test_host_label_for_dest_matches_home_paths_first(host_registry) -> None:
    """Mirrors Bash's case-statement precedence: the literal $HOME paths are checked before the
    wildcard */.cursor/skills pattern, so a $HOME path is never mislabeled as *-project."""
    from scripts.registry.legacy_install_resolver import host_label_for_dest

    home = Path("/home/u")
    assert host_label_for_dest(home / ".cursor" / "skills", home=home) == "cursor"
    assert host_label_for_dest(home / ".claude" / "skills", home=home) == "claude-user"
    assert host_label_for_dest(Path("/anywhere/else/.cursor/skills"), home=home) == "cursor-project"
    assert host_label_for_dest(Path("/anywhere/else/.claude/skills"), home=home) == "claude-project"
