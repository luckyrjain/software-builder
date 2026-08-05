"""Policy rows mirrored from mysql-to-postgres-sql pressure harness."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ROOT / "scripts" / "scan-mysql-dialect.sh"
HITS = ROOT / "tests" / "fixtures" / "mysql-dialect" / "hits"
CLEAN = ROOT / "tests" / "fixtures" / "mysql-dialect" / "clean"
SKILL_CONTRACT = ROOT / "reference" / "skill-contract.md"


def test_scan_hits_fixture_fails():
    result = subprocess.run(
        [str(SCAN), str(HITS)],
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0, "hits fixture must exit non-zero"


def test_scan_clean_fixture_passes():
    result = subprocess.run(
        [str(SCAN), str(CLEAN)],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, "clean fixture must exit 0"


def test_skill_contract_gates_premature_completion():
    text = SKILL_CONTRACT.read_text(encoding="utf-8")
    assert "Never report" in text or "Complete means gated" in text
