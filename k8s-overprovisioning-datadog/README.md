# k8s-overprovisioning-datadog

**Kubernetes Deployment Optimization Readiness Assessment (DORA — not the DevOps Research & Assessment
metrics acronym)** for Cursor. Queries Datadog for CPU, memory, replica, HPA, and cost signals and
produces a structured rightsizing report — not a single "reduce requests by X%" number.

Auto-invokes from natural language when you ask whether a service is overprovisioned, right-sized, or
wasting cluster cost.

## What it does

1. **Resolves the deployment** — service name → `kube_deployment`, namespace, environment (default
   `env:production`).
2. **Collects telemetry** via Datadog MCP — utilization, requests, limits, throttling, OOM, HPA, monitors,
   optional CCM cost.
3. **Normalizes units** and runs intent-specific analysis modules (CPU cyclic check, memory peak proxy,
   replica/HPA, Kafka lag, SLO correlation).
4. **Applies safety gates (P0)** — auth failure, insufficient metrics, manifest drift, active firing
   monitors, throttle >5%, conflicting signals block unsafe recommendations.
5. **Produces a DORA report** — per-dimension verdicts, decision confidence (0–1), waste estimate, optional
   monthly $ savings (observed / estimated / resource-only), rollback triggers.

**Analyze only** — no live cluster changes.

## When to use

| Use this skill | Use instead |
|----------------|-------------|
| "Is payment-service overprovisioned in prod?" | Post-incident RCA → **incident-rca** |
| "Right-size CPU/memory for X" | MR that caused a bad deploy → **pr-review** |
| "Which namespace wastes the most CPU?" | Non-optimization-only with no K8s context → narrow scope first |
| ArgoCD/Flux GitOps deployments | Confirm sync state before treating manifest drift as Finding #1 |
| — | Org-wide cost/waste ranking across many deployments → **cost-optimization-sprint-planner** |
| — | Pre-release go/no-go across several repos/services → **release-readiness-checker** |

## Invocation examples

```
Is example-service overprovisioned in production?
Review K8s resource utilization for payment-service
What cost could we save right-sizing payment-service?
Which namespace is wasting the most CPU in production?
Are replicas too high for order-service?
```

More scenarios: [examples.md](examples.md)

## What you get

**See real output first:** [reference/gold-human-report-excerpt.md](reference/gold-human-report-excerpt.md)
is a rendered example Human Report — read that before `report-template.md` or the decision-graph
internals below, which are the structural spec and machine format, not what you'll actually read.

| Output | Description |
|--------|-------------|
| **Human Report** | Prose-first deliverable (~2–4 pages) — recommendation, health, optimization decision, evidence summary, recommendations, rejected changes, risks, conclusion ([report-template.md](report-template.md) — full spec) |
| **Technical Appendix** | Full DORA audit trail (appendices A–E) — decision graph IDs, evidence registry, metadata, validation |
| **Decision graph** | Typed YAML/JSON primary artifact (`schema_version: 3`) |
| **`FINAL_DECISION`** | Machine-readable executive decision + computed confidence (appendix C) |
| **Invariants** | Self-validating graph (INV-01–INV-13) before render |
| **JSON export** | Lossless graph view ([render/json.md](render/json.md)); summary-only markdown optional |

Graph: [reference/decision-graph-schema.md](reference/decision-graph-schema.md). Render: [render/README.md](render/README.md). Presentation rules: [workflow/report.md](workflow/report.md).

## Pipeline (agent)

```
COLLECT → NORMALIZE → REASON → VALIDATE → [COST if gated] → BUILD_GRAPH → VALIDATE_INVARIANTS → RENDER
```

Routing and intent shortcuts: [workflow/orchestrator.md](workflow/orchestrator.md).

| Module | Role |
|--------|------|
| `collect-metrics.md` | Datadog queries for utilization and requests |
| `cpu-analysis.md` / `memory-analysis.md` | Dimension verdicts |
| `replica-analysis.md` | HPA / KEDA / replica count |
| `workload-analysis.md` | Kafka lag, monitors, SLO |
| `cost-analysis.md` | CCM (gated) |
| `stop-reasons.md` | P0 safety registry |
| `build-graph.md` | Assemble typed `decision_graph` (primary artifact) |
| `validate-invariants.md` | INV-01–INV-13 gate before render |
| `render.md` | Human Report + Technical Appendix (markdown) and/or JSON |
| `report.md` | Human-first presentation rules (ID translation, smoke tests) |

Lookup tables (do not invent inline): [queries.md](queries.md), [thresholds.md](thresholds.md), [cost-estimation.md](cost-estimation.md), [recommendation-framework.md](recommendation-framework.md).

## Prerequisites

- **Datadog MCP** (`plugin-datadog-datadog`) with metrics (+ monitors, optional CCM/traces)
- **`telemetry.intent`** on every Datadog call (skill supplies automatically)
- Optional **Git MCP** for manifest-vs-running drift check

Setup: [SETUP.md](SETUP.md).

## Quality checks

From repo root: `make lint-k8s-skill` (SKILL ≤150 lines, anchor links, memory p95 guard).

Smoke test after edits: [workflow/render.md](workflow/render.md#smoke-test).
