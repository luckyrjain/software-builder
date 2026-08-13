"""Tests for capability catalog backfill."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_capability_catalog_covers_all_registry_skills() -> None:
    from scripts.registry.backfill_capabilities import load_catalog
    from scripts.registry.schema import parse_registry

    catalog = load_catalog()
    registry = parse_registry(ROOT / "skills.yaml")
    assert set(catalog.keys()) == set(registry.skills.keys())


def test_all_skills_have_capabilities_block() -> None:
    from scripts.registry.backfill_capabilities import validate_capabilities_present

    assert validate_capabilities_present(ROOT / "skills.yaml") == []


def test_backfill_check_passes_on_repository() -> None:
    from scripts.registry.backfill_capabilities import cmd_backfill

    assert (
        cmd_backfill(check_only=True, overwrite=False, skills_path=ROOT / "skills.yaml") == 0
    )


def test_backfill_inserts_missing_block(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import backfill_skills_yaml_text

    skills_yaml = tmp_path / "skills.yaml"
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
skills:
  demo:
    required: [host.repository.read]
    optional: []
""",
        encoding="utf-8",
    )
    skills_yaml.write_text(
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
    updated, changes = backfill_skills_yaml_text(
        skills_yaml.read_text(encoding="utf-8"),
        catalog_path=catalog,
    )
    assert changes == ["demo"]
    assert "capabilities:" in updated
    assert "host.repository.read" in updated


def _write_two_skill_fixture(tmp_path: Path, *, alpha_capabilities: str = "") -> tuple[Path, Path]:
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
skills:
  alpha:
    required: [host.repository.read]
    optional: []
  beta:
    required: [gitlab.get_merge_request]
    optional: []
""",
        encoding="utf-8",
    )
    skills_yaml = tmp_path / "skills.yaml"
    skills_yaml.write_text(
        f"""
schema_version: 1
skills:
  alpha:
    path: alpha
    category: testing
    invocation: ambient
    install:
      requires: []
{alpha_capabilities}    lint:
      skill_md_max_lines: 180
      target: alpha
    risk_class: [read-only]

  beta:
    path: beta
    category: testing
    invocation: ambient
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: beta
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    return skills_yaml, catalog


def test_backfill_handles_multiple_skills_in_one_run(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import backfill_skills_yaml_text

    skills_yaml, catalog = _write_two_skill_fixture(tmp_path)
    updated, changes = backfill_skills_yaml_text(
        skills_yaml.read_text(encoding="utf-8"),
        catalog_path=catalog,
    )
    assert changes == ["alpha", "beta"]
    assert "host.repository.read" in updated
    assert "gitlab.get_merge_request" in updated


def test_backfill_strips_stray_top_level_capability_keys(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import backfill_skills_yaml_text

    # alpha's nested capabilities: already matches the catalog exactly, so this
    # only gets backfilled because of the stray top-level required/optional keys
    # -- exercising the "and not stray" gate itself, not the "missing/invalid
    # capabilities" path.
    skills_yaml, catalog = _write_two_skill_fixture(
        tmp_path,
        alpha_capabilities=(
            "    capabilities:\n"
            "      required: [host.repository.read]\n"
            "      optional: []\n"
            "    required: [stale.tool]\n"
            "    optional: []\n"
        ),
    )
    updated, changes = backfill_skills_yaml_text(
        skills_yaml.read_text(encoding="utf-8"),
        catalog_path=catalog,
    )
    assert "alpha" in changes
    assert "stale.tool" not in updated
    lines = updated.splitlines()
    top_level_required = [line for line in lines if line == "    required: [stale.tool]"]
    assert not top_level_required
    assert "host.repository.read" in updated


def test_backfill_handles_skill_at_end_of_file(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import backfill_skills_yaml_text

    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
skills:
  last:
    required: [host.repository.read]
    optional: []
""",
        encoding="utf-8",
    )
    skills_yaml = tmp_path / "skills.yaml"
    skills_yaml.write_text(
        """
schema_version: 1
skills:
  last:
    path: last
    category: testing
    invocation: ambient
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: last
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    updated, changes = backfill_skills_yaml_text(
        skills_yaml.read_text(encoding="utf-8"),
        catalog_path=catalog,
    )
    assert changes == ["last"]
    assert "host.repository.read" in updated
    assert updated.endswith("\n")


def test_backfill_overwrite_regenerates_drifted_catalog_entry(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import backfill_skills_yaml_text

    skills_yaml, catalog = _write_two_skill_fixture(
        tmp_path,
        alpha_capabilities="    capabilities:\n      required: [old.tool]\n      optional: []\n",
    )
    updated, changes = backfill_skills_yaml_text(
        skills_yaml.read_text(encoding="utf-8"),
        catalog_path=catalog,
        overwrite=True,
    )
    assert "alpha" in changes
    assert "old.tool" not in updated
    assert "host.repository.read" in updated


def test_backfill_overwrite_skips_when_already_matching_catalog(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import backfill_skills_yaml_text

    skills_yaml, catalog = _write_two_skill_fixture(
        tmp_path,
        alpha_capabilities="    capabilities:\n      required: [host.repository.read]\n      optional: []\n",
    )
    updated, changes = backfill_skills_yaml_text(
        skills_yaml.read_text(encoding="utf-8"),
        catalog_path=catalog,
        overwrite=True,
    )
    # alpha already matches the catalog exactly; only beta needs backfilling.
    assert changes == ["beta"]


def test_capabilities_equal_order_insensitive() -> None:
    from scripts.registry.backfill_capabilities import _capabilities_equal

    current = {"required": ["b", "a"], "optional": []}
    catalog_value = {"required": ["a", "b"], "optional": []}
    assert _capabilities_equal(current, catalog_value)


def test_backfill_overwrite_skips_matching_any_of_path_with_omitted_optional(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import backfill_skills_yaml_text

    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
skills:
  demo:
    required: []
    optional: []
    any_of:
      - name: GitHub read
        required: [github.get_pull_request, github.get_pull_request_files]
""",
        encoding="utf-8",
    )
    current = """
schema_version: 1
skills:
  demo:
    path: demo
    category: review
    invocation: ambient
    install: {requires: []}
    capabilities:
      required: []
      optional: []
      any_of:
        - name: GitHub read
          required: [github.get_pull_request, github.get_pull_request_files]
    lint: {skill_md_max_lines: 180, target: demo}
    risk_class: [read-only]
"""

    _updated, changes = backfill_skills_yaml_text(
        current,
        catalog_path=catalog,
        overwrite=True,
    )

    assert changes == []


def test_backfill_overwrite_detects_required_drift_in_any_of_path(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import backfill_skills_yaml_text

    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
skills:
  demo:
    required: []
    optional: []
    any_of:
      - name: GitHub read
        required: [github.get_pull_request, github.get_pull_request_files]
""",
        encoding="utf-8",
    )
    current = """
schema_version: 1
skills:
  demo:
    path: demo
    category: review
    invocation: ambient
    install: {requires: []}
    capabilities:
      required: []
      optional: []
      any_of:
        - name: GitHub read
          required: [github.get_pull_request, github.get_issue]
    lint: {skill_md_max_lines: 180, target: demo}
    risk_class: [read-only]
"""

    updated, changes = backfill_skills_yaml_text(
        current,
        catalog_path=catalog,
        overwrite=True,
    )

    assert changes == ["demo"]
    assert "github.get_pull_request_files" in updated
    assert "github.get_issue" not in updated


def test_capabilities_equal_rejects_without_raising_on_malformed_required() -> None:
    from scripts.registry.backfill_capabilities import _capabilities_equal

    catalog_value = {"required": ["a"], "optional": []}
    # Unhashable/non-string required items must not crash set().
    assert not _capabilities_equal({"required": [{"nested": "dict"}], "optional": []}, catalog_value)
    # Duplicate required entries must not silently collapse to "equal".
    assert not _capabilities_equal({"required": ["a", "a"], "optional": []}, catalog_value)


def test_capabilities_equal_rejects_without_raising_on_malformed_optional() -> None:
    from scripts.registry.backfill_capabilities import _capabilities_equal

    catalog_value = {"required": [], "optional": [{"name": "x", "enables": "y"}]}
    # Bare-string optional entries (schema.py's documented shorthand) must not
    # crash `.get("name")`.
    assert not _capabilities_equal({"required": [], "optional": ["x"]}, catalog_value)
    # Two optional entries sharing a name must not silently collapse to one.
    dup_current = {
        "required": [],
        "optional": [{"name": "x", "enables": "a"}, {"name": "x", "enables": "b"}],
    }
    assert not _capabilities_equal(dup_current, catalog_value)


def test_load_catalog_rejects_non_mapping_entry(tmp_path: Path) -> None:
    from scripts.registry.backfill_capabilities import load_catalog

    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("skills:\n  demo: null\n", encoding="utf-8")
    try:
        load_catalog(catalog)
    except ValueError as exc:
        assert "demo" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-mapping catalog entry")
