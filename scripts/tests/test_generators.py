"""Tests for scripts/registry/generators.py's collect_outputs."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry import generators as generators_module
from scripts.registry.generators import collect_outputs

ROOT = Path(__file__).resolve().parents[2]


def test_collect_outputs_covers_real_repo_with_no_collision() -> None:
    outputs = collect_outputs(ROOT)
    assert outputs  # sanity: at least one generator opted in for this repo


def test_collect_outputs_raises_on_generator_path_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    # Two generators claiming the same output path used to silently last-write-win
    # (dict.update's ordinary behavior) -- this proves it now fails loudly instead.
    def _generator_a(ctx: object) -> dict[Path, str]:
        return {Path("shared/output.txt"): "from a"}

    def _generator_b(ctx: object) -> dict[Path, str]:
        return {Path("shared/output.txt"): "from b"}

    monkeypatch.setattr(generators_module, "GENERATORS", (_generator_a, _generator_b))
    with pytest.raises(ValueError, match="generator collision"):
        collect_outputs(ROOT)
