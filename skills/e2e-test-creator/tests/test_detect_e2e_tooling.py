"""Tests for e2e-test-creator's browser-tooling detection script."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "detect-e2e-tooling.sh"
FIXTURES = ROOT / "tests" / "fixtures" / "e2e-detect"


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
    "fixture,expected_framework,expected_confidence,expected_layout_prefix",
    [
        ("playwright-repo", "playwright", "HIGH", "e2e/"),
        ("cypress-repo", "cypress", "HIGH", "cypress/e2e/"),
    ],
)
def test_detects_expected_framework(fixture, expected_framework, expected_confidence, expected_layout_prefix):
    result = run_detect(FIXTURES / fixture)
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == expected_framework
    assert fields["CONFIDENCE"] == expected_confidence
    assert fields["LAYOUT"].startswith(expected_layout_prefix)


def test_ambiguous_returns_both_candidates_and_exit_2():
    result = run_detect(FIXTURES / "ambiguous-both")
    fields = parse(result.stdout)
    assert result.returncode == 2
    assert fields["STATUS"] == "AMBIGUOUS"
    assert "playwright" in fields["CANDIDATES"]
    assert "cypress" in fields["CANDIDATES"]


def test_hint_resolves_ambiguity_without_asking():
    result = run_detect(FIXTURES / "ambiguous-both", ["--hint", "cypress"])
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == "cypress"
    assert fields["LAYOUT"].startswith("cypress/e2e/")


def test_hint_naming_an_undetected_framework_falls_back_to_ambiguous():
    result = run_detect(FIXTURES / "ambiguous-both", ["--hint", "selenium"])
    fields = parse(result.stdout)
    assert result.returncode == 2
    assert fields["STATUS"] == "AMBIGUOUS"
    assert "--hint 'selenium' matched no detected candidate" in result.stderr


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
