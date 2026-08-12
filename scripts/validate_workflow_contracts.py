#!/usr/bin/env python3
"""Validate workflow producer/consumer contracts across every declared route."""

from __future__ import annotations

import argparse
import itertools
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ENTRY_INPUT_KEYS = {"type", "provenance", "required", "trust"}
CONTRACT_KEYS = {
    "schema_version",
    "entry_inputs",
    "selector_domains",
    "route_selection",
    "routes",
}
ROUTE_SELECTION_KEYS = {"after_phase"}
ROUTE_KEYS = {"when", "phases"}
CONSUMES_KEYS = {"required", "optional", "conditional"}
CONDITIONAL_INPUT_KEYS = {"required", "optional"}
TRUST_VALUES = {"trusted", "untrusted", "mixed"}
SUPPORTED_FIELD_TYPES = {"boolean", "content", "list", "object", "string"}
PHASE_KEYS = {"workflow_version", "phase", "produces", "consumes"}
SCALAR_TYPES = (str, int, float, bool)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
MAX_YAML_CHARS = 1_000_000
MAX_YAML_NESTING = 100
# Route exhaustiveness is exponential in selector count. Reject larger spaces
# before constructing itertools.product so validation time and memory stay bounded.
MAX_SELECTOR_STATES = 256


class DuplicateKeyError(yaml.YAMLError):
    """Raised when YAML would otherwise silently overwrite a mapping key."""


class DuplicateKeySafeLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects duplicate keys recursively."""


def _construct_unique_mapping(
    loader: DuplicateKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        # Fully construct keys so malformed collection keys have deterministic content
        # instead of PyYAML's still-empty deferred placeholder.
        key = loader.construct_object(key_node, deep=True)
        try:
            hash(key)
        except TypeError as exc:
            raise DuplicateKeyError(f"unhashable YAML mapping key {key!r}") from exc
        if key in mapping:
            raise DuplicateKeyError(f"duplicate YAML mapping key {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


DuplicateKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_unique_yaml(text: str) -> Any:
    if len(text) > MAX_YAML_CHARS:
        raise yaml.YAMLError(f"YAML input exceeds {MAX_YAML_CHARS} characters")
    # Parser events distinguish real YAML collections from brackets in quoted or
    # block scalars and comments, while still running before recursive construction.
    depth = 0
    for event in yaml.parse(text, Loader=yaml.SafeLoader):
        if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
            depth += 1
            if depth > MAX_YAML_NESTING:
                raise yaml.YAMLError(f"YAML nesting exceeds {MAX_YAML_NESTING} levels")
        elif isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
            depth -= 1
    try:
        return yaml.load(text, Loader=DuplicateKeySafeLoader)
    except RecursionError as exc:
        raise yaml.YAMLError("YAML nesting exceeds safe decoder limits") from exc


def _load_unique_frontmatter(path: Path) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("missing YAML frontmatter")
    data = _load_unique_yaml(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data


@dataclass(frozen=True)
class PhaseContract:
    name: str
    produces: dict[str, str]
    required: dict[str, str]
    optional: dict[str, str]
    conditional: dict[str, dict[str, dict[str, str]]]


def _valid_mapping_keys(value: dict[object, Any], *, location: str, errors: list[str]) -> set[str]:
    """Return usable string keys while reporting malformed keys deterministically."""
    valid: set[str] = set()
    for key in value:
        if not isinstance(key, str) or not key:
            errors.append(f"{location} contains an empty or non-string mapping key {key!r}")
        else:
            valid.add(key)
    return valid


def _typed_fields(value: Any, *, location: str, errors: list[str]) -> dict[str, str]:
    if not isinstance(value, dict):
        errors.append(f"{location} must be a mapping of field names to types")
        return {}
    fields: dict[str, str] = {}
    for name, field_type in value.items():
        if not isinstance(name, str) or not name:
            errors.append(f"{location} contains an empty or non-string field name")
        elif not isinstance(field_type, str) or not field_type:
            errors.append(f"{location}.{name} must declare a non-empty string type")
        elif field_type not in SUPPORTED_FIELD_TYPES:
            errors.append(
                f"{location}.{name} has unsupported type {field_type!r}; supported types: "
                + ", ".join(sorted(SUPPORTED_FIELD_TYPES))
            )
        else:
            fields[name] = field_type
    return fields


def _load_phases(skill_dir: Path, errors: list[str]) -> dict[str, PhaseContract]:
    workflow_dir = skill_dir / "workflow"
    if not workflow_dir.is_dir():
        errors.append("missing workflow directory")
        return {}

    phases: dict[str, PhaseContract] = {}
    for path in sorted(workflow_dir.glob("*.md")):
        try:
            frontmatter = _load_unique_frontmatter(path)
        except UnicodeError:
            errors.append(f"{path.name}: file is not valid UTF-8")
            continue
        except (OSError, ValueError, yaml.YAMLError, RecursionError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        frontmatter_keys = _valid_mapping_keys(
            frontmatter, location=f"{path.name} frontmatter", errors=errors
        )
        unknown_phase_keys = sorted(frontmatter_keys - PHASE_KEYS)
        if unknown_phase_keys:
            errors.append(f"{path.name}: unknown frontmatter keys: {', '.join(unknown_phase_keys)}")
        missing_phase_keys = sorted(PHASE_KEYS - frontmatter_keys)
        if missing_phase_keys:
            errors.append(f"{path.name}: missing frontmatter keys: {', '.join(missing_phase_keys)}")
        workflow_version = frontmatter.get("workflow_version")
        if isinstance(workflow_version, bool) or not isinstance(workflow_version, (int, float)):
            errors.append(f"{path.name}: workflow_version must be a number")
        elif workflow_version <= 0:
            # workflow_version is a per-file edit counter (bumped on every substantive change to
            # that phase doc, see docs/skill-framework/README.md), not a contract-schema
            # compatibility marker — schema_version (top-level in workflow-contract.yaml) is what
            # gates that. It has no natural upper bound: real values across this repo already
            # range from 1.0 to 3.4 with irregular increments. Only reject the genuinely invalid
            # shape (non-positive), not an arbitrary ceiling that breaks every time a mature
            # skill's phase file gets its Nth edit.
            errors.append(f"{path.name}: workflow_version must be a positive number, got {workflow_version!r}")
        phase = frontmatter.get("phase")
        if not isinstance(phase, str) or not phase:
            errors.append(f"{path.name}: phase must be a non-empty string")
            continue
        if phase in phases:
            errors.append(f"duplicate phase {phase!r}: {path.name}")
            continue

        produces = _typed_fields(
            frontmatter.get("produces"), location=f"phase '{phase}'.produces", errors=errors
        )
        consumes = frontmatter.get("consumes")
        if not isinstance(consumes, dict):
            errors.append(
                f"phase '{phase}'.consumes must contain required, optional, and conditional mappings"
            )
            continue
        consumes_keys = _valid_mapping_keys(
            consumes, location=f"phase '{phase}'.consumes", errors=errors
        )
        unknown_consumes_keys = sorted(consumes_keys - CONSUMES_KEYS)
        if unknown_consumes_keys:
            errors.append(
                f"phase '{phase}'.consumes unknown keys: {', '.join(unknown_consumes_keys)}"
            )
        missing_consumes_keys = sorted(CONSUMES_KEYS - consumes_keys)
        if missing_consumes_keys:
            errors.append(
                f"phase '{phase}'.consumes missing keys: {', '.join(missing_consumes_keys)}"
            )
        required = _typed_fields(
            consumes.get("required"),
            location=f"phase '{phase}'.consumes.required",
            errors=errors,
        )
        optional = _typed_fields(
            consumes.get("optional"),
            location=f"phase '{phase}'.consumes.optional",
            errors=errors,
        )
        conditional_raw = consumes.get("conditional")
        conditional: dict[str, dict[str, dict[str, str]]] = {}
        if not isinstance(conditional_raw, dict):
            errors.append(f"phase '{phase}'.consumes.conditional must be a mapping")
        else:
            for route_id, route_inputs in conditional_raw.items():
                location = f"phase '{phase}'.consumes.conditional.{route_id}"
                if not isinstance(route_id, str) or not route_id:
                    errors.append(
                        f"phase '{phase}'.consumes.conditional contains an empty or non-string "
                        f"mapping key {route_id!r}"
                    )
                    continue
                if not isinstance(route_inputs, dict):
                    errors.append(f"{location} must be a mapping")
                    continue
                route_input_keys = _valid_mapping_keys(route_inputs, location=location, errors=errors)
                unknown_route_input_keys = sorted(route_input_keys - CONDITIONAL_INPUT_KEYS)
                if unknown_route_input_keys:
                    errors.append(
                        f"{location} unknown keys: {', '.join(unknown_route_input_keys)}"
                    )
                missing_route_input_keys = sorted(CONDITIONAL_INPUT_KEYS - route_input_keys)
                if missing_route_input_keys:
                    errors.append(
                        f"{location} missing keys: {', '.join(missing_route_input_keys)}"
                    )
                conditional[route_id] = {
                    "required": _typed_fields(
                        route_inputs.get("required"),
                        location=f"{location}.required",
                        errors=errors,
                    ),
                    "optional": _typed_fields(
                        route_inputs.get("optional"),
                        location=f"{location}.optional",
                        errors=errors,
                    ),
                }
        phases[phase] = PhaseContract(
            name=phase,
            produces=produces,
            required=required,
            optional=optional,
            conditional=conditional,
        )
    return phases


def _load_entry_inputs(raw: Any, errors: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    if not isinstance(raw, dict):
        errors.append("entry_inputs must be a mapping")
        return {}, {}
    required: dict[str, str] = {}
    optional: dict[str, str] = {}
    for name, schema in raw.items():
        location = f"entry_inputs.{name}"
        if not isinstance(name, str) or not name:
            errors.append(f"entry_inputs contains an empty or non-string mapping key {name!r}")
            continue
        if not isinstance(schema, dict):
            errors.append(f"{location} must be a mapping")
            continue
        schema_keys = _valid_mapping_keys(schema, location=location, errors=errors)
        unknown = sorted(schema_keys - ENTRY_INPUT_KEYS)
        if unknown:
            errors.append(f"{location} unknown keys: {', '.join(unknown)}")
        missing = sorted(ENTRY_INPUT_KEYS - schema_keys)
        if missing:
            errors.append(f"{location} missing keys: {', '.join(missing)}")
            continue
        field_type = schema.get("type")
        provenance = schema.get("provenance")
        is_required = schema.get("required")
        trust = schema.get("trust")
        if not isinstance(field_type, str) or not field_type:
            errors.append(f"{location}.type must be a non-empty string")
            continue
        if field_type not in SUPPORTED_FIELD_TYPES:
            errors.append(
                f"{location}.type has unsupported type {field_type!r}; supported types: "
                + ", ".join(sorted(SUPPORTED_FIELD_TYPES))
            )
            continue
        if not isinstance(provenance, str) or not provenance:
            errors.append(f"{location}.provenance must be a non-empty string")
        if not isinstance(is_required, bool):
            errors.append(f"{location}.required must be a boolean")
            continue
        if trust not in TRUST_VALUES:
            errors.append(f"{location}.trust must be one of: {', '.join(sorted(TRUST_VALUES))}")
        (required if is_required else optional)[name] = field_type
    return required, optional


def _check_consumed_fields(
    *,
    route_id: str,
    phase: str,
    consumed: dict[str, str],
    available: dict[str, str],
    required: bool,
    errors: list[str],
) -> None:
    for name, expected_type in consumed.items():
        actual_type = available.get(name)
        if actual_type is None:
            if required:
                errors.append(
                    f"route {route_id!r}: phase {phase!r} requires {name!r}, but no required "
                    "entry input or preceding phase produces it"
                )
            else:
                errors.append(
                    f"route {route_id!r}: phase {phase!r} optionally consumes {name!r}, but no "
                    "declared entry input or preceding phase produces it"
                )
            continue
        if actual_type != expected_type:
            errors.append(
                f"route {route_id!r}: phase {phase!r} consumes {name!r} as "
                f"{expected_type!r}, but the available type is {actual_type!r}"
            )


def _predicate_value_matches_type(value: object, field_type: str) -> bool:
    if field_type == "boolean":
        return isinstance(value, bool)
    if field_type in {"string", "content"}:
        return isinstance(value, str)
    if field_type == "list":
        return isinstance(value, list)
    if field_type == "object":
        return isinstance(value, dict)
    return isinstance(value, SCALAR_TYPES)


def _parse_predicates(
    *,
    route_id: str,
    raw: Any,
    available: dict[str, str],
    errors: list[str],
) -> dict[str, tuple[str, object]] | None:
    if not isinstance(raw, dict) or not raw:
        errors.append(f"route {route_id!r}.when must be a non-empty mapping")
        return None
    parsed: dict[str, tuple[str, object]] = {}
    error_count = len(errors)
    for name, predicate in raw.items():
        location = f"route {route_id!r}.when.{name}"
        if not isinstance(name, str) or name not in available:
            errors.append(
                f"route {route_id!r}.when references unknown or unavailable predicate input {name!r}"
            )
            continue
        operator = "equals"
        value = predicate
        if isinstance(predicate, dict):
            if set(predicate) != {"not_equals"}:
                errors.append(
                    f"{location} must be a scalar equality or a single 'not_equals' predicate"
                )
                continue
            operator = "not_equals"
            value = predicate["not_equals"]
        elif not isinstance(predicate, SCALAR_TYPES):
            errors.append(
                f"{location} must be a scalar equality or a single 'not_equals' predicate"
            )
            continue
        if not _predicate_value_matches_type(value, available[name]):
            errors.append(
                f"{location} value is incompatible with declared type {available[name]!r}"
            )
            continue
        parsed[name] = (operator, value)
    return parsed if len(errors) == error_count else None


def _predicate_matches(state: dict[str, object], predicates: dict[str, tuple[str, object]]) -> bool:
    for name, (operator, value) in predicates.items():
        if operator == "equals" and state[name] != value:
            return False
        if operator == "not_equals" and state[name] == value:
            return False
    return True


def _selector_domains(
    raw: Any,
    field_types: dict[str, str],
    errors: list[str],
) -> dict[str, list[object]]:
    declared = raw if isinstance(raw, dict) else {}
    if raw is not None and not isinstance(raw, dict):
        errors.append("selector_domains must be a mapping")
    domains: dict[str, list[object]] = {}
    for name in sorted(field_types):
        field_type = field_types[name]
        if field_type == "boolean":
            domain: list[object] = [False, True]
        else:
            domain = declared.get(name)
            if not isinstance(domain, list) or not domain:
                errors.append(
                    f"selector input {name!r} with type {field_type!r} requires a non-empty "
                    "selector_domains enum"
                )
                continue
        if any(not _predicate_value_matches_type(value, field_type) for value in domain):
            errors.append(f"selector_domains.{name} contains a value incompatible with {field_type!r}")
            continue
        if len({repr(value) for value in domain}) != len(domain):
            errors.append(f"selector_domains.{name} contains duplicate values")
            continue
        domains[name] = domain
    declared_keys = _valid_mapping_keys(declared, location="selector_domains", errors=errors)
    for name in sorted(declared_keys - set(field_types)):
        errors.append(f"selector_domains declares unused selector input {name!r}")
    return domains


def _check_route_prefix(
    route_id: str,
    route_schema: dict[str, Any],
    selection_phase: str | None,
    common_prefix: list[str] | None,
    errors: list[str],
) -> tuple[list[Any] | None, bool, list[str] | None]:
    """Validate one route's declared shape and its route-selection-phase prefix.

    Returns (phase_names, valid_selection_prefix, updated_common_prefix).
    phase_names is None when `route.phases` itself is malformed — the caller must
    skip the rest of this route, matching the original inline `continue`.
    """
    route_schema_keys = _valid_mapping_keys(
        route_schema, location=f"route {route_id!r}", errors=errors
    )
    unknown_route_keys = sorted(route_schema_keys - ROUTE_KEYS)
    if unknown_route_keys:
        errors.append(
            f"route {route_id!r} unknown keys: {', '.join(unknown_route_keys)}"
        )
    phase_names = route_schema.get("phases")
    if not isinstance(phase_names, list) or not phase_names:
        errors.append(f"route {route_id!r}.phases must be a non-empty list")
        return None, False, common_prefix
    selection_count = phase_names.count(selection_phase) if selection_phase is not None else 0
    valid_selection_prefix = selection_count == 1
    if selection_phase is not None and not valid_selection_prefix:
        errors.append(
            f"route {route_id!r} must include route-selection phase {selection_phase!r} "
            f"exactly once; found {selection_count}"
        )
    if valid_selection_prefix:
        selection_index = phase_names.index(selection_phase)
        selection_prefix = phase_names[: selection_index + 1]
        if common_prefix is None:
            common_prefix = selection_prefix
        elif selection_prefix != common_prefix:
            errors.append(
                f"route {route_id!r} selection prefix {selection_prefix!r} differs from "
                f"common prefix {common_prefix!r}"
            )
    return phase_names, valid_selection_prefix, common_prefix


@dataclass
class RoutePredicateResult:
    """One route's contribution to the cross-route selector-domain check.

    route_predicate_types is intentionally not named predicate_types: the
    caller accumulates every route's contribution into its own dict of that
    name, and giving this field the identical name risked a future edit
    writing `predicate_types = result.predicate_types` (silently discarding
    every other route's contribution) where `.update(...)` was meant.
    """

    parsed: dict[str, tuple[str, object]]
    route_predicate_types: dict[str, str]


def _check_predicate_types(
    route_id: str,
    phase_names: list[Any],
    phases: dict[str, PhaseContract],
    selection_phase: str | None,
    valid_selection_prefix: bool,
    entry_required: dict[str, str],
    entry_optional: dict[str, str],
    route_schema: dict[str, Any],
    errors: list[str],
) -> RoutePredicateResult | None:
    """Walk one route's phases checking consumed-field type/availability, then parse
    its `when` predicates at the route-selection phase. Returns this route's
    predicate/field-type contribution to the cross-route selector-domain check that
    runs after every route has been walked, or None if there's nothing to contribute:
    no valid selection prefix, the route never reaches a phase matching
    `selection_phase` (including because `phase_names` references an unknown phase),
    or its `when` predicates fail to parse.
    """
    available = dict(entry_required)
    possible = {**entry_optional, **entry_required}
    selection_available: dict[str, str] | None = None
    for phase_name in phase_names:
        if not isinstance(phase_name, str) or phase_name not in phases:
            errors.append(f"route {route_id!r} references unknown phase {phase_name!r}")
            continue
        phase = phases[phase_name]
        conditional = phase.conditional.get(route_id, {})
        required = {**phase.required, **conditional.get("required", {})}
        optional = {**phase.optional, **conditional.get("optional", {})}
        _check_consumed_fields(
            route_id=route_id,
            phase=phase_name,
            consumed=required,
            available=available,
            required=True,
            errors=errors,
        )
        _check_consumed_fields(
            route_id=route_id,
            phase=phase_name,
            consumed=optional,
            available=possible,
            required=False,
            errors=errors,
        )
        available.update(phase.produces)
        possible.update(phase.produces)
        if phase_name == selection_phase and selection_available is None:
            selection_available = dict(available)
    if valid_selection_prefix and selection_available is not None:
        parsed = _parse_predicates(
            route_id=route_id,
            raw=route_schema.get("when"),
            available=selection_available,
            errors=errors,
        )
        if parsed is not None:
            # selection_available (line 545) is already a fresh copy, never mutated
            # again after this point -- no need to copy it a second time here.
            return RoutePredicateResult(parsed=parsed, route_predicate_types=selection_available)
    return None


def _check_selector_coverage(
    routes: dict[str, Any],
    parsed_predicates: dict[str, dict[str, tuple[str, object]]],
    predicate_types: dict[str, str],
    contract: dict[str, Any],
    errors: list[str],
) -> None:
    """Cartesian-exhaustiveness/overlap check over the full selector space, once every
    route's predicates parsed successfully. Appends to errors in place; the several
    early `return`s below bail out of just this coverage pass (mirroring the original
    function's early `return errors` points, which had nothing left to run after them
    either — this was always the tail of validate_skill_contract()).
    """
    if len(parsed_predicates) != len(routes):
        return
    selector_fields = {
        name for predicates in parsed_predicates.values() for name in predicates
    }
    selector_types = {name: predicate_types[name] for name in selector_fields}
    domains = _selector_domains(contract.get("selector_domains"), selector_types, errors)
    if len(domains) != len(selector_fields):
        return
    for route_id, predicates in parsed_predicates.items():
        for name, (_, value) in predicates.items():
            if value not in domains[name]:
                errors.append(
                    f"route {route_id!r}.when.{name} value {value!r} is not in "
                    f"selector_domains.{name}"
                )
    if errors:
        return
    ordered_fields = sorted(domains)
    selector_state_count = math.prod(len(domains[name]) for name in ordered_fields)
    if selector_state_count > MAX_SELECTOR_STATES:
        errors.append(
            f"selector Cartesian space has {selector_state_count} states; "
            f"maximum is {MAX_SELECTOR_STATES}"
        )
        return
    overlapping_pairs: set[tuple[str, str]] = set()
    for values in itertools.product(*(domains[name] for name in ordered_fields)):
        state = dict(zip(ordered_fields, values, strict=True))
        matching = [
            route_id
            for route_id, predicates in parsed_predicates.items()
            if _predicate_matches(state, predicates)
        ]
        if not matching:
            rendered = ", ".join(f"{name}={state[name]!r}" for name in ordered_fields)
            errors.append(f"selector state {{{rendered}}} is not covered by any route")
        elif len(matching) > 1:
            for left_id, right_id in itertools.combinations(sorted(matching), 2):
                overlapping_pairs.add((left_id, right_id))
    for left_id, right_id in sorted(overlapping_pairs):
        errors.append(
            f"routes {left_id!r} and {right_id!r} have overlapping when predicates"
        )


def validate_skill_contract(skill_dir: Path) -> list[str]:
    """Return deterministic validation errors for one skill directory."""
    errors: list[str] = []
    contract_path = skill_dir / "workflow-contract.yaml"
    try:
        contract = _load_unique_yaml(contract_path.read_text(encoding="utf-8"))
    except UnicodeError:
        return ["workflow-contract.yaml is not valid UTF-8"]
    except OSError as exc:
        return [f"cannot read workflow-contract.yaml: {exc}"]
    except yaml.YAMLError as exc:
        return [f"invalid workflow-contract.yaml: {exc}"]
    if not isinstance(contract, dict):
        return ["workflow-contract.yaml root must be a mapping"]
    contract_keys = _valid_mapping_keys(contract, location="workflow-contract.yaml", errors=errors)
    unknown_contract_keys = sorted(contract_keys - CONTRACT_KEYS)
    if unknown_contract_keys:
        errors.append(
            "workflow-contract.yaml unknown keys: " + ", ".join(unknown_contract_keys)
        )
    schema_version = contract.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        errors.append("workflow-contract.yaml schema_version must be the integer 1")

    entry_required, entry_optional = _load_entry_inputs(contract.get("entry_inputs"), errors)
    errors_before_phases = len(errors)
    phases = _load_phases(skill_dir, errors)
    if len(errors) > errors_before_phases:
        return errors
    route_selection = contract.get("route_selection")
    selection_phase = None
    if not isinstance(route_selection, dict) or not isinstance(
        route_selection.get("after_phase"), str
    ):
        errors.append("route_selection.after_phase must be a phase name")
    else:
        selection_phase = route_selection["after_phase"]
        route_selection_keys = _valid_mapping_keys(
            route_selection, location="route_selection", errors=errors
        )
        unknown_route_selection_keys = sorted(route_selection_keys - ROUTE_SELECTION_KEYS)
        if unknown_route_selection_keys:
            errors.append(
                "route_selection unknown keys: " + ", ".join(unknown_route_selection_keys)
            )
    routes = contract.get("routes")
    if not isinstance(routes, dict) or not routes:
        errors.append("routes must be a non-empty mapping")
        return errors

    route_names = _valid_mapping_keys(routes, location="routes", errors=errors)
    for phase in phases.values():
        for route_id in phase.conditional:
            if route_id not in route_names:
                errors.append(
                    f"phase {phase.name!r} declares conditional inputs for unknown route {route_id!r}"
                )

    parsed_predicates: dict[str, dict[str, tuple[str, object]]] = {}
    predicate_types: dict[str, str] = {}
    common_prefix: list[str] | None = None
    for route_id, route_schema in routes.items():
        if not isinstance(route_id, str) or not route_id:
            continue
        if not isinstance(route_schema, dict):
            errors.append(f"route {route_id!r} must be a mapping")
            continue
        phase_names, valid_selection_prefix, common_prefix = _check_route_prefix(
            route_id, route_schema, selection_phase, common_prefix, errors,
        )
        if phase_names is None:
            continue
        result = _check_predicate_types(
            route_id,
            phase_names,
            phases,
            selection_phase,
            valid_selection_prefix,
            entry_required,
            entry_optional,
            route_schema,
            errors,
        )
        if result is not None:
            parsed_predicates[route_id] = result.parsed
            predicate_types.update(result.route_predicate_types)

    _check_selector_coverage(routes, parsed_predicates, predicate_types, contract, errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dirs", nargs="+", type=Path)
    args = parser.parse_args(argv)
    failed = False
    for skill_dir in args.skill_dirs:
        errors = validate_skill_contract(skill_dir)
        if errors:
            failed = True
            for error in errors:
                print(f"error: {skill_dir}: {error}", file=sys.stderr)
        else:
            print(f"ok: {skill_dir}: workflow contract valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
