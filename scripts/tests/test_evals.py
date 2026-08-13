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


def _make_golden_case(skill: str, tier: int, recorded_output: dict, assertions: list[dict], description: str = ""):
    from scripts.evals.golden import GoldenCase

    return GoldenCase(
        skill=skill,
        case_id="case",
        tier=tier,
        description=description,
        recorded_output=recorded_output,
        assertions=assertions,
        path=ROOT,
    )


def test_looks_like_multiline_anchor_flags_genuine_anchor() -> None:
    from scripts.evals.golden import _looks_like_multiline_anchor

    assert _looks_like_multiline_anchor(r"(?m)^## Heading$")


def test_looks_like_multiline_anchor_ignores_escaped_literal_dollar() -> None:
    from scripts.evals.golden import _looks_like_multiline_anchor

    # \$ is a literal dollar sign, not an end-of-line anchor -- this pattern only has a
    # real ^ anchor, no real $ anchor, so it isn't the vacuous shape being detected.
    assert not _looks_like_multiline_anchor(r"(?m)^Price: \$5")


def test_looks_like_multiline_anchor_ignores_negated_character_class() -> None:
    from scripts.evals.golden import _looks_like_multiline_anchor

    # The only ^ here negates a character class ([^x]); it isn't a line-start anchor.
    assert not _looks_like_multiline_anchor(r"(?m)Foo [^x]bar$")


def test_find_vacuous_anchored_patterns_flags_newline_free_field() -> None:
    from scripts.evals.golden import find_vacuous_anchored_patterns

    case = _make_golden_case(
        skill="test-skill",
        tier=3,
        recorded_output={"rendered": "no real newline here"},
        assertions=[{"type": "forbid_pattern", "path": "rendered", "pattern": r"(?m)^Marker$"}],
    )

    warnings = find_vacuous_anchored_patterns([case])

    assert len(warnings) == 1
    assert "rendered" in warnings[0]


def test_find_vacuous_anchored_patterns_silent_on_real_newline() -> None:
    from scripts.evals.golden import find_vacuous_anchored_patterns

    case = _make_golden_case(
        skill="test-skill",
        tier=3,
        recorded_output={"rendered": "line one\nMarker"},
        assertions=[{"type": "forbid_pattern", "path": "rendered", "pattern": r"(?m)^Marker$"}],
    )

    assert find_vacuous_anchored_patterns([case]) == []


def test_find_vacuous_anchored_patterns_respects_skill_and_tier_filters() -> None:
    from scripts.evals.golden import find_vacuous_anchored_patterns

    vacuous_assertions = [{"type": "forbid_pattern", "path": "rendered", "pattern": r"(?m)^Marker$"}]
    case_a = _make_golden_case("skill-a", 3, {"rendered": "no newline"}, vacuous_assertions)
    case_b = _make_golden_case("skill-b", 3, {"rendered": "no newline"}, vacuous_assertions)
    case_c = _make_golden_case("skill-a", 1, {"rendered": "no newline"}, vacuous_assertions)

    assert len(find_vacuous_anchored_patterns([case_a, case_b, case_c])) == 3
    assert len(find_vacuous_anchored_patterns([case_a, case_b, case_c], skill_filter="skill-a")) == 2
    assert len(find_vacuous_anchored_patterns([case_a, case_b, case_c], tier_filter=3)) == 2
    assert len(
        find_vacuous_anchored_patterns([case_a, case_b, case_c], skill_filter="skill-a", tier_filter=3),
    ) == 1


def test_find_oversized_descriptions_flags_long_description() -> None:
    from scripts.evals.golden import find_oversized_descriptions

    case = _make_golden_case(
        skill="test-skill",
        tier=3,
        recorded_output={},
        assertions=[{"type": "field_equals", "path": "x", "value": 1}],
        description="x" * 1500,
    )

    warnings = find_oversized_descriptions([case])

    assert len(warnings) == 1
    assert "1500" in warnings[0]


def test_find_oversized_descriptions_silent_on_short_description() -> None:
    from scripts.evals.golden import find_oversized_descriptions

    case = _make_golden_case(
        skill="test-skill",
        tier=3,
        recorded_output={},
        assertions=[{"type": "field_equals", "path": "x", "value": 1}],
        description="short and to the point",
    )

    assert find_oversized_descriptions([case]) == []


def test_find_oversized_descriptions_silent_exactly_at_threshold() -> None:
    from scripts.evals.golden import DESCRIPTION_LENGTH_WARNING_THRESHOLD, find_oversized_descriptions

    case = _make_golden_case(
        skill="test-skill",
        tier=3,
        recorded_output={},
        assertions=[{"type": "field_equals", "path": "x", "value": 1}],
        description="x" * DESCRIPTION_LENGTH_WARNING_THRESHOLD,
    )

    assert find_oversized_descriptions([case]) == []


def test_find_oversized_descriptions_respects_skill_and_tier_filters() -> None:
    from scripts.evals.golden import find_oversized_descriptions

    long_description = "x" * 1500
    minimal_assertions = [{"type": "field_equals", "path": "x", "value": 1}]
    case_a = _make_golden_case("skill-a", 3, {}, minimal_assertions, description=long_description)
    case_b = _make_golden_case("skill-b", 3, {}, minimal_assertions, description=long_description)
    case_c = _make_golden_case("skill-a", 1, {}, minimal_assertions, description=long_description)

    assert len(find_oversized_descriptions([case_a, case_b, case_c])) == 3
    assert len(find_oversized_descriptions([case_a, case_b, case_c], skill_filter="skill-a")) == 2
    assert len(find_oversized_descriptions([case_a, case_b, case_c], tier_filter=3)) == 2
    assert len(
        find_oversized_descriptions([case_a, case_b, case_c], skill_filter="skill-a", tier_filter=3),
    ) == 1
