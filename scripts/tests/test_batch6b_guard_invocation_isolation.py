"""Regression coverage for isolated test-creator guard invocation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shared_guard_invocation_uses_python_isolated_mode() -> None:
    contract = (
        ROOT / "docs" / "skill-framework" / "shared" / "test-creator-write-safety.md"
    ).read_text(encoding="utf-8")

    assert 'python3 -I "<installed creator package>/scripts/test_creator_write_guard.py"' in contract
