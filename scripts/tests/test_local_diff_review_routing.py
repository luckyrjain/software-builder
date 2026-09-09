"""Routing regression coverage for local-diff-review."""

from pathlib import Path

from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


def test_review_since_commit_routes_to_local_diff_review() -> None:
    result = _dispatch("Review the changes since main on my current branch for convention violations.")
    assert result.status == "selected", result
    assert result.owner == "local-diff-review"


def test_numbered_pr_does_not_route_to_local_diff_review() -> None:
    result = _dispatch("Review the diff since the main branch for PR #482 — does it match the ticket?")
    assert result.owner != "local-diff-review"


def test_existing_codebase_architecture_does_not_route_to_local_diff_review() -> None:
    result = _dispatch("Review this existing codebase's architecture for refactoring opportunities.")
    assert result.owner != "local-diff-review"
