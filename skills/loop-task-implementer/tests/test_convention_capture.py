from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "skills/loop-task-implementer/scripts/convention_capture.py"


def _load():
    spec = importlib.util.spec_from_file_location("convention_capture_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules *before* exec: convention_capture.py's dataclasses (Occurrence,
    # CandidateConvention) resolve their `from __future__ import annotations` string annotations by
    # looking the defining module up in sys.modules by name at class-creation time -- without this,
    # that lookup returns None and dataclass field-type resolution raises.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cc():
    return _load()


# =================================================================================================
# score_text_pair
# =================================================================================================


def test_score_text_pair_identical_is_one(cc):
    text = "Always cite the specific PR or task evidence inline when raising a finding"
    assert cc.score_text_pair(text, text) == 1.0


def test_score_text_pair_disjoint_is_zero(cc):
    assert cc.score_text_pair("a b c d", "e f g h") == 0.0


def test_score_text_pair_partial_overlap_is_computed_value(cc):
    # tokens(a) = [a, b, c, d] -> trigrams {(a,b,c), (b,c,d)}
    # tokens(b) = [a, b, c, e] -> trigrams {(a,b,c), (b,c,e)}
    # intersection = {(a,b,c)} (size 1); union = {(a,b,c),(b,c,d),(b,c,e)} (size 3)
    # score = 1/3
    score = cc.score_text_pair("a b c d", "a b c e")
    assert score == pytest.approx(1 / 3)


def test_score_text_pair_strips_checkbox_boilerplate(cc):
    text_a = "- [ ] Cite evidence inline for every claim made"
    text_b = "- [x] Cite evidence inline for every claim made"
    assert cc.score_text_pair(text_a, text_b) == 1.0


def test_score_text_pair_strips_html_comment_boilerplate(cc):
    text_a = "Cite evidence <!-- reviewer note: nitpick --> inline always"
    text_b = "Cite evidence inline always"
    assert cc.score_text_pair(text_a, text_b) == 1.0


def test_score_text_pair_strips_heading_boilerplate(cc):
    text_a = "## Description\nCite evidence inline for every claim"
    text_b = "Cite evidence inline for every claim"
    assert cc.score_text_pair(text_a, text_b) == 1.0


def test_score_text_pair_degenerate_empty_strings_is_zero(cc):
    assert cc.score_text_pair("", "") == 0.0


def test_score_text_pair_degenerate_short_strings_is_zero(cc):
    # Fewer than 3 words on both sides -> no trigrams at all -> empty union -> 0.0 by convention.
    assert cc.score_text_pair("ab", "cd ef") == 0.0


# =================================================================================================
# fetch_and_score (network layer fully mocked)
# =================================================================================================


def test_fetch_and_score_maps_pr_numbers_to_scores(cc, monkeypatch):
    fetched = {101: "Please cite evidence inline for this claim", 202: "totally unrelated text here"}

    def fake_fetch(pr_number, **kwargs):
        return fetched[pr_number]

    monkeypatch.setattr(cc, "_fetch_review_comment_text", fake_fetch)

    result = cc.fetch_and_score("Please cite evidence inline for this claim", [101, 202])

    assert result == {
        101: cc.score_text_pair("Please cite evidence inline for this claim", fetched[101]),
        202: cc.score_text_pair("Please cite evidence inline for this claim", fetched[202]),
    }
    assert result[101] == 1.0
    assert result[202] == 0.0


def test_fetch_review_comment_text_retries_then_raises_on_rate_limit(cc, monkeypatch):
    secret_marker = "SUPER_SECRET_FETCHED_COMMENT_TEXT_MUST_NEVER_LEAK"
    calls = {"count": 0}

    class _FakeResult:
        def __init__(self):
            self.returncode = 1
            # A verbose gh error that happens to echo back comment content -- exactly the shape
            # this function must never let leak into its own exception message.
            self.stderr = f"HTTP 429: rate limited ({secret_marker})"
            self.stdout = ""

    def fake_run(*args, **kwargs):
        calls["count"] += 1
        return _FakeResult()

    monkeypatch.setattr(cc.subprocess, "run", fake_run)
    sleeps: list[float] = []

    with pytest.raises(cc.ConventionCaptureFetchError) as excinfo:
        cc._fetch_review_comment_text(
            123, max_retries=2, backoff_seconds=0.001, sleep=lambda s: sleeps.append(s)
        )

    message = str(excinfo.value)
    assert secret_marker not in message
    assert "PR #123" in message or "123" in message
    assert "rate_limited" in message
    # 1 initial attempt + 2 retries = 3 calls total.
    assert calls["count"] == 3
    assert len(sleeps) == 2


def test_fetch_and_score_failure_never_leaks_fetched_text(cc, monkeypatch, capsys):
    secret_marker = "SUPER_SECRET_FETCHED_COMMENT_TEXT_MUST_NEVER_LEAK"

    def fake_fetch(pr_number, **kwargs):
        raise cc.ConventionCaptureFetchError(f"fetch failed for PR #{pr_number}: rate_limited (after 4 attempt(s))")

    monkeypatch.setattr(cc, "_fetch_review_comment_text", fake_fetch)

    with pytest.raises(cc.ConventionCaptureFetchError) as excinfo:
        cc.fetch_and_score(secret_marker, [999])

    assert secret_marker not in str(excinfo.value)
    captured = capsys.readouterr()
    assert secret_marker not in captured.out
    assert secret_marker not in captured.err


# =================================================================================================
# Conflict-check against existing learned-conventions.md entries
# =================================================================================================


def _write_learned_conventions(path: Path, principle: str) -> None:
    path.write_text(
        "# Learned conventions\n\n"
        "Cross-run patterns proposed by loop-task-implementer's convention-capture procedure.\n\n"
        f"### {principle}\n\n"
        "**Category:** cite-evidence-inline — for human browsing only; not used for "
        "duplicate-recognition\n"
        "**Evidence:** PR #1, PR #2, PR #3 (3 distinct PRs)\n"
        "**Scope:** loop-task-implementer\n",
        encoding="utf-8",
    )


def test_check_against_existing_entries_flags_close_paraphrase(cc, tmp_path):
    existing_principle = (
        "Always cite the specific PR or task evidence inline when raising a review finding"
    )
    path = tmp_path / "learned-conventions.md"
    _write_learned_conventions(path, existing_principle)

    paraphrase = "Review findings should always cite the specific PR or task evidence inline"

    already_captured, score, match = cc.check_against_existing_entries(
        paraphrase, learned_conventions_path=path
    )

    assert already_captured is True
    assert score > 0.4
    assert match == existing_principle


def test_check_against_existing_entries_does_not_flag_different_candidate(cc, tmp_path):
    existing_principle = (
        "Always cite the specific PR or task evidence inline when raising a review finding"
    )
    path = tmp_path / "learned-conventions.md"
    _write_learned_conventions(path, existing_principle)

    different = "Run integration tests in a dedicated CI stage before merging any change"

    already_captured, score, match = cc.check_against_existing_entries(
        different, learned_conventions_path=path
    )

    assert already_captured is False
    assert score <= 0.4


def test_check_against_existing_entries_empty_file_never_flags(cc, tmp_path):
    path = tmp_path / "learned-conventions.md"
    path.write_text("# Learned conventions\n\nNo entries yet.\n", encoding="utf-8")

    already_captured, score, match = cc.check_against_existing_entries(
        "Anything at all", learned_conventions_path=path
    )

    assert already_captured is False
    assert score == 0.0
    assert match is None


def test_check_against_existing_entries_missing_file_never_flags(cc, tmp_path):
    missing = tmp_path / "does-not-exist.md"

    already_captured, score, match = cc.check_against_existing_entries(
        "Anything at all", learned_conventions_path=missing
    )

    assert already_captured is False
    assert score == 0.0
    assert match is None


# =================================================================================================
# Occurrence/diversity threshold
# =================================================================================================


def test_aggregate_occurrences_below_threshold_with_two_distinct_prs(cc):
    occurrences = [
        cc.Occurrence(category="cite-evidence-inline", principle="Cite evidence inline.", pr_number=1),
        cc.Occurrence(category="cite-evidence-inline", principle="Cite evidence inline.", pr_number=1),
        cc.Occurrence(category="cite-evidence-inline", principle="Cite evidence inline.", pr_number=2),
    ]

    candidates = cc.aggregate_occurrences(occurrences)

    assert candidates == []


def test_aggregate_occurrences_meets_threshold_with_three_distinct_prs(cc):
    occurrences = [
        cc.Occurrence(category="cite-evidence-inline", principle="Cite evidence inline.", pr_number=1),
        cc.Occurrence(category="cite-evidence-inline", principle="Cite evidence inline.", pr_number=2),
        cc.Occurrence(category="cite-evidence-inline", principle="Cite evidence inline.", pr_number=3),
    ]

    candidates = cc.aggregate_occurrences(occurrences)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.category == "cite-evidence-inline"
    assert candidate.evidence_prs == (1, 2, 3)


def test_aggregate_occurrences_filters_by_eligible_prs(cc):
    occurrences = [
        cc.Occurrence(category="cite-evidence-inline", principle="Cite evidence inline.", pr_number=1),
        cc.Occurrence(category="cite-evidence-inline", principle="Cite evidence inline.", pr_number=2),
        cc.Occurrence(category="cite-evidence-inline", principle="Cite evidence inline.", pr_number=3),
    ]

    # PR #3 falls outside the bounded scan window -> only 2 distinct eligible PRs remain -> below threshold.
    candidates = cc.aggregate_occurrences(occurrences, eligible_prs={1, 2})

    assert candidates == []
