import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def section(relative_path: str, heading: str) -> str:
    return markdown_section(read(relative_path), heading)


def markdown_section(markdown: str, heading: str) -> str:
    start = markdown.index(heading)
    level = len(heading) - len(heading.lstrip("#"))
    match = re.search(rf"^#{{1,{level}}} (?!#)", markdown[start + len(heading) :], re.MULTILINE)
    end = len(markdown) if match is None else start + len(heading) + match.start()
    return markdown[start:end]


def assert_ordered(markdown: str, *tokens: str) -> None:
    positions = [markdown.index(token) for token in tokens]
    assert positions == sorted(positions), f"expected ordered tokens {tokens}, got offsets {positions}"


def table_row(markdown: str, contains: str) -> str:
    return next(line for line in markdown.splitlines() if line.startswith("|") and contains in line)


def test_repository_file_map_tracks_discovery_and_all_current_invariants():
    file_map = section("docs/README.md", "## k8s-overprovisioning-datadog file map")

    assert "workflow/discover-sources.md" in file_map
    assert "INV-01–INV-14" in file_map


def test_shared_k8s_phase_contract_starts_with_discovery_then_resolution():
    phase_map = section("docs/skill-framework/shared/phase-glossary.md", "## 4. k8s mapping")
    analogies = section("docs/skill-framework/shared/phase-glossary.md", "## 5. Cross-skill analogies")
    examples = read("docs/skill-framework/shared/examples-conventions.md")

    assert_ordered(phase_map, "DISCOVER_SOURCES", "RESOLVE", "COLLECT")
    assert "DISCOVER_SOURCES → RESOLVE → COLLECT" in phase_map
    assert "k8s DISCOVER_SOURCES→RENDER" in examples

    profile_row = table_row(analogies, "| MCP profile |")
    assert "Kubernetes MCP" in profile_row and "Datadog" in profile_row
    assert "source profile" in profile_row.lower()


def test_living_k8s_pipeline_references_include_source_discovery():
    paths = (
        "k8s-overprovisioning-datadog/reference/decision-graph-schema.md",
        "k8s-overprovisioning-datadog/workflow/report.md",
        "k8s-overprovisioning-datadog/examples.md",
    )

    for path in paths:
        markdown = read(path)
        assert_ordered(markdown, "DISCOVER_SOURCES", "RESOLVE", "COLLECT")


def test_handoff_and_smoke_docs_enter_through_capability_discovery():
    handoff = section("incident-rca/workflow/phase-5.md", "## K8s handoff block")
    smoke = read("docs/skill-framework/shared/smoke-test-conventions.md")
    k8s_smoke_row = table_row(smoke, "k8s-overprovisioning-datadog")

    assert_ordered(handoff, "DISCOVER_SOURCES", "RESOLVE", "COLLECT")
    assert "Kubernetes MCP" in handoff and "Datadog" in handoff
    assert "re-queries Datadog independently" not in handoff
    assert "Kubernetes MCP or Datadog" in k8s_smoke_row
    assert "DISCOVER_SOURCES" in k8s_smoke_row


def test_active_routing_spec_and_plan_assign_inventory_to_discover_sources():
    design_path = "docs/superpowers/specs/2026-08-06-k8s-mcp-first-routing-design.md"
    plan_path = "docs/superpowers/plans/2026-08-06-k8s-mcp-first-routing.md"
    source_design = section(design_path, "## Source routing")
    docs_design = section(design_path, "## Documentation changes")
    task_1 = section(plan_path, "### Task 1: Add routing contract tests")
    task_2 = section(plan_path, "### Task 2: Implement the source-routing policy")
    task_5 = section(plan_path, "### Task 5: Synchronize living documentation contracts")

    assert_ordered(source_design, "DISCOVER_SOURCES", "RESOLVE")
    assert "At COLLECT start" not in source_design
    assert "workflow/discover-sources.md" in task_2
    assert "DISCOVER_SOURCES" in task_1 and "COLLECT" in task_1
    assert "cross-skill wrappers" in docs_design
    assert "test_documentation_contract.py" in task_5


