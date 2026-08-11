"""Tests for the registered-skill-path listing helper.

scripts/list_registered_skill_paths.py backs the Makefile's lint-framework
target: it builds the repo-wide reference validator's --exclude list from
skills.yaml (via the registry loader) instead of a second, driftable
hand-maintained list of skill directories.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_lists_every_registered_skill_path(capsys) -> None:
    from scripts.list_registered_skill_paths import main
    from scripts.registry.load import load_registry

    registry = load_registry(ROOT)
    expected = sorted(entry.path for entry in registry.skills.values())

    code = main()

    assert code == 0
    output = capsys.readouterr().out
    printed = [line for line in output.splitlines() if line]
    assert printed == expected
    assert len(printed) > 0
