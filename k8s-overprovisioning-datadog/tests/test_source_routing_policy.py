from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def load_yaml(relative_path: str):
    return yaml.safe_load(read(relative_path))


def test_skill_entrypoint_declares_kubernetes_mcp_first_capability_routing():
    skill = read("SKILL.md")

    assert "Kubernetes MCP" in skill
    assert "capability" in skill.lower()
    assert "Datadog" in skill and "fallback" in skill.lower()
    assert "insufficient_metrics" in skill
    assert "Datadog MCP + **ddsetup**" not in skill


def test_capability_matrix_encodes_preferred_fallback_and_no_source_behavior():
    matrix = read("reference/mcp-capabilities.md")

    for heading in ("Capability", "Preferred source", "Fallback", "No source behavior"):
        assert heading in matrix
    assert "live-state truth" in matrix
    assert "historical truth" in matrix
    assert "conflicting_signals" in matrix
    assert "Kubernetes MCP absent" in matrix
    assert "Datadog absent" in matrix
    assert "Both sources insufficient" in matrix


def test_collect_inventories_capabilities_and_records_provenance():
    collect = read("workflow/collect-metrics.md")

    assert "source profile" in collect.lower()
    assert "per observation" in collect.lower()
    assert "live state" in collect.lower()
    assert "historical" in collect.lower()
    assert "source-scoped" in collect.lower()
    assert "conflicting_signals" in collect


def test_stop_policy_blocks_only_when_combined_evidence_is_insufficient():
    stop_reasons = read("workflow/stop-reasons.md")

    assert "one source" in stop_reasons.lower()
    assert "other source" in stop_reasons.lower()
    assert "attempted sources" in stop_reasons.lower()
    assert "missing capabilities" in stop_reasons.lower()
    assert "insufficient_metrics" in stop_reasons


def test_setup_and_readme_do_not_require_datadog_when_kubernetes_history_is_sufficient():
    setup = read("SETUP.md")
    readme = read("README.md")
    root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "Kubernetes MCP" in setup
    assert "fallback" in setup.lower()
    assert "Kubernetes MCP" in readme
    assert "fallback" in readme.lower()
    assert "Kubernetes MCP-first" in root_readme


def test_examples_and_pressure_tests_cover_all_degraded_routes():
    examples = read("examples.md")
    pressure = read("reference/pressure-tests.md")

    for expected in (
        "Kubernetes MCP with complete capabilities",
        "Kubernetes MCP with partial capabilities",
        "No Kubernetes MCP",
        "No Datadog with history-capable Kubernetes MCP",
        "Live-state-only Kubernetes MCP and no Datadog",
        "Conflicting live versus historical evidence",
        "Neither source sufficient",
    ):
        assert expected in pressure

    assert "Datadog fallback" in examples
    assert "STOP_REASON: insufficient_metrics" in examples
    assert "Cannot assess utilization without Datadog metrics" not in examples


def test_source_discovery_precedes_resolution_and_threads_profile_to_graph():
    orchestrator = read("workflow/orchestrator.md")
    resolve_frontmatter = load_yaml_frontmatter(read("workflow/resolve-service.md"))
    collect_frontmatter = load_yaml_frontmatter(read("workflow/collect-metrics.md"))
    evidence_frontmatter = load_yaml_frontmatter(read("workflow/evidence.md"))
    graph_frontmatter = load_yaml_frontmatter(read("workflow/build-graph.md"))

    assert orchestrator.index("discover-sources.md") < orchestrator.index("resolve-service.md")
    assert "source_profile" in resolve_frontmatter["consumes"]
    assert "source_profile" in collect_frontmatter["consumes"]
    assert "source_profile" in evidence_frontmatter["consumes"]
    assert "source_profile" in graph_frontmatter["consumes"]


def load_yaml_frontmatter(markdown: str):
    _, frontmatter, _ = markdown.split("---", 2)
    return yaml.safe_load(frontmatter)


def test_example_graphs_carry_a_structured_source_profile():
    for fixture in (
        "reference/decision-graph.example.yaml",
        "reference/decision-graph.trim.example.yaml",
        "reference/decision-graph.scale-up.example.yaml",
        "reference/decision-graph.insufficient-metrics.example.yaml",
    ):
        profile = load_yaml(fixture)["metadata"]["source_profile"]
        assert set(profile) == {"sources", "routes"}
        assert "kubernetes_mcp" in profile["sources"]
        assert "datadog" in profile["sources"]
        assert "live_state" in profile["routes"]
        assert "historical_metrics" in profile["routes"]


def test_dual_source_graph_retains_both_values_and_gates_conflict():
    graph = load_yaml("reference/decision-graph.example.yaml")
    observations = {item["id"]: item for item in graph["observations"]}
    evidence = {item["observation_id"]: item for item in graph["evidence"]}

    canonical = "OBS_CPU_REQUEST"
    alternate = "OBS_CPU_REQUEST_ALT_DATADOG"
    assert canonical in observations and alternate in observations
    assert observations[canonical]["value"] != observations[alternate]["value"]
    assert evidence[canonical]["source"] == "kubernetes-mcp"
    assert evidence[alternate]["source"] == "datadog"
    assert any(
        set(item["ids"]) == {canonical, alternate} and item["status"] == "Unresolved"
        for item in graph["contradictions"]
    )
    assert "conflicting_signals" in graph["stop_reasons"]
    assert not any(
        rec["status"] == "READY" and rec["id"] in {
            "REC_CPU_REDUCE",
            "REC_MEMORY_REDUCE",
            "REC_REPLICA_REDUCE",
        }
        for rec in graph["recommendations"]
    )


def test_all_approved_routing_scenarios_have_structured_expected_outputs():
    scenarios = load_yaml("tests/fixtures/source-routing-scenarios.yaml")["scenarios"]
    assert len(scenarios) == 7
    assert {scenario["id"] for scenario in scenarios} == {
        "kubernetes_complete",
        "kubernetes_partial",
        "kubernetes_absent",
        "datadog_absent_kubernetes_history",
        "live_only_no_datadog",
        "conflicting_sources",
        "neither_sufficient",
    }
    for scenario in scenarios:
        assert "routes" in scenario["expected"]
        assert "assessment" in scenario["expected"]
        if scenario["expected"]["assessment"] == "blocked":
            assert scenario["expected"]["recommendations"] == []
            assert scenario["expected"]["stop_reason"] == "insufficient_metrics"


def test_unknown_delivery_path_defers_instead_of_guessing():
    build_graph = read("workflow/build-graph.md")
    invariant_help = read("workflow/validate-invariants.md")

    assert "best path from deployment metadata" not in build_graph
    assert "set the recommendation to\n   `DEFERRED`" in build_graph
    assert "never invent a path" in build_graph
    assert "set the recommendation to `DEFERRED`" in invariant_help
