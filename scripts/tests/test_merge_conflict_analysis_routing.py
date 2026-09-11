"""Routing regression coverage for merge-conflict-analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


def test_merge_conflict_routes_to_merge_conflict_analysis() -> None:
    result = _dispatch("There's a merge conflict on this branch — analyze it and recommend how to resolve each hunk.")
    assert result.status == "selected", result
    assert result.owner == "merge-conflict-analysis"


def test_rebase_conflict_routes_to_merge_conflict_analysis() -> None:
    result = _dispatch("There's a rebase conflict I need help understanding — what does each side want?")
    assert result.status == "selected", result
    assert result.owner == "merge-conflict-analysis"


def test_clean_pr_review_does_not_route_to_merge_conflict_analysis() -> None:
    result = _dispatch("Review this PR for correctness and regressions — the diff is already clean, no conflicts.")
    assert "merge-conflict-analysis" not in result.candidates, result


def _positive_cases() -> list[tuple[str, str]]:
    raw = load_unique_yaml_file(ROOT / "evals" / "positive" / "cases.yaml")
    assert isinstance(raw, dict)
    return [
        (case["skill"], case["prompt"])
        for case in raw["cases"]
        if case["skill"] != "merge-conflict-analysis"
    ]


@pytest.mark.parametrize(
    ("skill", "prompt"),
    [
        pytest.param(skill, prompt, id=skill)
        for skill, prompt in _positive_cases()
    ],
)
def test_merge_conflict_analysis_does_not_capture_other_skills_positive_cases(skill: str, prompt: str) -> None:
    """Registry-wide guard: merge-conflict-analysis's patterns require the literal phrase "merge
    conflict"/"rebase conflict", confirmed unused elsewhere in the registry at spec time
    (docs/superpowers/specs/2026-09-11-two-skill-port-design.md, Global Constraint 1). This sweep
    locks that invariant in permanently, applied from Task 4 directly rather than discovered via a
    review round the way every prior port's own sweep test needed one to reach this shape.
    """
    result = _dispatch(prompt)
    assert "merge-conflict-analysis" not in result.candidates, (skill, prompt, result)
