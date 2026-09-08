# Architectural smells (normative)

**Artifact:** `RISK_MAP.md`. **Scan in:** P1 (initial), P4 (final).

Report smells with evidence — do not label without code/graph/runtime proof.

| Smell | Detection signal | Severity default |
|-------|------------------|------------------|
| **God service** | High fan-in + fan-out; many unrelated domains in one repo | High |
| **Cyclic dependency** | `depends_on` cycle in graph or import cycle | High |
| **Multiple writers** | 2+ repos migrate/write same table | Critical |
| **Hidden ownership** | No squad; conflicting GitLab/Datadog; no CODEOWNERS | Medium |
| **Shared database** | 2+ services write same schema without clear owner | Critical |
| **Missing contract** | Topic/API used but no schema/OpenAPI in producer | Medium |
| **Duplicate implementation** | Near-duplicate repos (inventory DUPLICATE) | Medium |
| **Temporal coupling** | Sync chain >4 hops on critical path | Medium |
| **Large transaction** | Multi-aggregate single `@Transactional` / long DB transaction | Medium |
| **Cross-domain join** | SQL joining tables owned by different contexts | High |
| **Leaky BFF** | Business logic in BFF not downstream | Low |
| **Dead path** | `dead_code` or CODE_ONLY on P2b critical hop | Medium |

## Full inventory (§ Smells)

| Smell | Location (repo/path) | Severity | Evidence | Confidence | Mitigation hint |
|-------|----------------------|----------|----------|------------|-----------------|

Cap confidence **MEDIUM** if smell inferred from graph only — verify in source for **HIGH**.

## Top smells (§ Top smells) — **required P4/P5**

Rank **at most 10** by `(severity × business impact)`. Large systems may have hundreds of observations —
leaders need prioritization.

| Rank | Smell | Severity | Business impact | Evidence | Recommended remediation |
|------|-------|----------|-----------------|----------|-------------------------|

**Business impact:** 1-line effect on revenue, compliance, availability, or delivery speed.

P5 Engineering Leader Summary links here — do not duplicate full inventory.
