"""Tests for SETUP.md freshness validation."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

from scripts.validate_setup_freshness import ensure_setup_freshness


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
        "schema_version: 1\nskills:\n  orphan-skill:\n    path: orphan-skill\n",
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
        f"schema_version: 1\nskills:\n  {skill_id}:\n    path: {skill_id}\n",
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
