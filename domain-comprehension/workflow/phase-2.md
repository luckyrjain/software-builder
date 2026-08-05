---
workflow_version: 1.11
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

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md)
