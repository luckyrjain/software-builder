"""Tests for the shared eval-result helpers in scripts.evals.types."""
from __future__ import annotations

from scripts.evals.types import EvalResult, missing_and_failing


def test_missing_and_failing_splits_refs_correctly() -> None:
    case_results = {
        "skill/present-pass": EvalResult("skill", "present-pass", True, []),
        "skill/present-fail": EvalResult("skill", "present-fail", False, ["broke"]),
    }
    refs = ["skill/present-pass", "skill/present-fail", "skill/absent"]

    missing, failing = missing_and_failing(refs, case_results)

    assert missing == ["skill/absent"]
    assert failing == ["skill/present-fail"]


def test_missing_and_failing_returns_empty_lists_when_all_pass() -> None:
    case_results = {"skill/a": EvalResult("skill", "a", True, [])}

    missing, failing = missing_and_failing(["skill/a"], case_results)

    assert missing == []
    assert failing == []


def test_missing_and_failing_sorts_output() -> None:
    case_results: dict[str, EvalResult] = {}

    missing, _failing = missing_and_failing(["skill/z", "skill/a"], case_results)

    assert missing == ["skill/a", "skill/z"]


def test_missing_and_failing_dedupes_repeated_refs() -> None:
    # Regression test: two of the three pre-extraction implementations deduped "missing" via
    # `set(refs) - set(case_results)`; a naive list-comprehension version doesn't, and would
    # report "missing referenced eval cases: x, x" if a YAML case_refs list names the same ref
    # twice by mistake.
    case_results = {"skill/failing": EvalResult("skill", "failing", False, ["broke"])}

    missing, failing = missing_and_failing(
        ["skill/absent", "skill/absent", "skill/failing", "skill/failing"],
        case_results,
    )

    assert missing == ["skill/absent"]
    assert failing == ["skill/failing"]
