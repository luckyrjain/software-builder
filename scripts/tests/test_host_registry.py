"""Tests for the declarative agent host registry schema."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.registry import cli
from scripts.registry.host_registry import parse_host_registry

ROOT = Path(__file__).resolve().parents[2]


def _valid_registry() -> dict[str, Any]:
    targets = []
    hosts = []
    for host_id in ("cursor", "claude", "kiro"):
        targets.extend(
            [
                {
                    "id": f"{host_id}-user",
                    "scope": "user",
                    "path": f"~/.{host_id}/skills",
                },
                {
                    "id": f"{host_id}-project",
                    "scope": "project",
                    "path": f"{{project_root}}/.{host_id}/skills",
                },
            ]
        )
        hosts.append(
            {
                "id": host_id,
                "surfaces": [
                    {
                        "kind": "LOCAL",
                        "discovery": [
                            {
                                "target": f"{host_id}-project",
                                "mode": "NATIVE",
                                "precedence": 10,
                            },
                            {
                                "target": f"{host_id}-user",
                                "mode": "NATIVE",
                                "precedence": 20,
                            },
                        ],
                    }
                ],
                "capabilities": {
                    "host.filesystem.read": "AVAILABLE",
                    "host.repository.read_write": "UNKNOWN",
                },
                "isolation": {"mode": "UNKNOWN"},
                "constraints": [],
                "verification": "UNVERIFIED",
                "evidence": [],
                "maintainer_support": "BEST_EFFORT",
            }
        )
    return {
        "schema_version": 1,
        "targets": targets,
        "aliases": [{"id": "cursor-code", "target": "cursor"}],
        "hosts": hosts,
    }


def _parse(tmp_path: Path, raw: dict[str, Any]):
    registry_file = tmp_path / "agent-hosts.yaml"
    registry_file.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return parse_host_registry(registry_file)


def _error(tmp_path: Path, raw: dict[str, Any]) -> str:
    with pytest.raises(ValueError) as caught:
        _parse(tmp_path, raw)
    return str(caught.value)


def test_parses_valid_cursor_claude_and_kiro_local_surfaces(tmp_path: Path) -> None:
    registry = _parse(tmp_path, _valid_registry())

    assert registry.schema_version == 1
    assert sorted(registry.hosts) == ["claude", "cursor", "kiro"]
    assert registry.aliases["cursor-code"] is registry.hosts["cursor"]
    assert registry.hosts["kiro"].surfaces[0].kind == "LOCAL"
    capabilities = registry.hosts["cursor"].capabilities
    assert capabilities.state_for("host.repository.read_write") == "UNKNOWN"
    assert "host.repository.read_write" not in capabilities.available


@pytest.mark.parametrize("surface", ["LOCAL", "REMOTE", "CLOUD", "WEB", "UNKNOWN"])
def test_accepts_approved_surface_vocabulary(tmp_path: Path, surface: str) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["surfaces"][0]["kind"] = surface

    registry = _parse(tmp_path, raw)

    assert registry.hosts["cursor"].surfaces[0].kind == surface


@pytest.mark.parametrize("mode", ["NATIVE", "ALIAS", "ADAPTER", "MANUAL", "NONE"])
def test_accepts_approved_discovery_vocabulary(tmp_path: Path, mode: str) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["surfaces"][0]["discovery"][0]["mode"] = mode

    registry = _parse(tmp_path, raw)

    assert registry.hosts["cursor"].surfaces[0].discovery[0].mode == mode


@pytest.mark.parametrize(
    ("verification", "evidence"),
    [
        ("VERIFIED", [{"kind": "RUNTIME", "reference": "scripts/tests/runtime.py"}]),
        ("STALE", []),
        ("UNVERIFIED", []),
        ("CONFLICTED", []),
    ],
)
def test_accepts_approved_verification_vocabulary(
    tmp_path: Path,
    verification: str,
    evidence: list[dict[str, str]],
) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["verification"] = verification
    raw["hosts"][0]["evidence"] = evidence

    registry = _parse(tmp_path, raw)

    assert registry.hosts["cursor"].verification == verification


@pytest.mark.parametrize(
    "support",
    ["FIRST_CLASS", "BEST_EFFORT", "COMMUNITY", "MANUAL_ONLY", "DEPRECATED"],
)
def test_accepts_approved_maintainer_support_vocabulary(
    tmp_path: Path,
    support: str,
) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["maintainer_support"] = support

    registry = _parse(tmp_path, raw)

    assert registry.hosts["cursor"].maintainer_support == support


@pytest.mark.parametrize(
    "isolation",
    ["STRONG", "PARTIAL", "SEQUENTIAL_ONLY", "NONE", "UNKNOWN"],
)
def test_accepts_approved_isolation_vocabulary(tmp_path: Path, isolation: str) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["isolation"]["mode"] = isolation

    registry = _parse(tmp_path, raw)

    assert registry.hosts["cursor"].isolation.mode == isolation


@pytest.mark.parametrize(
    ("field", "removed_value", "error_field"),
    [
        ("discovery", "GENERATED", "hosts.cursor.surfaces[0].discovery[0].mode"),
        ("verification", "UNKNOWN", "hosts.cursor.verification"),
        ("maintainer_support", "SUPPORTED", "hosts.cursor.maintainer_support"),
        ("maintainer_support", "EXPERIMENTAL", "hosts.cursor.maintainer_support"),
        ("maintainer_support", "UNKNOWN", "hosts.cursor.maintainer_support"),
        ("isolation", "PROCESS", "hosts.cursor.isolation.mode"),
        ("isolation", "WORKSPACE", "hosts.cursor.isolation.mode"),
    ],
)
def test_rejects_removed_enum_values(
    tmp_path: Path,
    field: str,
    removed_value: str,
    error_field: str,
) -> None:
    raw = _valid_registry()
    host = raw["hosts"][0]
    if field == "discovery":
        host["surfaces"][0]["discovery"][0]["mode"] = removed_value
    elif field == "isolation":
        host["isolation"]["mode"] = removed_value
    else:
        host[field] = removed_value

    assert error_field in _error(tmp_path, raw)


def test_rejects_duplicate_host_ids(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["hosts"].append(deepcopy(raw["hosts"][0]))

    assert "hosts.cursor.id" in _error(tmp_path, raw)


def test_rejects_duplicate_target_ids(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["targets"].append(deepcopy(raw["targets"][0]))

    assert "targets.cursor-user.id" in _error(tmp_path, raw)


def test_rejects_unknown_target_reference(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["surfaces"][0]["discovery"][0]["target"] = "missing"

    assert "hosts.cursor.surfaces[0].discovery[0].target" in _error(tmp_path, raw)


def test_rejects_unknown_alias_target(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["aliases"] = [{"id": "editor", "target": "missing"}]

    assert "aliases.editor.target" in _error(tmp_path, raw)


def test_rejects_alias_id_that_collides_with_host(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["aliases"] = [{"id": "cursor", "target": "claude"}]

    assert "aliases.cursor.id" in _error(tmp_path, raw)


def test_rejects_alias_cycle(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["aliases"] = [
        {"id": "editor", "target": "coding-agent"},
        {"id": "coding-agent", "target": "editor"},
    ]

    message = _error(tmp_path, raw)
    assert "aliases.coding-agent.target" in message
    assert "cycle" in message


def test_rejects_unsupported_surface(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["surfaces"][0]["kind"] = "DESKTOP"

    assert "hosts.cursor.surfaces[0].kind" in _error(tmp_path, raw)


def test_rejects_unsupported_discovery_mode(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["surfaces"][0]["discovery"][0]["mode"] = "MAGIC"

    assert "hosts.cursor.surfaces[0].discovery[0].mode" in _error(tmp_path, raw)


def test_rejects_unsupported_verification_state(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["verification"] = "TRUSTED"

    assert "hosts.cursor.verification" in _error(tmp_path, raw)


def test_rejects_unknown_capability_value(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["capabilities"]["host.filesystem.read"] = "PARTIAL"

    assert "hosts.cursor.capabilities.host.filesystem.read" in _error(tmp_path, raw)


def test_rejects_unknown_path_variable(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["targets"][1]["path"] = "{workspace}/.cursor/skills"

    assert "targets.cursor-project.path" in _error(tmp_path, raw)


def test_rejects_project_target_without_project_root(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["targets"][1]["path"] = "/tmp/.cursor/skills"

    assert "targets.cursor-project.path" in _error(tmp_path, raw)


def test_rejects_user_target_with_project_root(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["targets"][0]["path"] = "{project_root}/.cursor/skills"

    assert "targets.cursor-user.path" in _error(tmp_path, raw)


def test_rejects_path_traversal(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["targets"][0]["path"] = "~/.cursor/../skills"

    assert "targets.cursor-user.path" in _error(tmp_path, raw)


def test_rejects_second_user_home_variable(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["targets"][0]["path"] = "~/.cursor/~other/skills"

    assert "targets.cursor-user.path" in _error(tmp_path, raw)


def test_accepts_valid_project_and_user_path_templates(tmp_path: Path) -> None:
    registry = _parse(tmp_path, _valid_registry())

    assert registry.targets["cursor-user"].path == "~/.cursor/skills"
    assert registry.targets["cursor-project"].path == "{project_root}/.cursor/skills"


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "~/.cursor/$VAR/skills",
        "~/.cursor/${VAR}/skills",
        "~/.cursor/$()/skills",
        "~/.cursor/`id`/skills",
        "~/.cursor/\x01/skills",
        "~/.cursor/\x00/skills",
    ],
)
def test_rejects_unsafe_path_syntax(tmp_path: Path, unsafe_path: str) -> None:
    raw = _valid_registry()
    raw["targets"][0]["path"] = unsafe_path

    assert "targets.cursor-user.path" in _error(tmp_path, raw)


def test_rejects_malformed_evidence(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["evidence"] = [{"kind": "RUNTIME"}]

    assert "hosts.cursor.evidence[0].reference" in _error(tmp_path, raw)


def test_verified_host_requires_runtime_evidence(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["verification"] = "VERIFIED"
    raw["hosts"][0]["evidence"] = [
        {"kind": "DOCUMENTATION", "reference": "https://example.test/docs"}
    ]

    assert "hosts.cursor.verification" in _error(tmp_path, raw)


def test_rejects_unknown_top_level_field(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["unsupported"] = True

    assert "agent-hosts.yaml.unsupported" in _error(tmp_path, raw)


def test_rejects_unknown_nested_field(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["hosts"][0]["surfaces"][0]["unsupported"] = True

    assert "hosts.cursor.surfaces[0].unsupported" in _error(tmp_path, raw)


def test_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    raw = _valid_registry()
    raw["schema_version"] = 2

    assert "schema_version" in _error(tmp_path, raw)


def test_checked_in_host_registry_validates() -> None:
    registry = parse_host_registry(ROOT / "agent-hosts.yaml")

    assert sorted(registry.hosts) == ["claude", "cursor", "github-copilot", "kiro"]
    assert all(host.verification == "UNVERIFIED" for host in registry.hosts.values())
    assert all(host.maintainer_support == "BEST_EFFORT" for host in registry.hosts.values())


def test_checked_in_kiro_host_has_no_install_resolvable_target() -> None:
    """Regression for a real target/mechanism mismatch found investigating Candidate 9: a prior
    version of this file modeled Kiro with kiro-user (~/.kiro/steering) and kiro-project
    ({project_root}/.kiro/steering) targets, as if Kiro were a 5th install.sh destination like
    Cursor/Claude. In reality scripts/registry/generate_kiro.py only ever writes steering files at
    this repository's own fixed root via `make generate` -- a checked-in generated-docs artifact,
    never a per-user or per-target-repo install -- and there is no `--agent kiro` in install.sh to
    even reach one. kiro-user was pure fiction (nothing ever read or wrote ~/.kiro/steering); this
    pins the corrected single-target, non-install-resolvable shape so it can't silently regress."""
    registry = parse_host_registry(ROOT / "agent-hosts.yaml")

    assert "kiro-user" not in registry.targets
    kiro = registry.hosts["kiro"]
    bindings = [binding for surface in kiro.surfaces for binding in surface.discovery]
    assert len(bindings) == 1
    assert bindings[0].target.id == "kiro-generated"
    assert kiro.constraints.values, "kiro must document why it's not install.sh-resolvable"
    assert "not install.sh-resolvable" in kiro.constraints.values[0]

    # install.sh genuinely has no --agent kiro selector -- confirms the constraint's own claim,
    # not just that the registry says so.
    from scripts.registry.legacy_install_resolver import LEGACY_AGENT_SELECTORS

    assert "kiro" not in LEGACY_AGENT_SELECTORS


def test_checked_in_github_copilot_host_has_documentation_evidence() -> None:
    """Candidate 12: github-copilot is the first host added on documentation-tier evidence
    (spec Section 27) rather than being present since Phase 1 -- pins that its evidence entry is
    real, not empty like cursor/claude/kiro's placeholder UNVERIFIED baseline."""
    registry = parse_host_registry(ROOT / "agent-hosts.yaml")

    host = registry.hosts["github-copilot"]
    assert len(host.evidence) == 1
    assert host.evidence[0].kind == "DOCUMENTATION"
    assert host.evidence[0].reference.startswith("https://docs.github.com/")


def test_registry_cli_validates_hosts() -> None:
    assert cli.main(["validate-hosts"]) == 0
