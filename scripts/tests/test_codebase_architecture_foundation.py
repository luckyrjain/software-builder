import tarfile
from copy import deepcopy
from pathlib import Path

from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.artifact_contracts import validate_artifact_result
from scripts.registry.canonical_manifest import load_canonical_manifest
from scripts.registry.composition_contracts import load_contracts
from scripts.registry.load import load_registry

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


def _foundation_artifact_results() -> tuple[tuple[str, str, dict], ...]:
    revision = "a" * 40

    def success_result(artifact_type: str, producer_skill: str, payload: dict) -> dict:
        return {
            "skill_result": {
                "skill": producer_skill,
                "version": "1.0.0",
                "status": "SUCCESS",
                "confidence": "HIGH",
                "source_revision": revision,
                "evidence_status": "OBSERVED",
                "artifacts": [artifact_type],
                "blockers": [],
                "recommended_next_skill": None,
                "artifact_schema_version": 1,
                "state_semantic": "proposed_state",
            },
            "provenance": {
                "source_revision": revision,
                "sources": ["repository:foundation-fixture"],
            },
            "freshness": {
                "observed_at": "2026-08-31T00:00:00Z",
                "source_revision": revision,
                "source_environment": "repository",
            },
            "definition_of_done": {
                "required_artifacts": [artifact_type],
                "required_checks": ["contract_validated"],
                "completed_checks": ["contract_validated"],
                "blocked_conditions": [],
                "partial_result_behavior": "Return an explicit partial result when evidence is missing.",
            },
            "authority": {
                "write_authority": "read-only",
                "canonical_owner": producer_skill,
            },
            "payload": payload,
        }

    return (
        (
            "module_design_spec",
            "module-design",
            success_result(
                "module_design_spec",
                "module-design",
                {
                    "title": "Charge module boundary",
                    "module_scope": {"path": "src/payments/charge.py"},
                    "responsibility": "Translate payment requests and provider failures.",
                    "callers": ["checkout"],
                    "contract_surface": [],
                    "invariants": [],
                    "dependency_direction": "Callers depend on the module-owned contract.",
                    "seams": [],
                    "adapters": [],
                    "errors": [],
                    "state_model": {},
                    "concurrency_expectations": "No shared mutable state.",
                    "performance_sensitive_behavior": "None identified.",
                    "test_surface": [],
                    "migration_plan": [],
                    "alternatives_rejected": [],
                    "unresolved_questions": [],
                },
            ),
        ),
        (
            "codebase_architecture_report",
            "codebase-architecture-review",
            success_result(
                "codebase_architecture_report",
                "codebase-architecture-review",
                {
                    "title": "Checkout architecture review",
                    "scope": {"paths": ["src/checkout"]},
                    "analysis_budget": {"files": 1, "hotspots": 0},
                    "evidence_summary": [],
                    "candidates": [],
                    "top_recommendation": {},
                    "limitations": [],
                },
            ),
        ),
    )


def test_foundation_artifact_results_match_canonical_contracts() -> None:
    for artifact_type, producer_skill, result in _foundation_artifact_results():
        assert validate_artifact_result(
            ROOT,
            artifact_type,
            result,
            producer_skill=producer_skill,
        ) == []


