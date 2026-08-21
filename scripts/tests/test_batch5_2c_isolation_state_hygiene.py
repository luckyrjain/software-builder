from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "loop-task-implementer/scripts/validate_loop_lifecycle.py"


def _load():
    spec = importlib.util.spec_from_file_location("loop_lifecycle_isolation", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity():
    return {"head_sha": "a" * 40}


def test_isolated_review_rejects_stale_exception_provenance():
    errors = _load()._isolation_errors(
        "lens_a",
        {
            "isolation_status": "ISOLATED",
            "isolation_exception_authorized": False,
            "isolation_exception_provenance": "stale authorization from an earlier review",
            "isolation_exception_change_identity": None,
            "isolation_exception_review_generated_at": None,
            "reviewed_change_identity": _identity(),
            "review_evidence": {"generated_at": "2026-08-21T00:00:00Z"},
        },
    )

    assert any("must not retain isolation_exception_provenance" in error for error in errors)


def test_isolated_review_rejects_stale_exception_review_generation():
    errors = _load()._isolation_errors(
        "lens_a",
        {
            "isolation_status": "ISOLATED",
            "isolation_exception_authorized": False,
            "isolation_exception_provenance": None,
            "isolation_exception_change_identity": None,
            "isolation_exception_review_generated_at": "2026-08-20T00:00:00Z",
            "reviewed_change_identity": _identity(),
            "review_evidence": {"generated_at": "2026-08-21T00:00:00Z"},
        },
    )

    assert any("must not retain isolation_exception_review_generated_at" in error for error in errors)


def test_not_isolated_exception_is_bound_to_current_review_generation():
    identity = _identity()
    current_generation = "2026-08-21T01:00:00Z"
    errors = _load()._isolation_errors(
        "lens_a",
        {
            "isolation_status": "NOT_ISOLATED",
            "isolation_exception_authorized": True,
            "isolation_exception_provenance": "human accepted this degraded review",
            "isolation_exception_change_identity": identity,
            "isolation_exception_review_generated_at": current_generation,
            "reviewed_change_identity": identity,
            "review_evidence": {"generated_at": current_generation},
        },
    )

    assert errors == []


def test_same_identity_rerun_rejects_exception_from_earlier_review_generation():
    identity = _identity()
    errors = _load()._isolation_errors(
        "lens_a",
        {
            "isolation_status": "NOT_ISOLATED",
            "isolation_exception_authorized": True,
            "isolation_exception_provenance": "human accepted the earlier degraded review",
            "isolation_exception_change_identity": identity,
            "isolation_exception_review_generated_at": "2026-08-21T01:00:00Z",
            "reviewed_change_identity": identity,
            "review_evidence": {"generated_at": "2026-08-21T02:00:00Z"},
        },
    )

    assert any("must be bound to the current review_evidence.generated_at" in error for error in errors)
