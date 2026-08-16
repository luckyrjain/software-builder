from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str):
    return yaml.safe_load(_text(path))


def test_domain_comprehension_exposes_executable_machine_contract():
    contract = _yaml("domain-comprehension/reference/domain-model-contract.yaml")
    assert contract["producer"] == "domain-comprehension"
    assert contract["consumer"] == "prd-architect"

    budget = contract["discovery_budget"]
    assert "ADD_REPO" in budget["profile"]
    for profile in ("QUICK", "FULL", "DELTA", "ADD_REPO"):
        limits = budget["default_limits"][profile]
        assert limits["repositories"] > 0
        assert limits["search_queries"] > 0
        assert limits["deep_file_reads"] > 0
    assert "any_budget_limit_reached" in budget["stop_when"]
    assert budget["forbidden_behavior"] == "silently_exceed_budget"

    artifacts = contract["artifacts"]
    assert artifacts["api_event_schema"]["path"] == "API_EVENT_SCHEMA.yaml"
    assert artifacts["data_ownership_graph"]["path"] == "DATA_OWNERSHIP_GRAPH.yaml"
    assert artifacts["dependency_graph"]["path"] == "DEPENDENCY_GRAPH.yaml"
    assert artifacts["capability_code_ownership"]["path"] == "CAPABILITY_TRACEABILITY.yaml"

    deps = contract["dependency_edges"]
    assert deps["direction"] == "upstream | downstream"
    assert deps["interaction"] == "synchronous | asynchronous"
    assert "criticality" in deps
    assert "perspective" in deps["required_fields"]

    confidence = contract["confidence_aggregation"]
    assert confidence["ordering"] == ["UNKNOWN", "LOW", "MEDIUM", "HIGH"]
    assert confidence["section_rule"] == "minimum_material_claim"
    assert confidence["document_rule"] == "minimum_required_section"


def test_domain_machine_templates_exist_and_match_contract():
    expected = {
        "API_EVENT_SCHEMA.yaml": "records",
        "DATA_OWNERSHIP_GRAPH.yaml": "nodes",
        "DEPENDENCY_GRAPH.yaml": "edges",
        "CAPABILITY_TRACEABILITY.yaml": "capabilities",
    }
    for name, field in expected.items():
        path = f"domain-comprehension/templates/{name}"
        document = _yaml(path)
        assert document["schema_version"] == 1
        assert "source_revision" in document
        assert field in document

    deliverables = _text("domain-comprehension/reference/deliverable-templates.md")
    for name in expected:
        assert f"`{name}`" in deliverables


def test_domain_skill_requires_machine_artifacts_and_delta_staleness_check():
    text = _text("domain-comprehension/SKILL.md")
    for token in (
        "domain-model-contract.yaml",
        "API_EVENT_SCHEMA.yaml",
        "DATA_OWNERSHIP_GRAPH.yaml",
        "DEPENDENCY_GRAPH.yaml",
        "CAPABILITY_TRACEABILITY.yaml",
        "stale PRD",
        "stop PARTIAL",
    ):
        assert token in text


def test_prd_architect_has_current_state_ingestion_contract():
    contract = _yaml("prd-architect/reference/current-state-evidence-contract.yaml")
    assert contract["producer"] == "domain-comprehension"
    current = contract["current_state_evidence"]
    for artifact in (
        "PRD.md",
        "API_EVENT_SCHEMA.yaml",
        "DATA_OWNERSHIP_GRAPH.yaml",
        "DEPENDENCY_GRAPH.yaml",
        "CAPABILITY_TRACEABILITY.yaml",
    ):
        assert artifact in current["accepted_artifacts"]
    assert current["source_revision"]["required"] is True
    assert current["preserve_observed_state"] is True
    assert current["future_state_changes_must_be_explicit"] is True

    for section in (
        "assumption_register",
        "requirements_traceability",
        "success_metric_quality",
        "rollout_rollback_evidence",
        "operational_readiness",
        "backward_compatibility",
        "api_event_schema_impact",
        "data_privacy_trigger",
        "cost_trigger",
        "observability_requirements",
    ):
        assert section in contract


def test_prd_workflow_carries_and_gates_new_contract_fields():
    workflow = _yaml("prd-architect/workflow-contract.yaml")
    entry = workflow["entry_inputs"]["current_state_evidence"]
    assert entry["type"] == "object"
    assert entry["provenance"] == "domain_comprehension_or_repository"
    assert entry["trust"] == "untrusted"

    inputs = _text("prd-architect/workflow/inputs.md")
    assert "current_state_evidence: object" in inputs
    assert "artifact_set" not in inputs
    assert "preserve observed current state" in inputs.lower()

    specify = _text("prd-architect/workflow/specify.md")
    assert "current_state_evidence: object" in specify
    for token in (
        "FR-* -> AC-* -> TR-*",
        "success_metrics: list",
        "assumption_register: list",
        "engineering_impact: object",
        "Evaluate these engineering triggers explicitly",
    ):
        assert token in specify

    gate = _text("prd-architect/workflow/gate.md")
    assert "current_state_evidence: object" in gate
    for token in (
        "no traceability orphan remains",
        "baseline, target, timeframe, and measurement source",
        "every engineering trigger was evaluated",
        "a required engineering-impact section fired but lacks its contract fields",
    ):
        assert token in gate


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
