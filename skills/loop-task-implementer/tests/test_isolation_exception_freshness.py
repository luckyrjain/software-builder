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
            "isolation_exception_review_generation": None,
            "review_generation": 2,
            "reviewed_change_identity": _identity(),
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
            "isolation_exception_review_generation": 1,
            "review_generation": 2,
            "reviewed_change_identity": _identity(),
        },
    )

    assert any("must not retain isolation_exception_review_generation" in error for error in errors)


def test_not_isolated_exception_is_bound_to_current_review_generation():
    identity = _identity()
    errors = _load()._isolation_errors(
        "lens_a",
        {
            "isolation_status": "NOT_ISOLATED",
            "isolation_exception_authorized": True,
            "isolation_exception_provenance": "human accepted this degraded review",
            "isolation_exception_change_identity": identity,
            "isolation_exception_review_generation": 2,
            "review_generation": 2,
            "reviewed_change_identity": identity,
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
            "isolation_exception_review_generation": 1,
            "review_generation": 2,
            "reviewed_change_identity": identity,
        },
    )

    assert any("must be bound to the current review_generation" in error for error in errors)
