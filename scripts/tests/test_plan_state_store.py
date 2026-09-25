"""Tests for scripts/plan_state_store.py: durable, locked, atomic backing for plan_execution_state.

Fixtures mirror scripts/tests/test_plan_execution_state.py's `_plan`/`_task`/`_official_state`
helpers exactly, so a plan built here validates the same way against the already-tested
`advance_plan_execution_state`/`initial_plan_execution_state` this module wraps.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from scripts.implementation_plan import derive_plan_id
from scripts.plan_state_store import (
    MAX_COMPLETED_EVIDENCE_REFS,
    PlanStateCasError,
    PlanStateLockTimeoutError,
    PlanStateStoreError,
    _lock_path,
    _private_dir,
    cas_advance,
    read_state,
    resolve_state_dir,
    state_path,
)

if sys.platform != "win32":
    import fcntl

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX flock semantics")

ROOT = Path(__file__).resolve().parents[2]

UPDATED_AT = "2026-09-25T00:00:00Z"
HEAD = "a" * 40


def _task(task_id: str, dependencies: list[str] | None = None) -> dict[str, object]:
    return {
        "task_id": task_id,
        "title": f"Implement {task_id}",
        "task_type": "code",
        "executor": "loop-task-implementer",
        "scope": "Implement the bounded task.",
        "target_paths": ["src/checkout.py"],
        "acceptance_criteria": ["The task behavior is implemented."],
        "dependencies": dependencies or [],
        "required_tests": ["pytest -q tests/test_checkout.py"],
        "verification": ["Run the focused test command."],
        "rollout_notes": ["Deploy behind the existing release gate."],
        "completion_evidence": ["Focused test output and review evidence."],
        "source_condition_refs": ["condition:timeout-budget"],
        "source_action_refs": ["action:implement-timeout"],
        "estimated_scope": {
            "estimate_known": True,
            "files_upper_bound": 1,
            "changed_lines_upper_bound": 50,
            "confidence": "HIGH",
        },
    }


def _plan() -> dict[str, object]:
    plan_set_id = "PLANSET-123456789abc"
    target_repo = "https://github.com/acme/checkout"
    return {
        "plan_set_id": plan_set_id,
        "plan_id": derive_plan_id(plan_set_id, target_repo),
        "title": "Checkout resilience implementation",
        "readiness": "READY",
        "assessment_target": {"repo": "github.com/acme/checkout"},
        "target_repo": target_repo,
        "external_dependencies": [],
        "source_refs": ["change-impact:abc", "system-design:def", "architecture:ghi"],
        "tasks": [_task("TASK-001"), _task("TASK-002", ["TASK-001"])],
        "execution_waves": [["TASK-001"], ["TASK-002"]],
        "sequencing_constraints": ["Run TASK-001 before TASK-002."],
        "verification_gates": ["All required tests pass."],
        "traceability": {
            "condition_coverage": {"condition:timeout-budget": ["TASK-001"]},
            "action_coverage": {"action:implement-timeout": ["TASK-001"]},
            "required_test_coverage": {"pytest -q tests/test_checkout.py": ["TASK-001"]},
        },
    }


def _official_state(**overrides: str) -> dict[str, str]:
    state = {task["task_id"]: "NOT_STARTED" for task in _plan()["tasks"]}
    state.update(overrides)
    return state


# --- cas_advance success / CAS rejection ------------------------------------------------------


def test_cas_advance_creates_generation_zero_then_advances_to_one(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    plan = _plan()
    result = cas_advance(
        state_dir,
        plan,
        expected_generation=0,
        authoritative_task_statuses=_official_state(),
        current_head=HEAD,
        updated_at=UPDATED_AT,
    )
    assert result["state_generation"] == 1
    assert result["plan_id"] == plan["plan_id"]

    on_disk = read_state(state_dir, plan["plan_id"])
    assert on_disk == result

    advanced = cas_advance(
        state_dir,
        plan,
        expected_generation=1,
        authoritative_task_statuses=_official_state(**{"TASK-001": "COMPLETE"}),
        current_head=HEAD,
        updated_at="2026-09-25T00:01:00Z",
    )
    assert advanced["state_generation"] == 2
    assert advanced["task_statuses"]["TASK-001"] == "COMPLETE"


def test_cas_advance_rejects_a_stale_expected_generation(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    plan = _plan()
    cas_advance(
        state_dir,
        plan,
        expected_generation=0,
        authoritative_task_statuses=_official_state(),
        current_head=HEAD,
        updated_at=UPDATED_AT,
    )
    with pytest.raises(PlanStateCasError):
        cas_advance(
            state_dir,
            plan,
            expected_generation=0,  # stale: the store already advanced to generation 1
            authoritative_task_statuses=_official_state(**{"TASK-001": "COMPLETE"}),
            current_head=HEAD,
            updated_at="2026-09-25T00:02:00Z",
        )
    # The rejected write must not have landed.
    on_disk = read_state(state_dir, plan["plan_id"])
    assert on_disk["state_generation"] == 1
    assert on_disk["task_statuses"]["TASK-001"] != "COMPLETE"


# --- lock timeout ---------------------------------------------------------------------------


@posix_only
def test_a_live_held_lock_times_out_with_a_bounded_wait(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    plan = _plan()
    _private_dir(state_dir)
    lock_path = _lock_path(state_dir, plan["plan_id"])
    holder_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(holder_fd, fcntl.LOCK_EX)
    try:
        started = time.monotonic()
        with pytest.raises(PlanStateLockTimeoutError):
            cas_advance(
                state_dir,
                plan,
                expected_generation=0,
                authoritative_task_statuses=_official_state(),
                current_head=HEAD,
                updated_at=UPDATED_AT,
                timeout=0.3,
            )
        elapsed = time.monotonic() - started
        assert elapsed < 5.0  # nowhere near the 30s default: proves the short timeout was honored
    finally:
        fcntl.flock(holder_fd, fcntl.LOCK_UN)
        os.close(holder_fd)

    # Once released, the same call succeeds normally.
    result = cas_advance(
        state_dir,
        plan,
        expected_generation=0,
        authoritative_task_statuses=_official_state(),
        current_head=HEAD,
        updated_at=UPDATED_AT,
    )
    assert result["state_generation"] == 1


# --- directory refusal (Condition 2) ----------------------------------------------------------


def test_resolve_state_dir_refuses_a_path_inside_a_git_repository() -> None:
    assert (ROOT / ".git").exists(), "this test assumes it runs inside a git checkout"
    with pytest.raises(PlanStateStoreError):
        resolve_state_dir(str(ROOT / "scratch-plan-state-dir"))


def test_state_path_rejects_an_unsafe_plan_id(tmp_path: Path) -> None:
    for bad in ("../escape", "", "a/b", ".", ".."):
        with pytest.raises(PlanStateStoreError):
            state_path(tmp_path, bad)


# --- malformed/corrupt existing file fails closed -----------------------------------------------


def test_read_state_returns_none_when_nothing_was_ever_written(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    assert read_state(state_dir, "PLAN-NEVER-WRITTEN") is None


def test_read_state_fails_closed_on_invalid_json(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    plan_id = "PLAN-CORRUPT-JSON"
    _private_dir(state_dir)
    state_path(state_dir, plan_id).write_text("{not valid json", encoding="utf-8")
    with pytest.raises(PlanStateStoreError):
        read_state(state_dir, plan_id)


def test_read_state_fails_closed_on_a_wrong_shaped_object(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    plan_id = "PLAN-WRONG-SHAPE"
    _private_dir(state_dir)
    state_path(state_dir, plan_id).write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    with pytest.raises(PlanStateStoreError):
        read_state(state_dir, plan_id)


def test_cas_advance_fails_closed_on_a_corrupt_existing_file_rather_than_overwriting_it(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    plan = _plan()
    _private_dir(state_dir)
    corrupt_path = state_path(state_dir, plan["plan_id"])
    corrupt_path.write_text("]] not json [[", encoding="utf-8")
    with pytest.raises(PlanStateStoreError):
        cas_advance(
            state_dir,
            plan,
            expected_generation=0,
            authoritative_task_statuses=_official_state(),
            current_head=HEAD,
            updated_at=UPDATED_AT,
        )
    # The corrupt file must be left exactly as it was, never silently replaced.
    assert corrupt_path.read_text(encoding="utf-8") == "]] not json [["


# --- completed_evidence_refs cap ----------------------------------------------------------------


def test_cas_advance_refuses_to_exceed_the_evidence_ref_cap_rather_than_truncating(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    plan = _plan()
    cas_advance(
        state_dir,
        plan,
        expected_generation=0,
        authoritative_task_statuses=_official_state(),
        current_head=HEAD,
        updated_at=UPDATED_AT,
    )
    too_many = [f"ref-{i}" for i in range(MAX_COMPLETED_EVIDENCE_REFS + 1)]
    with pytest.raises(PlanStateStoreError):
        cas_advance(
            state_dir,
            plan,
            expected_generation=1,
            authoritative_task_statuses=_official_state(),
            current_head=HEAD,
            updated_at="2026-09-25T00:05:00Z",
            completed_evidence_refs=too_many,
        )
    # Refused, not truncated to the cap and written anyway: generation and refs are unchanged.
    on_disk = read_state(state_dir, plan["plan_id"])
    assert on_disk["state_generation"] == 1
    assert on_disk["completed_evidence_refs"] == []


def test_cas_advance_merges_evidence_refs_across_calls_rather_than_replacing(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    plan = _plan()
    cas_advance(
        state_dir,
        plan,
        expected_generation=0,
        authoritative_task_statuses=_official_state(),
        current_head=HEAD,
        updated_at=UPDATED_AT,
        completed_evidence_refs=["ci:task-001"],
    )
    result = cas_advance(
        state_dir,
        plan,
        expected_generation=1,
        authoritative_task_statuses=_official_state(),
        current_head=HEAD,
        updated_at="2026-09-25T00:06:00Z",
        completed_evidence_refs=["ci:task-002"],
    )
    assert result["completed_evidence_refs"] == ["ci:task-001", "ci:task-002"]