def test_wrappers_inherit_kubernetes_first_prerequisites():
    release_setup = read("release-readiness-checker/SETUP.md")
    cost_setup = read("cost-optimization-sprint-planner/SETUP.md")
    cost_readme = read("cost-optimization-sprint-planner/README.md")

    release_k8s_row = table_row(release_setup, "k8s-overprovisioning-datadog installed")
    cost_k8s_row = table_row(cost_setup, "k8s-overprovisioning-datadog installed")
    cost_datadog_row = table_row(cost_setup, "| Datadog MCP |")

    assert "Kubernetes MCP or Datadog" in release_k8s_row
    assert "Kubernetes MCP or Datadog" in cost_k8s_row
    assert "namespace_prefilter" in cost_datadog_row and "Required directly only" in cost_datadog_row
    assert "explicit" in cost_datadog_row and "Kubernetes MCP or Datadog" in cost_datadog_row
    assert "namespace_prefilter" in cost_readme
    assert "explicit" in cost_readme and "Kubernetes MCP or Datadog" in cost_readme


def test_cost_sweep_distinguishes_source_scoped_and_direct_datadog_auth_failures():
    sweep_policy = read("cost-optimization-sprint-planner/reference/sweep-policy.md")
    gate_policy = read("cost-optimization-sprint-planner/reference/gate-policy.md")
    examples = read("cost-optimization-sprint-planner/examples.md")
    smoke_test = read("cost-optimization-sprint-planner/reference/smoke-test.md")

    explicit_row = table_row(gate_policy, "explicit-deployment assessment")
    prefilter_row = table_row(gate_policy, "namespace pre-filter candidate discovery")
    exhausted_row = table_row(gate_policy, "All viable sources")
    candidate_policy = markdown_section(sweep_policy, "## 2. Candidate deployment list")
    continuation_policy = markdown_section(sweep_policy, "## 4. The continuation decision")

    assert "Continue" in explicit_row and "source-scoped" in explicit_row
    assert "Stop" in prefilter_row and "AUTH_FAILURE" in prefilter_row
    assert "Stop" in exhausted_row and "AUTH_FAILURE" in exhausted_row
    assert "direct dependency" in candidate_policy and "explicit deployments list" in candidate_policy
    assert "all viable sources" in continuation_policy.lower()
    for markdown in (examples, smoke_test):
        assert "explicit-deployment assessment" in markdown
        assert "namespace pre-filter" in markdown
        assert "all viable sources" in markdown.lower()


def test_cost_wrapper_defers_actionable_recommendations_without_verified_delivery_path():
    gate_policy = read("cost-optimization-sprint-planner/reference/gate-policy.md")
    manifest_row = next(
        line for line in gate_policy.splitlines() if line.startswith("| Manifest lookup")
    )

    assert "DEFERRED" in manifest_row
    assert "READY" in manifest_row
    assert "proceeds with `delivery_pointer` unverified" not in manifest_row


def test_release_wrapper_preserves_source_scoped_degraded_assessments():
    gate_policy = read("release-readiness-checker/reference/gate-policy.md")
    run_check = read("release-readiness-checker/workflow/run-check.md")
    smoke_test = read("release-readiness-checker/reference/smoke-test.md")

    fallback_row = table_row(gate_policy, "One Kubernetes MCP or Datadog source")
    run_section = markdown_section(run_check, "## 3. Rightsizing verdict per service")

    assert "Source-scoped failure; continue" in fallback_row
    assert "as-is" in fallback_row and "never convert" in fallback_row
    assert "Continue" in run_section and "degraded verdict" in run_section
    assert "all viable sources" in run_section
    assert "source-scoped Datadog failure" in smoke_test
    assert "assessment continues" in smoke_test


def test_shared_mcp_error_policy_uses_capability_level_k8s_fallback():
    policy = read("docs/skill-framework/shared/mcp-error-handling.md")

    assert "Kubernetes MCP ❌" in policy
    assert "Datadog ❌" in policy
    assert "all viable sources" in policy.lower()
    assert "Blocked (`STOP_REASON: auth_failure`); route to **ddsetup**" not in policy
