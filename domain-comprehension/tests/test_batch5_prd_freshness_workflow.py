from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_prd_inputs_ingest_domain_manifest_freshness_status():
    text = _text("prd-architect/workflow/inputs.md")
    for token in (
        "producer manifest PRD artifact freshness status",
        "`ok` — eligible to be used as current-state PRD evidence",
        "`stale` — **Blocking Before Build**",
        "missing/unknown freshness",
    ):
        assert token in text


def test_prd_gate_blocks_stale_or_unverified_domain_prd():
    text = _text("prd-architect/workflow/gate.md")
    for token in (
        "producer-manifest PRD artifact freshness was explicitly checked",
        "must be `ok` before the PRD is treated as current",
        "producer-manifest PRD freshness `stale` or missing/unknown freshness",
    ):
        assert token in text
