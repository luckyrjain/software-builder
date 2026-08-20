"""Behavioral and parity tests for Batch 6B test-creator safety contracts."""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
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


def _run_creator_guard(creator: str, repo: Path, planned_file: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / creator / "scripts" / "test_creator_write_guard.py"),
            "--repo-root",
            str(repo),
            "--planned-file",
            planned_file,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode in (0, 2), completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.parametrize("creator", CREATOR_ROOTS)
def test_all_creators_share_the_behavioral_write_safety_matrix(
    tmp_path: Path,
    creator: str,
) -> None:
    fixture = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    assert creator in fixture["creators"]
    for scenario in fixture["scenarios"]:
        repo = _git_repo(tmp_path / scenario["id"] / creator)
        _prepare_scenario(repo, scenario)
        result = _run_creator_guard(creator, repo, scenario["planned_file"])
        expected = scenario["expected"]
        assert result["allowed"] is expected["allowed"], scenario["id"]
        assert result["status"] == expected["status"], scenario["id"]
        assert result["conflicting_paths"] == expected["conflicts"], scenario["id"]
        assert result["dirty_paths_before"] == expected["dirty_paths"], scenario["id"]
        assert result["status_snapshot"] == sorted(result["status_snapshot"])
        assert result["writes_started"] is False
        if scenario["kind"] == "clean":
            assert result["status_snapshot"] == []
        else:
            assert result["status_snapshot"]


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


def test_guard_returns_structured_blocked_result_when_git_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.test_creator_write_guard as guard

    repo = _git_repo(tmp_path)

    def missing_git(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(guard.subprocess, "run", missing_git)
    result = guard.check_write_safety(repo, ["tests/generated/example_test.py"])

    assert result.status == "BLOCKED"
    assert result.writes_started is False
    assert result.to_dict()["status_snapshot"] == []
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
    assert result.dirty_paths_before == ()
    assert result.conflicting_paths == ("ignored-output.py",)


def test_guard_fails_closed_for_a_hardlinked_planned_output(tmp_path: Path) -> None:
    from scripts.test_creator_write_guard import check_write_safety

    repo = _git_repo(tmp_path)
    planned = repo / "generated_test.py"
    planned.write_text("tracked source\n", encoding="utf-8")
    _run("add", "generated_test.py", cwd=repo)
    _run(
        "-c",
        "user.name=Batch 6B",
        "-c",
        "user.email=batch6b@example.invalid",
        "commit",
        "-qm",
        "tracked output",
        cwd=repo,
    )
    external = tmp_path / "external-user-file.py"
    external.hardlink_to(planned)

    result = check_write_safety(repo, ["generated_test.py"])

    assert result.allowed is False
    assert result.status == "BLOCKED"
    assert result.conflicting_paths == ("generated_test.py",)
    assert "hard link" in result.reason.lower()


def test_guard_blocks_a_staged_overlap(tmp_path: Path) -> None:
    from scripts.test_creator_write_guard import check_write_safety

    repo = _git_repo(tmp_path)
    path = repo / "staged_test.py"
    path.write_text("committed\n", encoding="utf-8")
    _run("add", "staged_test.py", cwd=repo)
    _run(
        "-c",
        "user.name=Batch 6B",
        "-c",
        "user.email=batch6b@example.invalid",
        "commit",
        "-qm",
        "staged fixture",
        cwd=repo,
    )
    path.write_text("staged user change\n", encoding="utf-8")
    _run("add", "staged_test.py", cwd=repo)

    result = check_write_safety(repo, ["staged_test.py"])

    assert result.status == "BLOCKED"
    assert result.dirty_paths_before == ("staged_test.py",)
    assert result.conflicting_paths == ("staged_test.py",)


def test_guard_blocks_both_sides_of_a_rename_overlap(tmp_path: Path) -> None:
    from scripts.test_creator_write_guard import check_write_safety

    repo = _git_repo(tmp_path)
    old = repo / "old_test.py"
    old.write_text("test\n", encoding="utf-8")
    _run("add", "old_test.py", cwd=repo)
    _run(
        "-c",
        "user.name=Batch 6B",
        "-c",
        "user.email=batch6b@example.invalid",
        "commit",
        "-qm",
        "rename fixture",
        cwd=repo,
    )
    _run("mv", "old_test.py", "new_test.py", cwd=repo)

    result = check_write_safety(repo, ["old_test.py", "new_test.py"])

    assert result.status == "BLOCKED"
    assert result.conflicting_paths == ("new_test.py", "old_test.py")
    assert result.dirty_paths_before == ("new_test.py", "old_test.py")


def test_guard_blocks_untracked_output_with_a_newline_in_its_name(tmp_path: Path) -> None:
    from scripts.test_creator_write_guard import check_write_safety

    repo = _git_repo(tmp_path)
    filename = "user\nowned_test.py"
    (repo / filename).write_text("user output\n", encoding="utf-8")

    result = check_write_safety(repo, [filename])

    assert result.status == "BLOCKED"
    assert result.dirty_paths_before == (filename,)
    assert result.conflicting_paths == (filename,)


def test_guard_results_match_the_documented_write_evidence_schema(tmp_path: Path) -> None:
    from scripts.test_creator_write_guard import check_write_safety

    result = check_write_safety(_git_repo(tmp_path), ["tests/generated/example_test.py"])
    payload = result.to_dict()

    assert payload["status"] == "ALLOWED"
    assert payload["dirty_paths_before"] == []
    assert payload["status_snapshot"] == []
    assert payload["conflicting_paths"] == []
    assert payload["writes_started"] is False


def test_generic_bundle_contains_a_runnable_guard_for_each_creator(tmp_path: Path) -> None:
    from scripts.registry.generic_package import build_generic_package

    archive_path = tmp_path / "software-builder.tar.gz"
    build_generic_package(ROOT, archive_path)
    extract_root = tmp_path / "extract"
    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(extract_root, filter="data")

    packaged_root = extract_root / "software-builder"
    for creator in CREATOR_ROOTS:
        repo = _git_repo(tmp_path / "fixtures" / creator)
        result = _run_creator_guard_from_root(
            packaged_root / creator / "scripts" / "test_creator_write_guard.py",
            repo,
            "tests/generated/example_test.py",
        )
        assert result["allowed"] is True, creator


def _run_creator_guard_from_root(script: Path, repo: Path, planned_file: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(script), "--repo-root", str(repo), "--planned-file", planned_file],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode in (0, 2), completed.stderr
    return json.loads(completed.stdout)


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
    assert parity["router_gate_policy"] == "classification-only"
    required = set(parity["forwarded_fields"])
    for creator in [*CREATOR_ROOTS, "test-writer"]:
        consumed = set(contracts["skills"][creator]["consume_fields"]["implementation_task"])
        assert required <= consumed, creator


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
    assert "complete" in delegate
    assert "`skill_result` envelope" in delegate
    aggregate = (ROOT / "test-writer" / "workflow" / "aggregate.md").read_text(encoding="utf-8")
    assert "Dispatched entries must also carry `skill_result`" in aggregate
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
