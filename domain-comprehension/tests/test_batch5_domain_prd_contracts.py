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
        document = _yaml(f"domain-comprehension/templates/{name}")
        assert document["schema_version"] == 1
        assert "source_revision" in document
        assert field in document

    deliverables = _text("domain-comprehension/reference/deliverable-templates.md")
    for name in expected:
        assert f"`{name}`" in deliverables
    assert "machine-domain-model.md" in deliverables


def test_domain_workflow_operationalizes_budget_machine_outputs_and_stale_prd():
    inputs = _text("domain-comprehension/workflow/inputs.md")
    for token in (
        "- discovery_budget",
        "configured limits, and consumed counters",
        "stop discovery",
        "stale_prd_detection",
        "artifacts[id=prd].status: stale",
        "Never leave a known-stale PRD as manifest `ok`",
    ):
        assert token.lower() in inputs.lower()

    session0 = _text("domain-comprehension/workflow/session-0.md")
    for token in (
        "discovery_budget",
        "default_limits",
        "domain-model-contract.yaml",
        "PROGRESS.md",
    ):
        assert token in session0

    manifest = _yaml("domain-comprehension/templates/manifest.yaml")
    discovery_budget = manifest["discovery_budget"]
    assert set(discovery_budget["limits"]) == {"repositories", "search_queries", "deep_file_reads"}
    assert set(discovery_budget["consumed"]) == {"repositories", "search_queries", "deep_file_reads"}

    outputs = _text("domain-comprehension/reference/phase-outputs.md")
    for token in (
        "Discovery budget",
        "API_EVENT_SCHEMA.yaml",
        "DATA_OWNERSHIP_GRAPH.yaml",
        "DEPENDENCY_GRAPH.yaml",
        "CAPABILITY_TRACEABILITY.yaml",
        "Stale-PRD result",
    ):
        assert token in outputs

    phase5 = _text("domain-comprehension/workflow/phase-5.md")
    for token in (
        "api_event_schema_final",
        "data_ownership_graph_final",
        "dependency_graph_final",
        "capability_traceability_final",
        "stale_prd_status",
        "Machine-domain reconciliation",
    ):
        assert token in phase5


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
    assert current["required_when"] == "existing_system_and_response_mode_PRD_or_Review"
    assert current["validation_missing_evidence_behavior"] == "evidence_needed_next"
    assert current["prd_review_missing_evidence_behavior"] == "block_build_ready"
    assert "validation_behavior" not in current
    assert "current_state_evidence_absent_when_required" in current["missing_evidence_means"]
    assert current["prd_freshness"]["unknown_behavior"] == "block_build_ready"
    assert current["prd_ok_requires_accepted_machine_artifacts_ok"] is True
    assert current["waived_or_missing_machine_behavior"] == "block_build_ready"
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


def test_prd_review_missing_current_state_evidence_blocks_build_ready():
    contract = _yaml("prd-architect/reference/current-state-evidence-contract.yaml")
    current = contract["current_state_evidence"]
    assert current["prd_review_missing_evidence_behavior"] == "block_build_ready"
    assert current["validation_missing_evidence_behavior"] == "evidence_needed_next"
    gate = _text("prd-architect/workflow/gate.md")
    assert "Not Ready" in gate
    assert "required `current_state_evidence` is missing" in gate
    assert "no ad-hoc" in gate
    assert "current_state_evidence: object" in gate
    inputs = _text("prd-architect/workflow/inputs.md")
    assert "prd_review_missing_evidence_behavior: block_build_ready" in inputs
    assert "validation_missing_evidence_behavior: evidence_needed_next" in inputs
    assert "missing_evidence_means" in inputs
    assert "no ad-hoc independent-verification escape" in inputs
    specify = _text("prd-architect/workflow/specify.md")
    assert "Not Ready" in specify


