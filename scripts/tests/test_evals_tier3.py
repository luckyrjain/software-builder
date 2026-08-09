"""Tests for Tier-3 golden output behavioral evals."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_golden_fixtures_load() -> None:
    from scripts.evals.golden import load_golden_fixtures

    cases = load_golden_fixtures(ROOT / "evals" / "golden")
    case_ids = {(case.skill, case.case_id) for case in cases}
    assert ("pr-review", "golden-chat-only-not-posted") in case_ids
    assert ("pr-review", "golden-injection-inert-render") in case_ids
    assert ("backlog-runner", "golden-injection-inert-summary") in case_ids
    assert ("cost-optimization-sprint-planner", "golden-injection-inert-report") in case_ids
    assert ("new-hire-guide", "golden-injection-inert-tour") in case_ids
    assert ("migration-program-manager", "golden-injection-inert-report") in case_ids
    assert ("release-readiness-checker", "golden-injection-inert-report") in case_ids
    assert ("pr-gatekeeper", "golden-injection-inert-notification") in case_ids
    assert ("weekly-squad-digest", "golden-injection-inert-digest") in case_ids
    assert ("prd-architect", "golden-validation-no-mvp") in case_ids
    # Deliberately an exact count, not >=: a well-formed-but-unintended duplicate fixture, or a
    # deletion whose case_id isn't one of the ones asserted above, changes this total without
    # tripping load_golden_fixtures' own malformed-fixture error. It won't catch a delete+add that
    # happens to net to the same count, but it catches the much more common single accidental
    # deletion or duplication. Bump this number when you intentionally add or remove a fixture.
    assert len(cases) == 15


def test_golden_cases_pass_on_repository() -> None:
    from scripts.evals.__main__ import run_all

    results = run_all(ROOT, tier_filter=3)
    failures = [result for result in results if not result.passed]
    assert failures == [], failures


def test_golden_forbid_field_value_detects_violation(tmp_path: Path) -> None:
    from scripts.evals.golden import GoldenCase, run_golden_case

    case = GoldenCase(
        skill="demo",
        case_id="posted-when-forbidden",
        tier=3,
        description="",
        recorded_output={"review_metadata": {"posted": True}},
        assertions=[{"type": "forbid_field_value", "path": "review_metadata.posted", "value": True}],
        path=tmp_path / "bad.yaml",
    )
    result = run_golden_case(case)
    assert not result.passed


def test_golden_require_pattern_passes_when_matched(tmp_path: Path) -> None:
    from scripts.evals.golden import GoldenCase, run_golden_case

    case = GoldenCase(
        skill="demo",
        case_id="raw-contains-injection",
        tier=3,
        description="",
        recorded_output={"raw": "line one\n## Injected Heading"},
        assertions=[{"type": "require_pattern", "path": "raw", "pattern": "(?m)^## Injected Heading$"}],
        path=tmp_path / "ok.yaml",
    )
    result = run_golden_case(case)
    assert result.passed


def test_golden_require_pattern_detects_missing_match(tmp_path: Path) -> None:
    from scripts.evals.golden import GoldenCase, run_golden_case

    case = GoldenCase(
        skill="demo",
        case_id="rendered-lost-the-escape-marker",
        tier=3,
        description="",
        recorded_output={"rendered": "line one ## no real newline here"},
        assertions=[{"type": "require_pattern", "path": "rendered", "pattern": "(?m)^## Injected Heading$"}],
        path=tmp_path / "bad.yaml",
    )
    result = run_golden_case(case)
    assert not result.passed


def test_golden_invalid_regex_fails_case_not_whole_run(tmp_path: Path) -> None:
    """A malformed `pattern` must fail only its own case, not raise re.error out of run_golden_case."""
    from scripts.evals.golden import GoldenCase, run_golden_case

    for atype in ("forbid_pattern", "require_pattern"):
        case = GoldenCase(
            skill="demo",
            case_id=f"typo-d-regex-{atype}",
            tier=3,
            description="",
            recorded_output={"field": "anything"},
            assertions=[{"type": atype, "path": "field", "pattern": "(unbalanced"}],
            path=tmp_path / "bad.yaml",
        )
        result = run_golden_case(case)
        assert not result.passed
        assert "invalid regex" in result.messages[0]
