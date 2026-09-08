from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_report_template_places_coverage_gaps_before_suppressed_items():
    text = (ROOT / "pr-review/report-template.md").read_text(encoding="utf-8")
    section_map = text.split("## Section map", 1)[1].split("## Partial review", 1)[0]
    assert section_map.index("Coverage gaps") < section_map.index("Not raised (suppressed)")
    assert "inspection_status: partial|unable" in section_map


def test_report_template_covers_inspection_partial_and_unable_states():
    text = (ROOT / "pr-review/report-template.md").read_text(encoding="utf-8")
    for token in (
        "### Coverage gaps",
        "Mandatory unavailable coverage",
        "requires explicit posting",
        "inspection_status: unable",
        "Confidence Low",
    ):
        assert token in text
