"""Tests for api-test-creator's Postman/Newman-tooling detection script."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "detect-postman-tooling.sh"
FIXTURES = ROOT / "tests" / "fixtures" / "postman-detect"


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


def test_single_collection_detected_high_confidence():
    result = run_detect(FIXTURES / "single-collection")
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["FRAMEWORK"] == "postman"
    assert fields["CONFIDENCE"] == "HIGH"
    assert fields["COLLECTION_COUNT"] == "1"


def test_newman_dep_only_detected_medium_confidence():
    result = run_detect(FIXTURES / "newman-dep-only")
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert fields["CONFIDENCE"] == "MEDIUM"
    assert fields["COLLECTION_COUNT"] == "0"
    assert fields["NEWMAN"] == "yes"


def test_ambiguous_multi_collection_returns_exit_2():
    result = run_detect(FIXTURES / "ambiguous-multi-collection")
    fields = parse(result.stdout)
    assert result.returncode == 2
    assert fields["STATUS"] == "AMBIGUOUS"
    assert fields["COLLECTION_COUNT"] == "2"
    assert "orders.postman_collection.json" in fields["CANDIDATES"]
    assert "payments.postman_collection.json" in fields["CANDIDATES"]


def test_no_markers_returns_none_detected_and_exit_3():
    result = run_detect(FIXTURES / "none")
    fields = parse(result.stdout)
    assert result.returncode == 3
    assert fields["STATUS"] == "NONE_DETECTED"
    assert fields["COLLECTION_COUNT"] == "0"
    assert fields["NEWMAN"] == "no"


def test_naming_convention_resolves_without_asking():
    result = run_detect(FIXTURES / "resolved-by-naming")
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert "main.postman_collection.json" in fields["MARKER"]


def test_ci_reference_resolves_without_asking():
    result = run_detect(FIXTURES / "resolved-by-ci")
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert "orders.postman_collection.json" in fields["MARKER"]
    assert "scratch.postman_collection.json" not in fields["MARKER"]


def test_hint_selects_named_candidate_on_ambiguous_repo():
    result = run_detect(
        FIXTURES / "ambiguous-multi-collection",
        ["--hint", "payments.postman_collection.json"],
    )
    fields = parse(result.stdout)
    assert result.returncode == 0
    assert fields["STATUS"] == "DETECTED"
    assert "payments.postman_collection.json" in fields["MARKER"]


def test_hint_naming_an_undiscovered_collection_falls_back_with_warning():
    result = run_detect(
        FIXTURES / "ambiguous-multi-collection",
        ["--hint", "nope.postman_collection.json"],
    )
    fields = parse(result.stdout)
    assert "matched no discovered collection file" in result.stderr
    assert result.returncode == 2
    assert fields["STATUS"] == "AMBIGUOUS"


def test_missing_root_directory_errors():
    result = run_detect(FIXTURES / "does-not-exist")
    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_missing_root_argument_prints_usage():
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "usage:" in result.stderr
