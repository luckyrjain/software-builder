"""Behavioral and parity tests for Batch 6B test-creator safety contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts" / "tests" / "fixtures" / "batch6b_test_creator_write_safety.yaml"
CREATOR_ROOTS = [
    "unit-test-creator",
    "integration-test-creator",
    "contract-test-creator",
    "e2e-test-creator",
    "api-test-creator",
]
COMMON_PHASES = (
    "workflow/inputs.md",
    "workflow/detect-conventions.md",
    "workflow/select-targets.md",
    "workflow/generate-tests.md",
    "workflow/verify-and-iterate.md",
    "workflow/report.md",
)
SHARED_GUARD_DOC = "test-creator-write-safety.md"


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _run("init", "-q", cwd=repo)
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _run("add", "README.md", cwd=repo)
    _run(
        "-c",
        "user.name=Batch 6B",
        "-c",
        "user.email=batch6b@example.invalid",
        "commit",
        "-qm",
        "initial",
        cwd=repo,
    )
    return repo


def _prepare_scenario(repo: Path, scenario: dict[str, object]) -> None:
    kind = scenario["kind"]
    dirty_file = scenario.get("dirty_file")
    if kind == "tracked_dirty":
        assert isinstance(dirty_file, str)
        path = repo / dirty_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("before\n", encoding="utf-8")
        _run("add", dirty_file, cwd=repo)
        _run(
            "-c",
            "user.name=Batch 6B",
            "-c",
            "user.email=batch6b@example.invalid",
            "commit",
            "-qm",
            "fixture file",
            cwd=repo,
        )
        path.write_text("user change\n", encoding="utf-8")
    elif kind == "untracked":
        assert isinstance(dirty_file, str)
        path = repo / dirty_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("user-created output\n", encoding="utf-8")
    elif kind != "clean":
        raise AssertionError(f"unknown fixture kind: {kind}")


@pytest.mark.parametrize("creator", CREATOR_ROOTS)
def test_all_creators_share_the_behavioral_write_safety_matrix(
    tmp_path: Path,
    creator: str,
) -> None:
    from scripts.test_creator_write_guard import check_write_safety

    fixture = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    assert creator in fixture["creators"]
    for scenario in fixture["scenarios"]:
        repo = _git_repo(tmp_path / scenario["id"] / creator)
        _prepare_scenario(repo, scenario)
        result = check_write_safety(repo, [scenario["planned_file"]])
        expected = scenario["expected"]
        assert result.allowed is expected["allowed"], scenario["id"]
        assert result.status == expected["status"], scenario["id"]
        assert list(result.conflicting_paths) == expected["conflicts"], scenario["id"]
        assert list(result.dirty_paths) == expected["dirty_paths"], scenario["id"]
        assert result.status_snapshot == tuple(result.status_snapshot)
        if scenario["kind"] == "clean":
            assert result.status_snapshot == ()
        else:
            assert result.status_snapshot


def test_guard_fails_closed_for_paths_outside_the_repository(tmp_path: Path) -> None:
    from scripts.test_creator_write_guard import check_write_safety

    repo = _git_repo(tmp_path)
    result = check_write_safety(repo, ["../outside-test.py"])
    assert result.allowed is False
    assert result.status == "BLOCKED"
    assert "outside repository" in result.reason.lower()


def test_guard_fails_closed_when_git_status_cannot_be_read(tmp_path: Path) -> None:
    from scripts.test_creator_write_guard import check_write_safety

    result = check_write_safety(tmp_path, ["tests/generated/example_test.py"])
    assert result.allowed is False
    assert result.status == "BLOCKED"
    assert "git status" in result.reason.lower()


def test_guard_fails_closed_for_a_symlinked_planned_path(tmp_path: Path) -> None:
    from scripts.test_creator_write_guard import check_write_safety

    repo = _git_repo(tmp_path)
    (repo / "real-output").mkdir()
    (repo / "linked-output").symlink_to(repo / "real-output", target_is_directory=True)
    result = check_write_safety(repo, ["linked-output/generated_test.py"])
    assert result.allowed is False
    assert result.status == "BLOCKED"
    assert "symlink" in result.reason.lower()


def test_guard_fails_closed_for_an_existing_ignored_output(tmp_path: Path) -> None:
    from scripts.test_creator_write_guard import check_write_safety

    repo = _git_repo(tmp_path)
    (repo / ".gitignore").write_text("ignored-output.py\n", encoding="utf-8")
    _run("add", ".gitignore", cwd=repo)
    _run(
        "-c",
        "user.name=Batch 6B",
        "-c",
        "user.email=batch6b@example.invalid",
        "commit",
        "-qm",
        "ignore generated output",
        cwd=repo,
    )
    (repo / "ignored-output.py").write_text("user file\n", encoding="utf-8")
    result = check_write_safety(repo, ["ignored-output.py"])
    assert result.allowed is False
    assert result.status == "BLOCKED"
    assert result.dirty_paths == ()
    assert result.conflicting_paths == ("ignored-output.py",)


def test_creator_workflows_reference_one_canonical_guard_and_report_contract() -> None:
    for creator in CREATOR_ROOTS:
        for phase in ("workflow/generate-tests.md", "workflow/report.md"):
            text = (ROOT / creator / phase).read_text(encoding="utf-8")
            assert SHARED_GUARD_DOC in text, f"{creator}/{phase} drifted from shared guard"


def test_all_creator_phases_reference_the_canonical_common_workflow() -> None:
    for creator in CREATOR_ROOTS:
        for phase in COMMON_PHASES:
            text = (ROOT / creator / phase).read_text(encoding="utf-8")
            assert "test-creator-common-workflow.md" in text, f"{creator}/{phase} drifted from common behavior"


def test_composition_contract_declares_creator_parity_requirements() -> None:
    contracts = yaml.safe_load(
        (ROOT / "scripts" / "registry" / "composition_contracts.yaml").read_text(encoding="utf-8"),
    )
    parity = contracts["creator_parity"]
    assert parity["skills"] == CREATOR_ROOTS
    assert parity["forwarded_fields"] == [
        "request",
        "repo_root",
        "target",
        "test_framework_hint",
        "run_tests",
        "max_files_per_run",
        "deadline",
        "session_token_budget",
        "output_dir",
        "specialist_inputs",
    ]
    assert parity["framework_owned_fields"] == ["execution_context"]
    assert parity["child_authority"] == "skill_result"
    assert parity["degraded_status"] == "BLOCKED"
    assert parity["interactive_gate_policy"] == "specialist-only"


def test_router_handoff_preserves_common_inputs_and_child_authority() -> None:
    inputs = (ROOT / "test-writer" / "workflow" / "inputs.md").read_text(encoding="utf-8")
    delegate = (ROOT / "test-writer" / "workflow" / "delegate.md").read_text(encoding="utf-8")
    for field in (
        "test_framework_hint",
        "run_tests",
        "max_files_per_run",
        "deadline",
        "session_token_budget",
        "output_dir",
        "specialist_inputs",
    ):
        assert field in delegate
    assert "byte-for-byte" in inputs
    assert "must not rewrite a child `BLOCKED`, `FAILED`, or `ESCALATED` result" in delegate
    assert "Do not add a router-level write or interactive gate" in (
        ROOT / "test-writer" / "SKILL.md"
    ).read_text(encoding="utf-8")


def test_shared_contract_defines_degraded_and_noninteractive_behavior() -> None:
    text = (ROOT / "docs" / "skill-framework" / "shared" / "test-creator-write-safety.md").read_text(
        encoding="utf-8",
    )
    for token in (
        "fails closed",
        "Dirty paths outside the planned set",
        "writes_started",
        "degraded `BLOCKED`",
        "must not introduce an interactive gate",
    ):
        assert token in text


def test_all_creator_contracts_produce_the_compatible_test_suite_shape() -> None:
    contracts = yaml.safe_load(
        (ROOT / "scripts" / "registry" / "composition_contracts.yaml").read_text(encoding="utf-8"),
    )
    expected = ["tests", "framework", "target_path"]
    for creator in CREATOR_ROOTS:
        assert contracts["skills"][creator]["produce_fields"]["test_suite"] == expected


@pytest.mark.parametrize("creator", CREATOR_ROOTS)
def test_each_installed_creator_bundle_contains_the_same_guard(tmp_path: Path, creator: str) -> None:
    from scripts.package_skill import package_skill

    destination = tmp_path / creator
    package_skill(skill=creator, repo_root=ROOT, dest=destination, host="test")
    packaged = destination / "scripts" / "test_creator_write_guard.py"
    canonical = ROOT / "scripts" / "test_creator_write_guard.py"
    assert packaged.read_bytes() == canonical.read_bytes()
