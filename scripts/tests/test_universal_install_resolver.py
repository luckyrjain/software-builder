"""Tests for the universal `--agent agents` install destination resolver (Candidate 7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry.host_registry import parse_host_registry

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def host_registry():
    return parse_host_registry(ROOT / "agent-hosts.yaml")


def test_resolves_to_user_target_without_target_dir(host_registry) -> None:
    from scripts.registry.universal_install_resolver import resolve_universal_install_destination

    dest, label = resolve_universal_install_destination(
        host_registry, home=Path("/home/u"), target_dir=None
    )
    assert dest == Path("/home/u/.agents/skills")
    assert label == "agents-user"


def test_resolves_to_project_target_with_target_dir(host_registry) -> None:
    from scripts.registry.universal_install_resolver import resolve_universal_install_destination

    dest, label = resolve_universal_install_destination(
        host_registry, home=Path("/home/u"), target_dir=Path("/repo")
    )
    assert dest == Path("/repo/.agents/skills")
    assert label == "agents-project"


def test_agents_targets_exist_in_the_real_registry(host_registry) -> None:
    assert "agents-user" in host_registry.targets
    assert "agents-project" in host_registry.targets
    assert host_registry.targets["agents-user"].path == "~/.agents/skills"
    assert host_registry.targets["agents-project"].path == "{project_root}/.agents/skills"
