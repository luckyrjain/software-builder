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


def _make_entry(*, invokes=(), required=(), degraded_modes=None):
    # A synthetic minimal SkillEntry for render_skill_status branches
    # pr-review's fixture doesn't reach (no composition.invokes, no
    # degraded_modes on a required capability) -- built by hand instead of
    # hunting for a real skills.yaml entry with that exact shape, so the
    # test doesn't silently break if skills.yaml changes.
    from scripts.registry.models import (
        CapabilitiesSpec,
        CompositionSpec,
        HostClaude,
        HostCursor,
        Hosts,
        HostKiro,
        InstallSpec,
        LintSpec,
        SkillEntry,
    )

    return SkillEntry(
        path="synthetic-skill",
        category="test",
        invocation="ambient",
        hosts=Hosts(cursor=HostCursor(discovery="skill.md"), claude=HostClaude(), kiro=HostKiro(discovery="skill.md")),
        install=InstallSpec(),
        lint=LintSpec(skill_md_max_lines=500, target="skill.md"),
        composition=CompositionSpec(invokes=list(invokes)),
        capabilities=CapabilitiesSpec(required=list(required), degraded_modes=degraded_modes or {}),
    )


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


def test_render_skill_status_includes_composition_invokes() -> None:
    from scripts.doctor import SkillStatus, render_skill_status

    status = SkillStatus(
        skill_id="synthetic-skill",
        entry=_make_entry(invokes=["other-skill"]),
        status="READY",
    )

    text = render_skill_status(status)

    assert "invokes: other-skill" in text


def test_render_skill_status_includes_missing_required_degraded_hint() -> None:
    from scripts.doctor import SkillStatus, render_skill_status

    status = SkillStatus(
        skill_id="synthetic-skill",
        entry=_make_entry(required=["cap.a"], degraded_modes={"cap.a": "fallback text"}),
        status="BLOCKED",
        missing_required=["cap.a"],
    )

    text = render_skill_status(status)

    assert "missing required: cap.a" in text
    assert "cap.a -> fallback text" in text


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


def test_cmd_doctor_exits_nonzero_when_blocked(capsys) -> None:
    # The exit-code aggregation (`if status.status in {"BLOCKED", "VERSION_MISMATCH"}:
    # exit_code = 1`) lives in cmd_doctor itself, not in _skill_status -- the
    # structured-data tests above cover status computation but never exercise
    # this line, so a broken/typo'd condition there would pass the suite while
    # doctor silently stopped returning a failing exit code.
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


def test_cmd_doctor_exits_nonzero_on_version_mismatch(tmp_path: Path, capsys) -> None:
    from scripts.doctor import cmd_doctor
    from scripts.reference_utils import MANIFEST_NAME

    skill_dest = tmp_path / "pr-review"
    skill_dest.mkdir()
    (skill_dest / MANIFEST_NAME).write_text(
        json.dumps({"distribution_version": None, "source_sha": "deadbeefcafef00d1234"}),
        encoding="utf-8",
    )

    code = cmd_doctor(
        ROOT,
        skill_filter="pr-review",
        available=None,
        install_roots=[tmp_path],
    )

    assert code == 1
    output = capsys.readouterr().out
    assert "pr-review: VERSION_MISMATCH" in output
