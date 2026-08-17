---
workflow_version: 1.11
phase: 2b
produces:
  - runtime_validation_table
  - kubesense_log_evidence
  - runtime_graph
  - datadog_subgraphs
  - exercise_updates
  - dependency_graph_runtime_reconciled
  - discovery_budget_checkpoint
consumes:
  - trigger_catalog
  - runtime_sequence
  - critical_path
  - deployment_graph
  - code_graph_divergence
  - mcp_profile
---

# Comprehension Phase P2b — Runtime Validation

Validate static flow analysis against Datadog runtime traces, updating graphs and artifacts with observed patterns.

## Runtime validation location (normative)

**Always** write `{map_file}` § **Runtime validation (Datadog)** with the three-way table per hop.

When E2E/runtime detail is large, add a **stub** in the map section (heading + one-line summary) and put
the full table in `E2E_FLOW.md` § Runtime validation — link from the map stub. Do **not** skip the map
section entirely.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Runtime validation table | `{map_file}` § Runtime validation **or** `E2E_FLOW.md` § Runtime validation (with map stub+link) | From→To, Code (P2), Graph, Datadog, Verdict, Confidence, Evidence | Phase incomplete if Datadog ✅ |
| KubeSense log evidence | `{map_file}` § Runtime validation | Exact quoted error strings, workload, namespace, filter SQL | Phase incomplete if KubeSense ✅ |
| Runtime graph | `DEPENDENCY_GRAPH.md` § Runtime | Datadog-confirmed edges, Mermaid | Phase incomplete if Datadog ✅ |
| Exercise updates | `API_CATALOG.md`, `EVENT_CATALOG.md`, `BUSINESS_FLOWS.md` | `runtime_confirmed` where applicable | Phase incomplete if Datadog ✅ |
| Datadog subgraphs | `.understand-anything/diagrams/datadog-service-deps.md` | Per entry service | Phase incomplete if Datadog ✅ |
| Skip record | `{map_file}` § Flow stub + `KNOWN_OMISSIONS.md` | Skip reason | Required when Datadog ❌ |
| Machine dependency runtime reconciliation | `DEPENDENCY_GRAPH.yaml` | runtime-confirmed/divergent edges retain evidence/confidence | Phase incomplete if Datadog ✅ |
| Discovery budget checkpoint | root `manifest.yaml` + `PROGRESS.md` | Configured + consumed counters synchronized | Phase incomplete unless PARTIAL for budget exhaustion, or waived when Datadog ❌ |

## Machine-domain projection (required when Datadog ✅)

Reconcile `DEPENDENCY_GRAPH.yaml` against the runtime validation table above: mark edges the Datadog trace
confirms as runtime-confirmed, and keep divergent or unconfirmed edges visible with their existing
evidence/confidence rather than deleting or silently averaging them away. Do not invent an edge's intent
from telemetry alone — traffic volume/latency corroborates an already-evidenced edge, it does not create a
new one. Skipped (Datadog ❌) runs leave the P2 `DEPENDENCY_GRAPH.yaml` as-is.

## Discovery budget checkpoint (required when Datadog ✅)

Before the checkpoint below, update root `manifest.yaml` `discovery_budget.consumed` (repositories,
search_queries, deep_file_reads) to reflect what this phase's Datadog trace/log queries actually spent and
mirror the totals into `PROGRESS.md`. If any limit is reached before runtime validation is complete, stop,
mark the engagement `PARTIAL`, and record the gap in `UNKNOWNS.md` — never silently exceed a configured
limit. Skipped (Datadog ❌) runs leave the counters as-is. See
[manifest-schema.md § discovery_budget](../reference/manifest-schema.md#discoverybudget).

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md)
