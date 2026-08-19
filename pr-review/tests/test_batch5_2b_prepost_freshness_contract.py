from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_phase2_to_3_rebuilds_full_identity_before_posting():
    text = (ROOT / "pr-review/workflow/phase-2-3-gate.md").read_text(encoding="utf-8")
    for token in (
        "fresh read-only provider/Git snapshot",
        "current full `change_identity`",
        "current base/head/merge-base SHAs",
        "normalized effective-patch fingerprint",
        "Do not reuse the Phase 1 identity",
        "validate_review_coverage(...)",
        "conflict_resolution_occurred=True",
        "never fall back to a head-only freshness claim",
        "review_metrics.review_complete: false",
    ):
        assert token in text
