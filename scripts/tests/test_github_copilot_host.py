"""Tests for the github-copilot host (Candidate 12): discovery vocabulary validation and that
adding a fourth agent-hosts.yaml host correctly makes it a required key in every skill's own
hosts: block (Candidate 3's "host set is data-driven" design)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]

_AGENT_HOSTS_WITH_GITHUB_COPILOT = {
    "schema_version": 1,
    "targets": [
        {"id": "cursor-user", "scope": "user", "path": "~/.cursor/skills"},
        {"id": "claude-user", "scope": "user", "path": "~/.claude/skills"},
        {"id": "kiro-user", "scope": "user", "path": "~/.kiro/steering"},
        {"id": "github-copilot-user", "scope": "user", "path": "~/.copilot/skills"},
    ],
    "aliases": [],
    "hosts": [
        {
            "id": host_id,
            "surfaces": [
                {
                    "kind": "LOCAL",
                    "discovery": [{"target": f"{host_id}-user", "mode": "NATIVE", "precedence": 10}],
                }
            ],
            "capabilities": {"host.filesystem.read": "UNKNOWN"},
            "isolation": {"mode": "UNKNOWN"},
            "constraints": [],
            "verification": "UNVERIFIED",
            "evidence": [],
            "maintainer_support": "BEST_EFFORT",
        }
        for host_id in ("cursor", "claude", "kiro", "github-copilot")
    ],
}


def _skills_yaml(*, github_copilot_discovery: str) -> str:
    return f"""
schema_version: 1
skills:
  demo:
    path: demo
    category: testing
    invocation: ambient
    hosts:
      cursor: {{discovery: rule}}
      claude: {{install: true}}
      kiro: {{discovery: manual}}
      github-copilot: {{discovery: {github_copilot_discovery}}}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: demo
    risk_class: [read-only]
"""


def _write_fixture(tmp_path: Path, *, github_copilot_discovery: str) -> Path:
    (tmp_path / "agent-hosts.yaml").write_text(
        yaml.safe_dump(_AGENT_HOSTS_WITH_GITHUB_COPILOT, sort_keys=False), encoding="utf-8"
    )
    skills_path = tmp_path / "skills.yaml"
    skills_path.write_text(_skills_yaml(github_copilot_discovery=github_copilot_discovery), encoding="utf-8")
    return skills_path


@pytest.mark.parametrize("discovery", ["manual", "always"])
def test_accepts_approved_github_copilot_discovery_vocabulary(tmp_path: Path, discovery: str) -> None:
    from scripts.registry.schema import parse_registry

    skills_path = _write_fixture(tmp_path, github_copilot_discovery=discovery)

    registry = parse_registry(skills_path)

    assert registry.skills["demo"].hosts["github-copilot"].discovery == discovery


def test_rejects_unapproved_github_copilot_discovery_value(tmp_path: Path) -> None:
    from scripts.registry.schema import RegistryParseError, parse_registry

    skills_path = _write_fixture(tmp_path, github_copilot_discovery="rule")

    with pytest.raises(RegistryParseError) as excinfo:
        parse_registry(skills_path)

    assert any(
        "hosts.github-copilot.discovery invalid: 'rule'" in error for error in excinfo.value.errors
    )


def test_skill_missing_github_copilot_key_fails_closed(tmp_path: Path) -> None:
    """Once agent-hosts.yaml declares github-copilot, every skill's hosts: block must declare it
    too (Candidate 3) -- confirms this isn't silently optional for a newly added host."""
    from scripts.registry.schema import RegistryParseError, parse_registry

    (tmp_path / "agent-hosts.yaml").write_text(
        yaml.safe_dump(_AGENT_HOSTS_WITH_GITHUB_COPILOT, sort_keys=False), encoding="utf-8"
    )
    skills_path = tmp_path / "skills.yaml"
    skills_path.write_text(
        """
schema_version: 1
skills:
  demo:
    path: demo
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: demo
    risk_class: [read-only]
""",
        encoding="utf-8",
    )

    with pytest.raises(RegistryParseError) as excinfo:
        parse_registry(skills_path)

    assert any("hosts.github-copilot" in error for error in excinfo.value.errors)


def test_broken_sibling_agent_hosts_yaml_fails_closed_instead_of_falling_back(tmp_path: Path) -> None:
    """A sibling agent-hosts.yaml that exists but fails to parse is a broken registry, not an
    absent one -- Candidate 13 final-review fix. Regression for a bug where _skill_host_ids
    silently downgraded to the stale 3-host default (cursor/claude/kiro) on ANY parse failure,
    which would have made a skill missing its required hosts.github-copilot block pass validation
    instead of failing, exactly when the registry most needs it to fail loudly."""
    from scripts.registry.schema import RegistryParseError, parse_registry

    (tmp_path / "agent-hosts.yaml").write_text("not: [valid, host, registry", encoding="utf-8")
    skills_path = tmp_path / "skills.yaml"
    skills_path.write_text(
        """
schema_version: 1
skills:
  demo:
    path: demo
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: demo
    risk_class: [read-only]
""",
        encoding="utf-8",
    )

    with pytest.raises(RegistryParseError):
        parse_registry(skills_path)


def test_real_repo_skills_all_declare_github_copilot_discovery() -> None:
    """End-to-end: every one of the 38 checked-in skills already migrated for the new host, not
    just a representative sample."""
    from scripts.registry.schema import ALLOWED_GITHUB_COPILOT_DISCOVERY, parse_registry

    registry = parse_registry(ROOT / "skills.yaml")

    assert len(registry.skills) > 0
    for skill_id, entry in registry.skills.items():
        assert "github-copilot" in entry.hosts, skill_id
        assert entry.hosts["github-copilot"].discovery in ALLOWED_GITHUB_COPILOT_DISCOVERY, skill_id
