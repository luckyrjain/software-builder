from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[2]


def _load_validator():
    path = ROOT / "scripts/validate_review_contracts.py"
    spec = importlib.util.spec_from_file_location("validate_review_contracts_generated", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_file_content_changes_effective_patch_fingerprint():
    validator = _load_validator()
    before = "diff --git a/generated/client.py b/generated/client.py\n+version = 1\n"
    after = "diff --git a/generated/client.py b/generated/client.py\n+version = 2\n"
    assert validator.normalized_diff_fingerprint(before) != validator.normalized_diff_fingerprint(after)
