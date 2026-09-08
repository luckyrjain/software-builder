"""Tests for k8s decision graph invariant validator."""

import copy
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_decision_graph import validate_invariants  # noqa: E402

EXAMPLE = ROOT / "reference" / "decision-graph.example.yaml"
TRIM = ROOT / "reference" / "decision-graph.trim.example.yaml"
SCALE_UP = ROOT / "reference" / "decision-graph.scale-up.example.yaml"
BLOCKED = ROOT / "reference" / "decision-graph.insufficient-metrics.example.yaml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _mutate(path: Path) -> dict:
    return copy.deepcopy(_load(path))


def _errors_for(mutator, base: Path = EXAMPLE) -> list[str]:
    graph = _mutate(base)
    mutator(graph)
    return validate_invariants(graph)


def _assert_inv(inv: str, mutator, base: Path = EXAMPLE):
    errors = _errors_for(mutator, base)
    assert any(inv in e for e in errors), f"expected {inv} in {errors}"


@pytest.mark.parametrize("path", [EXAMPLE, TRIM, SCALE_UP, BLOCKED])
def test_example_graphs_pass_invariants(path: Path):
    graph = _load(path)
    assert validate_invariants(graph) == []


def test_inv01_missing_decision_dependency():
    def mutate(graph):
        graph["recommendations"][0]["depends_on"]["decisions"] = []

    _assert_inv("INV-01", mutate)


def test_inv02_decision_empty_supports():
    def mutate(graph):
        graph["decisions"][0]["supports"] = []

    _assert_inv("INV-02", mutate)


def test_inv03_observation_evidence_count_mismatch():
    def mutate(graph):
        graph["evidence"] = [
            ev for ev in graph["evidence"] if ev.get("observation_id") != "OBS_CPU_USAGE_AVG"
        ]

    _assert_inv("INV-03", mutate)


def test_inv04_evidence_missing_source():
    def mutate(graph):
        for ev in graph["evidence"]:
            if ev.get("id") == "EVID_CPU_USAGE_AVG":
                ev["source"] = None
                ev["quality"] = "measured"

    _assert_inv("INV-04", mutate)


def test_inv05_forbidden_value_on_decision():
    def mutate(graph):
        graph["decisions"][0]["value"] = 0.42

    _assert_inv("INV-05", mutate)


def test_inv06_wrong_id_prefix():
    def mutate(graph):
        graph["observations"][0]["id"] = "BAD_CPU_USAGE_AVG"

    _assert_inv("INV-06", mutate)


def test_inv07_assessment_confidence_mismatch():
    def mutate(graph):
        graph["assessment"]["assessment_confidence"]["value"] = 0.1

    _assert_inv("INV-07", mutate)


def test_inv08_ready_with_blocked_parent():
    def mutate(graph):
        graph["recommendations"][0]["status"] = "READY"

    _assert_inv("INV-08", mutate)


def test_inv09_cut_rec_ready_with_unresolved_contradiction():
    def mutate(graph):
        graph["contradictions"] = [
            {
                "ids": ["OBS_CPU_USAGE_AVG", "OBS_CPU_P95_FLEET"],
                "status": "Open",
                "resolution": None,
            }
        ]
        for rec in graph["recommendations"]:
            if rec.get("id") == "REC_CPU_REDUCE":
                rec["status"] = "READY"

    _assert_inv("INV-09", mutate)


def test_inv10_dangling_support_reference():
    def mutate(graph):
        graph["decisions"][0]["supports"].append("OBS_DOES_NOT_EXIST")

    _assert_inv("INV-10", mutate)


def test_inv11_recommendation_confidence_mismatch():
    def mutate(graph):
        rec = graph["recommendations"][0]
        rec["recommendation_confidence"]["value"] = 0.99
        rec["recommendation_confidence"]["factors"] = {
            "support_completeness": 0.1,
            "support_quality": 0.1,
            "contradiction_resolution": 0.1,
            "telemetry_availability": 0.1,
        }

    _assert_inv("INV-11", mutate)


def test_inv12_ready_actionable_rec_missing_delivery_pointer():
    """INV-12 is critical — validator must fail (blocks RENDER)."""

    def mutate(graph):
        for rec in graph["recommendations"]:
            if rec.get("id") == "REC_CPU_INCREASE":
                rec.pop("delivery_pointer", None)

    _assert_inv("INV-12", mutate, base=SCALE_UP)


def test_inv12_ready_actionable_rec_requires_verified_pointer():
    def mutate(graph):
        for rec in graph["recommendations"]:
            if rec.get("id") == "REC_CPU_INCREASE":
                rec["delivery_pointer"]["verified"] = False

    _assert_inv("INV-12", mutate, base=SCALE_UP)


def test_inv13_dangling_assume_reference():
    def mutate(graph):
        graph["recommendations"][0]["depends_on"]["assumptions"] = ["ASSUME_MISSING"]

    _assert_inv("INV-13", mutate)
    errors = _errors_for(mutate)
    assert not any("INV-10" in e and "ASSUME_MISSING" in e for e in errors)


def test_inv14_missing_source_profile():
    def mutate(graph):
        graph["metadata"].pop("source_profile", None)

    _assert_inv("INV-14", mutate)


def test_inv14_missing_required_route():
    def mutate(graph):
        graph["metadata"]["source_profile"]["routes"].pop("historical_metrics", None)

    _assert_inv("INV-14", mutate)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda graph: graph["metadata"]["source_profile"]["sources"]["datadog"].__setitem__("status", "nonsense"),
        lambda graph: graph["metadata"]["source_profile"]["sources"]["datadog"].pop("failures", None),
        lambda graph: graph["metadata"]["source_profile"]["routes"].__setitem__("live_state", "datadog"),
        lambda graph: graph["metadata"]["source_profile"]["routes"].__setitem__("historical_metrics", "nonsense"),
        lambda graph: graph["metadata"]["source_profile"]["routes"].__setitem__("current_metrics", "git"),
        lambda graph: graph["metadata"]["source_profile"]["sources"]["datadog"].__setitem__("status", "absent"),
        lambda graph: graph["metadata"]["source_profile"]["sources"]["datadog"]["capabilities"].remove("historical_metrics"),
    ],
)
def test_inv14_rejects_invalid_source_profile_values(mutator):
    _assert_inv("INV-14", mutator)
