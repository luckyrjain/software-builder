from __future__ import annotations

from pathlib import Path

from scripts.registry.install_targets_sync import MAKEFILE_RELATIVE, validate_install_targets
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


def test_real_makefile_has_no_dangling_or_missing_install_targets() -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    assert validate_install_targets(ROOT, registry) == []


def test_install_target_for_unregistered_skill_is_rejected(tmp_path: Path) -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    makefile_path = tmp_path / MAKEFILE_RELATIVE
    makefile_path.write_text(
        "install-ghost:\n\tbash scripts/install.sh totally-unregistered-skill\n",
        encoding="utf-8",
    )

    errors = validate_install_targets(tmp_path, registry)
    assert any("totally-unregistered-skill" in error for error in errors)


def test_missing_install_target_for_registered_skill_is_rejected(tmp_path: Path) -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    makefile_path = tmp_path / MAKEFILE_RELATIVE
    makefile_path.write_text(
        "install-pr-review:\n\tbash scripts/install.sh pr-review\n",
        encoding="utf-8",
    )

    errors = validate_install_targets(tmp_path, registry)
    assert any("squad-map" in error for error in errors)


def test_missing_makefile_is_not_an_error(tmp_path: Path) -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    assert validate_install_targets(tmp_path, registry) == []
