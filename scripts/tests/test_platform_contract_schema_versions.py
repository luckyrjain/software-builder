from __future__ import annotations

from pathlib import Path

from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def test_platform_contract_files_use_supported_schema_version() -> None:
    for relative in (
        "scripts/registry/host_contracts.yaml",
        "scripts/registry/eval_contracts.yaml",
    ):
        raw = load_unique_yaml_file(ROOT / relative)
        assert isinstance(raw, dict), relative
        assert raw.get("schema_version") == 1, relative

    # The platform contract has no standalone file: it lives only in skills.yaml, so its own
    # schema_version is checked where it is actually declared.
    manifest = load_unique_yaml_file(ROOT / "skills.yaml")
    assert manifest["contracts"]["platform"]["schema_version"] == 1
