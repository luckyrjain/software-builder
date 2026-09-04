"""Tests for the universal `--agent agents` selector in scripts/registry/install_resolver.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry.host_registry import parse_host_registry

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def host_registry():
    return parse_host_registry(ROOT / "agent-hosts.yaml")


def test_resolves_to_user_target_without_target_dir(host_registry) -> None:
    from scripts.registry.install_resolver import resolve_install_destinations

    assert resolve_install_destinations(
        host_registry, "agents", home=Path("/home/u"), target_dir=None
    ) == [(Path("/home/u/.agents/skills"), "agents-user")]


def test_resolves_to_project_target_with_target_dir(host_registry) -> None:
    from scripts.registry.install_resolver import resolve_install_destinations

    assert resolve_install_destinations(
        host_registry, "agents", home=Path("/home/u"), target_dir=Path("/repo")
    ) == [(Path("/repo/.agents/skills"), "agents-project")]


def test_agents_targets_exist_in_the_real_registry(host_registry) -> None:
    assert "agents-user" in host_registry.targets
    assert "agents-project" in host_registry.targets
    assert host_registry.targets["agents-user"].path == "~/.agents/skills"
    assert host_registry.targets["agents-project"].path == "{project_root}/.agents/skills"


def test_raises_a_clear_error_when_the_universal_target_is_missing_from_the_registry() -> None:
    """A registry that lacks agents-user/agents-project (unlike the real repo's) must fail with a
    clear error, not an unguarded KeyError -- mirrors the resolver's own unknown-selector
    ValueError rather than leaking an implementation-detail exception type."""
    from scripts.registry.host_registry import HostRegistry
    from scripts.registry.install_resolver import resolve_install_destinations

    empty_registry = HostRegistry(schema_version=1, targets={}, hosts={}, aliases={})

    with pytest.raises(ValueError, match="agents-user"):
        resolve_install_destinations(
            empty_registry, "agents", home=Path("/home/u"), target_dir=None
        )

    with pytest.raises(ValueError, match="agents-project"):
        resolve_install_destinations(
            empty_registry, "agents", home=Path("/home/u"), target_dir=Path("/repo")
        )
