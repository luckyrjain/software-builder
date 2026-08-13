# domain-comprehension

**Verifiable, evidence-backed** domain mapping from executable source code and runtime validation, plus an
**as-built/current-state PRD** for the in-scope service(s) and/or domain. **Prefer UNKNOWN over speculation.**
Deterministic phase outputs for repeatable agent runs.

Generated domain artifacts live under `docs/domain-comprehension/<domain-slug>/` by default; the skill
creates the directory when absent. Root `manifest.yaml` is retained only as machine state/resume metadata.

Auto-invokes from natural language when you ask to map a domain, understand bounded contexts, reconstruct
what an existing service/domain actually does, or onboard into an unfamiliar codebase.

## What it does

1. **Mandatory phase artifacts** — [phase-outputs.md](reference/phase-outputs.md) + completion gate
2. **Split deliverables** — bounded contexts, data ownership, dependency graph, state machine, catalogs, risk map, glossary, ADRs
3. **As-built PRD (P5)** — stable functional/business-rule/NFR IDs with evidence and traceability
4. **Five critical questions** — Evidence → Conclusion → Confidence
5. **Required diagrams** — context, sequence, state machine, critical path, dependencies
6. **Mechanical model (P0.5)** — `/understand`; **runtime validation (P2b)** — Datadog/KubeSense when available
7. **Engineering Leader Summary (P5)**
8. **Optional Memory Bank/Postman exports (P5)**

The PRD is deliberately **current-state/as-built**. Implementation evidence can establish behavior; it
cannot safely establish undocumented rationale, roadmap, desired future behavior, KPI targets, or SLO
targets. Use **prd-architect** for future-state product specification/build-readiness decisions.

**Read-only on application source** — no deploys or app-code edits. Optional export directories are the
only non-domain-doc write exceptions.

## When to use

| Use domain-comprehension | Use instead |
|--------------------------|-------------|
| Map a subsystem/domain | Post-incident RCA → **incident-rca** |
| Multi-repo onboarding / ground truth | MR review → **pr-review** |
| Create a PRD for what an existing service/domain does today | Future-state/MVP PRD → **prd-architect** |
| Trace an end-to-end flow | K8s sizing → **k8s-overprovisioning-datadog** |
| Squad/repo ownership only | **squad-map** |

## Invocation examples

```text
Comprehend the disbursement domain in /Users/me/Projects
Map the auth subsystem in this monorepo
Create an evidence-backed current-state PRD for the repayment service and its domain
Resume domain comprehension from manifest.yaml
```

More patterns: [examples.md](examples.md)

## What you get

Under `docs/domain-comprehension/<domain-slug>/`:

| Artifact | Purpose |
|----------|---------|
| `EXEC_SUMMARY.md` | Five questions + Engineering Leader Summary |
| `PRD.md` | As-built/current-state PRD with `FR-*`, `BR-*`, `NFR-*` traceability |
| `BOUNDED_CONTEXTS.md` / `DATA_OWNERSHIP.md` | Context and entity authority |
| `DEPENDENCY_GRAPH.md` / `STATE_MACHINE.md` | Architecture and domain state |
| `API_CATALOG.md` / `EVENT_CATALOG.md` | Contracts |
| `RISK_MAP.md` / `ARCHITECTURE_DECISIONS.md` | Risks and ADRs |
| `{DOMAIN}_MAP.md` / `DOMAIN_GLOSSARY.md` | Narrative map and terminology |
| `SQUAD_MAP.md` | Domain snapshot of shared squad mapping |
| `UNKNOWNS.md` / `RUNBOOK.md` / `PROGRESS.md` | Ops + resume context |
| `domain-config.yaml` | Domain-comprehension configuration |

At workspace root: `manifest.yaml` only, plus squad-map's optional shared `SQUAD_MAP.md` if that skill is
used independently/shared across domains.

## Prerequisites

- Target workspace with source code
- **understand-anything** recommended for P0.5 ([SETUP.md](SETUP.md))
- Node.js ≥22 for `/understand` scripts

## Install

```bash
cd software-builder
make install-domain-comprehension
```

Restart Cursor after install.

## Framework

Uses shared [skill-framework](../docs/skill-framework/README.md) confidence bands and cross-skill escalation.
