"""Pure validators for the common artifact-v2 machine summary."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

COMMON_MACHINE_SUMMARY_FIELDS = frozenset(
    {
        "assessment_target",
        "normalized_decision",
        "findings",
        "conditions",
        "required_actions",
        "evidence_refs",
    }
)

_FINDING_FIELDS = frozenset(
    {"id", "category", "summary", "blocking", "evidence_status", "evidence_refs"}
)
_CONDITION_FIELDS = frozenset({"id", "summary", "required_before", "evidence_refs"})
_REQUIRED_ACTION_FIELDS = frozenset(
    {"id", "summary", "required_before", "verification", "evidence_refs"}
)
_SOURCE_FIELDS = frozenset(
    {"ref", "authority", "kind", "observed_at", "source_revision", "source_environment", "derived_from"}
)
_EVIDENCE_STATUSES = frozenset(
    {"OBSERVED", "INFERRED", "UNKNOWN", "CONFLICTED", "NOT_APPLICABLE"}
)
_NORMALIZED_DECISION_FIELDS = frozenset({"status", "raw_verdict"})
_DECISIONS = frozenset({"PASS", "CONDITIONAL", "FAIL", "UNKNOWN", "NOT_APPLICABLE"})
_EVIDENCE_REQUIRED_DECISIONS = frozenset({"PASS", "CONDITIONAL", "FAIL"})
_REQUIRED_BEFORE = frozenset({"IMPLEMENTATION", "MERGE", "DEPLOY", "FOLLOW_UP"})
_AUTHORITIES = frozenset(
    {"authoritative_host", "repository", "trusted_runtime", "caller", "model_knowledge"}
)
_SOURCE_KINDS = frozenset(
    {
        "scm",
        "repo_content",
        "ci",
        "runtime_metric",
        "service_metadata",
        "build_provenance",
        "artifact",
        "caller_input",
        "model_knowledge",
    }
)


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_exact_mapping(
    value: object, fields: frozenset[str], label: str
) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(value, dict):
        return None, [f"error: {label} must be a mapping"]
    errors: list[str] = []
    missing = sorted(fields - set(value))
    extra = sorted(set(value) - fields)
    if missing:
        errors.append(f"error: {label} missing fields: {', '.join(missing)}")
    if extra:
        errors.append(f"error: {label} contains undeclared fields: {', '.join(extra)}")
    return value, errors


def _validate_evidence_refs(
    value: object, label: str, *, allow_empty: bool
) -> tuple[list[str] | None, list[str]]:
    if not isinstance(value, list) or not all(_non_empty_string(ref) for ref in value):
        return None, [f"error: {label} must be a list of non-empty strings"]
    errors: list[str] = []
    if not allow_empty and not value:
        errors.append(f"error: {label} must not be empty")
    if len(value) != len(set(value)):
        errors.append(f"error: {label} must not contain duplicates")
    return value, errors


def _validate_item_strings(
    item: Mapping[str, Any], fields: tuple[str, ...], label: str
) -> list[str]:
    return [
        f"error: {label}.{field} must be a non-empty string"
        for field in fields
        if not _non_empty_string(item.get(field))
    ]


def validate_finding_item(item: object) -> list[str]:
    """Validate one exact, typed finding item."""
    parsed, errors = _validate_exact_mapping(item, _FINDING_FIELDS, "finding")
    if parsed is None:
        return errors
    errors.extend(_validate_item_strings(parsed, ("id", "category", "summary"), "finding"))
    if type(parsed.get("blocking")) is not bool:
        errors.append("error: finding.blocking must be a boolean")
    if parsed.get("evidence_status") not in _EVIDENCE_STATUSES:
        errors.append("error: finding.evidence_status must be OBSERVED|INFERRED|UNKNOWN|CONFLICTED|NOT_APPLICABLE")
    _, ref_errors = _validate_evidence_refs(
        parsed.get("evidence_refs"), "finding.evidence_refs", allow_empty=False
    )
    errors.extend(ref_errors)
    return errors


def validate_condition_item(item: object) -> list[str]:
    """Validate one exact, typed condition item."""
    parsed, errors = _validate_exact_mapping(item, _CONDITION_FIELDS, "condition")
    if parsed is None:
        return errors
    errors.extend(_validate_item_strings(parsed, ("id", "summary"), "condition"))
    if parsed.get("required_before") not in _REQUIRED_BEFORE:
        errors.append("error: condition.required_before must be IMPLEMENTATION|MERGE|DEPLOY|FOLLOW_UP")
    _, ref_errors = _validate_evidence_refs(
        parsed.get("evidence_refs"), "condition.evidence_refs", allow_empty=False
    )
    errors.extend(ref_errors)
    return errors


def validate_required_action_item(item: object) -> list[str]:
    """Validate one exact, typed required-action item."""
    parsed, errors = _validate_exact_mapping(item, _REQUIRED_ACTION_FIELDS, "required_action")
    if parsed is None:
        return errors
    errors.extend(_validate_item_strings(parsed, ("id", "summary", "verification"), "required_action"))
    if parsed.get("required_before") not in _REQUIRED_BEFORE:
        errors.append("error: required_action.required_before must be IMPLEMENTATION|MERGE|DEPLOY|FOLLOW_UP")
    _, ref_errors = _validate_evidence_refs(
        parsed.get("evidence_refs"), "required_action.evidence_refs", allow_empty=False
    )
    errors.extend(ref_errors)
    return errors


def _machine_summary_parts(
    summary: object,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    if not isinstance(summary, dict):
        return None, None, ["error: machine summary must be a mapping"]
    payload = summary.get("payload", summary)
    provenance = summary.get("provenance")
    if not isinstance(payload, dict):
        return None, None, ["error: machine summary payload must be a mapping"]
    if not isinstance(provenance, dict):
        return payload, None, ["error: provenance must be a mapping"]
    return payload, provenance, []


def _validate_source(source: object) -> list[str]:
    parsed, errors = _validate_exact_mapping(source, _SOURCE_FIELDS, "provenance.sources item")
    if parsed is None:
        return errors
    if not _non_empty_string(parsed.get("ref")):
        errors.append("error: provenance.sources item.ref must be a non-empty string")
    if parsed.get("authority") not in _AUTHORITIES:
        errors.append("error: provenance.sources item.authority has an invalid value")
    if parsed.get("kind") not in _SOURCE_KINDS:
        errors.append("error: provenance.sources item.kind has an invalid value")
    for field in ("source_revision", "source_environment"):
        value = parsed.get(field)
        if value not in (None, "UNKNOWN") and not _non_empty_string(value):
            errors.append(
                f"error: provenance.sources item.{field} must be a non-empty string, null, or UNKNOWN"
            )
    observed_at = parsed.get("observed_at")
    if observed_at not in (None, "UNKNOWN"):
        if not _non_empty_string(observed_at):
            errors.append(
                "error: provenance.sources item.observed_at must be an ISO-8601 "
                "datetime with timezone, null, or UNKNOWN"
            )
        else:
            try:
                if datetime.fromisoformat(observed_at.replace("Z", "+00:00")).tzinfo is None:
                    raise ValueError
            except ValueError:
                errors.append(
                    "error: provenance.sources item.observed_at must be an ISO-8601 "
                    "datetime with timezone, null, or UNKNOWN"
                )
    _, derived_errors = _validate_evidence_refs(
        parsed.get("derived_from"), "provenance.sources item.derived_from", allow_empty=True
    )
    errors.extend(derived_errors)
    return errors


def _typed_sources(provenance: Mapping[str, Any], errors: list[str]) -> dict[str, dict[str, Any]]:
    if set(provenance) != {"source_revision", "sources"}:
        missing = sorted({"source_revision", "sources"} - set(provenance))
        extra = sorted(set(provenance) - {"source_revision", "sources"})
        if missing:
            errors.append(f"error: provenance missing fields: {', '.join(missing)}")
        if extra:
            errors.append(f"error: provenance contains undeclared fields: {', '.join(extra)}")
    source_revision = provenance.get("source_revision")
    if source_revision not in (None, "UNKNOWN") and not _non_empty_string(source_revision):
        errors.append(
            "error: provenance.source_revision must be a non-empty string, null, or UNKNOWN"
        )
    sources = provenance.get("sources")
    if not isinstance(sources, list):
        errors.append("error: provenance.sources must be a list of typed source mappings")
        return {}
    parsed_sources: dict[str, dict[str, Any]] = {}
    for source in sources:
        errors.extend(_validate_source(source))
        if isinstance(source, dict) and _non_empty_string(source.get("ref")):
            ref = source["ref"]
            if ref in parsed_sources:
                errors.append("error: provenance.sources must not contain duplicate refs")
            else:
                parsed_sources[ref] = source
    return parsed_sources


def _sanitized_adjacency(
    sources: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, tuple[str, ...]], list[str]]:
    """Return only well-typed source edges and their unresolved-reference errors."""
    errors: list[str] = []
    adjacency: dict[str, tuple[str, ...]] = {}
    for ref, source in sources.items():
        derived_from = source.get("derived_from")
        if (
            not isinstance(derived_from, list)
            or not all(_non_empty_string(parent) for parent in derived_from)
            or len(derived_from) != len(set(derived_from))
        ):
            adjacency[ref] = ()
            continue
        adjacency[ref] = tuple(parent for parent in derived_from if parent in sources)
        for parent in derived_from:
            if parent not in sources:
                errors.append(
                    f"error: provenance.sources {ref!r} derived_from ref {parent!r} does not resolve"
                )
    return adjacency, errors


def _source_graph_errors(adjacency: Mapping[str, tuple[str, ...]]) -> list[str]:
    """Detect cycles iteratively so hostile source depth cannot exhaust the stack."""
    errors: list[str] = []
    states: dict[str, int] = {}
    for start in adjacency:
        if states.get(start) == 2:
            continue
        stack: list[tuple[str, bool]] = [(start, False)]
        while stack:
            ref, exiting = stack.pop()
            if exiting:
                states[ref] = 2
                continue
            state = states.get(ref, 0)
            if state == 2:
                continue
            if state == 1:
                errors.append(f"error: provenance.sources derived_from cycle includes {ref!r}")
                continue
            states[ref] = 1
            stack.append((ref, True))
            for parent in reversed(adjacency[ref]):
                if states.get(parent) == 1:
                    errors.append(
                        f"error: provenance.sources derived_from cycle includes {parent!r}"
                    )
                elif states.get(parent) != 2:
                    stack.append((parent, False))
    return errors


def effective_authorities(summary: object, ref: str) -> set[str]:
    """Return leaf-source authorities for one reference, preserving caller authority."""
    _payload, provenance, _errors = _machine_summary_parts(summary)
    if provenance is None or not _non_empty_string(ref):
        return set()
    sources = provenance.get("sources")
    if not isinstance(sources, list):
        return set()
    source_by_ref = {
        source.get("ref"): source
        for source in sources
        if isinstance(source, dict) and _non_empty_string(source.get("ref"))
    }

    adjacency, _errors = _sanitized_adjacency(source_by_ref)
    if ref not in adjacency:
        return set()
    authorities: set[str] = set()
    visited: set[str] = set()
    stack = [ref]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        parents = adjacency[current]
        if parents:
            stack.extend(parents)
            continue
        authority = source_by_ref[current].get("authority")
        if authority in _AUTHORITIES:
            authorities.add(authority)
    return authorities


def validate_machine_summary(summary: object) -> list[str]:
    """Validate the common payload fields plus typed envelope provenance."""
    payload, provenance, errors = _machine_summary_parts(summary)
    if payload is None or provenance is None:
        return errors
    missing = sorted(COMMON_MACHINE_SUMMARY_FIELDS - set(payload))
    if missing:
        errors.append(f"error: machine summary payload missing fields: {', '.join(missing)}")
    if not isinstance(payload.get("assessment_target"), dict) or not payload.get("assessment_target"):
        errors.append("error: assessment_target must be a non-empty mapping")
    normalized_decision, decision_errors = _validate_exact_mapping(
        payload.get("normalized_decision"),
        _NORMALIZED_DECISION_FIELDS,
        "normalized_decision",
    )
    errors.extend(decision_errors)
    decision_status: str | None = None
    if normalized_decision is not None:
        decision_status = normalized_decision.get("status")
        if decision_status not in _DECISIONS:
            errors.append(
                "error: normalized_decision.status must be "
                "PASS|CONDITIONAL|FAIL|UNKNOWN|NOT_APPLICABLE"
            )
        if not _non_empty_string(normalized_decision.get("raw_verdict")):
            errors.append("error: normalized_decision.raw_verdict must be a non-empty string")
    root_refs, root_ref_errors = _validate_evidence_refs(
        payload.get("evidence_refs"), "evidence_refs", allow_empty=True
    )
    errors.extend(root_ref_errors)

    nested_refs: set[str] = set()
    for label, validator in (
        ("findings", validate_finding_item),
        ("conditions", validate_condition_item),
        ("required_actions", validate_required_action_item),
    ):
        items = payload.get(label)
        if not isinstance(items, list):
            errors.append(f"error: {label} must be a list")
            continue
        ids: set[str] = set()
        for item in items:
            errors.extend(validator(item))
            if isinstance(item, dict):
                identifier = item.get("id")
                if _non_empty_string(identifier):
                    if identifier in ids:
                        errors.append(f"error: {label} must not contain duplicate ids")
                    ids.add(identifier)
                refs = item.get("evidence_refs")
                if isinstance(refs, list) and all(_non_empty_string(ref) for ref in refs):
                    nested_refs.update(refs)
    if root_refs is not None:
        missing_nested_refs = sorted(nested_refs - set(root_refs))
        if missing_nested_refs:
            errors.append(
                "error: evidence_refs must include every nested evidence ref: "
                + ", ".join(missing_nested_refs)
            )
        if decision_status in _EVIDENCE_REQUIRED_DECISIONS and not root_refs:
            errors.append("error: evidence_refs must identify the basis for every normalized decision")

    sources = _typed_sources(provenance, errors)
    adjacency, source_errors = _sanitized_adjacency(sources)
    errors.extend(source_errors)
    errors.extend(_source_graph_errors(adjacency))
    if root_refs is not None:
        unresolved = sorted(set(root_refs) - set(sources))
        if unresolved:
            errors.append("error: evidence_refs must resolve to provenance.sources: " + ", ".join(unresolved))
    return errors
