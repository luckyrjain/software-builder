"""Tests for contract-test-creator's Pact-tooling detection script."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "detect-pact-tooling.sh"
FIXTURES = ROOT / "tests" / "fixtures" / "pact-detect"


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


def test_node_consumer_with_broker_detected_medium_confidence():
    result = run_detect(FIXTURES / "node-consumer-with-broker")
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == "pact-js"
    assert fields["CONFIDENCE"] == "MEDIUM"
    assert fields["BROKER"] == "yes"


def test_python_provider_local_detected_high_confidence_no_broker():
    result = run_detect(FIXTURES / "python-provider-local")
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == "pact-python"
    assert fields["CONFIDENCE"] == "HIGH"
    assert fields["BROKER"] == "no"


def test_no_markers_returns_none_detected_and_exit_3():
    result = run_detect(FIXTURES / "none")
    fields = parse(result.stdout)
    assert result.returncode == 3
    assert fields["STATUS"] == "NONE_DETECTED"
    assert fields["BROKER"] == "no"


def test_hint_selects_named_candidate_when_present():
    result = run_detect(FIXTURES / "python-provider-local", ["--hint", "pact-python"])
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == "pact-python"


def test_hint_naming_an_undetected_library_falls_back_with_warning():
    result = run_detect(FIXTURES / "python-provider-local", ["--hint", "pact-go"])
    fields = parse(result.stdout)
    assert "matched no detected candidate" in result.stderr
    assert result.returncode == 0
    assert fields["FRAMEWORK"] == "pact-python"


def test_missing_root_directory_errors():
    result = run_detect(FIXTURES / "does-not-exist")
    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_missing_root_argument_prints_usage():
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "usage:" in result.stderr
