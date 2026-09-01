"""Tests for the generated Makefile skill-roster variable."""

from __future__ import annotations

from pathlib import Path

from scripts.registry.generate_makefile_roster import (
    ALL_SKILLS_ORDER,
    generate_makefile_roster,
    render_makefile_roster,
)
from scripts.registry.load import load_registry

ROOT = Path(__file__).resolve().parents[2]


def test_render_matches_frozen_order_on_real_repo() -> None:
    registry = load_registry(ROOT)
    rendered = render_makefile_roster(registry)
    assert f"ALL_SKILLS := {' '.join(ALL_SKILLS_ORDER)}\n" in rendered
    assert set(registry.skills) == set(ALL_SKILLS_ORDER)


def test_unknown_skill_appends_after_frozen_order_instead_of_raising(tmp_path: Path) -> None:
    from scripts.registry.schema import parse_registry

    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
        """
schema_version: 1
skills:
  solo:
    path: solo
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install: {requires: []}
    capabilities:
      required: [host.repository.read]
    lint: {skill_md_max_lines: 180, target: solo}
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    registry = parse_registry(registry_file)

    rendered = render_makefile_roster(registry)

    assert "ALL_SKILLS := solo\n" in rendered


def test_generate_makefile_roster_writes_expected_path(tmp_path: Path) -> None:
    registry = load_registry(ROOT)
    outputs = generate_makefile_roster(tmp_path, registry)
    assert set(outputs) == {tmp_path / "make" / "generated-roster.mk"}
