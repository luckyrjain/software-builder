from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_prd_inputs_ingest_domain_manifest_freshness_status():
    text = _text("prd-architect/workflow/inputs.md")
    for token in (
        "producer manifest PRD artifact freshness status",
        "`ok` — eligible as current-state PRD evidence",
        "`stale` — **Blocking Before Build**",
        "missing/unknown freshness — **Blocking Before Build**",
        "no ad-hoc independent-verification escape",
    ):
        assert token in text


def test_prd_gate_blocks_stale_or_unverified_domain_prd():
    text = _text("prd-architect/workflow/gate.md")
    for token in (
        "producer-manifest PRD freshness is `ok`",
        "every accepted machine artifact is `ok`",
        "producer-manifest PRD freshness `stale` or missing/unknown",
        "no ad-hoc “independently verified” escape",
    ):
        assert token in text


def test_machine_domain_model_forbids_independently_reverified_escape():
    text = _text("domain-comprehension/reference/machine-domain-model.md")
    assert "independently re-verified" not in text
    assert "no ad-hoc independently verified escape" in text
    assert "integrity check against source revisions/machine artifacts passes" in text
