"""Regressions found during the final PR 148 review passes."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry import generic_package

ROOT = Path(__file__).resolve().parents[2]
COMMON_WORKFLOW = ROOT / "docs" / "skill-framework" / "shared" / "test-creator-common-workflow.md"


def test_common_workflow_requires_separate_report_and_state_guards() -> None:
    text = COMMON_WORKFLOW.read_text(encoding="utf-8")

    assert "fresh report-only guard" in text
    assert "fresh state-only guard" in text
    assert text.index("fresh report-only guard") < text.index("fresh state-only guard")


def test_common_workflow_preserves_unverified_when_execution_is_unavailable() -> None:
    text = COMMON_WORKFLOW.read_text(encoding="utf-8")

    assert "remain `UNVERIFIED`" in text
    assert "unsafe repository state" in text


def test_test_writer_aggregate_change_is_versioned_in_2_4_changelog() -> None:
    aggregate = (ROOT / "test-writer" / "workflow" / "aggregate.md").read_text(encoding="utf-8")
    changelog = (ROOT / "test-writer" / "CHANGELOG.md").read_text(encoding="utf-8")
    current_entry = changelog.split("## [2.4.0]", 1)[1].split("## [2.3.0]", 1)[0]

    assert "workflow_version: 1.6" in aggregate
    assert "`workflow/aggregate.md` → 1.6" in current_entry


@pytest.mark.parametrize(
    "required_rel",
    [
        "scripts/test_creator_write_guard.py",
        "scripts/git_paths.py",
    ],
)
def test_generic_package_requires_test_creator_runtime(
    monkeypatch: pytest.MonkeyPatch,
    required_rel: str,
) -> None:
    tracked = generic_package._tracked_files(ROOT)
    missing = (ROOT / required_rel).resolve()
    monkeypatch.setattr(
        generic_package,
        "_tracked_files",
        lambda root: {path for path in tracked if path.resolve() != missing},
    )

    with pytest.raises(ValueError, match="test-creator runtime"):
        generic_package._package_files(ROOT)
