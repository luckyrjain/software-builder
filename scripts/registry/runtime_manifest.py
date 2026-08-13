from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.registry.manifest import ROOT, build_manifest
from scripts.yaml_safety import load_unique_yaml_file

P1_CONTRACT_KEYS = (
    "result_envelope",
    "input_resolution",
    "source_precedence",
    "freshness",
    "handoff",
    "execution_context",
    "state_semantics",
    "artifact_ownership",
)


def build_runtime_manifest(root: Path = ROOT) -> dict[str, Any]:
    """Return the normalized skill manifest plus P1 portable runtime contracts."""
    manifest = build_manifest(root)
    platform = load_unique_yaml_file(root / "scripts/registry/platform_contracts.yaml")
    if not isinstance(platform, dict):
        raise ValueError("platform contracts must be a mapping")
    contracts = manifest.get("contracts")
    if not isinstance(contracts, dict):
        raise ValueError("platform manifest contracts must be a mapping")
    for key in P1_CONTRACT_KEYS:
        if key not in platform:
            raise ValueError(f"platform contracts missing P1 section: {key}")
        contracts[key] = platform[key]
    return manifest
