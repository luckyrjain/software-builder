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


def test_differential_scan_detects_only_changed_files(tmp_path: Path):
    """Differential scan: files fixed between before/after trees should drop out of hits."""
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "Bad.java").write_text('String q = "SELECT IFNULL(x,0)";', encoding="utf-8")
    (after / "Bad.java").write_text('String q = "SELECT COALESCE(x,0)";', encoding="utf-8")
    (before / "StillBad.java").write_text('String q = "SELECT DATE_FORMAT(x,\'%Y\')";', encoding="utf-8")
    (after / "StillBad.java").write_text('String q = "SELECT DATE_FORMAT(x,\'%Y\')";', encoding="utf-8")

    before_result = subprocess.run([str(SCAN), str(before)], capture_output=True, check=False)
    after_result = subprocess.run([str(SCAN), str(after)], capture_output=True, check=False)
    assert before_result.returncode != 0
    assert after_result.returncode != 0
    before_hits = before_result.stdout.decode().splitlines()
    after_hits = after_result.stdout.decode().splitlines()
    assert any(line.endswith("/Bad.java:1:") or "/Bad.java:" in line for line in before_hits)
    assert not any("/Bad.java:" in line for line in after_hits)
    assert any("/StillBad.java:" in line for line in after_hits)
