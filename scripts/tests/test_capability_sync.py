from __future__ import annotations

from pathlib import Path

from scripts.registry.capability_sync import validate_capability_catalog_sync


def _write_fixture(root: Path, *, registry_required: str, catalog_required: str) -> None:
    registry_dir = root / "scripts" / "registry"
    registry_dir.mkdir(parents=True)
    (root / "skills.yaml").write_text(
        f"""
schema_version: 1
skills:
  demo:
    capabilities:
      required: [{registry_required}]
      optional: []
""",
        encoding="utf-8",
    )
    (registry_dir / "capability_catalog.yaml").write_text(
        f"""
skills:
  demo:
    required: [{catalog_required}]
    optional: []
""",
        encoding="utf-8",
    )


def test_capability_sync_treats_required_order_as_semantically_equal(tmp_path: Path) -> None:
    _write_fixture(
        tmp_path,
        registry_required="host.repository.read, host.test_runner.execute",
        catalog_required="host.test_runner.execute, host.repository.read",
    )

    assert validate_capability_catalog_sync(tmp_path) == []


def test_capability_sync_reports_real_content_drift(tmp_path: Path) -> None:
    _write_fixture(
        tmp_path,
        registry_required="host.repository.read",
        catalog_required="host.repository.write",
    )

    assert validate_capability_catalog_sync(tmp_path) == [
        "error: capability catalog content drift: demo",
    ]


def test_capability_sync_resolves_extends_profile(tmp_path: Path) -> None:
    # `extends:` only touches authority/entrypoint/hosts/invocation/risk_class/
    # supported_hosts/version_source -- capabilities always stay inline, so a
    # skill using extends should sync exactly like a fully-inlined one.
    registry_dir = tmp_path / "scripts" / "registry"
    registry_dir.mkdir(parents=True)
    (tmp_path / "skills.yaml").write_text(
        """
schema_version: 1
profiles:
  read-only-leaf-review:
    authority: read-only
skills:
  demo:
    extends: read-only-leaf-review
    capabilities:
      required: [host.repository.read]
      optional: []
""",
        encoding="utf-8",
    )
    (registry_dir / "capability_catalog.yaml").write_text(
        """
skills:
  demo:
    required: [host.repository.read]
    optional: []
""",
        encoding="utf-8",
    )

    assert validate_capability_catalog_sync(tmp_path) == []


def test_capability_sync_reports_missing_catalog_file(tmp_path: Path) -> None:
    (tmp_path / "skills.yaml").write_text("schema_version: 1\nskills: {}\n", encoding="utf-8")

    errors = validate_capability_catalog_sync(tmp_path)
    assert len(errors) == 1
    assert errors[0].startswith("error: capability catalog sync:")
