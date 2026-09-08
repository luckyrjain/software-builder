# Change-risk map (normative)

**Artifact:** `RISK_MAP.md` § Change risk. **Produced in:** P4 (uses P0.5 graph + P2b runtime + ownership).

Per repo or bounded context, classify modification risk for engineering leaders.

| Risk | Criteria |
|------|----------|
| **Safe** | Low fan-out; single owner; good tests; no shared DB; leaf service |
| **Moderate** | Multiple consumers; partial tests; cross-context reads only |
| **High** | Tier 0/1; many downstream deps; multiple writers; runtime-critical path; weak observability |
| **Unknown** | Incomplete inventory or missing graph |

## Table (required)

| Repo / context | Risk | Fan-out (downstream count) | Runtime critical? | Test coverage signal | Owner clarity | Evidence |

### Signals

- **Fan-out** — from `DEPENDENCY_GRAPH.md` § Service call + P2b Datadog downstream count
- **Runtime critical** — on P2 business flow with `runtime_confirmed` hop
- **Test coverage** — qualitative from P4 (unit/integration presence, not % unless measured)
- **Owner clarity** — `SQUAD_MAP.md` confidence HIGH

## Change impact (per bounded context) — **required P4**

**Artifact:** `BOUNDED_CONTEXTS.md` context cards + `RISK_MAP.md` § Change impact.

For each bounded context:

| If modified | Detail |
|-------------|--------|
| Impacted services | Downstream repos/services |
| Impacted events | Topics produced/consumed |
| Impacted APIs | HTTP/gRPC consumers |
| Runtime consumers | P2b-confirmed callers |
| Confidence | Propagated minimum |

Rollup table in `RISK_MAP.md` § Change impact:

| Context | Impacted services (n) | Impacted events (n) | Impacted APIs (n) | Runtime consumers (n) | Confidence |

## Link to smells

Repos with Critical/High smells default to **High** change risk unless evidence contradicts.

Top 10 smells: [architectural-smells.md](architectural-smells.md).
