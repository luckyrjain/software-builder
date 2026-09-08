"""Validate golden Phase 5 review_metadata footer (v2 blocks)."""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "phase5-review-metadata.yaml"

sys.path.insert(0, str(ROOT / "scripts"))

from validate_metadata_footer import validate_footer_document  # noqa: E402


def test_phase5_golden_footer_validates():
    data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    assert validate_footer_document(data) == []


def test_phase5_footer_has_v2_blocks():
    data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    meta = data["review_metadata"]
    assert "history" in meta
    assert "precision" in meta
    assert "review_quality" in meta
    assert meta["history"]["approval_iteration"] >= 2
