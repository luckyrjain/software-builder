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


def _make_case(skill: str, case_id: str):
    from scripts.evals.__main__ import EvalCase

    return EvalCase(skill=skill, case_id=case_id, tier=1, description="", assertions=[], path=ROOT)


def test_admit_case_rejects_duplicate_id() -> None:
    from scripts.evals.__main__ import admit_case
    from scripts.evals.types import EvalResult
    from scripts.registry.schema import parse_registry

    registry = parse_registry(ROOT / "skills.yaml")
    skill_id = next(iter(sorted(registry.skills)))
    case = _make_case(skill_id, "dup")
    seen = {(skill_id, "dup")}

    result = admit_case(case, lambda c: EvalResult(c.skill, c.case_id, True, []), seen=seen, registry=registry)

    assert not result.passed
    assert "duplicate eval case id" in result.messages[0]


def test_admit_case_rejects_unregistered_skill() -> None:
    from scripts.evals.__main__ import admit_case
    from scripts.evals.types import EvalResult
    from scripts.registry.schema import parse_registry

    registry = parse_registry(ROOT / "skills.yaml")
    case = _make_case("definitely-not-a-real-skill-id", "case-1")

    result = admit_case(case, lambda c: EvalResult(c.skill, c.case_id, True, []), seen=set(), registry=registry)

    assert not result.passed
    assert result.messages == ["skill not in skills.yaml"]


def test_admit_case_dispatches_registered_skill() -> None:
    from scripts.evals.__main__ import admit_case
    from scripts.evals.types import EvalResult
    from scripts.registry.schema import parse_registry

    registry = parse_registry(ROOT / "skills.yaml")
    skill_id = next(iter(sorted(registry.skills)))
    case = _make_case(skill_id, "case-1")

    result = admit_case(case, lambda c: EvalResult(c.skill, c.case_id, True, ["ran"]), seen=set(), registry=registry)

    assert result == EvalResult(skill_id, "case-1", True, ["ran"])
