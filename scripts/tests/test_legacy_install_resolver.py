"""Golden destination/label table for scripts/registry/install_resolver.py's host selectors.

Every expected value here was cross-checked by hand-tracing scripts/install.sh's original
dest_roots()/host_label_for_dest() Bash functions for the same inputs, so this pins the exact
behavior install.sh must keep producing now that it calls into that module instead.
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
    from scripts.registry.install_resolver import resolve_install_destinations

    with pytest.raises(ValueError, match="unknown --agent 'kiro'"):
        resolve_install_destinations(host_registry, "kiro", home=Path("/home/u"), target_dir=None)


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
def test_resolve_install_destinations(host_registry, agent, target_dir, expected) -> None:
    from scripts.registry.install_resolver import resolve_install_destinations

    result = resolve_install_destinations(
        host_registry,
        agent,
        home=Path("/home/u"),
        target_dir=Path(target_dir) if target_dir else None,
    )
    assert [(str(dest), label) for dest, label in result] == expected


def test_labels_come_from_the_resolved_target_not_the_destination_path(host_registry) -> None:
    """The label used to be re-derived by string-matching the resolved path against hard-coded
    `$HOME/.cursor/skills`-style literals, with an unconditional `claude-project` fallback for
    anything unmatched. It is now the resolved agent-hosts.yaml target's own label, so a target
    whose path changes can no longer be silently mislabeled."""
    from scripts.registry.install_resolver import TARGET_LABELS, label_for_target

    assert label_for_target("cursor-user") == "cursor"
    assert label_for_target("claude-project") == "claude-project"
    assert set(TARGET_LABELS) <= set(host_registry.targets)


def test_every_registry_target_is_reachable_or_explicitly_allowlisted(host_registry) -> None:
    from scripts.registry.install_resolver import check_target_reachability

    assert check_target_reachability(host_registry) == []


def test_unreachable_allowlist_entries_each_carry_a_reason() -> None:
    from scripts.registry.install_resolver import UNREACHABLE_TARGETS

    assert UNREACHABLE_TARGETS
    for target_id, reason in UNREACHABLE_TARGETS.items():
        assert reason.strip(), f"{target_id} needs a reason"


def test_reachability_check_reports_an_unrouted_target(host_registry) -> None:
    import dataclasses

    from scripts.registry.host_registry import TargetSpec
    from scripts.registry.install_resolver import check_target_reachability

    targets = dict(host_registry.targets)
    targets["brand-new-user"] = TargetSpec(id="brand-new-user", scope="user", path="~/.brand/skills")
    drifted = dataclasses.replace(host_registry, targets=targets)

    errors = check_target_reachability(drifted)
    assert any("brand-new-user" in error for error in errors)


def test_install_selectors_order_is_the_installer_facing_order() -> None:
    from scripts.registry.install_resolver import install_selectors

    assert install_selectors() == [
        "cursor",
        "cursor-project",
        "claude-user",
        "claude-project",
        "all",
        "agents",
    ]
