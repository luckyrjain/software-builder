from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_domain_comprehension_exposes_machine_contract():
    contract = ROOT / "domain-comprehension/reference/domain-model-contract.yaml"
    assert contract.is_file()
    text = contract.read_text(encoding="utf-8")
    for token in (
        "discovery_budget:",
        "confidence_aggregation:",
        "api_event_schema:",
        "data_ownership_graph:",
        "interaction: synchronous | asynchronous",
        "criticality:",
        "capability_code_ownership:",
        "stale_prd_detection:",
        "consumer: prd-architect",
    ):
        assert token in text


def test_domain_skill_requires_machine_artifacts_and_delta_staleness_check():
    text = _text("domain-comprehension/SKILL.md")
    for token in (
        "domain-model-contract.yaml",
        "API_EVENT_SCHEMA.yaml",
        "DATA_OWNERSHIP_GRAPH.yaml",
        "CAPABILITY_TRACEABILITY.yaml",
        "stale PRD",
    ):
        assert token in text


def test_prd_architect_has_current_state_ingestion_contract():
    contract = ROOT / "prd-architect/reference/current-state-evidence-contract.yaml"
    assert contract.is_file()
    text = contract.read_text(encoding="utf-8")
    for token in (
        "producer: domain-comprehension",
        "current_state_evidence:",
        "source_revision:",
        "assumption_register:",
        "requirements_traceability:",
        "success_metric_quality:",
        "rollout_rollback_evidence:",
        "operational_readiness:",
        "backward_compatibility:",
        "api_event_schema_impact:",
        "data_privacy_trigger:",
        "cost_trigger:",
        "observability_requirements:",
    ):
        assert token in text


def test_prd_workflow_contract_accepts_current_state_evidence():
    text = _text("prd-architect/workflow-contract.yaml")
    assert "current_state_evidence:" in text
    assert "provenance: domain_comprehension_or_repository" in text


def test_prd_template_exposes_traceability_and_readiness_sections():
    text = _text("prd-architect/report-template.md")
    for heading in (
        "## Success Metrics",
        "## Assumption Register",
        "## Requirements Traceability",
        "## Rollout / Rollback",
        "## Operational Readiness",
        "## Migration / Backward Compatibility",
        "## API / Event / Schema Impact",
        "## Observability Requirements",
    ):
        assert heading in text