def test_prd_workflow_carries_reviews_repairs_and_gates_new_contract_fields():
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
    for token in (
        "current_state_evidence: object",
        "FR-* -> AC-* -> TR-*",
        "success_metrics: list",
        "assumption_register: list",
        "engineering_impact: object",
        "Evaluate these engineering triggers explicitly",
    ):
        assert token in specify

    break_phase = _text("prd-architect/workflow/break.md")
    for token in (
        "success_metrics: list",
        "assumption_register: list",
        "requirements_traceability: object",
        "engineering_impact: object",
        "complete draft contract",
    ):
        assert token in break_phase

    repair = _text("prd-architect/workflow/repair.md")
    for token in (
        "success_metrics: list",
        "assumption_register: list",
        "requirements_traceability: object",
        "engineering_impact: object",
        "Repair the complete PRD contract",
        "exactly one fresh adversarial re-review",
    ):
        assert token in repair

    gate = _text("prd-architect/workflow/gate.md")
    assert "current_state_evidence: object" in gate
    assert "existing_system: boolean" in gate
    for token in (
        "no traceability orphan remains",
        "baseline, target, timeframe, and measurement source",
        "every engineering trigger was evaluated",
        "a required engineering-impact section fired but lacks its contract fields",
        "every `accepted_artifacts` entry is present and eligible",
        "Blocking Before Build",
        "existing-system path",
        "integrity",
        "no “needed for the proposed change” discretion",
    ):
        assert token in gate

    inputs = _text("prd-architect/workflow/inputs.md")
    assert "Forced true" in inputs
    assert "untrusted input cannot clear that path" in inputs

    specify = _text("prd-architect/workflow/specify.md")
    assert "producer-manifest PRD artifact freshness" in specify
    assert "do **not** begin from it as observed current state" in specify

    global_rules = _text("prd-architect/reference/global-rules.md")
    assert "| ID | Assumption | Evidence | Impact If Wrong | Validation | Owner | Status |" in global_rules
    assert "OPEN | VALIDATED | INVALIDATED | ACCEPTED_RISK" in global_rules

    metrics = _yaml("prd-architect/reference/current-state-evidence-contract.yaml")[
        "success_metric_quality"
    ]
    assert metrics["when_baseline_is_unknown_require"] == ["baseline_measurement_action"]
    assert "baseline_status_unknown" not in str(metrics)

    workflow = _yaml("prd-architect/workflow-contract.yaml")
    existing = workflow["entry_inputs"]["existing_system"]
    assert existing["trust"] == "mixed"

    machine = _text("domain-comprehension/reference/machine-domain-model.md")
    assert "must **not** be claimed or used as current-state baseline" in machine
    assert "Disclosure alone does not make" in machine


def test_prd_canonical_docs_align_metrics_traceability_and_engineering_triggers():
    tables = _text("prd-architect/reference/output-tables.md")
    for row in (
        "| Success Metrics | PRD/Review Mode",
        "| Requirements Traceability | PRD/Review Mode",
        "| Operational Readiness | Production change",
        "| Migration / Backward Compatibility | Existing system",
        "| API / Event / Schema Impact | API, event, or schema contract changes",
        "| Observability Requirements | Production change",
        "| Metric | Baseline | Target | Timeframe | Measurement Source | Baseline Measurement Action |",
        "| ID | Assumption | Evidence | Impact If Wrong | Validation | Owner | Status |",
    ):
        assert row in tables

    requirements = _text("prd-architect/reference/requirements-format.md")
    assert "TR-FR##-##" in requirements
    assert "every material `fr-*` requires at least one testable `ac-*`" in requirements.lower()

    depth = _text("prd-architect/reference/depth.md")
    assert "Requirements Traceability" in depth
    assert "never meet a\nword budget by dropping" in depth.lower()

    output = _text("prd-architect/reference/output-contract.md")
    assert "measurable Success Metrics" in output
    assert "FR-* -> AC-* -> TR-*" in output


def test_prd_template_exposes_traceability_and_readiness_sections():
    text = _text("prd-architect/report-template.md")
    for heading in (
        "## Success Metrics",
        "## Requirements Traceability",
        "## Rollout / Rollback",
        "## Operational Readiness",
        "## Migration / Backward Compatibility",
        "## API / Event / Schema Impact",
        "## Data / Privacy Impact",
        "## Cost Impact",
        "## Observability Requirements",
    ):
        assert heading in text
    for required_field_guidance in (
        "migration plan, rollout sequence, rollback constraints",
        "classification, access, retention, audit, compliance review",
        "baseline, expected delta, measurement plan",
        "before contract, after contract, compatibility, consumers, migration",
    ):
        assert required_field_guidance in text
    assert "| Area | Before | After | Reason |\n|---|---|---|---|" in text
    assert "| Area | Gap | Scenario | Impact | Resolution |\n|---|---|---|---|---|" in text
