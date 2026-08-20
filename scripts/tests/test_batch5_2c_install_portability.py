from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from scripts.package_skill import package_skill


ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packaged_loop_validator_loads_only_vendored_shared_runtime(tmp_path: Path):
    dest = tmp_path / "loop-task-implementer"
    package_skill(
        skill="loop-task-implementer",
        repo_root=ROOT,
        dest=dest,
        host="test",
    )

    runtime = dest / "docs/skill-framework/shared/review_contract_runtime.py"
    validator_path = dest / "scripts/validate_loop_lifecycle.py"
    assert runtime.is_file()
    assert validator_path.is_file()

    validator = _load(validator_path, "installed_loop_lifecycle")
    shared = validator._load_shared_runtime()
    assert shared.validate_change_identity(
        {
            "schema_version": 1,
            "base_sha": "a" * 40,
            "head_sha": "b" * 40,
            "merge_base_sha": "a" * 40,
            "normalized_diff_fingerprint": "c" * 64,
            "changed_paths": ["src/a.py"],
            "generated_paths": [],
            "dependency_changes": [],
            "config_changes": [],
        }
    ) == []

    runtime.unlink()
    with pytest.raises(RuntimeError, match="packaged shared review runtime"):
        validator._load_shared_runtime()
