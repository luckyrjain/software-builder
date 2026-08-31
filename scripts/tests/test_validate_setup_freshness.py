"""Tests for SETUP.md freshness validation."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from scripts.validate_setup_freshness import ensure_setup_freshness


def _minimal_registry_yaml(skill_id: str) -> str:
    # ensure_setup_freshness now reads skill ids via scripts.registry.schema.registered_skill_ids,
    # which fully validates each entry (not just "skills: is a mapping") — so the fixture needs
    # every field _parse_skill_entry requires, not just `path:`.
    return (
        "schema_version: 1\n"
        "skills:\n"
        f"  {skill_id}:\n"
        f"    path: {skill_id}\n"
        "    category: testing\n"
        "    invocation: ambient\n"
        "    hosts:\n"
        "      cursor: {discovery: rule}\n"
        "      claude: {install: true}\n"
        "      kiro: {discovery: manual}\n"
        "    install:\n"
        "      requires: []\n"
        "    capabilities:\n"
        "      required: []\n"
        "    lint:\n"
        "      skill_md_max_lines: 180\n"
        f"      target: {skill_id}\n"
        "    risk_class: [read-only]\n"
    )


def _write_minimal_skill(root: Path, skill_id: str, *, external: str, reviewed: str) -> None:
    skill_dir = root / skill_id
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {skill_id}\ndescription: test\n---\n", encoding="utf-8")
    (skill_dir / "SETUP.md").write_text(
        f"# {skill_id}\n\n"
        "## Freshness\n\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        "| **Owner** | software-builder maintainers |\n"
        f"| **Last reviewed** | {reviewed} |\n"
        "| **Review cadence** | Quarterly |\n"
        f"| **External services** | {external} |\n\n"
        "See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md).\n",
        encoding="utf-8",
    )


def test_registry_skill_missing_from_setup_freshness_config(tmp_path: Path) -> None:
    (tmp_path / "skills.yaml").write_text(
        _minimal_registry_yaml("orphan-skill"),
        encoding="utf-8",
    )
    (tmp_path / "scripts/registry").mkdir(parents=True)
    (tmp_path / "scripts/registry/setup_freshness.yaml").write_text(
        "defaults:\n  last_reviewed: 2026-08-09\nskills: {}\n",
        encoding="utf-8",
    )
    errors = ensure_setup_freshness(tmp_path, write=False)
    assert any("missing from scripts/registry/setup_freshness.yaml" in e for e in errors)


def test_stale_last_reviewed_fails_validation(tmp_path: Path) -> None:
    stale = (date.today() - timedelta(days=200)).isoformat()
    skill_id = "demo-skill"
    _write_minimal_skill(tmp_path, skill_id, external="None", reviewed=stale)
    (tmp_path / "skills.yaml").write_text(
        _minimal_registry_yaml(skill_id),
        encoding="utf-8",
    )
    (tmp_path / "scripts/registry").mkdir(parents=True)
    (tmp_path / "scripts/registry/setup_freshness.yaml").write_text(
        yaml.safe_dump(
            {
                "defaults": {"last_reviewed": "2026-08-09", "max_age_days": 120},
                "skills": {skill_id: {"external_services": "None"}},
            },
        ),
        encoding="utf-8",
    )
    errors = ensure_setup_freshness(tmp_path, write=False)
    assert any("exceeds 120d cadence" in e for e in errors)


def test_unrelated_registry_schema_error_is_prefixed_and_not_mistaken_for_freshness(
    tmp_path: Path,
) -> None:
    # Regression test: registered_skill_ids() now fully validates skills.yaml (not just "skills:
    # is a mapping"), so an unrelated schema error elsewhere in the registry surfaces here too.
    # Without a clarifying prefix, someone running this validator to debug a stale SETUP.md would
    # see a risk_class/hosts/etc. error with no indication their actual target was never reached.
    (tmp_path / "skills.yaml").write_text(
        # Missing every required field _parse_skill_entry needs beyond `path` -- a genuinely
        # broken registry entry, unrelated to SETUP.md freshness.
        "schema_version: 1\nskills:\n  broken-skill:\n    path: broken-skill\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts/registry").mkdir(parents=True)
    (tmp_path / "scripts/registry/setup_freshness.yaml").write_text(
        "defaults:\n  last_reviewed: 2026-08-09\nskills: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="schema errors unrelated to SETUP.md freshness"):
        ensure_setup_freshness(tmp_path, write=False)
