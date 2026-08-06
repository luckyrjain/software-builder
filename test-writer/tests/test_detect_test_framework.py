"""Tests for test-writer's framework-detection script."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "detect-test-framework.sh"
FIXTURES = ROOT / "tests" / "fixtures" / "test-framework-detect"


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


@pytest.mark.parametrize(
    "fixture,expected_framework,expected_confidence",
    [
        ("python-pytest", "pytest", "HIGH"),
        ("node-jest", "jest", "HIGH"),
        ("go-testing", "go test", "HIGH"),
    ],
)
def test_detects_expected_framework(fixture, expected_framework, expected_confidence):
    result = run_detect(FIXTURES / fixture)
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == expected_framework
    assert fields["CONFIDENCE"] == expected_confidence


def test_ambiguous_returns_both_candidates_and_exit_2():
    result = run_detect(FIXTURES / "ambiguous-js")
    fields = parse(result.stdout)
    assert result.returncode == 2
    assert fields["STATUS"] == "AMBIGUOUS"
    assert "jest" in fields["CANDIDATES"]
    assert "mocha" in fields["CANDIDATES"]


def test_hint_resolves_ambiguity_without_asking():
    result = run_detect(FIXTURES / "ambiguous-js", ["--hint", "mocha"])
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == "mocha"


def test_hint_naming_an_undetected_framework_falls_back_to_ambiguous():
    result = run_detect(FIXTURES / "ambiguous-js", ["--hint", "pytest"])
    fields = parse(result.stdout)
    assert result.returncode == 2
    assert fields["STATUS"] == "AMBIGUOUS"
    assert "--hint 'pytest' matched no detected candidate" in result.stderr


def test_no_markers_returns_none_detected_and_exit_3():
    result = run_detect(FIXTURES / "none")
    fields = parse(result.stdout)
    assert result.returncode == 3
    assert fields["STATUS"] == "NONE_DETECTED"


def test_missing_root_directory_errors():
    result = run_detect(FIXTURES / "does-not-exist")
    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_missing_root_argument_prints_usage():
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "usage:" in result.stderr
