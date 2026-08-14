from __future__ import annotations

from pathlib import Path

from scripts.registry.routing_sync import ROUTING_DOC_RELATIVE, validate_skill_routing_references
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


def test_real_routing_doc_has_no_dangling_or_missing_references() -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    assert validate_skill_routing_references(ROOT, registry) == []


def test_dangling_skill_reference_is_rejected(tmp_path: Path) -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    doc_path = tmp_path / ROUTING_DOC_RELATIVE
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text("Route to **totally-unregistered-skill**.\n", encoding="utf-8")

    errors = validate_skill_routing_references(tmp_path, registry)
    assert any("totally-unregistered-skill" in error for error in errors)


def test_missing_route_for_a_registered_skill_is_rejected(tmp_path: Path) -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    doc_path = tmp_path / ROUTING_DOC_RELATIVE
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text("Route to **pr-review** only.\n", encoding="utf-8")

    errors = validate_skill_routing_references(tmp_path, registry)
    assert any("squad-map" in error for error in errors)


def test_missing_routing_doc_is_not_an_error(tmp_path: Path) -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    assert validate_skill_routing_references(tmp_path, registry) == []
