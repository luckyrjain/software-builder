"""Tests for the host x skill compatibility resolver (Candidate 4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.registry.host_adapter import CAPABILITIES as HOST_ADAPTER_CAPABILITIES
from scripts.registry.host_registry import parse_host_registry

ROOT = Path(__file__).resolve().parents[2]


def _raw_registry(
    *,
    verification: str = "UNVERIFIED",
    capabilities: dict[str, str] | None = None,
    evidence: list[dict[str, str]] | None = None,
    discovery: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "targets": [{"id": "cursor-user", "scope": "user", "path": "~/.cursor/skills"}],
        "aliases": [{"id": "cursor-code", "target": "cursor"}],
        "hosts": [
            {
                "id": "cursor",
                "surfaces": [
                    {
                        "kind": "LOCAL",
                        "discovery": discovery
                        if discovery is not None
                        else [{"target": "cursor-user", "mode": "NATIVE", "precedence": 10}],
                    }
                ],
                "capabilities": capabilities
                if capabilities is not None
                else {"host.repository.read": "AVAILABLE"},
                "isolation": {"mode": "UNKNOWN"},
                "constraints": [],
                "verification": verification,
                "evidence": evidence or [],
                "maintainer_support": "BEST_EFFORT",
            }
        ],
    }


def _host_registry(tmp_path: Path, **kwargs: Any):
    path = tmp_path / "agent-hosts.yaml"
    path.write_text(yaml.safe_dump(_raw_registry(**kwargs), sort_keys=False), encoding="utf-8")
    return parse_host_registry(path)


def _skill_registry(*, required: list[str], optional: list[str] | None = None):
    from scripts.registry.models import (
        CapabilitiesSpec,
        CapabilityOptional,
        CompositionSpec,
        HostDiscoverySpec,
        InstallSpec,
        LintSpec,
        Registry,
        SkillEntry,
    )

    hosts = {
        "cursor": HostDiscoverySpec(discovery="rule"),
        "claude": HostDiscoverySpec(install=True),
        "kiro": HostDiscoverySpec(discovery="manual"),
    }
    entry = SkillEntry(
        path="demo",
        category="testing",
        invocation="ambient",
        hosts=hosts,
        install=InstallSpec(requires=[]),
        lint=LintSpec(skill_md_max_lines=180, target="demo"),
        composition=CompositionSpec(),
        capabilities=CapabilitiesSpec(
            required=required,
            optional=[CapabilityOptional(name=name) for name in (optional or [])],
        ),
    )
    return Registry(schema_version=1, skills={"demo": entry})


def test_host_capability_families_bridge_stays_inside_both_vocabularies() -> None:
    """The single `host.* -> capability family` bridge (host_adapter.py) must only ever
    name families host_adapter itself declares -- an unmapped family would make the
    compatibility matrix gate a requirement against a support level nothing publishes."""
    from scripts.registry.host_adapter import HOST_CAPABILITY_FAMILIES

    assert all(name.startswith("host.") for name in HOST_CAPABILITY_FAMILIES)
    mapped = {family for families in HOST_CAPABILITY_FAMILIES.values() for family in families}
    assert mapped <= HOST_ADAPTER_CAPABILITIES


def test_resolve_host_follows_one_alias_hop(tmp_path: Path) -> None:
    from scripts.registry.compatibility_resolver import resolve_host

    registry = _host_registry(tmp_path)
    host = resolve_host(registry, "cursor-code")
    assert host is registry.hosts["cursor"]
    assert resolve_host(registry, "cursor") is registry.hosts["cursor"]


def test_resolve_host_raises_on_unknown_id(tmp_path: Path) -> None:
    from scripts.registry.compatibility_resolver import UnknownHostError, resolve_host

    registry = _host_registry(tmp_path)
    with pytest.raises(UnknownHostError, match="unknown host 'nonexistent'"):
        resolve_host(registry, "nonexistent")


def test_available_capabilities_excludes_unavailable_and_unknown(tmp_path: Path) -> None:
    from scripts.registry.compatibility_resolver import available_capabilities

    registry = _host_registry(
        tmp_path,
        capabilities={
            "host.repository.read": "AVAILABLE",
            "host.repository.read_write": "UNAVAILABLE",
            "host.filesystem.read": "UNKNOWN",
        },
    )
    assert available_capabilities(registry.hosts["cursor"]) == frozenset({"host.repository.read"})


def test_is_discoverable_true_with_a_discovery_binding(tmp_path: Path) -> None:
    from scripts.registry.compatibility_resolver import is_discoverable

    registry = _host_registry(tmp_path)
    assert is_discoverable(registry.hosts["cursor"]) is True


def test_is_discoverable_always_true_given_current_schema_invariants(tmp_path: Path) -> None:
    """host_registry.py's own _parse_surfaces/_parse_discovery reject an empty surfaces list and an
    empty discovery list respectively (schema invariants, not this resolver's business) -- so a
    False result is currently unreachable for any host that parses at all. Documented here rather
    than silently assumed; is_discoverable exists for when a future schema change relaxes that."""
    from scripts.registry.compatibility_resolver import is_discoverable

    registry = _host_registry(tmp_path)
    assert is_discoverable(registry.hosts["cursor"]) is True


@pytest.mark.parametrize(
    ("capability_status", "host_verification", "expected"),
    [
        ("BLOCKED", "VERIFIED", "BLOCKED"),
        ("BLOCKED", "UNVERIFIED", "BLOCKED"),
        ("BLOCKED", "CONFLICTED", "BLOCKED"),
        ("READY", "CONFLICTED", "CONFLICTED"),
        ("DEGRADED", "CONFLICTED", "CONFLICTED"),
        ("READY", "UNVERIFIED", "UNVERIFIED"),
        ("DEGRADED", "UNVERIFIED", "UNVERIFIED"),
        ("READY", "VERIFIED", "READY"),
        ("DEGRADED", "VERIFIED", "DEGRADED"),
        ("READY", "STALE", "READY"),
        ("DEGRADED", "STALE", "DEGRADED"),
    ],
)
def test_combine_status_precedence(capability_status: str, host_verification: str, expected: str) -> None:
    from scripts.registry.compatibility_resolver import _combine_status

    assert _combine_status(capability_status, host_verification) == expected


def test_resolve_end_to_end_ready_when_capability_available_and_verified(tmp_path: Path) -> None:
    from scripts.registry.compatibility_resolver import resolve

    host_registry = _host_registry(
        tmp_path,
        verification="VERIFIED",
        capabilities={"host.repository.read": "AVAILABLE"},
        evidence=[{"kind": "RUNTIME", "reference": "scripts/tests/runtime.py"}],
    )
    registry = _skill_registry(required=["host.repository.read"])

    result = resolve(host_registry, registry, "cursor", "demo")
    assert result.status == "READY"
    assert result.capability_status == "READY"
    assert result.host_verification == "VERIFIED"
    assert result.missing_required == []
    assert result.discoverable is True


def test_resolve_end_to_end_blocked_on_missing_required_capability(tmp_path: Path) -> None:
    """BLOCKED wins even against a genuinely VERIFIED host -- a concrete missing capability is
    always reported, never masked by an otherwise-trustworthy host."""
    from scripts.registry.compatibility_resolver import resolve

    host_registry = _host_registry(
        tmp_path,
        verification="VERIFIED",
        evidence=[{"kind": "RUNTIME", "reference": "scripts/tests/runtime.py"}],
    )
    registry = _skill_registry(required=["host.repository.read_write"])

    result = resolve(host_registry, registry, "cursor", "demo")
    assert result.status == "BLOCKED"
    assert result.missing_required == ["host.repository.read_write"]


def test_resolve_end_to_end_unverified_host_caps_a_would_be_ready_result(tmp_path: Path) -> None:
    from scripts.registry.compatibility_resolver import resolve

    host_registry = _host_registry(tmp_path, verification="UNVERIFIED")
    registry = _skill_registry(required=["host.repository.read"])

    result = resolve(host_registry, registry, "cursor", "demo")
    assert result.capability_status == "READY"
    assert result.status == "UNVERIFIED"


def test_resolve_unknown_skill_raises(tmp_path: Path) -> None:
    from scripts.registry.compatibility_resolver import UnknownSkillError, resolve

    host_registry = _host_registry(tmp_path)
    registry = _skill_registry(required=[])
    with pytest.raises(UnknownSkillError, match="unknown skill 'nonexistent'"):
        resolve(host_registry, registry, "cursor", "nonexistent")


def test_resolve_matrix_is_deterministic_and_covers_every_pair(tmp_path: Path) -> None:
    from scripts.registry.compatibility_resolver import resolve_matrix

    host_registry = _host_registry(tmp_path)
    registry = _skill_registry(required=[])

    first = resolve_matrix(host_registry, registry)
    second = resolve_matrix(host_registry, registry)
    assert first == second
    assert [(r.host_id, r.skill_id) for r in first] == [("cursor", "demo")]


def test_resolve_matrix_against_real_repo_never_crashes_and_uses_valid_statuses() -> None:
    from scripts.registry.compatibility_resolver import resolve_matrix
    from scripts.registry.schema import parse_registry

    host_registry = parse_host_registry(ROOT / "agent-hosts.yaml")
    registry = parse_registry(ROOT / "skills.yaml")

    matrix = resolve_matrix(host_registry, registry)
    assert len(matrix) == len(host_registry.hosts) * len(registry.skills)
    assert all(
        result.status in {"READY", "DEGRADED", "BLOCKED", "UNVERIFIED", "CONFLICTED"}
        for result in matrix
    )
