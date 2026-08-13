"""Tests for doctor preflight command."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_doctor_unspecified_without_available(capsys) -> None:
    from scripts.doctor import cmd_doctor

    code = cmd_doctor(
        ROOT,
        skill_filter="pr-review",
        available=None,
        install_roots=[Path("/nonexistent")],
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "pr-review: UNSPECIFIED" in output


def test_doctor_reports_blocked_capabilities(capsys) -> None:
    from scripts.doctor import cmd_doctor

    code = cmd_doctor(
        ROOT,
        skill_filter="pr-review",
        available={"gitlab.get_merge_request"},
        install_roots=[Path("/nonexistent")],
    )
    assert code == 1
    output = capsys.readouterr().out
    assert "pr-review: BLOCKED" in output
    assert "gitlab.get_merge_request_diffs" in output


def test_doctor_ready_when_all_required_present(capsys) -> None:
    from scripts.doctor import cmd_doctor

    code = cmd_doctor(
        ROOT,
        skill_filter="pr-review",
        available={"gitlab.get_merge_request", "gitlab.get_merge_request_diffs"},
        install_roots=[Path("/nonexistent")],
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "pr-review: READY" in output or "pr-review: DEGRADED" in output


def test_doctor_handles_null_source_sha_in_manifest(tmp_path, capsys) -> None:
    from scripts.doctor import cmd_doctor
    from scripts.reference_utils import MANIFEST_NAME
    from scripts.release_info import read_distribution_version

    distribution_version = read_distribution_version(ROOT)

    skill_dest = tmp_path / "pr-review"
    skill_dest.mkdir()
    manifest_path = skill_dest / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps({"distribution_version": distribution_version, "source_sha": None}),
        encoding="utf-8",
    )

    code = cmd_doctor(
        ROOT,
        skill_filter="pr-review",
        available=None,
        install_roots=[tmp_path],
    )

    output = capsys.readouterr().out
    assert "pr-review: UNSPECIFIED" in output
    assert f"install: installed ({distribution_version} @ unknown)" in output
    assert code == 0
