---
workflow_version: 1.9
phase: 4
produces:
  - quality_ops_section
  - runbook
  - smells_full
  - top_smells
  - change_impact
  - change_risk_map
  - evidence_summary
consumes:
  - core_domain_deep_dive
  - fraud_compliance_review
  - bounded_contexts
  - smells_initial
---

# Comprehension Phase P4 — Risk and resilience

Scan for architectural smells, failure modes, and change impact — then rank and mitigate.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Quality & ops section | `{map_file}` § Quality & Ops | Tests, observability, correlation IDs, debt, feature toggles, non-entity Redis/ES usage | Phase incomplete |
| Runbook | `RUNBOOK.md` | All procedures or explicit ⚠️ absent | Phase incomplete |
| Smells (full) | `RISK_MAP.md` § Architectural smells | Complete scan across all in-scope repos | Phase incomplete |
| Top smells | `RISK_MAP.md` § Top smells | ≤10 ranked rows by severity × business impact | Phase incomplete |
| Change impact | `BOUNDED_CONTEXTS.md` + `RISK_MAP.md` § Change impact | Per-context if-modified tables | Phase incomplete |
| Change-risk map | `RISK_MAP.md` § Change risk | Safe / Moderate / High / Unknown per service | Phase incomplete |
| Evidence summary | `EXEC_SUMMARY.md` + `manifest.evidence_summary` | All counters updated | Phase incomplete |

## Investigation recipes

- **Feature toggles:** `rg -l 'FeatureFlag|feature\.toggle|toggle\.enabled|@ConditionalOnProperty' --glob '!test*'`
- **Non-entity Redis usage** (session store, locks, rate limiters — NOT entity caching, that's
  `DATA_OWNERSHIP.md` § Caches): `rg -l 'RedisTemplate|@RedisHash|redisson' --glob '!test*'`
  — exclude matches already recorded as entity caches in `DATA_OWNERSHIP.md`. (Don't grep bare
  `rate.?limit` here — it over-matches in-memory limiters like Bucket4j/Resilience4j that have
  nothing to do with Redis; a Redis-backed rate limiter will already surface via `redisson` or
  `RedisTemplate`.)
- **Non-entity Elasticsearch usage** (logging indices, non-domain search — NOT entity search-indexing,
  that's `DATA_OWNERSHIP.md` § Search indexes): `rg -l 'ElasticsearchTemplate|@Document\(indexName' --glob '!test*'`
  — same exclusion rule.

Record findings in `{map_file}` § Quality & Ops. `UNKNOWN` with reason when a toggle/Redis/ES dependency
is referenced in config but no evidence of its runtime effect is found in code.

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md)
