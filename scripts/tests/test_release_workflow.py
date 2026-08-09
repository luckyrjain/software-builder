"""Tests for release tagging and compatibility matrix generation."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_verify_release_tag_matches_version(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.4.0\n", encoding="utf-8")
    from scripts.verify_release_tag import main

    assert main(["v1.4.0", "--repo-root", str(tmp_path)]) == 0
    assert main(["v1.3.0", "--repo-root", str(tmp_path)]) == 1


def test_compatibility_matrix_lists_all_skills() -> None:
    from scripts.registry.generate_compatibility import render_compatibility_matrix
    from scripts.registry.schema import parse_registry

    text = render_compatibility_matrix(ROOT)
    registry = parse_registry(ROOT / "skills.yaml")
    assert "GENERATED from skills.yaml" in text
    for skill_id in registry.skills:
        assert f"`{skill_id}`" in text
