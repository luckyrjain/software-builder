from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_partial_coverage_projects_into_existing_incomplete_review_gate():
    text = (ROOT / "pr-review/workflow/phase-2-evidence.md").read_text(encoding="utf-8")
    assert "review_metrics: object" in text
    assert "inspection_status` is `partial` or `unable`" in text
    assert "review_metrics.review_complete: false" in text
    assert "must never inherit the \"review and post\" auto-confirm path" in text
