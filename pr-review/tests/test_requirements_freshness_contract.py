from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_phase2_to_3_reloads_authoritative_requirements_before_posting():
    text = (ROOT / "pr-review/workflow/phase-2-3-gate.md").read_text(encoding="utf-8")
    for token in (
        "same authoritative requirements source",
        "Do not reuse the Phase 1/2 requirements object",
        "cannot be re-read or normalized",
        "freshly re-established",
        "requirements drift",
        "never post against requirements whose freshness cannot be established",
    ):
        assert token in text
