"""Tests for doctor preflight command."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# pr-review's registry entry (skills.yaml) is the fixture every test below uses:
# 2 required capabilities, 2 optional (each with a degraded_modes entry), no
# composition.invokes. Asserting against it directly means status.status can be
# pinned exactly instead of read off rendered text.


def _pr_review_entry():
    from scripts.registry.schema import parse_registry

    registry = parse_registry(ROOT / "skills.yaml")
    return registry.skills["pr-review"]


def test_skill_status_unspecified_without_available() -> None:
    from scripts.doctor import _skill_status

    status = _skill_status(
        "pr-review",
        _pr_review_entry(),
        available=None,
        install_roots=[Path("/nonexistent")],
        distribution_version="1.0.0",
    )

    assert status.status == "UNSPECIFIED"
    assert status.missing_required == []
    assert status.missing_optional == []
    assert status.installed_label == "not installed"


def test_skill_status_blocked_on_missing_required_capability() -> None:
    from scripts.doctor import _skill_status

    status = _skill_status(
        "pr-review",
        _pr_review_entry(),
        available={"gitlab.get_merge_request"},
        install_roots=[Path("/nonexistent")],
        distribution_version="1.0.0",
    )

    assert status.status == "BLOCKED"
    assert status.missing_required == ["gitlab.get_merge_request_diffs"]


def test_skill_status_degraded_on_missing_optional_capability() -> None:
    from scripts.doctor import _skill_status

    status = _skill_status(
        "pr-review",
        _pr_review_entry(),
        available={"gitlab.get_merge_request", "gitlab.get_merge_request_diffs"},
        install_roots=[Path("/nonexistent")],
        distribution_version="1.0.0",
    )

    assert status.status == "DEGRADED"
    assert status.missing_required == []
    assert set(status.missing_optional) == {
        "gitlab.create_merge_request_thread",
        "gitlab.create_note",
    }


def test_skill_status_ready_when_all_capabilities_present() -> None:
    from scripts.doctor import _skill_status

    status = _skill_status(
        "pr-review",
        _pr_review_entry(),
        available={
            "gitlab.get_merge_request",
            "gitlab.get_merge_request_diffs",
            "gitlab.create_merge_request_thread",
            "gitlab.create_note",
        },
        install_roots=[Path("/nonexistent")],
        distribution_version="1.0.0",
    )

    assert status.status == "READY"
    assert status.missing_required == []
    assert status.missing_optional == []


def test_skill_status_handles_null_source_sha_in_manifest(tmp_path: Path) -> None:
    from scripts.doctor import _skill_status
    from scripts.reference_utils import MANIFEST_NAME

    skill_dest = tmp_path / "pr-review"
    skill_dest.mkdir()
    (skill_dest / MANIFEST_NAME).write_text(
        json.dumps({"distribution_version": "1.0.0", "source_sha": None}),
        encoding="utf-8",
    )

    status = _skill_status(
        "pr-review",
        _pr_review_entry(),
        available=None,
        install_roots=[tmp_path],
        distribution_version="1.0.0",
    )

    assert status.installed_label == "installed (1.0.0 @ unknown)"
    assert status.status == "UNSPECIFIED"


def test_skill_status_handles_null_distribution_version_in_manifest(tmp_path: Path) -> None:
    # distribution_version got the same null-vs-missing treatment as source_sha
    # above: manifest.get(key, default) only falls back for a missing key, not
    # an explicit JSON null, so a null distribution_version used to print as
    # the literal string "None" instead of "unknown".
    from scripts.doctor import _skill_status
    from scripts.reference_utils import MANIFEST_NAME

    skill_dest = tmp_path / "pr-review"
    skill_dest.mkdir()
    (skill_dest / MANIFEST_NAME).write_text(
        json.dumps({"distribution_version": None, "source_sha": "deadbeefcafef00d1234"}),
        encoding="utf-8",
    )

    status = _skill_status(
        "pr-review",
        _pr_review_entry(),
        available=None,
        install_roots=[tmp_path],
        distribution_version="1.0.0",
    )

    assert status.installed_label == "installed (unknown @ deadbeefcafe)"
    assert status.status == "VERSION_MISMATCH"


def test_render_skill_status_includes_missing_optional_and_degraded_hints() -> None:
    from scripts.doctor import _skill_status, render_skill_status

    status = _skill_status(
        "pr-review",
        _pr_review_entry(),
        available={"gitlab.get_merge_request", "gitlab.get_merge_request_diffs"},
        install_roots=[Path("/nonexistent")],
        distribution_version="1.0.0",
    )

    text = render_skill_status(status)

    assert "pr-review: DEGRADED" in text
    assert "missing optional: gitlab.create_merge_request_thread, gitlab.create_note" in text
    assert "gitlab.create_merge_request_thread -> summary-only or chat-only posting" in text
    assert "gitlab.create_note -> chat-only posting" in text
    assert "install: not installed" in text


def test_render_skill_status_includes_capability_check_hint_when_unspecified() -> None:
    from scripts.doctor import _skill_status, render_skill_status

    status = _skill_status(
        "pr-review",
        _pr_review_entry(),
        available=None,
        install_roots=[Path("/nonexistent")],
        distribution_version="1.0.0",
    )

    text = render_skill_status(status)

    assert "capability check: pass --available to evaluate host capabilities" in text


def test_cmd_doctor_wires_status_and_render_together(capsys) -> None:
    # Thin integration check that cmd_doctor actually composes _skill_status ->
    # render_skill_status -> print correctly, and returns the exit code the
    # rendered status implies. The detailed status/render behavior is covered
    # by the structured-data tests above; this only confirms the wiring.
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
    assert "capability check: pass --available to evaluate host capabilities" in output
