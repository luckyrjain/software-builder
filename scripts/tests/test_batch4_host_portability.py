from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from scripts.registry.host_adapter import HOSTS, capability_support, validate_host_adapter_interface
from scripts.registry.host_portability import validate_host_portability
from scripts.registry.generic_package import build_generic_package
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


def test_host_adapter_interface_covers_canonical_hosts() -> None:
    assert HOSTS == {"cursor", "claude", "codex", "chatgpt", "kiro", "generic"}
    assert validate_host_adapter_interface(ROOT) == []
    assert capability_support(ROOT, "codex", "scm") == "full"
    assert capability_support(ROOT, "chatgpt", "terminal") == "unsupported"
    with pytest.raises(ValueError):
        capability_support(ROOT, "unknown-host", "scm")
    with pytest.raises(ValueError):
        capability_support(ROOT, "codex", "unknown-capability")


def test_host_packaging_semantics_validate() -> None:
    assert validate_host_portability(ROOT) == []


def test_generic_package_is_deterministic_and_complete(tmp_path: Path) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    build_generic_package(ROOT, first)
    build_generic_package(ROOT, second)
    assert first.read_bytes() == second.read_bytes()

    registry = parse_registry(ROOT / "skills.yaml")
    with tarfile.open(first, "r:gz") as archive:
        names = set(archive.getnames())
    for skill_id, entry in registry.skills.items():
        assert f"software-builder/{entry.path}/SKILL.md" in names, skill_id
    assert "software-builder/skills.yaml" in names
    assert "software-builder/docs/skill-framework/shared/skill-routing.md" in names
    assert "software-builder/docs/skill-framework/shared/runtime-contract.md" in names
    assert not any("/.git/" in f"/{name}/" or "/.github/" in f"/{name}/" for name in names)
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
