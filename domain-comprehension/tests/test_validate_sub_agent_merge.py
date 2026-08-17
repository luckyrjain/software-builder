"""Tests for sub-agent merge JSON validator."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_sub_agent_merge import validate_merge  # noqa: E402

VALID = ROOT / "tests" / "fixtures" / "sub-agent-merge" / "valid.json"


def test_valid_fixture():
    data = json.loads(VALID.read_text(encoding="utf-8"))
    assert validate_merge(data) == []


def test_missing_repo():
    data = json.loads(VALID.read_text(encoding="utf-8"))
    del data["repo"]
    errors = validate_merge(data)
    assert any("repo" in e for e in errors)


def test_invalid_confidence():
    data = json.loads(VALID.read_text(encoding="utf-8"))
    data["findings"][0]["confidence"] = "HIGHISH"
    errors = validate_merge(data)
    assert any("confidence" in e for e in errors)


def test_unhashable_confidence_reports_error_instead_of_crashing():
    """A malformed sub-agent merge payload can put a list/mapping where confidence expects a string.

    validate_merge()'s job is to report that cleanly, not raise TypeError from `x not in
    a_frozenset` — unhashable values must never reach a frozenset membership test.
    """
    data = json.loads(VALID.read_text(encoding="utf-8"))
    data["findings"][0]["confidence"] = ["HIGH"]
    errors = validate_merge(data)
    assert any("confidence" in e for e in errors)


@pytest.mark.parametrize("field", ["repo", "phase", "findings", "open_questions", "conflicts", "files_read"])
def test_explicit_null_required_field_is_rejected(field: str):
    """A required field present with an explicit JSON `null` must not pass as if absent.

    The schema types repo/phase as non-nullable strings and open_questions/conflicts/files_read
    as non-nullable arrays, so `null` must be reported just like a missing or wrong-typed value.
    """
    data = json.loads(VALID.read_text(encoding="utf-8"))
    data[field] = None
    errors = validate_merge(data)
    assert any(field in e for e in errors)


def test_explicit_null_confidence_is_rejected():
    data = json.loads(VALID.read_text(encoding="utf-8"))
    data["findings"][0]["confidence"] = None
    errors = validate_merge(data)
    assert any("confidence" in e for e in errors)


@pytest.mark.parametrize("field", ["open_questions", "conflicts", "files_read"])
def test_non_string_list_item_is_rejected(field: str):
    """open_questions/conflicts/files_read must contain only strings per the JSON schema."""
    data = json.loads(VALID.read_text(encoding="utf-8"))
    data[field] = [123, {"a": 1}, None]
    errors = validate_merge(data)
    assert any(f"{field}[0]" in e for e in errors)
