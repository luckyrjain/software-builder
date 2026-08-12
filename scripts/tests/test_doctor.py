"""Tests for doctor preflight command."""

from __future__ import annotations

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


def test_doctor_blocks_when_no_read_capabilities_are_available(capsys) -> None:
    from scripts.doctor import cmd_doctor

    code = cmd_doctor(
        ROOT,
        skill_filter="pr-review",
        available=set(),
        install_roots=[Path("/nonexistent")],
    )
    assert code == 1
    output = capsys.readouterr().out
    assert "pr-review: BLOCKED" in output
    assert "GitLab read" in output
    assert "GitHub read" in output


def test_doctor_blocks_write_only_install(capsys) -> None:
    from scripts.doctor import cmd_doctor

    code = cmd_doctor(
        ROOT,
        skill_filter="pr-review",
        available={
            "gitlab.create_merge_request_thread",
            "gitlab.create_note",
            "github.create_pull_request_comment",
            "github.create_issue_comment",
        },
        install_roots=[Path("/nonexistent")],
    )
    assert code == 1
    assert "pr-review: BLOCKED" in capsys.readouterr().out


def test_doctor_blocks_incomplete_gitlab_read_path(capsys) -> None:
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


def test_doctor_blocks_incomplete_github_read_path(capsys) -> None:
    from scripts.doctor import cmd_doctor

    code = cmd_doctor(
        ROOT,
        skill_filter="pr-review",
        available={"github.get_pull_request"},
        install_roots=[Path("/nonexistent")],
    )
    assert code == 1
    output = capsys.readouterr().out
    assert "pr-review: BLOCKED" in output
    assert "github.get_pull_request_files" in output


def test_doctor_reports_degraded_when_optional_posting_is_missing(capsys) -> None:
    from scripts.doctor import cmd_doctor

    code = cmd_doctor(
        ROOT,
        skill_filter="pr-review",
        available={"gitlab.get_merge_request", "gitlab.get_merge_request_diffs"},
        install_roots=[Path("/nonexistent")],
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "pr-review: DEGRADED" in output
    assert "gitlab.create_merge_request_thread" in output


def test_doctor_supports_complete_github_read_path_without_posting(capsys) -> None:
    from scripts.doctor import cmd_doctor

    code = cmd_doctor(
        ROOT,
        skill_filter="pr-review",
        available={"github.get_pull_request", "github.get_pull_request_files"},
        install_roots=[Path("/nonexistent")],
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "pr-review: DEGRADED" in output
    assert "github.create_pull_request_comment" in output


def test_doctor_ready_for_complete_gitlab_read_and_write_path(capsys) -> None:
    from scripts.doctor import cmd_doctor

    code = cmd_doctor(
        ROOT,
        skill_filter="pr-review",
        available={
            "gitlab.get_merge_request",
            "gitlab.get_merge_request_diffs",
            "gitlab.create_merge_request_thread",
            "gitlab.create_note",
        },
        install_roots=[Path("/nonexistent")],
    )
    assert code == 0
    assert "pr-review: READY" in capsys.readouterr().out
