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
    result = _run('{"ci":{"required_checks_green":false,"required_checks_green":true}}', tmp_path)

    assert result.returncode == 2
    assert "duplicate JSON object key" in result.stderr
    assert "failed closed" in result.stderr


def test_cli_rejects_nonfinite_json_values(tmp_path: Path):
    raw = json.dumps({"irrelevant": float("nan")})
    assert "NaN" in raw

    result = _run(raw, tmp_path)

    assert result.returncode == 2
    assert "non-finite JSON value is not allowed" in result.stderr
    assert "failed closed" in result.stderr