def test_foundation_artifact_results_reject_contract_mutations() -> None:
    for artifact_type, producer_skill, valid_result in _foundation_artifact_results():
        mutations = [
            ("missing provenance field", "provenance", "sources", "provenance missing fields: sources"),
            ("missing freshness field", "freshness", "observed_at", "freshness missing fields: observed_at"),
            ("missing authority field", "authority", "canonical_owner", "authority missing fields: canonical_owner"),
        ]
        for _label, section, field, expected_error in mutations:
            result = deepcopy(valid_result)
            del result[section][field]
            errors = validate_artifact_result(ROOT, artifact_type, result, producer_skill=producer_skill)
            assert any(expected_error in error for error in errors), errors

        result = deepcopy(valid_result)
        result["skill_result"]["skill"] = (
            "codebase-architecture-review" if producer_skill == "module-design" else "module-design"
        )
        errors = validate_artifact_result(ROOT, artifact_type, result, producer_skill=producer_skill)
        assert any("does not match trusted producer context" in error for error in errors), errors

        result = deepcopy(valid_result)
        result["skill_result"]["artifact_schema_version"] = 99
        errors = validate_artifact_result(ROOT, artifact_type, result, producer_skill=producer_skill)
        assert any("artifact schema version is unsupported" in error for error in errors), errors

        result = deepcopy(valid_result)
        result["payload"]["undeclared"] = "fixture mutation"
        errors = validate_artifact_result(ROOT, artifact_type, result, producer_skill=producer_skill)
        assert any("payload contains undeclared fields" in error for error in errors), errors

        result = deepcopy(valid_result)
        result["skill_result"]["recommended_next_skill"] = "not-registered"
        errors = validate_artifact_result(ROOT, artifact_type, result, producer_skill=producer_skill)
        assert any("recommended_next_skill must be a registered skill or null" in error for error in errors), errors


def test_existing_codebase_architecture_request_has_a_dedicated_owner() -> None:
    result = _dispatch(
        "Review this existing codebase architecture and find evidence-backed refactoring opportunities."
    )
    assert result.status == "selected", result
    assert result.owner == "codebase-architecture-review"


def test_one_module_seam_request_has_a_dedicated_owner() -> None:
    result = _dispatch(
        "Design the contract and seam for this one code-level payment module."
    )
    assert result.status == "selected", result
    assert result.owner == "module-design"


def test_proposed_architecture_still_routes_to_architecture_review() -> None:
    result = _dispatch(
        "Review this proposed architecture and its failure modes before implementation."
    )
    assert result.status == "selected", result
    assert result.owner == "architecture-review"


def test_implementation_level_design_still_routes_to_system_design() -> None:
    result = _dispatch(
        "Turn this ready PRD into an implementation-oriented system design."
    )
    assert result.status == "selected", result
    assert result.owner == "system-design"


def test_routing_rules_cover_foundation_intents_without_collisions() -> None:
    routes = (ROOT / "docs/skill-framework/shared/skill-routing.md").read_text()
    assert "codebase-architecture-review" in routes
    assert "module-design" in routes
    assert "architecture-review" in routes
    assert "system-design" in routes


def test_shared_codebase_design_doctrine_is_normative_and_complete() -> None:
    text = (ROOT / "docs/skill-framework/shared/codebase-design-principles.md").read_text()
    for heading in (
        "Contract surface", "Change locality", "Behavioral leverage", "Seam",
        "Adapter", "Cohesion", "Coupling", "Dependency direction", "Test surface",
        "Abstraction cost", "AI navigability",
    ):
        assert f"## {heading}" in text
    assert "large file" in text and "refactor" in text
    assert "does not independently prove" in text
    assert "behavior.kind" not in text


def test_module_design_contract_is_read_only_and_contains_required_boundaries() -> None:
    text = (ROOT / "module-design/SKILL.md").read_text()
    assert "name: module-design" in text
    assert "Keywords:" in text
    assert "module-design" in text
    assert "read-only" in text
    assert "Do not create an interface solely to enable mocking" in text
    assert "two materially different designs" in text
    assert "MODULE_DESIGN_SPEC.md" in text
    assert "codebase-design-principles.md" in text
    assert "prompt-injection.md" in text
    assert "safe-output.md" in text
    assert "cross-skill-escalation.md" in text
    assert len(text.splitlines()) <= 180


def test_codebase_architecture_review_contract_is_evidence_gated_and_read_only() -> None:
    text = (ROOT / "codebase-architecture-review/SKILL.md").read_text()
    assert "name: codebase-architecture-review" in text
    assert "Keywords:" in text
    assert "read-only" in text
    assert "CODEBASE_ARCHITECTURE_REVIEW.md" in text
    assert "codebase-design-principles.md" in text
    assert "200 commits" in text
    assert "180 days" in text
    assert "zero candidates" in text
    assert "falsif" in text
    assert "recommended_next_skill" in text
    assert "prompt-injection.md" in text
    assert "safe-output.md" in text
    assert "cross-skill-escalation.md" in text
    assert len(text.splitlines()) <= 180


