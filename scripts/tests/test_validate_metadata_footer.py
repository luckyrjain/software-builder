"""Tests for scripts/validate_metadata_footer.py"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_metadata_footer import (  # noqa: E402
    validate_assessment_metadata,
    validate_footer_document,
    validate_review_metadata,
)

REVIEW_MINIMAL = {
    "review_type": "full",
    "started": "2026-06-25T10:10:00Z",
    "finished": "2026-06-25T10:15:00Z",
    "head_sha": "abc123def4567890abcdef1234567890abcdef12",
    "review_hash": {"scope": "full"},
    "findings": [],
    "recommendation": "approve",
    "confidence": "high",
    "review_complete": True,
}

RCA_MINIMAL = {
    "assessment_type": "full",
    "started": "2026-06-28T15:00:00Z",
    "finished": "2026-06-28T15:22:00Z",
    "service": "neo-disbursement-service",
    "incident_window": {
        "from": "2026-06-28T14:00:00Z",
        "to": "2026-06-28T16:00:00Z",
    },
    "primary_hypothesis": "deploy_regression",
    "confidence": "high",
    "assessment_complete": True,
}

K8S_MINIMAL = {
    "assessment_type": "full",
    "started": "2026-06-28T11:00:00Z",
    "finished": "2026-06-28T11:18:00Z",
    "service": "neo-disbursement",
    "final_decision": "KEEP_CONFIGURATION",
    "assessment_confidence": 0.9,
    "assessment_complete": True,
}


def test_review_metadata_minimal_ok() -> None:
    assert validate_review_metadata(REVIEW_MINIMAL) == []


def test_assessment_metadata_rca_ok() -> None:
    assert validate_assessment_metadata(RCA_MINIMAL) == []


def test_assessment_metadata_k8s_ok() -> None:
    assert validate_assessment_metadata(K8S_MINIMAL) == []


def test_footer_document_rejects_both_keys() -> None:
    errors = validate_footer_document(
        {"review_metadata": REVIEW_MINIMAL, "assessment_metadata": RCA_MINIMAL}
    )
    assert any("only one metadata key" in err for err in errors)


def test_review_metadata_missing_head_sha() -> None:
    meta = dict(REVIEW_MINIMAL)
    del meta["head_sha"]
    errors = validate_review_metadata(meta)
    assert any("head_sha" in err for err in errors)


def test_assessment_metadata_mixed_profiles() -> None:
    meta = {**RCA_MINIMAL, "final_decision": "KEEP_CONFIGURATION"}
    errors = validate_assessment_metadata(meta)
    assert any("cannot mix" in err for err in errors)


def test_assessment_confidence_out_of_range() -> None:
    meta = {**K8S_MINIMAL, "assessment_confidence": 1.5}
    errors = validate_assessment_metadata(meta)
    assert any("assessment_confidence" in err for err in errors)


@pytest.mark.parametrize(
    "example",
    [
        "docs/skill-framework/shared/examples/review-metadata.example.yaml",
        "docs/skill-framework/shared/examples/assessment-metadata-rca.example.yaml",
        "docs/skill-framework/shared/examples/assessment-metadata-k8s.example.yaml",
    ],
)
def test_golden_examples(example: str) -> None:
    import yaml

    path = ROOT / example
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert validate_footer_document(data) == []
