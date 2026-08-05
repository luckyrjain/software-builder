# Deliverable templates

Copy **all** files from [templates/](../templates/) to `workspace_root` at Session 0.
Normative phase requirements: [phase-outputs.md](phase-outputs.md).

## Split deliverables (workspace root)

| File | Populated in |
|------|--------------|
| `EXEC_SUMMARY.md` | Session 0 → P5 (evidence summary, time & effort, overall confidence, leader summary) |
| `{map_file}` | All phases (narrative index) |
| `BOUNDED_CONTEXTS.md` | P0 initial, P1 refined, P4 change impact |
| `DATA_OWNERSHIP.md` | P1 initial, P3 refined |
| `DEPENDENCY_GRAPH.md` | Four views: logical / service / deployment / runtime |
| `BUSINESS_FLOWS.md` | P2 (≥3 journeys) |
| `STATE_MACHINE.md` | P2 |
| `API_CATALOG.md` | P0.25 (+ exercise in P2b) |
| `EVENT_CATALOG.md` | P0.25 (+ exercise in P2b) |
| `RISK_MAP.md` | P1 smells seed, P4 top smells + change impact |
| `KNOWN_OMISSIONS.md` | Session 0 → continuous (scope limits) |
| `DOMAIN_GLOSSARY.md` | P1 |
| `ARCHITECTURE_DECISIONS.md` | P4 |
| `SQUAD_MAP.md` | Session 0b (via **squad-map**; template at [squad-map/templates/SQUAD_MAP.md](../../squad-map/templates/SQUAD_MAP.md)) |
| `UNKNOWNS.md` | Continuous (unanswered questions) |
| `RUNBOOK.md` | P4 |
| `PROGRESS.md` | Continuous |
| `domain-config.yaml` | Session 0 |
| `manifest.yaml` | Every phase ([manifest-schema.md](manifest-schema.md), schema v2) |
| `E2E_FLOW.md` | Optional P2 supplement — E2E/runtime detail when map § Runtime validation is stub+link |
| `<repo>/memory-bank/*.md` | Optional P5 — per-repo Memory Bank export ([memory-bank-integration.md](memory-bank-integration.md)) |
| `postman/*` | Optional P5 — Postman/curl export ([api-tooling-integration.md](api-tooling-integration.md)) |

Export templates (not copied at Session 0): [templates/memory-bank/](../templates/memory-bank/),
[templates/postman/](../templates/postman/).

## {map_file} sections (order fixed)

Inventory · Contracts · Mechanical Insights · Per-Repo Deep Dives · Flow · Runtime validation (Datadog) ·
core_section · Fraud & Compliance · Quality & Ops

## Diagrams

[required-diagrams.md](required-diagrams.md) — four architecture views + business flows.

## .understand-anything/

`knowledge-graph.json`, `domain-graph.json`, `manifest.json`, `metrics.csv`, `diagrams/`
