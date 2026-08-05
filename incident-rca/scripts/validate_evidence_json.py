#!/usr/bin/env python3
"""Validate incident-rca evidence bundle JSON (schema_version 3 or 4)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL = (
    "schema_version",
    "window",
    "service",
    "symptom",
    "environment",
    "error_signals",
    "deploy_events",
    "jira_issues",
    "infra_signals",
    "known_issue_matches",
    "evidence_links",
    "query_references",
    "recurrence_history",
)

REQUIRED_WINDOW = ("from_time", "to_time")

ERROR_SIGNAL_REQUIRED = ("signal_type", "detected_at", "magnitude")
ERROR_SIGNAL_OPTIONAL_STRING = ("source", "service", "link", "raw_summary")

QUERY_SIGNAL_REQUIRED = ("query_text", "source", "detected_at")
QUERY_SIGNAL_OPTIONAL_STRING = (
    "query_signature",
    "client_service",
    "index_or_table",
    "pattern",
    "link",
)


def _validate_error_signals(signals: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(signals, list):
        return errors

    for index, signal in enumerate(signals):
        prefix = f"error_signals[{index}]"
        if not isinstance(signal, dict):
            errors.append(f"{prefix} must be an object")
            continue

        for key in ERROR_SIGNAL_REQUIRED:
            value = signal.get(key)
            if key not in signal:
                errors.append(f"{prefix} missing required field: {key}")
            elif not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{key} must be a non-empty string")

        for key in ERROR_SIGNAL_OPTIONAL_STRING:
            if key in signal and signal[key] is not None and not isinstance(signal[key], str):
                errors.append(f"{prefix}.{key} must be a string when present")

        sample_messages = signal.get("sample_messages")
        if sample_messages is not None:
            if not isinstance(sample_messages, list):
                errors.append(f"{prefix}.sample_messages must be an array")
            else:
                for msg_index, message in enumerate(sample_messages):
                    if not isinstance(message, str):
                        errors.append(
                            f"{prefix}.sample_messages[{msg_index}] must be a string"
                        )

    return errors


def _validate_query_signals(signals: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(signals, list):
        return errors

    for index, signal in enumerate(signals):
        prefix = f"query_signals[{index}]"
        if not isinstance(signal, dict):
            errors.append(f"{prefix} must be an object")
            continue

        for key in QUERY_SIGNAL_REQUIRED:
            value = signal.get(key)
            if key not in signal:
                errors.append(f"{prefix} missing required field: {key}")
            elif not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{key} must be a non-empty string")

        for key in QUERY_SIGNAL_OPTIONAL_STRING:
            if key in signal and signal[key] is not None and not isinstance(signal[key], str):
                errors.append(f"{prefix}.{key} must be a string when present")

        exec_count = signal.get("exec_count")
        if exec_count is not None and not isinstance(exec_count, (int, float, str)):
            errors.append(f"{prefix}.exec_count must be a number or string when present")

        p95_latency_ms = signal.get("p95_latency_ms")
        if p95_latency_ms is not None and not isinstance(p95_latency_ms, (int, float)):
            errors.append(f"{prefix}.p95_latency_ms must be a number when present")

    return errors


def _parse_iso8601(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _validate_temporal_bounds(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    window = data.get("window")
    if not isinstance(window, dict):
        return errors

    from_raw = window.get("from_time")
    to_raw = window.get("to_time")
    if not isinstance(from_raw, str) or not isinstance(to_raw, str):
        return errors

    window_start = _parse_iso8601(from_raw)
    if window_start is None:
        errors.append(f"window.from_time is not valid ISO-8601: {from_raw!r}")
        return errors

    window_end = _parse_iso8601(to_raw)
    if window_end is None:
        errors.append(f"window.to_time is not valid ISO-8601: {to_raw!r}")
        return errors

    if window_start > window_end:
        errors.append("window.from_time must be <= window.to_time")
        return errors

    for field_name in ("error_signals", "query_signals"):
        signals = data.get(field_name)
        if not isinstance(signals, list):
            continue
        for index, signal in enumerate(signals):
            if not isinstance(signal, dict):
                continue
            detected_at = signal.get("detected_at")
            if not isinstance(detected_at, str) or not detected_at.strip():
                continue
            prefix = f"{field_name}[{index}]"
            timestamp = _parse_iso8601(detected_at)
            if timestamp is None:
                errors.append(f"{prefix}.detected_at is not valid ISO-8601: {detected_at!r}")
                continue
            if timestamp < window_start or timestamp > window_end:
                errors.append(
                    f"{prefix}.detected_at {detected_at} outside window "
                    f"[{from_raw}, {to_raw}]"
                )

    return errors


def _validate_dependency_chain(chain: Any) -> list[str]:
    errors: list[str] = []
    if chain is None:
        return errors
    if not isinstance(chain, list):
        return ["dependency_chain must be an array when present"]
    if not chain:
        errors.append("dependency_chain must not be empty when present")
        return errors
    for index, hop in enumerate(chain):
        if not isinstance(hop, str) or not hop.strip():
            errors.append(f"dependency_chain[{index}] must be a non-empty string")
    return errors


def validate_evidence(data: Any) -> list[str]:
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["root must be a JSON object"]

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            errors.append(f"missing required field: {key}")

    version = data.get("schema_version")
    if not isinstance(version, int) or version < 3:
        errors.append("schema_version must be an integer >= 3")
    elif version > 4:
        errors.append("schema_version must be <= 4 (unknown future version)")

    window = data.get("window")
    if not isinstance(window, dict):
        errors.append("window must be an object")
    else:
        for key in REQUIRED_WINDOW:
            if key not in window:
                errors.append(f"window missing required field: {key}")

    for list_field in (
        "error_signals",
        "deploy_events",
        "jira_issues",
        "infra_signals",
        "known_issue_matches",
        "evidence_links",
        "query_references",
        "recurrence_history",
        "query_signals",
    ):
        value = data.get(list_field)
        if value is not None and not isinstance(value, list):
            errors.append(f"{list_field} must be an array")

    service = data.get("service")
    if service is not None and not isinstance(service, str):
        errors.append("service must be a string when present")

    symptom = data.get("symptom")
    if symptom is not None and not isinstance(symptom, str):
        errors.append("symptom must be a string when present")
    elif "symptom" in data and not symptom:
        errors.append("symptom must be a non-empty string")

    environment = data.get("environment")
    if environment is not None and not isinstance(environment, str):
        errors.append("environment must be a string when present")
    elif "environment" in data and not environment:
        errors.append("environment must be a non-empty string")

    errors.extend(_validate_error_signals(data.get("error_signals")))
    errors.extend(_validate_query_signals(data.get("query_signals")))
    if isinstance(data, dict):
        errors.extend(_validate_temporal_bounds(data))
        errors.extend(_validate_dependency_chain(data.get("dependency_chain")))

    return errors


def main(argv: list[str] | None = None) -> int:
    paths = (argv if argv is not None else sys.argv[1:]) or [
        "incident-rca/reference/evidence.example.json"
    ]
    exit_code = 0
    for path_str in paths:
        path = Path(path_str)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        errors = validate_evidence(data)
        if errors:
            exit_code = 1
            print(f"{path}: validation failed", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
        else:
            print(f"{path}: ok")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
