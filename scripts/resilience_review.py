"""Runtime normalization for the resilience-review specialist."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from scripts.registry.assessment_target import normalize_environment_identity
from scripts.registry.artifact_trust import _AUTHORITIES, classify_assessment_context_trust

DIMENSIONS = (
    "timeout_budgets", "retry_policy", "circuit_breaking", "load_shedding",
    "backpressure", "queue_handling", "idempotency", "downstream_behavior",
    "partial_failure_consistency", "recovery_reconciliation",
)
ALLOWED_STATE_SEMANTICS = frozenset({"proposed_state", "current_state"})
ALLOWED_AUTHORITIES = frozenset(_AUTHORITIES)
ALLOWED_KINDS = frozenset(
    {"scm", "repo_content", "ci", "runtime_metric", "service_metadata", "build_provenance",
     "artifact", "caller_input", "model_knowledge"}
)
ASSESSMENT_STATUSES = frozenset({"PASS", "CONDITIONAL", "FAIL", "UNKNOWN"})
RUNTIME_CONFIG_SOURCE_KINDS = frozenset({"runtime_metric", "service_metadata", "artifact"})
RUNTIME_CONFIG_DIMENSIONS = frozenset({"timeout_budgets", "retry_policy", "circuit_breaking"})
DEPLOYMENT_CONFIG_MARKERS = frozenset(
    {
        "config", "configuration", "configmap", "deploy", "deployment", "env", "environment",
        "helm", "ini", "k8s", "kubernetes", "manifest", "overlay", "properties", "runtime",
        "setting", "settings", "toml", "values", "yaml", "yml",
    }
)
SOURCE_CODE_SUFFIXES = (
    "c", "cc", "clj", "cljs", "cpp", "cs", "ex", "exs", "fs", "fsx", "go", "groovy",
    "h", "hpp", "hrl", "java", "js", "jsx", "kt", "kts", "lua", "php", "py", "rb",
    "rs", "scala", "swift", "ts", "tsx",
)
SOURCE_CODE_LANGUAGES = frozenset(
    {
        "c", "csharp", "clojure", "cpp", "elixir", "erlang", "fsharp", "go", "golang",
        "groovy", "java", "javascript", "kotlin", "lua", "php", "python", "ruby", "rust",
        "scala", "swift", "typescript",
    }
)
SOURCE_CODE_DECLARATION = re.compile(
    r"(?m)^\s*(?:async\s+def|class|def|export\s+(?:async\s+)?function|func|function|"
    r"interface|namespace|package|public\s+(?:class|interface)|struct)\s+\w+"
)
_MAX_UNTRUSTED_VALUE_DEPTH = 32
_MAX_UNTRUSTED_VALUE_NODES = 4_096


def _non_empty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _empty_target() -> dict[str, str]:
    return {"kind": "unknown"}


def _runtime_source(ref: str) -> dict[str, Any]:
    return {
        "ref": ref, "authority": "trusted_runtime", "kind": "artifact", "observed_at": None,
        "source_revision": "UNKNOWN", "source_environment": None, "derived_from": [],
        "dimensions": [], "environment_sensitive_dimensions": [], "markers": "",
        "source_defined_application_code": False,
    }


def _caller_source(ref: str) -> dict[str, Any]:
    source = _runtime_source(ref)
    source["authority"] = "caller"
    source["kind"] = "caller_input"
    return source


def _string_values(value: object) -> list[str] | None:
    """Collect nested strings, returning None when untrusted input exceeds safe bounds."""
    strings: list[str] = []
    stack: list[tuple[object, int, frozenset[int]]] = [(value, 0, frozenset())]
    scheduled_nodes = 1

    while stack:
        nested, depth, ancestors = stack.pop()
        if isinstance(nested, str):
            strings.append(nested)
            continue
        if not isinstance(nested, (Mapping, list, tuple)):
            continue
        if depth > _MAX_UNTRUSTED_VALUE_DEPTH or id(nested) in ancestors:
            return None

        child_ancestors = ancestors | {id(nested)}
        children: list[tuple[object, int, frozenset[int]]] = []
        values = nested.items() if isinstance(nested, Mapping) else ((None, item) for item in nested)
        for key, item in values:
            if isinstance(key, str):
                scheduled_nodes += 1
                if scheduled_nodes > _MAX_UNTRUSTED_VALUE_NODES:
                    return None
                children.append((key, depth + 1, child_ancestors))
            scheduled_nodes += 1
            if scheduled_nodes > _MAX_UNTRUSTED_VALUE_NODES:
                return None
            children.append((item, depth + 1, child_ancestors))
        stack.extend(reversed(children))

    return strings


def _source_markers(value: Mapping[str, Any]) -> tuple[str, list[str]] | None:
    markers = [value.get(field) for field in ("ref", "path", "source_path", "artifact_path", "content")]
    metadata_markers = _string_values(value.get("metadata"))
    if metadata_markers is None:
        return None
    markers.extend(metadata_markers)
    return " ".join(item.lower() for item in markers if isinstance(item, str)), metadata_markers


def _marker_tokens(markers: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", markers))


def _has_runtime_config_signal(value: object) -> bool:
    strings = _string_values(value)
    if strings is None:
        return True
    tokens = _marker_tokens(" ".join(item.lower() for item in strings))
    return bool(tokens & DEPLOYMENT_CONFIG_MARKERS)


def _source_defined_application_code(value: Mapping[str, Any], markers: str, metadata_markers: list[str]) -> bool:
    paths = " ".join(
        item.lower()
        for field in ("ref", "path", "source_path", "artifact_path")
        for item in [value.get(field)]
        if isinstance(item, str)
    )
    suffix_pattern = r"\.(?:" + "|".join(SOURCE_CODE_SUFFIXES) + r")(?:$|[\s:#?])"
    if re.search(suffix_pattern, paths):
        return True
    metadata_tokens = _marker_tokens(" ".join(item.lower() for item in metadata_markers))
    if metadata_tokens & SOURCE_CODE_LANGUAGES or {"source", "code"} <= metadata_tokens:
        return True
    content = value.get("content")
    if isinstance(content, str) and SOURCE_CODE_DECLARATION.search(content) is not None:
        return True
    return not _has_runtime_config_signal(markers)


def _normalized_source(value: object, *, trusted_authority: str = "caller") -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or not _non_empty(value.get("ref")):
        return None
    dimensions = value.get("dimensions", [])
    sensitive = value.get("environment_sensitive_dimensions", [])
    derived_from = value.get("derived_from", [])
    kind = value.get("kind")
    markers_result = _source_markers(value)
    if markers_result is None:
        return None
    markers, metadata_markers = markers_result
    return {
        "ref": value["ref"].strip(),
        "authority": trusted_authority if trusted_authority in ALLOWED_AUTHORITIES else "caller",
        "kind": kind if isinstance(kind, str) and kind in ALLOWED_KINDS else "caller_input",
        "observed_at": value.get("observed_at") if _non_empty(value.get("observed_at")) else None,
        "source_revision": value.get("source_revision") if _non_empty(value.get("source_revision")) else "UNKNOWN",
        "source_environment": value.get("source_environment") if _non_empty(value.get("source_environment")) else None,
        "derived_from": list(derived_from) if isinstance(derived_from, list) and all(_non_empty(ref) for ref in derived_from) else [],
        "dimensions": [item for item in dimensions if item in DIMENSIONS] if isinstance(dimensions, list) else [],
        "environment_sensitive_dimensions": [item for item in sensitive if item in DIMENSIONS] if isinstance(sensitive, list) else [],
        "markers": markers,
        "source_defined_application_code": _source_defined_application_code(value, markers, metadata_markers),
    }


def _resolve_inputs(
    invocation: Mapping[str, Any], *, runtime_metadata: object
) -> tuple[dict[str, Any], dict[str, Any], list[str], str]:
    """Resolve standalone or typed embedded inputs without treating content as directives."""
    context = invocation.get("assessment_context")
    if context is None:
        target = invocation.get("assessment_target")
        return dict(invocation), dict(target) if isinstance(target, Mapping) else _empty_target(), [], "caller"
    if not isinstance(context, dict):
        return {}, _empty_target(), ["assessment_context"], "caller"
    inputs = context.get("inputs")
    target = context.get("assessment_target")
    if not isinstance(inputs, dict) or not isinstance(target, dict):
        return {}, _empty_target(), ["assessment_context.inputs"], "caller"
    if not isinstance(context.get("input_provenance"), dict) or not isinstance(context.get("evidence_refs"), list) or not isinstance(context.get("unresolved"), list):
        return {}, _empty_target(), ["assessment_context"], "caller"
    resolved = dict(inputs)
    embedded_state = resolved.get("state_semantic")
    top_level_state = invocation.get("state_semantic")
    blockers: list[str] = []
    if embedded_state is not None and top_level_state is not None and embedded_state != top_level_state:
        blockers.append("state_semantic_conflict")
    elif top_level_state is not None:
        resolved["state_semantic"] = top_level_state
    if "dimension_assessments" in invocation:
        resolved["dimension_assessments"] = invocation["dimension_assessments"]
    resolved["_context_evidence_refs"] = [ref for ref in context["evidence_refs"] if _non_empty(ref)]
    resolved["_input_provenance"] = dict(context["input_provenance"])
    trust = classify_assessment_context_trust(context, runtime_metadata=runtime_metadata)
    return resolved, dict(target), blockers, trust.effective_authority("evidence")


def _source_supports(
    source: Mapping[str, Any],
    dimension: str,
    target: Mapping[str, Any],
    state_semantic: str,
    runtime_config_dimensions: set[str],
) -> bool:
    if dimension not in source["dimensions"]:
        return False
    target_revision = target.get("head_revision_or_digest")
    if state_semantic == "current_state" and (
        not _non_empty(target_revision) or source["source_revision"] != target_revision
    ):
        return False
    if state_semantic == "proposed_state" and _non_empty(target_revision) and source["source_revision"] != target_revision:
        return False
    target_environment = target.get("environment")
    source_environment = source["source_environment"]
    sensitive = (
        dimension in source["environment_sensitive_dimensions"]
        or dimension in runtime_config_dimensions
        or (
            dimension in RUNTIME_CONFIG_DIMENSIONS
            and source["kind"] in RUNTIME_CONFIG_SOURCE_KINDS
        )
        or (
            dimension in RUNTIME_CONFIG_DIMENSIONS
            and source["kind"] == "repo_content"
            and not source["source_defined_application_code"]
        )
    )
    if sensitive and (not _non_empty(target_environment) or not _non_empty(source_environment)):
        return False
    if _non_empty(source_environment):
        if not _non_empty(target_environment) or normalize_environment_identity(source_environment) != normalize_environment_identity(target_environment):
            return False
    return state_semantic != "current_state" or source["authority"] in {"repository", "authoritative_host"}


def _report(target: dict[str, Any], verdict: str, findings: list[dict[str, Any]], conditions: list[dict[str, Any]], required_actions: list[dict[str, Any]], evidence_refs: list[str]) -> dict[str, Any]:
    status = {
        "Approved": "PASS", "Approved with conditions": "CONDITIONAL",
        "Changes required": "FAIL", "Blocked — insufficient evidence": "UNKNOWN",
    }[verdict]
    return {
        "title": "Resilience review", "verdict": verdict, "assessment_target": target,
        "normalized_decision": {"status": status, "raw_verdict": verdict},
        "findings": findings, "conditions": conditions, "required_actions": required_actions,
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
    }


def _runtime_config_dimensions(inputs: Mapping[str, Any], behavior: object) -> set[str]:
    dimensions = inputs.get("runtime_config_dimensions", [])
    detected = {dimension for dimension in dimensions if dimension in DIMENSIONS} if isinstance(dimensions, list) else set()
    if isinstance(behavior, Mapping):
        for dimension, detail in behavior.items():
            if dimension not in DIMENSIONS:
                continue
            if _has_runtime_config_signal(detail):
                detected.add(dimension)
    return detected


def _valid_observed_at(value: object) -> str | None:
    if not _non_empty(value):
        return None
    try:
        if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
            return None
    except ValueError:
        return None
    return value


def _freshness_observed_at(
    sources: list[dict[str, Any]],
    supported_dimensions_by_ref: dict[str, set[str]],
) -> str:
    supported_dimensions: set[str] = set()
    observations: list[str] = []
    for source in sources:
        if source["authority"] not in {"repository", "authoritative_host"}:
            continue
        matched_dimensions = supported_dimensions_by_ref.get(source["ref"], set())
        if not matched_dimensions:
            continue
        observed_at = _valid_observed_at(source["observed_at"])
        if observed_at is None:
            return "UNKNOWN"
        supported_dimensions.update(matched_dimensions)
        observations.append(observed_at)
    if supported_dimensions != set(DIMENSIONS):
        return "UNKNOWN"
    return min(
        observations,
        key=lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")),
    )


def to_envelope(
    *,
    payload: dict[str, Any],
    sources: list[dict[str, Any]],
    source_revision: object,
    source_environment: object,
    observed_at: str,
    completion_status: str,
    confidence: str,
    evidence_status: str,
    blockers: list[str],
    state_semantic: str,
    completed_checks: list[str],
) -> dict[str, Any]:
    """Build the complete canonical runtime envelope for a resilience report."""
    return {
        "skill_result": {
            "skill": "resilience-review", "version": "1.0.0", "status": completion_status,
            "confidence": confidence, "source_revision": source_revision,
            "evidence_status": evidence_status, "artifacts": ["resilience_review_report"],
            "blockers": blockers, "recommended_next_skill": None, "artifact_schema_version": 1,
            "state_semantic": state_semantic,
        },
        "provenance": {
            "source_revision": source_revision,
            "sources": [{key: source[key] for key in ("ref", "authority", "kind", "observed_at", "source_revision", "source_environment", "derived_from")} for source in sources],
        },
        "freshness": {
            "observed_at": observed_at, "source_revision": source_revision,
            "source_environment": source_environment if _non_empty(source_environment) else None,
        },
        "definition_of_done": {
            "required_artifacts": ["resilience_review_report"], "required_checks": list(DIMENSIONS),
            "completed_checks": completed_checks, "blocked_conditions": blockers,
            "partial_result_behavior": "Unresolved dimensions remain explicit UNKNOWN conditions and required actions.",
        },
        "authority": {"write_authority": "read-only", "canonical_owner": "resilience-review"},
        "payload": payload,
    }


def review_resilience(invocation: Mapping[str, Any], *, runtime_metadata: object = None) -> dict[str, Any]:
    """Review all dimensions against typed evidence and return an artifact-v2 envelope."""
    if not isinstance(invocation, Mapping):
        invocation = {}
    inputs, target, blockers, evidence_authority = _resolve_inputs(invocation, runtime_metadata=runtime_metadata)
    state_semantic = inputs.get("state_semantic", "proposed_state")
    behavior = inputs.get("resilience_behavior")
    dependency_paths = inputs.get("dependency_paths")
    if not isinstance(state_semantic, str) or state_semantic not in ALLOWED_STATE_SEMANTICS:
        blockers.append("state_semantic")
    if not isinstance(behavior, Mapping) or not behavior:
        blockers.append("resilience_behavior")
    if not (isinstance(dependency_paths, list) and dependency_paths and all(_non_empty(path) for path in dependency_paths)):
        blockers.append("dependency_paths")
    if state_semantic == "current_state" and (
        target == _empty_target() or not _non_empty(target.get("head_revision_or_digest"))
    ):
        blockers.append("assessment_target")

    raw_sources = inputs.get("evidence", [])
    raw_sources = raw_sources if isinstance(raw_sources, list) else []
    sources: list[dict[str, Any]] = []
    known_refs: set[str] = set()
    for value in raw_sources:
        source = _normalized_source(value, trusted_authority=evidence_authority)
        if source and source["ref"] not in known_refs:
            sources.append(source)
            known_refs.add(source["ref"])
    input_provenance_refs: set[str] = set()
    for ref in inputs.get("_context_evidence_refs", []):
        if ref not in known_refs:
            sources.append(_caller_source(ref))
            known_refs.add(ref)
    for field, metadata in inputs.get("_input_provenance", {}).items():
        if not isinstance(field, str) or not isinstance(metadata, Mapping):
            continue
        derived_from = metadata.get("evidence_refs", [])
        if not isinstance(derived_from, list) or not all(_non_empty(ref) for ref in derived_from):
            continue
        for ref in derived_from:
            if ref not in known_refs:
                sources.append(_caller_source(ref))
                known_refs.add(ref)
        provenance_ref = f"input:{field}"
        if provenance_ref not in known_refs:
            source = _caller_source(provenance_ref)
            source["derived_from"] = list(derived_from)
            sources.append(source)
            known_refs.add(provenance_ref)
            input_provenance_refs.add(provenance_ref)

    findings: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    required_actions: list[dict[str, Any]] = []
    evidence_refs = [source["ref"] for source in sources if source["ref"] not in input_provenance_refs]
    unknown, failed, conditional = [], [], []
    assessments = inputs.get("dimension_assessments")
    assessments = assessments if isinstance(assessments, Mapping) else {}
    runtime_config_dimensions = _runtime_config_dimensions(inputs, behavior)
    supported_dimensions_by_ref: dict[str, set[str]] = {}

    for dimension in DIMENSIONS:
        fallback_ref = f"runtime:resolution:{dimension}"
        if fallback_ref not in known_refs:
            sources.append(_runtime_source(fallback_ref))
            known_refs.add(fallback_ref)
        supported_sources = [
            source
            for source in sources
            if _source_supports(source, dimension, target, state_semantic, runtime_config_dimensions)
        ]
        for source in supported_sources:
            supported_dimensions_by_ref.setdefault(source["ref"], set()).add(dimension)
        configured = assessments.get(dimension, "PASS")
        dimension_status = configured if (
            isinstance(behavior, Mapping) and _non_empty(behavior.get(dimension))
            and supported_sources and isinstance(configured, str) and configured in ASSESSMENT_STATUSES
        ) else "UNKNOWN"
        refs = [source["ref"] for source in sources if dimension in source["dimensions"]] or [fallback_ref]
        evidence_refs.extend(refs)
        label = dimension.replace("_", " ")
        if dimension_status == "FAIL":
            failed.append(dimension)
            findings.append({"id": f"failure-{dimension.replace('_', '-')}", "category": dimension,
                             "summary": f"{label} has a resilience failure requiring remediation.",
                             "blocking": True, "evidence_status": "OBSERVED", "evidence_refs": refs})
        elif dimension_status == "CONDITIONAL":
            conditional.append(dimension)
            conditions.append({"id": f"condition-{dimension.replace('_', '-')}",
                               "summary": f"{label} needs the documented mitigation before implementation.",
                               "required_before": "IMPLEMENTATION", "evidence_refs": refs})
        elif dimension_status == "UNKNOWN":
            unknown.append(dimension)
            conditions.append({"id": f"unknown-{dimension.replace('_', '-')}",
                               "summary": f"{label} lacks required, identity-matched evidence.",
                               "required_before": "IMPLEMENTATION", "evidence_refs": refs})
            required_actions.append({"id": f"evidence-{dimension.replace('_', '-')}",
                                     "summary": f"Provide authoritative evidence for {label}.",
                                     "required_before": "IMPLEMENTATION",
                                     "verification": f"Re-run resilience review with evidence covering {label}.",
                                     "evidence_refs": refs})

    if failed:
        verdict, completion_status = "Changes required", "SUCCESS"
    elif blockers:
        verdict, completion_status = "Blocked — insufficient evidence", "BLOCKED"
    elif unknown:
        verdict, completion_status = "Blocked — insufficient evidence", "PARTIAL"
    elif conditional:
        verdict, completion_status = "Approved with conditions", "SUCCESS"
    else:
        verdict, completion_status = "Approved", "SUCCESS"
    for blocker in sorted(set(blockers)):
        ref = f"runtime:missing:{blocker}"
        if ref not in known_refs:
            sources.append(_runtime_source(ref))
            known_refs.add(ref)
        evidence_refs.append(ref)
        conditions.append({"id": f"unknown-{blocker.replace('_', '-')}",
                           "summary": f"Required input {blocker} is missing or invalid.",
                           "required_before": "IMPLEMENTATION", "evidence_refs": [ref]})

    source_revision = target.get("head_revision_or_digest")
    source_revision = source_revision if _non_empty(source_revision) else "UNKNOWN"
    normalized_state = state_semantic if isinstance(state_semantic, str) and state_semantic in ALLOWED_STATE_SEMANTICS else "proposed_state"
    observed_at = _freshness_observed_at(sources, supported_dimensions_by_ref)
    source_environment = target.get("environment")
    source_environment = source_environment if _non_empty(source_environment) else None
    freshness_known = (
        source_revision not in (None, "UNKNOWN")
        and observed_at not in (None, "UNKNOWN")
        and source_environment not in (None, "UNKNOWN")
    )
    return to_envelope(
        payload=_report(target, verdict, findings, conditions, required_actions, evidence_refs),
        sources=sources,
        source_revision=source_revision,
        source_environment=source_environment,
        observed_at=observed_at,
        completion_status=completion_status,
        confidence="HIGH" if not verdict.startswith("Blocked") and freshness_known else "UNKNOWN",
        evidence_status="UNKNOWN" if unknown or blockers else "OBSERVED",
        blockers=sorted(set(blockers)),
        state_semantic=normalized_state,
        completed_checks=[dimension for dimension in DIMENSIONS if dimension not in unknown],
    )
