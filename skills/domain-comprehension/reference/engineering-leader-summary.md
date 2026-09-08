# Engineering leader summary (normative)

**Artifact:** `EXEC_SUMMARY.md` § Engineering Leader Summary. **Produced in:** P5 only.

Audience: Directors / Staff Engineers. ≤1 page. Every rating includes **Confidence** (propagated minimum).

## Lead block (read first)

### Overall confidence

From [confidence-rubric.md](confidence-rubric.md) — display question table + **Overall:** band.

### Evidence summary (one line)

Repos scanned / in scope · files inspected · runtime edges confirmed · unknowns · omissions.

### Top smells

Link to `RISK_MAP.md` § Top smells (≤10) — do not paste full inventory.

## Required subsections

### Domain maturity

| Dimension | Rating (1–5 or Mature/Emerging/Unknown) | One-line evidence |
|-----------|----------------------------------------|-------------------|
| Domain model clarity | | |
| Bounded context separation | | |
| API/event contract discipline | | |

### Operational maturity

| Dimension | Rating | Evidence |
|-----------|--------|----------|
| Observability (logs/metrics/traces) | | |
| Runbook coverage | | |
| Failure handling / retry | | |
| Reconciliation | | |

### Architecture quality

| Dimension | Rating | Evidence |
|-----------|--------|----------|
| Coupling / cohesion | | |
| Critical path clarity | | |
| Runtime vs code alignment (P2b) | | |
| Smell count (Critical/High) | | |

### Ownership clarity

From `SQUAD_MAP.md` + `BOUNDED_CONTEXTS.md`: % repos with HIGH squad confidence; conflict count.

### Documentation quality

Code vs external docs alignment; ADRs found (`ARCHITECTURE_DECISIONS.md`).

### Testing confidence

From P4 — critical path tested? integration/e2e presence?

### Deployment risk

Summary from `RISK_MAP.md` § Change risk — count Safe/Moderate/High/Unknown.

### Recommended investments

3–5 bullets, prioritized, tied to top smells / unknowns / change impact.

### Top 5 technical debt items

| # | Item | Impact | Evidence | Confidence |

## Anti-patterns

- Generic platitudes without evidence paths
- HIGH ratings when overall confidence is LOW/UNKNOWN
- Omitting P2b misalignment when `RUNTIME_ONLY` hops exist
- Listing hundreds of smells instead of Top 10
