"""The Windows CI job lists its test files by name, so a new engine test file would silently not
run there unless it is added. Fail instead of skipping quietly."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_the_windows_job_runs_every_install_engine_test_file() -> None:
    workflow = (ROOT / ".github" / "workflows" / "lint.yml").read_text(encoding="utf-8")
    job = workflow.split("  install-engine-windows:", 1)[1]
    for test_file in sorted((ROOT / "scripts" / "tests").glob("test_install_engine_*.py")):
        assert f"scripts/tests/{test_file.name}" in job, (
            f"{test_file.name} is not run by the install-engine-windows job in .github/workflows/lint.yml"
        )