def test_codebase_architecture_handoffs_are_offers_not_typed_dispatch() -> None:
    skill_text = (ROOT / "codebase-architecture-review/SKILL.md").read_text()
    report_text = (ROOT / "codebase-architecture-review/workflow/report.md").read_text()
    matrix_text = (ROOT / "docs/skill-framework/shared/cross-skill-escalation.md").read_text()

    assert "recommended_next_skill: null" in skill_text
    assert "optional, human-visible handoff offers" in skill_text
    assert "separate user-authorized invocation" in skill_text
    assert "module-design" in skill_text and "domain-comprehension" in skill_text
    assert "never emit it in this typed result" in report_text
    assert "codebase-architecture-review → module-design" in matrix_text
    assert "codebase-architecture-review → domain-comprehension" in matrix_text
    assert "codebase_architecture_report.recommended_next_skill" in matrix_text


def test_codebase_design_skills_have_canonical_read_only_artifact_contracts() -> None:
    manifest = load_canonical_manifest(ROOT)
    registry = load_registry(ROOT)
    artifact_types, artifact_schemas, _levels, composition = load_contracts(ROOT / "skills.yaml")
    platform = manifest["contracts"]["platform"]
    runtime = manifest["contracts"]["composition_runtime"]

    expected = {
        "module-design": {
            "artifact": "module_design_spec",
            "fields": [
                "title", "module_scope", "responsibility", "callers", "contract_surface",
                "invariants", "dependency_direction", "seams", "adapters", "errors", "state_model",
                "concurrency_expectations", "performance_sensitive_behavior", "test_surface",
                "migration_plan", "alternatives_rejected", "unresolved_questions",
            ],
            "payload_types": {
                "title": "string", "module_scope": "mapping", "responsibility": "string",
                "callers": "list", "contract_surface": "list", "invariants": "list",
                "dependency_direction": "string", "seams": "list", "adapters": "list",
                "errors": "list", "state_model": "mapping", "concurrency_expectations": "string",
                "performance_sensitive_behavior": "string", "test_surface": "list",
                "migration_plan": "list", "alternatives_rejected": "list",
                "unresolved_questions": "list",
            },
            "escalation_targets": ["system-design", "architecture-review"],
        },
        "codebase-architecture-review": {
            "artifact": "codebase_architecture_report",
            "fields": [
                "title", "scope", "analysis_budget", "evidence_summary", "candidates",
                "top_recommendation", "limitations",
            ],
            "payload_types": {
                "title": "string", "scope": "mapping", "analysis_budget": "mapping",
                "evidence_summary": "list", "candidates": "list", "top_recommendation": "mapping",
                "limitations": "list",
            },
            "escalation_targets": ["module-design", "domain-comprehension"],
        },
    }

    for skill_id, contract in expected.items():
        artifact = contract["artifact"]
        entry = registry.skills[skill_id]
        assert entry.invocation == "ambient"
        assert entry.capabilities.required == ["host.report.write", "host.repository.read"]
        assert entry.composition.invokes == []
        assert entry.composition.escalation_targets == contract["escalation_targets"]
        assert entry.install.requires == []
        assert manifest["skills"][skill_id]["type"] == "leaf"
        assert manifest["skills"][skill_id]["authority"] == "read-only"
        assert manifest["skills"][skill_id]["supported_hosts"] == [
            "chatgpt", "claude", "codex", "cursor", "generic", "kiro",
        ]
        assert manifest["skills"][skill_id]["permissions"] == {
            "repository": "read", "external_actions": "none", "unattended": False, "merge": False,
        }
        assert manifest["skills"][skill_id]["output_contract"] == {
            "produces": [artifact], "produce_fields": {artifact: contract["fields"]},
        }
        assert composition[skill_id].produces == [artifact]
        assert composition[skill_id].consumes == []
        assert composition[skill_id].produce_fields == {artifact: contract["fields"]}
        assert artifact in artifact_types
        assert artifact_schemas[artifact] == contract["fields"]
        assert platform["artifact_runtime"]["artifact_schema_versions"][artifact] == 1
        assert platform["artifact_runtime"]["state_semantics"][artifact] == "proposed_state"
        assert platform["artifact_runtime"]["allowed_state_semantics"][artifact] == ["proposed_state"]
        assert platform["artifact_runtime"]["payload_types"][artifact] == contract["payload_types"]
        assert runtime["artifact_ownership"][artifact] == {
            "mode": "canonical", "owners": [skill_id],
        }


