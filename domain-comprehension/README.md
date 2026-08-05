# domain-comprehension

**Verifiable, evidence-backed** domain mapping from executable source code and runtime validation.
**Prefer UNKNOWN over speculation.** Deterministic phase outputs for repeatable agent runs.

## What it does

1. **Mandatory phase artifacts** — [phase-outputs.md](reference/phase-outputs.md) + completion gate
2. **Split deliverables** — bounded contexts, data ownership, dependency graph, state machine, catalogs, risk map, glossary, ADRs
3. **Five critical questions** — Evidence → Conclusion → Confidence; section confidence propagation
4. **Required diagrams** — context, sequence, state machine, critical path, dependencies
5. **Mechanical model (P0.5)** — `/understand` graphs; **runtime validation (P2b)** — Datadog deps
6. **Engineering Leader Summary (P5)** — maturity, debt, investments for directors/staff engineers
7. **Optional Memory Bank export (P5)** — per-repo `memory-bank/*.md` from deliverables + graph appendix
8. **Optional API tooling export (P5)** — runnable Postman collection + curl generator from deliverables
   ([api-tooling-integration.md](reference/api-tooling-integration.md))

**Read-only on application source** — no prod calls, deploys, or app code edits. Exception: `memory-bank/**`
and `postman/**` when export is enabled ([memory-bank-integration.md](reference/memory-bank-integration.md),
[api-tooling-integration.md](reference/api-tooling-integration.md)).

## When to use

| Use domain-comprehension | Use instead |
|--------------------------|-------------|
| "Map the disbursement subsystem" | Post-incident RCA → **incident-rca** |
| Multi-repo onboarding / ground truth | MR review → **pr-review** |
| "How does X flow end-to-end?" (code evidence) | K8s sizing → **k8s-overprovisioning-datadog** |
| Squad / repo ownership only | **squad-map** |

## Invocation examples

```
Comprehend the disbursement domain in /Users/me/Projects — use fintech-payout pack
Map the auth subsystem in this monorepo — Session 0 quick orientation
Resume domain comprehension from PROGRESS.md
```

More patterns: [examples.md](examples.md)

## What you get

| Artifact | Purpose |
|----------|---------|
| `EXEC_SUMMARY.md` | Five questions + Engineering Leader Summary |
| `BOUNDED_CONTEXTS.md` | Context cards + map |
| `DATA_OWNERSHIP.md` | Entity authority |
| `DEPENDENCY_GRAPH.md` | Service dependencies + runtime |
| `STATE_MACHINE.md` | Domain states |
| `API_CATALOG.md` / `EVENT_CATALOG.md` | Contracts |
| `RISK_MAP.md` | Smells + change risk |
| `DOMAIN_GLOSSARY.md` | Terms |
| `ARCHITECTURE_DECISIONS.md` | ADRs |
| `{DOMAIN}_MAP.md` | Narrative index |
| `SQUAD_MAP.md` | Squad mapping (Session 0b via **squad-map**) |
| `manifest.yaml` | Phase + artifact state (machine-readable) |
| `UNKNOWNS.md` / `RUNBOOK.md` / `PROGRESS.md` | Ops + resume |
| `<repo>/memory-bank/*.md` | Optional P5 — per-repo agent onboarding ([memory-bank-integration.md](reference/memory-bank-integration.md)) |

## Prerequisites

- Target workspace with source code
- **understand-anything** plugin recommended for P0.5 ([SETUP.md](SETUP.md))
- Node.js ≥ 22 for `/understand` scripts

## Install

**Canonical source:** edit this directory in the [ai-skills](https://gitlab.example.com/lucky.jain/ai-skills) repo at
`domain-comprehension/`, then install to `~/.cursor/skills/domain-comprehension`:

```bash
cd ai-skills
make install-domain-comprehension
```

Restart Cursor after install.

## Framework

Uses shared [skill-framework](../docs/skill-framework/README.md) confidence bands and cross-skill escalation.
