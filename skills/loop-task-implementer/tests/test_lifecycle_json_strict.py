from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "loop-task-implementer/scripts/validate_loop_lifecycle.py"


def _run(raw: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    state_path = tmp_path / "state.json"
    state_path.write_text(raw, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--state", str(state_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_rejects_duplicate_json_object_keys(tmp_path: Path):
    raw = '{"ci":{"required_checks_green":false,"required_checks_green":true}}'
    result = _run(raw, tmp_path)

    assert result.returncode == 2
    assert "duplicate JSON object key" in result.stderr
    assert "failed closed" in result.stderr


def test_cli_rejects_nonfinite_json_constants(tmp_path: Path):
    raw = json.dumps({"irrelevant": float("nan")})
    assert "NaN" in raw

    result = _run(raw, tmp_path)

    assert result.returncode == 2
    assert "non-finite JSON value is not allowed" in result.stderr
    assert "failed closed" in result.stderr


def test_cli_rejects_finite_syntax_that_overflows_python_float(tmp_path: Path):
    result = _run('{"irrelevant":1e999}', tmp_path)

    assert result.returncode == 2
    assert "JSON floating-point value is out of finite range" in result.stderr
    assert "failed closed" in result.stderr
