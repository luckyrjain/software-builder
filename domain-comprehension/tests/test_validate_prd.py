"""Tests for validate_prd.py."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_prd import validate_prd  # noqa: E402


def _write_valid_prd(path: Path) -> None:
    path.write_text(
        """# As-Built Product Requirements Document

## 4. Functional requirements
| ID | Requirement | Scope | Evidence | Status | Confidence |
|---|---|---|---|---|---|
| FR-001 | Return current balance | ledger | src/balance.py:10 | Observed | HIGH |

## 5. Business rules and invariants
| ID | Rule / invariant | Scope | Trigger / precondition | Outcome | Evidence | Status | Confidence |
|---|---|---|---|---|---|---|---|
| BR-001 | Balance cannot be negative | ledger | write | reject | src/ledger.py:20 | Observed | HIGH |

## 12. Non-functional requirements
| ID | Area | Requirement / observed constraint | Scope | Evidence | Status | Confidence |
|---|---|---|---|---|---|---|
| NFR-001 | Idempotency | Duplicate key is rejected | write API | src/api.py:30 | Observed | MEDIUM |

## 19. Requirement traceability
| Requirement ID | Requirement status | Evidence source(s) | Evidence type | Confidence | Notes / contradiction |
|---|---|---|---|---|---|
| FR-001 | Observed | src/balance.py:10 | Code | HIGH | none |
| BR-001 | Observed | src/ledger.py:20 | Code | HIGH | none |
| NFR-001 | Observed | src/api.py:30 | Code | MEDIUM | none |

## 20. Open product-intent questions
UNKNOWN
""",
        encoding="utf-8",
    )


def test_valid_prd_passes(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    _write_valid_prd(prd)
    assert validate_prd(prd) == []


def test_business_rule_requires_status_column(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    _write_valid_prd(prd)
    text = prd.read_text(encoding="utf-8").replace(
        "| ID | Rule / invariant | Scope | Trigger / precondition | Outcome | Evidence | Status | Confidence |",
        "| ID | Rule / invariant | Scope | Trigger / precondition | Outcome | Evidence | Confidence |",
    ).replace(
        "| BR-001 | Balance cannot be negative | ledger | write | reject | src/ledger.py:20 | Observed | HIGH |",
        "| BR-001 | Balance cannot be negative | ledger | write | reject | src/ledger.py:20 | HIGH |",
    )
    prd.write_text(text, encoding="utf-8")
    errors = validate_prd(prd)
    assert any("Business rules" in error and "status" in error for error in errors)


def test_every_requirement_must_be_traced(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    _write_valid_prd(prd)
    text = prd.read_text(encoding="utf-8").replace(
        "| NFR-001 | Observed | src/api.py:30 | Code | MEDIUM | none |\n",
        "",
    )
    prd.write_text(text, encoding="utf-8")
    assert "missing traceability row: NFR-001" in validate_prd(prd)


def test_observed_requirement_requires_evidence(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    _write_valid_prd(prd)
    text = prd.read_text(encoding="utf-8").replace(
        "| FR-001 | Return current balance | ledger | src/balance.py:10 | Observed | HIGH |",
        "| FR-001 | Return current balance | ledger | UNKNOWN | Observed | HIGH |",
    )
    prd.write_text(text, encoding="utf-8")
    assert "FR-001: Observed requirement must cite evidence" in validate_prd(prd)


def test_unresolved_status_placeholder_fails(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    _write_valid_prd(prd)
    text = prd.read_text(encoding="utf-8").replace(
        "| FR-001 | Return current balance | ledger | src/balance.py:10 | Observed | HIGH |",
        "| FR-001 | Return current balance | ledger | src/balance.py:10 | Observed / Inferred / Unknown | HIGH |",
    )
    prd.write_text(text, encoding="utf-8")
    assert any("unresolved PRD status placeholder" in error for error in validate_prd(prd))


def test_duplicate_requirement_definition_fails(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    _write_valid_prd(prd)
    text = prd.read_text(encoding="utf-8").replace(
        "| FR-001 | Return current balance | ledger | src/balance.py:10 | Observed | HIGH |",
        "| FR-001 | Return current balance | ledger | src/balance.py:10 | Observed | HIGH |\n"
        "| FR-001 | Return cached balance | ledger | src/cache.py:11 | Observed | HIGH |",
    )
    prd.write_text(text, encoding="utf-8")
    assert "duplicate requirement definition: FR-001" in validate_prd(prd)


def test_trace_status_must_match_definition(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    _write_valid_prd(prd)
    text = prd.read_text(encoding="utf-8").replace(
        "| FR-001 | Observed | src/balance.py:10 | Code | HIGH | none |",
        "| FR-001 | Inferred | src/balance.py:10 | Code | HIGH | none |",
    )
    prd.write_text(text, encoding="utf-8")
    assert any("traceability status" in error and "FR-001" in error for error in validate_prd(prd))


def test_trace_confidence_must_match_definition(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    _write_valid_prd(prd)
    text = prd.read_text(encoding="utf-8").replace(
        "| NFR-001 | Observed | src/api.py:30 | Code | MEDIUM | none |",
        "| NFR-001 | Observed | src/api.py:30 | Code | LOW | none |",
    )
    prd.write_text(text, encoding="utf-8")
    assert any("traceability confidence" in error and "NFR-001" in error for error in validate_prd(prd))


def test_traceability_requires_evidence_type_column(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    _write_valid_prd(prd)
    text = prd.read_text(encoding="utf-8").replace(
        "| Requirement ID | Requirement status | Evidence source(s) | Evidence type | Confidence | Notes / contradiction |",
        "| Requirement ID | Requirement status | Evidence source(s) | Confidence | Notes / contradiction |",
    )
    prd.write_text(text, encoding="utf-8")
    assert "traceability table missing column: evidence type" in validate_prd(prd)


def test_escaped_pipe_in_requirement_text_does_not_break_table(tmp_path: Path) -> None:
    prd = tmp_path / "PRD.md"
    _write_valid_prd(prd)
    text = prd.read_text(encoding="utf-8").replace(
        "Return current balance",
        r"Return current \| available balance",
    )
    prd.write_text(text, encoding="utf-8")
    assert validate_prd(prd) == []
