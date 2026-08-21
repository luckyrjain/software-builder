from __future__ import annotations

from pathlib import Path

from scripts.registry.manifest import _normalize_version, _version_input, build_manifest

ROOT = Path(__file__).resolve().parents[2]


def test_legacy_numeric_version_preserves_source_minor_digits(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "---\nname: demo\nskill_version: 1.10\ndescription: Demo.\n---\n",
        encoding="utf-8",
    )

    assert _version_input(skill_md, 1.1) == "1.10"
    assert _normalize_version(_version_input(skill_md, 1.1)) == "1.10.0"


def test_repository_manifest_marks_legacy_numeric_version_source() -> None:
    skill = build_manifest(ROOT)["skills"]["mysql-to-postgres-sql"]
    assert skill["version_source"] == "skill_frontmatter_legacy_numeric"
    assert skill["version"] == "1.6.0"
