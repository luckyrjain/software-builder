from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _load(path: str):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def test_domain_and_prd_share_source_revision_shape():
    domain = _load("domain-comprehension/reference/domain-model-contract.yaml")
    prd = _load("prd-architect/reference/current-state-evidence-contract.yaml")

    producer = domain["source_revision"]
    consumer = prd["current_state_evidence"]["source_revision"]
    assert producer["shape"] == consumer["shape"] == "repos"
    assert producer["repo_required_fields"] == consumer["repo_required_fields"] == [
        "repo",
        "branch",
        "commit_sha",
        "observed_at",
    ]
    assert producer["unknown_rule"] == consumer["unknown_rule"]
    assert producer["build_ready_requires"] == consumer["build_ready_requires"]
    assert producer["repo_field_constraints"] == consumer["repo_field_constraints"]


def test_domain_and_prd_share_prd_freshness_values():
    domain = _load("domain-comprehension/reference/domain-model-contract.yaml")
    prd = _load("prd-architect/reference/current-state-evidence-contract.yaml")

    producer = domain["compatibility"]["prd_freshness"]
    consumer = prd["current_state_evidence"]["prd_freshness"]
    assert producer["handoff_required"] is True
    assert producer["current_value"] == consumer["current_value"] == "ok"
    assert producer["stale_value"] == consumer["stale_value"] == "stale"
    assert producer["stale_behavior"] == consumer["stale_behavior"]
    assert "integrity_check" in producer
    assert "integrity_check" in consumer


def test_prd_consumer_rejects_stale_domain_prd_as_current_state():
    prd = _load("prd-architect/reference/current-state-evidence-contract.yaml")
    current = prd["current_state_evidence"]
    freshness = current["prd_freshness"]
    assert freshness["source"] == "domain_comprehension_manifest_prd_artifact_status"
    assert freshness["current_value"] == "ok"
    assert freshness["stale_value"] == "stale"
    assert freshness["stale_behavior"] == "blocking_before_build_do_not_treat_PRD_as_current"
    assert freshness["integrity_mismatch_behavior"] == "treat_as_stale_and_block_build_ready"
    assert current["stale_behavior"] == "blocking_before_build_do_not_treat_as_current_disclosure_insufficient"


def test_all_machine_templates_use_multi_repo_source_revision():
    for name in (
        "API_EVENT_SCHEMA.yaml",
        "DATA_OWNERSHIP_GRAPH.yaml",
        "DEPENDENCY_GRAPH.yaml",
        "CAPABILITY_TRACEABILITY.yaml",
    ):
        document = _load(f"domain-comprehension/templates/{name}")
        assert document["source_revision"] == {"repos": []}
