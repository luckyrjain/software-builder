"""Tests for golden_refresh maintainer workflow."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.evals.golden import load_golden_fixtures, run_golden_case
from scripts.evals.golden_refresh import _golden_dir_for_fixture, refresh_fixture


def test_refresh_fixture_updates_recorded_output_and_meta(tmp_path: Path) -> None:
    fixture = tmp_path / "pr-review" / "sample.yaml"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(
        """\
schema_version: 1
skill: pr-review
case_id: sample-case
tier: 3
description: test
recorded_output:
  review_metadata:
    posted: false
assertions:
  - type: field_equals
    path: review_metadata.posted
    value: false
""",
        encoding="utf-8",
    )

    new_output = {"review_metadata": {"posted": False, "posting_mode": "chat-only"}}
    refresh_fixture(fixture, new_output, dry_run=False, note="pytest")

    raw = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    assert raw["recorded_output"] == new_output
    assert raw["refresh_meta"]["refresh_note"] == "pytest"
    assert "last_refreshed_at" in raw["refresh_meta"]

    cases = load_golden_fixtures(tmp_path)
    assert len(cases) == 1
    assert run_golden_case(cases[0]).passed


def test_refresh_dry_run_does_not_write(tmp_path: Path) -> None:
    fixture = tmp_path / "case.yaml"
    original = "schema_version: 1\nskill: pr-review\ncase_id: x\ntier: 3\ndescription: d\nrecorded_output: {}\nassertions:\n  - type: field_equals\n    path: review_metadata.posted\n    value: false\n"
    fixture.write_text(original, encoding="utf-8")
    refresh_fixture(fixture, {"review_metadata": {"posted": False}}, dry_run=True, note="dry")
    assert fixture.read_text(encoding="utf-8") == original


def test_golden_dir_for_nested_and_flat_paths(tmp_path: Path) -> None:
    nested = tmp_path / "evals" / "golden" / "pr-review" / "case.yaml"
    nested.parent.mkdir(parents=True)
    nested.write_text("x: 1\n", encoding="utf-8")
    assert _golden_dir_for_fixture(nested) == tmp_path / "evals" / "golden"

    flat = tmp_path / "evals" / "golden" / "case.yaml"
    flat.write_text("x: 1\n", encoding="utf-8")
    assert _golden_dir_for_fixture(flat) == tmp_path / "evals" / "golden"
