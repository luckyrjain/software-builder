"""Tests for incident-rca evidence JSON validator."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_evidence_json import validate_evidence  # noqa: E402

EXAMPLE = ROOT / "reference" / "evidence.example.json"


def test_example_json_valid():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert validate_evidence(data) == []


def test_missing_schema_version():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    del data["schema_version"]
    errors = validate_evidence(data)
    assert any("schema_version" in e for e in errors)


def test_invalid_window():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["window"] = {"from_time": "2026-01-01T00:00:00Z"}
    errors = validate_evidence(data)
    assert any("to_time" in e for e in errors)


def test_missing_symptom():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    del data["symptom"]
    errors = validate_evidence(data)
    assert any("symptom" in e for e in errors)


def test_missing_environment():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    del data["environment"]
    errors = validate_evidence(data)
    assert any("environment" in e for e in errors)


def test_error_signal_missing_detected_at():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    del data["error_signals"][0]["detected_at"]
    errors = validate_evidence(data)
    assert any("error_signals[0]" in e and "detected_at" in e for e in errors)


def test_error_signal_sample_messages_must_be_strings():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["error_signals"][0]["sample_messages"] = ["ok", 42]
    errors = validate_evidence(data)
    assert any("sample_messages[1]" in e for e in errors)


def test_error_signal_entry_must_be_object():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["error_signals"] = ["not-an-object"]
    errors = validate_evidence(data)
    assert any("error_signals[0] must be an object" in e for e in errors)


def test_opensearch_example_json_valid():
    path = ROOT / "reference" / "evidence.example.opensearch-query-governance.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert validate_evidence(data) == []


def test_query_signal_missing_detected_at():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["query_signals"] = [{"query_text": "SELECT 1", "source": "dbm"}]
    errors = validate_evidence(data)
    assert any("query_signals[0]" in e and "detected_at" in e for e in errors)


def test_query_signal_entry_must_be_object():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["query_signals"] = ["not-an-object"]
    errors = validate_evidence(data)
    assert any("query_signals[0] must be an object" in e for e in errors)


def test_query_signal_exec_count_type():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["query_signals"] = [
        {
            "query_text": "SELECT 1",
            "source": "dbm",
            "detected_at": "2026-01-01T00:00:00Z",
            "exec_count": {"bad": "type"},
        }
    ]
    errors = validate_evidence(data)
    assert any("exec_count" in e for e in errors)


def test_error_signal_detected_at_before_window():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["error_signals"][0]["detected_at"] = "2026-06-28T13:59:00Z"
    errors = validate_evidence(data)
    assert any("error_signals[0].detected_at" in e and "outside window" in e for e in errors)


def test_error_signal_detected_at_after_window():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["error_signals"][0]["detected_at"] = "2026-06-28T16:01:00Z"
    errors = validate_evidence(data)
    assert any("error_signals[0].detected_at" in e and "outside window" in e for e in errors)


def test_query_signal_detected_at_outside_window():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["query_signals"] = [
        {
            "query_text": "SELECT 1",
            "source": "dbm",
            "detected_at": "2026-06-28T17:00:00Z",
        }
    ]
    errors = validate_evidence(data)
    assert any("query_signals[0].detected_at" in e and "outside window" in e for e in errors)


def test_error_signal_detected_at_invalid_iso8601():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["error_signals"][0]["detected_at"] = "not-a-timestamp"
    errors = validate_evidence(data)
    assert any("error_signals[0].detected_at is not valid ISO-8601" in e for e in errors)


def test_window_from_after_to():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["window"] = {
        "from_time": "2026-06-28T16:00:00Z",
        "to_time": "2026-06-28T14:00:00Z",
    }
    errors = validate_evidence(data)
    assert any("window.from_time must be <= window.to_time" in e for e in errors)


def test_dependency_chain_valid():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["dependency_chain"] = ["neo-disbursement-service", "payment-gateway"]
    assert validate_evidence(data) == []


def test_dependency_chain_invalid_hop():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["dependency_chain"] = ["ok", ""]
    errors = validate_evidence(data)
    assert any("dependency_chain[1]" in e for e in errors)
