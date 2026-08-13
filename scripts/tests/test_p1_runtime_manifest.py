from __future__ import annotations

from pathlib import Path

from scripts.registry.runtime_manifest import P1_CONTRACT_KEYS, build_runtime_manifest

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_manifest_exposes_all_p1_contracts() -> None:
    manifest = build_runtime_manifest(ROOT)
    contracts = manifest["contracts"]
    assert set(P1_CONTRACT_KEYS).issubset(contracts)
    assert contracts["execution_context"]["default_max_depth"] == 3
    assert contracts["input_resolution"]["order"][0] == "supplied_facts"
    assert contracts["artifact_ownership"]["consumers_may_silently_rewrite"] is False
