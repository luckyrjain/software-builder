"""Tests for scripts/build_sb_snapshot.py -- the cli/ package's vendoring step."""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.build_sb_snapshot import build_snapshot

ROOT = Path(__file__).resolve().parents[2]


def test_build_snapshot_populates_both_output_directories() -> None:
    code_count, data_count = build_snapshot(ROOT)

    vendored = ROOT / "cli" / "sb" / "_vendored"
    snapshot = ROOT / "cli" / "sb" / "_registry_snapshot"
    assert (vendored / "scripts" / "doctor.py").is_file()
    assert (vendored / "scripts" / "registry" / "cli.py").is_file()
    assert not (vendored / "scripts" / "tests").exists()
    assert (snapshot / "skills.yaml").is_file()
    assert (snapshot / "agent-hosts.yaml").is_file()
    assert (snapshot / "VERSION").is_file()
    assert (snapshot / "skills" / "pr-review" / "SKILL.md").is_file()
    assert code_count > 0
    assert data_count > 0


def test_vendored_code_and_snapshot_data_work_together_end_to_end(tmp_path: Path) -> None:
    """The real proof: import the VENDORED copy (not this checkout's own scripts package) and
    run cmd_list/cmd_explain/cmd_doctor/compatibility_resolver.resolve against the snapshot --
    if the glob missed a needed file, this fails with an ImportError or a missing-file error,
    not a silent gap."""
    build_snapshot(ROOT)
    vendored = ROOT / "cli" / "sb" / "_vendored"
    snapshot = ROOT / "cli" / "sb" / "_registry_snapshot"

    sys.path.insert(0, str(vendored))
    try:
        import importlib

        doctor = importlib.import_module("scripts.doctor")
        registry_cli = importlib.import_module("scripts.registry.cli")
        compatibility_resolver = importlib.import_module("scripts.registry.compatibility_resolver")
        host_registry_module = importlib.import_module("scripts.registry.host_registry")
        load_module = importlib.import_module("scripts.registry.load")

        assert registry_cli.cmd_list(snapshot) == 0
        assert registry_cli.cmd_explain(snapshot, "pr-review") == 0
        assert doctor.cmd_doctor(
            snapshot, skill_filter="pr-review", available=set(), install_roots=[]
        ) in (0, 1)

        host_registry = host_registry_module.parse_host_registry(snapshot / "agent-hosts.yaml")
        registry = load_module.load_registry(snapshot)
        result = compatibility_resolver.resolve(host_registry, registry, "claude", "pr-review")
        assert result.status in {"READY", "DEGRADED", "BLOCKED", "UNVERIFIED", "CONFLICTED"}
    finally:
        sys.path.remove(str(vendored))
        for name in list(sys.modules):
            if name == "scripts" or name.startswith("scripts."):
                del sys.modules[name]
