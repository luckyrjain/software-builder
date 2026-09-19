from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.package_skill import package_skill


ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "run-packaged-1"
SECRET = "Xk9f" + "Q2mZp7Lr4TvB8nWd"  # a made-up value, assembled so a scanner does not read it as a real one


def _package(tmp_path: Path) -> Path:
    dest = tmp_path / "loop-task-implementer"
    package_skill(skill="loop-task-implementer", repo_root=ROOT, dest=dest, host="test")
    return dest


def _run(script: Path, cwd: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args], cwd=cwd, input=stdin, capture_output=True, text=True, check=False,
        env={**os.environ},
    )


def test_the_installed_run_log_works_from_another_directory_and_ships_redaction(tmp_path: Path):
    package = _package(tmp_path)
    script = package / "scripts/run_log.py"
    assert script.is_file() and (package / "docs/skill-framework/shared/redaction.py").is_file()
    elsewhere = tmp_path / "some-other-place"
    elsewhere.mkdir()
    log_dir = tmp_path / "logs"
    common = ["--run-id", RUN_ID, "--log-dir", str(log_dir)]

    started = _run(script, elsewhere, "append", *common, "--event", "run_started", "--actor", "orchestrator",
                   "--data-json", "-", stdin=json.dumps({"note": "token=" + SECRET}))
    assert started.returncode == 0, started.stderr
    head = json.loads(started.stdout)["chain_head"]
    assert SECRET not in (log_dir / f"{RUN_ID}.jsonl").read_text()  # the vendored redaction ran
    assert _run(script, elsewhere, "verify", *common, "--expect-head", head).returncode == 0
    assert _run(script, elsewhere, "budget", *common, "--expect-head", head).returncode == 0
    made = _run(script, elsewhere, "run-id", stdin='["repo","main","T-1"]')
    assert made.returncode == 0 and made.stdout.startswith("run-")


def test_an_installed_run_log_without_its_redaction_module_fails_closed_even_with_no_data(tmp_path: Path):
    package = _package(tmp_path)
    (package / "docs/skill-framework/shared/redaction.py").unlink()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = _run(package / "scripts/run_log.py", elsewhere, "append", "--run-id", RUN_ID, "--log-dir",
                  str(tmp_path / "logs"), "--event", "run_started", "--actor", "orchestrator")
    assert result.returncode == 2 and "redaction" in result.stderr
    assert not (tmp_path / "logs" / f"{RUN_ID}.jsonl").exists()
