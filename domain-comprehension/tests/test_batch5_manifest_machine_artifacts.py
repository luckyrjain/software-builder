from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_manifest_tracks_required_machine_artifacts():
    manifest = yaml.safe_load(
        (ROOT / "domain-comprehension/templates/manifest.yaml").read_text(encoding="utf-8")
    )
    by_id = {item["id"]: item for item in manifest["artifacts"]}
    expected = {
        "api_event_schema": "API_EVENT_SCHEMA.yaml",
        "data_ownership_graph": "DATA_OWNERSHIP_GRAPH.yaml",
        "dependency_graph_machine": "DEPENDENCY_GRAPH.yaml",
        "capability_traceability": "CAPABILITY_TRACEABILITY.yaml",
    }
    for artifact_id, path in expected.items():
        row = by_id[artifact_id]
        assert row["path"] == path
        assert row["phase"] == "p5"
        assert row["required"] is True
        assert row["status"] == "stub"
