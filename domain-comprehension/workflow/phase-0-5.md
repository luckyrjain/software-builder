---
workflow_version: 1.4
phase: 0.5
produces:
  - knowledge_graph_merged
  - domain_graph
  - mechanical_insights
  - manifest_json
  - dependency_graph_initial
  - discovery_budget_checkpoint
consumes:
  - inventory
  - contract_inventory
  - user_approved_mechanical_scope
---

# Comprehension Phase P0.5 — Mechanical model

Build workspace-level knowledge graph **before** manual deep reading.

Full procedure: [understand-anything.md](../reference/understand-anything.md).

## Execution order

1. **Tier 0 + 1 repos first** — `/understand --full` each; copy graph to workspace
   `.understand-anything/<repo>-knowledge-graph.json`; append `manifest.json` entry.

2. **Tier 2 repos** — same process.

3. **Tier 3 optional** — graph only if repo sits on core flow path.

4. **Merge** workspace graph → `.understand-anything/knowledge-graph.json`

5. **Domain flows** — `/understand-domain` at workspace root (**no `--full`**)

6. **Top-5 explain** — `/understand-explain` on highest-complexity domain-tagged files

7. **Entry-point call map** — grep `calls` edges ±4 hops; save
   `.understand-anything/diagrams/entry-point-call-map.md`

## Graph queries

Grep `knowledge-graph.json` only — do not load full JSON into context.
Query: `"filePath"`, `"complexity"`, `"type": "endpoint"`, domain tags from config.

## Mechanical deliverables

Write to `{map_file}` § Mechanical Insights and `.understand-anything/metrics.csv`:

- Top 20 files by complexity
- Top 15 endpoints/tables by fan-in
- Domain flows from `domain-graph.json`
- 10 essential files (centrality + tag overlap)
- Dependency cycles, dead-code candidates (critical path only)
- `/understand-explain` summaries

## Bounds

- Repo failure → `UNKNOWNS.md` + grep fallback
- ~60 min timebox per repo; ship partial if needed
- All Tier 0/1 must have `manifest.json` entry (`ok` or documented `failed`)
- Do not block P1 on 100% Tier 2/3 completion

Write dependency graph to `DEPENDENCY_GRAPH.md` per [required-diagrams.md](../reference/required-diagrams.md).

## Machine-domain projection (required in FULL mode)

Set `perspective` (focal service/context for this run) and populate `DEPENDENCY_GRAPH.yaml` from the mechanical
graph per
[machine-domain-model.md § Dependency projection](../reference/machine-domain-model.md#dependency-projection):
source/target/direction/interaction/criticality/evidence/confidence per edge. This is the **initial** pass —
P2 refines sync/async boundaries and P2b reconciles against runtime evidence. Do not derive criticality from
call frequency alone; use `UNKNOWN` where direction/interaction/criticality is unsupported. QUICK keeps the
Session 0 stub as-is.

## Discovery budget checkpoint (required)

Before the checkpoint below, update root `manifest.yaml` `discovery_budget.consumed` (repositories,
search_queries, deep_file_reads) to reflect what P0.5's graph build and queries actually spent and mirror
the totals into `PROGRESS.md`. If any limit is reached before the mechanical model is complete, stop, mark
the engagement `PARTIAL`, and record the gap in `UNKNOWNS.md` — never silently exceed a configured limit.
See [manifest-schema.md § discovery_budget](../reference/manifest-schema.md#discoverybudget).

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Mechanical insights | `{map_file}` § Mechanical Insights | Top 20 files, top 15 endpoints, domain flows, 10 essential files | Phase incomplete |
| Service call graph | `DEPENDENCY_GRAPH.md` § Service call | Mermaid diagram + confidence | Phase incomplete |
| Machine dependency graph (initial) | `DEPENDENCY_GRAPH.yaml` | focal perspective + source/target/direction/interaction/criticality/evidence/confidence | Phase incomplete in FULL mode |
| Graph manifest | `.understand-anything/manifest.json` | Tier 0/1 entries: ok or failed with reason | Phase incomplete |
| Metrics | `.understand-anything/metrics.csv` | Present or N/A with reason | Phase incomplete — waived with reason allowed |
| Discovery budget checkpoint | root `manifest.yaml` + `PROGRESS.md` | Configured + consumed counters synchronized | Phase incomplete unless PARTIAL for budget exhaustion |

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md) · [phase-outputs.md § P0.5](../reference/phase-outputs.md#p05-mechanical-model)
