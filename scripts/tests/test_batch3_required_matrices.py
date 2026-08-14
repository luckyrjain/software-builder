from __future__ import annotations

from pathlib import Path

from scripts.yaml_safety import load_unique_yaml_file, require_mapping

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_MUTATION_CLASSES = {
    "instruction_override",
    "gate_bypass",
    "confidence_forcing",
    "unauthorized_external_action",
}
REQUIRED_UNTRUSTED_SURFACES = {
    "repository_documentation",
    "confluence_pages",
    "code_comments",
    "tickets",
    "pull_request_descriptions",
    "logs",
    "slack_threads",
    "webhook_payloads",
    "api_responses",
    "skill_artifacts",
}
REQUIRED_DEGRADED_HOST_CASES = {
    "missing_observability",
    "live_state_without_history",
    "scm_without_checkout",
    "local_git_without_scm",
    "missing_ci_visibility",
    "missing_issue_tracker",
    "missing_subagents",
}
REQUIRED_ROUTING_COLLISIONS = {
    "architecture-vs-code-review",
    "prd-vs-code-review",
    "pr-number-review",
    "prod-failure-vs-sizing",
    "resource-safety-vs-incident",
    "write-tests-vs-test-review",
    "current-state-before-change",
}


def _contract() -> dict:
    raw = load_unique_yaml_file(ROOT / "scripts" / "registry" / "eval_contracts.yaml")
    return require_mapping(raw, "eval contracts")


def test_batch3_adversarial_and_surface_matrices_are_complete() -> None:
    contract = _contract()
    mutations = require_mapping(contract.get("adversarial_classes"), "adversarial_classes")
    surfaces = require_mapping(contract.get("untrusted_surfaces"), "untrusted_surfaces")
    assert set(mutations) == REQUIRED_MUTATION_CLASSES
    assert set(surfaces) == REQUIRED_UNTRUSTED_SURFACES


def test_batch3_degraded_host_matrix_is_complete() -> None:
    contract = _contract()
    degraded = require_mapping(contract.get("degraded_host_cases"), "degraded_host_cases")
    assert set(degraded) == REQUIRED_DEGRADED_HOST_CASES


def test_batch3_routing_collision_matrix_is_complete() -> None:
    contract = _contract()
    collisions = contract.get("routing_collisions")
    assert isinstance(collisions, list)
    ids = {str(item.get("id")) for item in collisions if isinstance(item, dict)}
    assert ids == REQUIRED_ROUTING_COLLISIONS
    assert len(collisions) == len(REQUIRED_ROUTING_COLLISIONS)
