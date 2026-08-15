from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _phony_targets(makefile: Path) -> set[str]:
    targets: set[str] = set()
    for line in makefile.read_text(encoding="utf-8").splitlines():
        if line.startswith(".PHONY:"):
            targets.update(line.removeprefix(".PHONY:").split())
    return targets


def test_lint_prd_architect_is_declared_phony() -> None:
    assert "lint-prd-architect" in _phony_targets(ROOT / "Makefile")
