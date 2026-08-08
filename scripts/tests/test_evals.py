"""Tests for behavioral eval runner."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_evals_cover_all_registered_skills() -> None:
    from scripts.evals.__main__ import run_all
    from scripts.registry.schema import parse_registry

    registry = parse_registry(ROOT / "skills.yaml")
    results = run_all(ROOT)
    covered = {(result.skill, result.case_id) for result in results}

    for skill_id in registry.skills:
        assert any(case_id.startswith("global-happy") for skill, case_id in covered if skill == skill_id)
        assert any(
            case_id.startswith("global-adversarial") for skill, case_id in covered if skill == skill_id
        )


def test_evals_pass_on_repository() -> None:
    from scripts.evals.__main__ import run_all

    results = run_all(ROOT)
    failures = [result for result in results if not result.passed]
    assert not failures, failures
