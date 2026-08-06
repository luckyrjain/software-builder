# Kubernetes MCP-first Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `k8s-overprovisioning-datadog` prefer Kubernetes MCP capabilities and fall back to Datadog per capability without weakening evidence gates.

**Architecture:** Add one capability-routing policy in DISCOVER_SOURCES and make every entry point refer to it. Produce the source profile before RESOLVE, then preserve it through COLLECT and the existing decision graph. Keep the analysis modules unchanged; only source selection, provenance, degraded modes, and documentation change. Protect the policy with repository tests that assert the required routing and blocked behavior.

**Tech Stack:** Markdown skills/workflows, Python `pytest`, GNU Make.

## Global Constraints

- Keep the legacy `k8s-overprovisioning-datadog` directory and skill name.
- Remain read-only and recommendation-only.
- Route by capability, not exact MCP server or tool names.
- Use Kubernetes MCP as live-state truth and Datadog as historical truth when both exist.
- Emit `STOP_REASON: insufficient_metrics` and no sizing recommendation when neither source supplies sufficient evidence.
- Require `telemetry.intent` only on Datadog calls.

---

### Task 1: Add routing contract tests

**Files:**
- Create: `k8s-overprovisioning-datadog/tests/test_source_routing_policy.py`
- Modify: `Makefile`

**Interfaces:**
- Consumes: Approved routing design and existing `lint-k8s-skill` target.
- Produces: Automated assertions for Kubernetes-first routing, per-capability fallback, provenance, conflict handling, and insufficient-evidence blocking.

- [x] **Step 1: Write failing tests** that inspect the skill entry point, capability matrix, DISCOVER_SOURCES/COLLECT workflows, setup, examples, pressure tests, and stop-reason registry.
- [x] **Step 2: Run** `python3 -m pytest -p no:cacheprovider k8s-overprovisioning-datadog/tests/test_source_routing_policy.py -q` and verify failures describe the missing policy.
- [x] **Step 3: Ensure** `make lint-k8s-skill` continues to execute the full K8s test directory.

### Task 2: Implement the source-routing policy

**Files:**
- Modify: `k8s-overprovisioning-datadog/SKILL.md`
- Modify: `k8s-overprovisioning-datadog/reference/mcp-capabilities.md`
- Modify: `k8s-overprovisioning-datadog/workflow/discover-sources.md`
- Modify: `k8s-overprovisioning-datadog/workflow/collect-metrics.md`
- Modify: `k8s-overprovisioning-datadog/workflow/orchestrator.md`
- Modify: `k8s-overprovisioning-datadog/workflow/stop-reasons.md`
- Modify: `k8s-overprovisioning-datadog/dependencies.md`
- Modify: `k8s-overprovisioning-datadog/skills-lock.json`

**Interfaces:**
- Consumes: Runtime tool inventory and capability observations.
- Produces: A source profile plus per-observation provenance and source-scoped degraded behavior.

- [x] **Step 1: Add** a DISCOVER_SOURCES capability inventory covering live state, current metrics, historical metrics, incidents/monitors/APM/change history, manifests, and cost.
- [x] **Step 2: Define** Kubernetes-first, Datadog fallback, dual-source truth, `conflicting_signals`, and source-scoped auth behavior.
- [x] **Step 3: Update** prerequisites and stop reasons so a missing individual MCP never halts collection from another sufficient source.
- [x] **Step 4: Run** the focused tests and fix only policy gaps.

### Task 3: Align user-facing documentation and scenarios

**Files:**
- Modify: `k8s-overprovisioning-datadog/README.md`
- Modify: `k8s-overprovisioning-datadog/SETUP.md`
- Modify: `k8s-overprovisioning-datadog/examples.md`
- Modify: `k8s-overprovisioning-datadog/reference/pressure-tests.md`
- Modify: `k8s-overprovisioning-datadog/reference/smoke-test.md`
- Modify: `README.md`
- Modify: `k8s-overprovisioning-datadog/CHANGELOG.md`

**Interfaces:**
- Consumes: Routing policy from Task 2.
- Produces: Consistent setup, invocation, fallback, and validation guidance.

- [x] **Step 1: Document** Kubernetes MCP discovery and Datadog fallback setup.
- [x] **Step 2: Replace** the Datadog-absent blocking example with capability-level degraded scenarios.
- [x] **Step 3: Add** all seven approved pressure scenarios and update smoke checks.
- [x] **Step 4: Update** root catalog copy and changelog.

### Task 4: Verify and publish

**Files:**
- Verify: all changed files on `feature/k8s-mcp-first-routing`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: Validated branch and draft pull request to `main`.

- [x] **Step 1: Run** focused routing tests.
- [x] **Step 2: Run** `make lint-k8s-skill`.
- [x] **Step 3: Run** `make lint` when dependencies are available; report unrelated environmental blockers explicitly.
- [x] **Step 4: Review** `git diff --check`, the complete diff, and approved-spec coverage.
- [x] **Step 5: Commit**, publish the branch, and open a draft PR with checks and behavior summarized.

### Task 5: Synchronize living documentation contracts

**Files:**
- Modify: shared K8s phase/error documentation and repository file map
- Modify: `release-readiness-checker` and `cost-optimization-sprint-planner` operational wrappers
- Modify: this active design/plan and current K8s examples/schema/report guidance
- Create: `k8s-overprovisioning-datadog/tests/test_documentation_contract.py`

**Interfaces:**
- Consumes: Implemented DISCOVER_SOURCES routing, source-scoped auth behavior, INV-12/INV-14 contracts.
- Produces: Synchronized living documentation plus regression coverage; dated historical records remain unchanged.

- [x] **Step 1: Add failing contract tests** for phase order, invariant range, wrapper prerequisites, auth scope, and delivery-path safety.
- [x] **Step 2: Align shared and K8s operational docs** to DISCOVER_SOURCES → RESOLVE → COLLECT and INV-01–INV-14.
- [x] **Step 3: Align cross-skill wrappers** so source-scoped failures continue, all-source auth failures stop, and direct Datadog dependencies remain explicitly capability-scoped.
- [x] **Step 4: Preserve historical specs/plans/changelogs** and validate living-doc links, packages, focused suites, and repository lint.
