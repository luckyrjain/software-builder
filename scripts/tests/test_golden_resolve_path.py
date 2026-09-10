"""Tests for golden.resolve_path's list-index and predicate syntax."""

from __future__ import annotations

import pytest

from scripts.evals.golden import resolve_path

DATA = {
    "hypotheses_tested": [
        {"candidate": "sql injection", "result": "rejected", "evidence": "no user input reaches query"},
        {"candidate": "race condition", "result": "confirmed", "evidence": "logs show concurrent writes"},
    ],
    "research_brief": {
        "findings": [
            {"claim": "rate limit missing", "evidence_status": "OBSERVED", "source": "src/middleware/rate_limit.py:14"},
            {"claim": "cache is warm", "evidence_status": "INFERRED", "source": "docs/notes.md"},
        ],
    },
    "plain_list": [1, 2, 3],
    "duplicate_candidates": [{"x": 1}, {"x": 1}],
}


def test_plain_dotted_path_still_works() -> None:
    assert resolve_path(DATA, "research_brief.findings") == DATA["research_brief"]["findings"]


def test_missing_key_raises_key_error() -> None:
    with pytest.raises(KeyError):
        resolve_path(DATA, "research_brief.missing")


def test_positive_and_negative_list_index() -> None:
    assert resolve_path(DATA, "hypotheses_tested[0].candidate") == "sql injection"
    assert resolve_path(DATA, "hypotheses_tested[-1].result") == "confirmed"


def test_index_out_of_range_raises_key_error() -> None:
    with pytest.raises(KeyError):
        resolve_path(DATA, "hypotheses_tested[5].candidate")


def test_predicate_selects_one_item() -> None:
    assert resolve_path(DATA, "hypotheses_tested[?candidate=='race condition'].result") == "confirmed"


def test_predicate_value_may_contain_dots() -> None:
    assert (
        resolve_path(DATA, "research_brief.findings[?evidence_status=='OBSERVED'].source")
        == "src/middleware/rate_limit.py:14"
    )


def test_predicate_zero_matches_raises_key_error() -> None:
    with pytest.raises(KeyError):
        resolve_path(DATA, "hypotheses_tested[?candidate=='nonexistent'].result")


def test_predicate_multiple_matches_raises_value_error() -> None:
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_path(DATA, "duplicate_candidates[?x==1].x")


def test_index_on_non_list_raises_key_error() -> None:
    with pytest.raises(KeyError):
        resolve_path(DATA, "research_brief[0]")


def test_invalid_predicate_syntax_raises_value_error() -> None:
    with pytest.raises(ValueError):
        resolve_path(DATA, "hypotheses_tested[?not a predicate].result")
