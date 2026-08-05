"""Tests for incident-rca causal graph validator (CG-01..CG-09)."""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_causal_graph import validate_causal_graph  # noqa: E402

GRAPH_EXAMPLE = ROOT / "reference" / "causal-graph.example.yaml"
EVIDENCE_EXAMPLE = ROOT / "reference" / "evidence.example.json"


def load():
    graph = yaml.safe_load(GRAPH_EXAMPLE.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_EXAMPLE.read_text(encoding="utf-8"))
    return graph, evidence


def test_example_graph_valid():
    graph, evidence = load()
    assert validate_causal_graph(graph, evidence) == []


def test_cg01_cycle_detected():
    graph, evidence = load()
    graph["edges"].append(
        {"from": "event_5xx", "to": "trigger_deploy", "evidence": ["error_signals[0]"]}
    )
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-01") for e in errors)


def test_cg02_unknown_node_kind():
    graph, evidence = load()
    graph["nodes"][0]["kind"] = "symptom"
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-02") for e in errors)


def test_cg02_edge_to_missing_node():
    graph, evidence = load()
    graph["edges"][0]["to"] = "nonexistent_node"
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-02") for e in errors)


def test_cg03_edge_without_evidence():
    graph, evidence = load()
    graph["edges"][0]["evidence"] = []
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-03") for e in errors)


def test_cg03_dangling_evidence_ref():
    graph, evidence = load()
    graph["edges"][0]["evidence"] = ["error_signals[5]"]
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-03") for e in errors)


def test_cg03_malformed_evidence_ref():
    graph, evidence = load()
    graph["edges"][0]["evidence"] = ["not a ref"]
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-03") for e in errors)


def test_cg04_arithmetic_mismatch():
    graph, evidence = load()
    graph["hypotheses"][0]["adjusted"] = 70  # should be 62
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-04") for e in errors)


def test_cg04_quality_bonus_over_cap():
    graph, evidence = load()
    h = graph["hypotheses"][0]
    h["quality_bonus"] = 20
    h["adjusted"] = 75  # keep arithmetic self-consistent so only the cap fires
    h["display_score"] = 88  # 75/85
    graph["hypotheses"][1]["display_score"] = 12  # 10/85
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-04") for e in errors)


def test_cg04_negative_counter_penalty():
    graph, evidence = load()
    h = graph["hypotheses"][0]
    h["counter_penalty"] = -13
    h["adjusted"] = 75  # max(0, 45+7+10-(-13)-0) = 75, keep arithmetic self-consistent
    h["display_score"] = 88  # 75/85
    graph["hypotheses"][1]["display_score"] = 12  # 10/85
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-04") for e in errors)


def test_cg04_counter_penalty_not_matching_contradictions():
    graph, evidence = load()
    h = graph["hypotheses"][0]
    h["counter_penalty"] = 10  # unresolved_contradictions is still 0
    h["adjusted"] = 52  # max(0, 45+7+10-10-0) = 52, keep arithmetic self-consistent
    h["display_score"] = 84  # round(52/62*100)
    graph["hypotheses"][1]["display_score"] = 16  # round(10/62*100)
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-04") for e in errors)


def test_cg05_display_score_mismatch():
    graph, evidence = load()
    graph["hypotheses"][0]["display_score"] = 99  # should be 86
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-05") for e in errors)


def test_cg06_single_source_caps_medium():
    graph, evidence = load()
    graph["observability_sources_responded"] = 1
    errors = validate_causal_graph(graph, evidence)  # H1 still HIGH → violation
    assert any(e.startswith("CG-06") for e in errors)


def test_cg06_trigger_unknown_caps_medium():
    graph, evidence = load()
    graph["trigger_status"] = "unknown"
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-06") for e in errors)


def test_cg06_assumed_only_caps_low():
    graph, evidence = load()
    h = graph["hypotheses"][0]
    h["supporting_quality"] = ["Assumed"]
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-06") for e in errors)


def test_cg06_band_exceeds_score_band():
    graph, evidence = load()
    graph["hypotheses"][1]["band"] = "HIGH"  # display 14 → UNKNOWN band max
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-06") for e in errors)


def test_cg07_primary_requires_high_band():
    graph, evidence = load()
    graph["hypotheses"][0]["band"] = "MEDIUM"
    errors = validate_causal_graph(graph, evidence)  # primary still H1
    assert any(e.startswith("CG-07") for e in errors)


def test_cg07_no_high_requires_primary_none():
    graph, evidence = load()
    graph["hypotheses"][0]["band"] = "MEDIUM"
    graph["conclusion"]["primary"] = "none"
    errors = validate_causal_graph(graph, evidence)
    assert not any(e.startswith("CG-07") for e in errors)


def test_cg08_ruled_out_inconsistent():
    graph, evidence = load()
    graph["hypotheses"][1]["ruled_out"] = False  # 10 < 31 → must be ruled out
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-08") for e in errors)


def test_missing_top_level_field():
    graph, evidence = load()
    del graph["trigger_status"]
    errors = validate_causal_graph(graph, evidence)
    assert any("trigger_status" in e for e in errors)


def test_observability_sources_responded_string_rejected():
    graph, evidence = load()
    graph["observability_sources_responded"] = "1"
    errors = validate_causal_graph(graph, evidence)
    assert any("observability_sources_responded" in e for e in errors)


def test_unresolved_contradictions_non_numeric_does_not_crash():
    graph, evidence = load()
    graph["hypotheses"][0]["unresolved_contradictions"] = "two"
    errors = validate_causal_graph(graph, evidence)  # must not raise
    assert any(e.startswith("CG-06") for e in errors)


def test_cg09_declared_count_exceeds_actual_evidence():
    graph, evidence = load()
    graph["observability_sources_responded"] = 3  # bundle only backs 2 (datadog, kubesense-mcp)
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-09") for e in errors)


def test_cg09_declared_count_below_actual_evidence():
    graph, evidence = load()
    graph["observability_sources_responded"] = 1  # bundle actually backs 2
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-09") for e in errors)


def test_cg09_change_management_sources_not_counted():
    graph, evidence = load()
    # jenkins/jira entries in the fixture must not inflate the observability count
    assert evidence["deploy_events"][0]["source"] == "jenkins"
    assert evidence["jira_issues"][0]  # present, not an observability source
    errors = validate_causal_graph(graph, evidence)
    assert not any(e.startswith("CG-09") for e in errors)
