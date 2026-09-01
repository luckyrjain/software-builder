"""Tests for discovery-precedence shadow detection (Candidate 8)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.registry.host_registry import parse_host_registry

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts" / "install.sh"


@pytest.fixture(scope="module")
def host_registry():
    return parse_host_registry(ROOT / "agent-hosts.yaml")


def _write_install(dest: Path, *, files: dict[str, str] | None = None) -> None:
    dest.mkdir(parents=True)
    manifest = {"skill": dest.name, "files": files or {"SKILL.md": "abc123"}}
    (dest / ".software-builder-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_none_when_no_higher_precedence_root_has_the_skill(host_registry, tmp_path: Path) -> None:
    from scripts.registry.shadow_detector import SHADOW_NONE, detect_shadow

    home = tmp_path / "home"
    written = home / ".claude" / "skills" / "pr-review"
    _write_install(written)

    result = detect_shadow(
        host_registry, "claude", "claude-user", written, home=home, target_dir=None
    )
    assert result.status == SHADOW_NONE
    assert result.shadowing_path is None


def test_shadowed_when_higher_precedence_root_has_different_content(
    host_registry, tmp_path: Path
) -> None:
    from scripts.registry.shadow_detector import SHADOW_SHADOWED, detect_shadow

    home = tmp_path / "home"
    project = tmp_path / "project"
    written = home / ".claude" / "skills" / "pr-review"
    _write_install(written, files={"SKILL.md": "user-version-hash"})
    higher = project / ".claude" / "skills" / "pr-review"
    _write_install(higher, files={"SKILL.md": "project-version-hash"})

    result = detect_shadow(
        host_registry, "claude", "claude-user", written, home=home, target_dir=project
    )
    assert result.status == SHADOW_SHADOWED
    assert result.shadowing_path == higher


def test_duplicate_identical_when_higher_precedence_root_has_the_same_content(
    host_registry, tmp_path: Path
) -> None:
    from scripts.registry.shadow_detector import SHADOW_DUPLICATE_IDENTICAL, detect_shadow

    home = tmp_path / "home"
    project = tmp_path / "project"
    same_files = {"SKILL.md": "identical-hash"}
    written = home / ".claude" / "skills" / "pr-review"
    _write_install(written, files=same_files)
    higher = project / ".claude" / "skills" / "pr-review"
    _write_install(higher, files=same_files)

    result = detect_shadow(
        host_registry, "claude", "claude-user", written, home=home, target_dir=project
    )
    assert result.status == SHADOW_DUPLICATE_IDENTICAL
    assert result.shadowing_path == higher


def test_unknown_precedence_when_higher_precedence_root_has_unreadable_manifest(
    host_registry, tmp_path: Path
) -> None:
    from scripts.registry.shadow_detector import SHADOW_UNKNOWN_PRECEDENCE, detect_shadow

    home = tmp_path / "home"
    project = tmp_path / "project"
    written = home / ".claude" / "skills" / "pr-review"
    _write_install(written)
    higher = project / ".claude" / "skills" / "pr-review"
    higher.mkdir(parents=True)
    (higher / ".software-builder-manifest.json").write_text("{not valid json", encoding="utf-8")

    result = detect_shadow(
        host_registry, "claude", "claude-user", written, home=home, target_dir=project
    )
    assert result.status == SHADOW_UNKNOWN_PRECEDENCE
    assert result.shadowing_path == higher


def test_none_when_higher_precedence_root_directory_does_not_exist(
    host_registry, tmp_path: Path
) -> None:
    from scripts.registry.shadow_detector import SHADOW_NONE, detect_shadow

    home = tmp_path / "home"
    project = tmp_path / "project"
    written = home / ".claude" / "skills" / "pr-review"
    _write_install(written)

    result = detect_shadow(
        host_registry, "claude", "claude-user", written, home=home, target_dir=project
    )
    assert result.status == SHADOW_NONE


def test_none_when_written_target_is_already_the_highest_precedence(
    host_registry, tmp_path: Path
) -> None:
    """Writing to claude-project (precedence 10) has nothing higher above it to check."""
    from scripts.registry.shadow_detector import SHADOW_NONE, detect_shadow

    project = tmp_path / "project"
    written = project / ".claude" / "skills" / "pr-review"
    _write_install(written)

    result = detect_shadow(
        host_registry, "claude", "claude-project", written, home=tmp_path / "home", target_dir=project
    )
    assert result.status == SHADOW_NONE


def test_none_when_written_target_id_is_unknown_for_the_host(host_registry, tmp_path: Path) -> None:
    from scripts.registry.shadow_detector import SHADOW_NONE, detect_shadow

    written = tmp_path / "somewhere" / "pr-review"
    _write_install(written)

    result = detect_shadow(
        host_registry, "claude", "not-a-real-target", written, home=tmp_path, target_dir=None
    )
    assert result.status == SHADOW_NONE


def test_none_when_written_destinations_own_manifest_is_unreadable(
    host_registry, tmp_path: Path
) -> None:
    """written_dest is what install.sh itself just staged and moved into place -- a missing or
    corrupt manifest there means something else is wrong (checked separately elsewhere), not a
    shadow question, and must not be mistaken for the read_manifest_file failure on the *higher*
    precedence root (which reports SHADOW_UNKNOWN_PRECEDENCE instead -- see the test above)."""
    from scripts.registry.shadow_detector import SHADOW_NONE, detect_shadow

    home = tmp_path / "home"
    project = tmp_path / "project"
    written = home / ".claude" / "skills" / "pr-review"
    written.mkdir(parents=True)
    (written / ".software-builder-manifest.json").write_text("{not valid json", encoding="utf-8")
    higher = project / ".claude" / "skills" / "pr-review"
    _write_install(higher)

    result = detect_shadow(
        host_registry, "claude", "claude-user", written, home=home, target_dir=project
    )
    assert result.status == SHADOW_NONE
    assert result.shadowing_path is None


def test_shadow_precedence_is_scoped_to_the_written_bindings_own_surface(
    host_registry, tmp_path: Path
) -> None:
    """agent-hosts.yaml only guarantees precedence numbers are unique within one surface, not
    across a host's whole surface list -- detect_shadow must compare precedence only within the
    surface written_target_id belongs to, not flatten every surface into one ordering. Regression
    test for a host with two surfaces whose precedence numbers legitimately overlap."""
    from scripts.registry.host_registry import (
        DiscoveryBinding,
        HostRegistry,
        HostSpec,
        CapabilitySpec,
        ConstraintsSpec,
        IsolationSpec,
        SurfaceSpec,
        TargetSpec,
    )
    from scripts.registry.shadow_detector import SHADOW_NONE, detect_shadow

    home = tmp_path / "home"
    cloud_root = tmp_path / "cloud"
    local_target = TargetSpec(id="demo-local", scope="user", path="~/.demo/skills")
    cloud_target = TargetSpec(id="demo-cloud", scope="user", path="~/.demo/cloud-skills")
    registry = HostRegistry(
        schema_version=1,
        targets={local_target.id: local_target, cloud_target.id: cloud_target},
        aliases={},
        hosts={
            "demo": HostSpec(
                id="demo",
                surfaces=(
                    SurfaceSpec(
                        kind="LOCAL",
                        discovery=(DiscoveryBinding(target=local_target, mode="NATIVE", precedence=10),),
                    ),
                    # Same precedence number (10) as the LOCAL surface above -- legal, because
                    # host_registry.py's uniqueness check is scoped per-surface, not per-host.
                    SurfaceSpec(
                        kind="CLOUD",
                        discovery=(DiscoveryBinding(target=cloud_target, mode="NATIVE", precedence=10),),
                    ),
                ),
                capabilities=CapabilitySpec(),
                isolation=IsolationSpec(mode="UNKNOWN"),
                constraints=ConstraintsSpec(),
                verification="UNVERIFIED",
                evidence=(),
                maintainer_support="BEST_EFFORT",
            )
        },
    )

    written = home / ".demo" / "skills" / "pr-review"
    _write_install(written)
    cloud_written = cloud_root / ".demo" / "cloud-skills" / "pr-review"
    _write_install(cloud_written, files={"SKILL.md": "unrelated-cloud-copy"})

    result = detect_shadow(
        registry, "demo", "demo-local", written, home=home, target_dir=None
    )
    # The CLOUD surface's binding must never be compared against the LOCAL surface's precedence,
    # even though the raw numbers collide -- the fix returns NONE; the pre-fix flattened logic
    # would have treated the identical-precedence CLOUD binding as neither strictly higher nor
    # excluded, and any future surface with a *lower* number would incorrectly report a shadow.
    assert result.status == SHADOW_NONE


def test_host_label_map_stays_in_sync_with_the_legacy_resolvers_label_set() -> None:
    """HOST_LABEL_TO_HOST_AND_TARGET (this module), legacy_install_resolver.py's
    _SINGLE_DEST_ROUTING, and install.sh's own --agent case statement are three independent copies
    of the same "which legacy selectors/labels exist" fact (Candidate 13 maintainability finding) --
    nothing previously asserted they agree. A future selector added to one and forgotten in another
    would otherwise fail silently: shadow_detector.HOST_LABEL_TO_HOST_AND_TARGET.get(label) would
    return None and cmd_check_shadow would report SHADOW_NONE for that host forever, with no error."""
    from scripts.registry.legacy_install_resolver import _SINGLE_DEST_ROUTING
    from scripts.registry.shadow_detector import HOST_LABEL_TO_HOST_AND_TARGET

    assert set(HOST_LABEL_TO_HOST_AND_TARGET) == set(_SINGLE_DEST_ROUTING)

    agent_case_line = re.search(
        r'^case "\$\{AGENT\}" in\n([a-z][a-z0-9 |-]*)\)',
        INSTALLER.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert agent_case_line is not None, "could not find install.sh's --agent validation case line"
    installer_agents = {token.strip() for token in agent_case_line.group(1).split("|")}
    assert installer_agents == set(_SINGLE_DEST_ROUTING) | {"all", "agents"}
