"""The canonical runtime vocabularies every contract validator checks the registry against.

`skills.yaml`'s `contracts.platform` section declares the result envelope, handoff
envelope, execution context, state semantics, completion/confidence/evidence enums and
eval dimensions as data. Three validators independently assert that the declared data
still matches the shape the runtime was built for -- `p1_validation.validate_p1_contracts`,
`artifact_contracts.validate_artifact_contracts` and `manifest._load_platform_contracts` --
and each used to carry its own hand-copied literal of the same sets. This module is the one
place those literals live; the validators import them, so widening a vocabulary is one edit
here plus the YAML edit, and forgetting the YAML edit still fails loudly.

`assert_no_drift` is the shared shape check behind those assertions: a declared value must
be a duplicate-free list naming each canonical member exactly once.
"""

from __future__ import annotations

from typing import Any

# skills.yaml `contracts.platform.result_envelope.required_fields`.
RESULT_FIELDS = {
    "skill",
    "version",
    "status",
    "confidence",
    "source_revision",
    "evidence_status",
    "artifacts",
    "blockers",
    "recommended_next_skill",
    "artifact_schema_version",
    "state_semantic",
}
# `contracts.platform.handoff.required_fields`.
HANDOFF_FIELDS = {"target_skill", "reason", "inputs", "evidence_refs", "assumptions", "unresolved"}
# `contracts.platform.execution_context.required_fields`.
EXECUTION_FIELDS = {"invocation_id", "parent_skill", "visited_skills", "depth"}
# `contracts.platform.state_semantics.values`.
STATE_VALUES = {"current_state", "proposed_state", "desired_state", "transitional_state"}
# `contracts.platform.completion.statuses` and its required fields.
COMPLETION_STATUSES = {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "ESCALATED"}
COMPLETION_FIELDS = {"status", "evidence_status", "blockers", "artifacts", "recommended_next_skill"}
# A skill result's `confidence` band.
CONFIDENCE_VALUES = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
# `contracts.platform.evidence.statuses` and its required fields.
EVIDENCE_STATUSES = {"OBSERVED", "INFERRED", "UNKNOWN", "CONFLICTED", "NOT_APPLICABLE"}
EVIDENCE_FIELDS = {"claim", "status", "provenance", "limitations"}
# `contracts.platform.definition_of_done.required_fields`.
DEFINITION_OF_DONE_FIELDS = {
    "required_artifacts",
    "required_checks",
    "completed_checks",
    "blocked_conditions",
    "partial_result_behavior",
}
# eval_contracts.yaml `required_dimensions`.
EVAL_DIMENSIONS = {"positive", "negative", "ambiguous", "adversarial", "degraded"}

# The composition-topology axis every skill declares as `type:`. Projected into
# `contracts.platform.skill_types` and `contracts.composition_runtime.skill_types`, and
# validated against all three by canonical_manifest, manifest and composition_runtime --
# which is why the enum lives here rather than being restated in each of them.
SKILL_TYPES = {"leaf", "router", "orchestrator", "trigger"}


def assert_no_drift(actual: Any, canonical: set[str], label: str) -> list[str]:
    """Errors when `actual` does not name each member of `canonical` exactly once.

    Returns a list so callers that accumulate errors can extend it directly; an empty
    list means the declared vocabulary still matches this module.
    """
    if not isinstance(actual, list) or not all(isinstance(item, str) for item in actual):
        return [f"error: {label} must be a list of strings"]
    if len(actual) != len(set(actual)):
        return [f"error: {label} must not contain duplicates"]
    if set(actual) != canonical:
        return [f"error: {label} drift"]
    return []
