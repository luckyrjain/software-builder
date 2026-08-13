"""Tests for pr-gatekeeper/scripts/check-ask-point-drift.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-ask-point-drift.py"
SPEC = importlib.util.spec_from_file_location("check_ask_point_drift", SCRIPT)
assert SPEC and SPEC.loader
DRIFT_CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIFT_CHECK)


def test_unrelated_preceding_section_does_not_dilute_covered_gate(
    tmp_path: Path, monkeypatch,
) -> None:
    workflow_dir = tmp_path / "workflow"
    workflow_dir.mkdir()
    (workflow_dir / "posting.md").write_text(
        """# Posting

## Safe rendered-output boundary

Redact credentials immediately before external provider write calls. Rebuild every destination body
independently so retry fallback summary copying partial recovery cannot reveal sensitive private
information.

## User text input gates

When the skill must wait for the user at posting confirmation, or when ask-question is unavailable:

1. Pause execution until the user's next message contains an explicit choice from the numbered options.
2. Never infer consent from silence.
""",
        encoding="utf-8",
    )
    policy = tmp_path / "auto-post-policy.md"
    policy.write_text(
        """# Policy

Every user input gate for posting confirmation has one automation answer. When ask-question is
unavailable, wait for the next message with an explicit numbered option choice. Pause execution and
never infer consent.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(DRIFT_CHECK, "PR_REVIEW_WORKFLOW_DIR", workflow_dir)
    monkeypatch.setattr(DRIFT_CHECK, "AUTO_POST_POLICY", policy)
    monkeypatch.setattr(DRIFT_CHECK, "REPO_ROOT", tmp_path)

    assert DRIFT_CHECK.main() == 0
