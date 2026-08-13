from __future__ import annotations

from pathlib import Path

from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def test_p1_contract_files_use_supported_schema_version() -> None:
    for relative in (
        "scripts/registry/platform_contracts.yaml",
        "scripts/registry/host_contracts.yaml",
        "scripts/registry/eval_contracts.yaml",
    ):
        raw = load_unique_yaml_file(ROOT / relative)
        assert isinstance(raw, dict), relative
        assert raw.get("schema_version") == 1, relative
