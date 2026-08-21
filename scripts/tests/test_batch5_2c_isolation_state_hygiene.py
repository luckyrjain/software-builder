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


def test_isolated_review_rejects_stale_exception_provenance():
    errors = _load()._isolation_errors(
        "lens_a",
        {
            "isolation_status": "ISOLATED",
            "isolation_exception_authorized": False,
            "isolation_exception_provenance": "stale authorization from an earlier review",
            "isolation_exception_change_identity": None,
            "reviewed_change_identity": {"head_sha": "a" * 40},
        },
    )

    assert any("must not retain isolation_exception_provenance" in error for error in errors)
