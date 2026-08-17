---
workflow_version: 1.12
phase: 2
produces:
  - trigger_catalog
  - runtime_sequence
  - business_flows
  - critical_path
  - state_machine
  - deployment_graph
  - sync_async_boundary_table
  - code_graph_divergence
  - dependency_graph_refined
consumes:
  - per_repo_deep_dives
  - ownership_cards
  - bounded_contexts
  - data_ownership
  - domain_graph
---

# Comprehension Phase P2 — Static Flow Analysis

Map runtime flow patterns from code and config, building trigger catalogs, sequence diagrams, and flow analysis.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Trigger catalog | `{map_file}` § Flow | All trigger types + entry repo | Phase incomplete |
| Runtime sequence | `{map_file}` § Flow | Numbered narrative + Mermaid sequence (happy + failure paths) | Phase incomplete |
| Business flows | `BUSINESS_FLOWS.md` | ≥3 journeys | Phase incomplete |
| Critical path | `{map_file}` § Flow | Vertical chain diagram | Phase incomplete |
| State machine | `STATE_MACHINE.md` | States, transitions, Mermaid stateDiagram-v2 | Phase incomplete |
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config, plus per-env base URL (BFF + direct ingress) | Phase incomplete — UNKNOWN allowed with reason |
| Sync/async boundary table | `{map_file}` § Flow | Step, sync/async, transport, timeout owner, evidence | Phase incomplete |
| Code/graph divergence | `{map_file}` § Flow | Classified edges: MISSING_IN_CODE \| DEAD_CODE \| DYNAMIC_DISPATCH \| UNKNOWN | Phase incomplete |
| Machine dependency graph (refined) | `DEPENDENCY_GRAPH.yaml` | sync/async boundaries + upstream/downstream semantics + evidence-backed criticality | Phase incomplete in FULL mode |

## Machine-domain projection (required in FULL mode)

Refine the P0.5 `DEPENDENCY_GRAPH.yaml` with this phase's sync/async boundary table and code/graph
divergence findings per
[machine-domain-model.md § Dependency projection](../reference/machine-domain-model.md#dependency-projection):
resolve `interaction` (synchronous/asynchronous) and `direction` (upstream/downstream relative to the focal
perspective) from evidenced transport/control flow, and update `criticality` from user impact plus recovery
dependency — never from call frequency alone. Preserve edges/evidence already recorded in P0.5; do not
overwrite an evidenced value with `UNKNOWN`.

## Investigation recipes (Code/graph divergence)

Classify each edge where the P0.5 mechanical graph and the manually-observed runtime sequence
disagree:

1. **Enumerate mechanical edges for the flow under review** — query `.understand-anything/knowledge-graph.json` for `calls` edges touching the entry point and its one-hop callees (see `reference/understand-anything.md` § Graph queries for the query form).
2. **Cross-reference against the manual sequence** built for this phase's Required outputs. For each mechanical edge not confirmed by manual reading, and each manually-observed step not present as a mechanical edge, classify:
   - **MISSING_IN_CODE** — manually observed (e.g. via a config-driven call, reflection, or runtime dispatch) but the mechanical graph has no static edge for it. Record the evidence path that proves the call happens.
   - **DEAD_CODE** — mechanical graph has the edge, but no manual evidence the path is ever reached (no caller, feature-flagged off, or superseded route). `rg` for the calling method's own callers to confirm zero live entry points before classifying as dead, not just "I didn't happen to trace it."
   - **DYNAMIC_DISPATCH** — mechanical graph correctly shows *a* call but can't resolve which implementation (interface/strategy/event-listener fan-out); manual reading confirms the actual implementation(s) taken for this flow.
   - **UNKNOWN** — disagreement noted but neither static nor manual evidence is sufficient to classify; state the reason, do not guess.
3. Record all four classes in `{map_file}` § Flow even when a category is empty — an empty
   MISSING_IN_CODE/DEAD_CODE list is a real (positive) finding, not an omission.

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md)