def test_codebase_design_eval_admission_has_required_ids_and_dimension_coverage() -> None:
    from scripts.evals.__main__ import load_fixtures
    from scripts.evals.golden import load_golden_fixtures
    from scripts.evals.transcript import load_transcript_fixtures
    from scripts.yaml_safety import load_unique_yaml_file

    tier1_ids = {(case.skill, case.case_id) for case in load_fixtures(ROOT / "evals" / "fixtures")}
    tier2_ids = {
        (case.skill, case.case_id)
        for case in load_transcript_fixtures(ROOT / "evals" / "transcripts")
    }
    tier3_ids = {(case.skill, case.case_id) for case in load_golden_fixtures(ROOT / "evals" / "golden")}

    assert {
        ("module-design", "contract-boundary-read-only"),
        ("codebase-architecture-review", "evidence-gated-zero-candidate-report"),
    } <= tier1_ids
    assert {
        ("module-design", "contract-boundary"),
        ("codebase-architecture-review", "no-automatic-refactor"),
    } <= tier2_ids
    assert {
        ("module-design", "golden-contract"),
        ("module-design", "golden-injection"),
        ("codebase-architecture-review", "golden-report"),
        ("codebase-architecture-review", "golden-injection"),
    } <= tier3_ids

    required_skills = {"module-design", "codebase-architecture-review"}
    for dimension in ("positive", "negative", "ambiguous", "adversarial", "degraded"):
        raw = load_unique_yaml_file(ROOT / "evals" / dimension / "cases.yaml")
        assert isinstance(raw, dict)
        cases = raw["cases"]
        assert isinstance(cases, list)
        covered = {case["skill"] for case in cases if isinstance(case, dict)}
        assert required_skills <= covered, dimension


def test_foundation_generation_projects_skills_and_shared_doctrine(tmp_path: Path) -> None:
    from scripts.registry.cli import _collect_outputs
    from scripts.registry.generic_package import build_generic_package

    outputs = _collect_outputs(ROOT)
    skill_ids = ("module-design", "codebase-architecture-review")

    for directory, suffix in ((".cursor/rules", ".mdc"), (".kiro/steering", ".md")):
        for skill_id in skill_ids:
            path = ROOT / directory / f"{skill_id}{suffix}"
            assert path in outputs
            assert skill_id in outputs[path]
            assert "GENERATED from skills.yaml + SKILL.md" in outputs[path]

    for path in (
        ROOT / "generated/catalogue/compatibility-matrix.md",
        ROOT / "generated/catalogue/composition-deps.mmd",
        ROOT / "generated/catalogue/composition-runtime.mmd",
        ROOT / "docs/README.md",
        ROOT / "docs/REPOSITORY.md",
    ):
        assert path in outputs
        for skill_id in skill_ids:
            assert skill_id in outputs[path]

    archive_path = tmp_path / "generic-skills.tar.gz"
    build_generic_package(ROOT, archive_path)
    with tarfile.open(archive_path, "r:gz") as archive:
        members = set(archive.getnames())

    assert {
        "software-builder/module-design/SKILL.md",
        "software-builder/codebase-architecture-review/SKILL.md",
        "software-builder/docs/skill-framework/shared/codebase-design-principles.md",
    } <= members
