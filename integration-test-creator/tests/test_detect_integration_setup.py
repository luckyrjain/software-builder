"""Tests for integration-test-creator's two-dimension detection script."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "detect-integration-setup.sh"
FIXTURES = ROOT / "tests" / "fixtures" / "integration-detect"


def run_detect(fixture_dir, extra_args=None):
    cmd = ["bash", str(SCRIPT), str(fixture_dir)]
    if extra_args:
        cmd += extra_args
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def parse(stdout):
    fields = {}
    for line in stdout.splitlines():
        if ": " in line:
            key, _, value = line.partition(": ")
            fields[key] = value
    return fields


def test_testcontainers_python_detects_both_dimensions():
    result = run_detect(FIXTURES / "testcontainers-python")
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == "pytest"
    assert fields["CONFIDENCE"] == "HIGH"
    assert fields["ORCHESTRATION"] == "testcontainers"
    assert fields["ORCHESTRATION_CONFIDENCE"] == "HIGH"
    assert "testcontainers" in fields["ORCHESTRATION_MARKER"]
    assert fields["CONVENTION"] != "none"


def test_docker_compose_node_detects_both_dimensions():
    result = run_detect(FIXTURES / "docker-compose-node")
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == "jest"
    assert fields["CONFIDENCE"] == "HIGH"
    assert fields["ORCHESTRATION"] == "docker-compose"
    assert fields["ORCHESTRATION_CONFIDENCE"] == "HIGH"
    assert "docker-compose" in fields["ORCHESTRATION_MARKER"]


def test_tag_only_no_orchestration_is_the_gate_case():
    """A repo with an integration tag/naming convention but no orchestration tool: base runner is
    still DETECTED, CONVENTION is set, but ORCHESTRATION is none — the NEEDS_INTEGRATION_ENV gate
    case, not a NONE_DETECTED run."""
    result = run_detect(FIXTURES / "tag-only-no-orchestration")
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == "pytest"
    assert fields["ORCHESTRATION"] == "none"
    assert fields["CONVENTION"] != "none"


def test_none_fixture_returns_none_detected_and_exit_3():
    result = run_detect(FIXTURES / "none")
    fields = parse(result.stdout)
    assert result.returncode == 3
    assert fields["STATUS"] == "NONE_DETECTED"
    assert fields["ORCHESTRATION"] == "none"
    assert fields["CONVENTION"] == "none"


def test_hint_resolves_base_runner_without_asking():
    result = run_detect(FIXTURES / "testcontainers-python", ["--hint", "pytest"])
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == "pytest"
    # Orchestration is still reported even when the base runner is resolved via hint.
    assert fields["ORCHESTRATION"] == "testcontainers"


def test_hint_naming_an_undetected_framework_falls_back(tmp_path):
    result = run_detect(FIXTURES / "testcontainers-python", ["--hint", "mocha"])
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == "pytest"
    assert "--hint 'mocha' matched no detected candidate" in result.stderr


def test_missing_root_directory_errors():
    result = run_detect(FIXTURES / "does-not-exist")
    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_missing_root_argument_prints_usage():
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "usage:" in result.stderr


@pytest.mark.parametrize(
    "fixture",
    ["testcontainers-python", "docker-compose-node", "tag-only-no-orchestration", "none"],
)
def test_orchestration_and_convention_fields_always_present(fixture):
    """Every run — regardless of STATUS/exit code — always reports ORCHESTRATION, ORCHESTRATION_CONFIDENCE,
    ORCHESTRATION_MARKER, and CONVENTION alongside the base-runner fields."""
    result = run_detect(FIXTURES / fixture)
    fields = parse(result.stdout)
    for key in ("ORCHESTRATION", "ORCHESTRATION_CONFIDENCE", "ORCHESTRATION_MARKER", "CONVENTION"):
        assert key in fields
