"""Host adapter interface and host packaging semantics.

The generic bundle these adapters ultimately ship is exercised separately in
test_generic_package.py; this module stays on the host-facing seam.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts.registry import cli as registry_cli
from scripts.registry.host_adapter import (
    HOSTS,
    capability_support,
    validate_host_adapter_identities,
    validate_host_adapter_interface,
)
from scripts.registry.host_portability import (
    HOST_BRANCH_RE,
    _claude_marketplace_errors,
    _plugin_errors,
    _runtime_host_branch_errors,
    validate_host_portability,
)

ROOT = Path(__file__).resolve().parents[2]


def test_host_adapter_interface_covers_canonical_hosts() -> None:
    assert HOSTS == {"cursor", "claude", "codex", "chatgpt", "kiro", "generic"}
    assert validate_host_adapter_interface(ROOT) == []
    assert validate_host_adapter_identities(ROOT) == []
    assert capability_support(ROOT, "codex", "scm") == "full"
    assert capability_support(ROOT, "chatgpt", "terminal") == "unsupported"
    with pytest.raises(ValueError):
        capability_support(ROOT, "unknown-host", "scm")
    with pytest.raises(ValueError):
        capability_support(ROOT, "codex", "unknown-capability")


def test_host_adapter_interface_rejects_mixed_type_host_keys(tmp_path: Path) -> None:
    registry_dir = tmp_path / "scripts" / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "host_contracts.yaml").write_text(
        "schema_version: 1\ncapability_families: []\nallowed_support: []\nhosts:\n  1: {}\n  cursor: {}\n",
        encoding="utf-8",
    )

    errors = validate_host_adapter_interface(tmp_path)

    assert errors and errors[0].startswith("error: host adapter interface:")


def test_host_adapter_identity_rejects_extra_parity_keys(tmp_path: Path) -> None:
    registry_dir = tmp_path / "scripts" / "registry"
    registry_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/registry/host_contracts.yaml", registry_dir / "host_contracts.yaml")
    parity_dir = tmp_path / "evals" / "host-parity"
    parity_dir.mkdir(parents=True)
    expected = ROOT / "evals/host-parity/expected.yaml"
    (parity_dir / "expected.yaml").write_text(
        expected.read_text(encoding="utf-8") + "  1: {adapter: evil}\n",
        encoding="utf-8",
    )

    errors = validate_host_adapter_identities(tmp_path)

    assert any("keys must be strings" in error for error in errors)


def test_host_branch_detector_rejects_directives_not_neutral_host_lists() -> None:
    assert HOST_BRANCH_RE.search("If running on Cursor, load .cursor/rules.")
    assert HOST_BRANCH_RE.search("On Claude Code: use the plugin adapter.")
    assert HOST_BRANCH_RE.search("For Kiro, load the steering file.")
    assert not HOST_BRANCH_RE.search(
        "Read platform-adapters.md for Cursor, ChatGPT/Codex, Claude Code, and Kiro setup.",
    )


def test_runtime_host_branch_detector_scans_workflow_and_reference_docs(tmp_path: Path) -> None:
    skill_root = tmp_path / "sample-skill"
    (skill_root / "workflow").mkdir(parents=True)
    (skill_root / "reference").mkdir()
    (skill_root / "SKILL.md").write_text("# Sample\nHost-neutral core.\n", encoding="utf-8")
    (skill_root / "workflow" / "phase.md").write_text(
        "# Phase\nOn Cursor: use the generated adapter.\n",
        encoding="utf-8",
    )
    (skill_root / "reference" / "notes.md").write_text(
        "# Notes\nSupports Cursor, Claude Code, and Kiro through adapters.\n",
        encoding="utf-8",
    )
    assert _runtime_host_branch_errors(skill_root, "sample-skill") == [
        "error: canonical skill sample-skill contains host-brand conditional logic in workflow/phase.md",
    ]


def test_host_packaging_semantics_validate() -> None:
    assert validate_host_portability(ROOT) == []


def test_host_manifests_fail_closed_on_non_object_json(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin.json"
    plugin.write_text("[]\n", encoding="utf-8")
    assert _plugin_errors(plugin, "TestHost") == ["error: TestHost package manifest must be a JSON object"]

    marketplace_dir = tmp_path / ".claude-plugin"
    marketplace_dir.mkdir()
    (marketplace_dir / "marketplace.json").write_text("[]\n", encoding="utf-8")
    assert _claude_marketplace_errors(tmp_path) == ["error: Claude marketplace manifest must be a JSON object"]


def test_registry_validate_includes_host_portability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry_cli, "_validate_for_generate", lambda root, *args, **kwargs: [])
    monkeypatch.setattr(registry_cli, "validate_runtime_manifest", lambda root: [])
    monkeypatch.setattr(
        registry_cli,
        "validate_host_portability",
        lambda root: ["error: host-portability-marker"],
    )
    assert registry_cli._validate_all(ROOT) == ["error: host-portability-marker"]
