# Calibration snippets

Load during workflow step **3 (Rewrite)** alongside [function-translations.md](function-translations.md). Short few-shots — not a substitute for the full translation table.

## 1. P0 rewrite (cooling window)

**Context:** `TblSmsCaptureRecordRepository.findCoolingWithinWindow`

**MySQL:**
```sql
TIMESTAMPDIFF(MINUTE, tsc.added_timestamp, CURRENT_TIMESTAMP()) < :cool
```

**PostgreSQL:**
```sql
EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - tsc.added_timestamp)) / 60 < :cool
```

**Evidence anchor:** cite `file:line` from scan output. Tier: **P0**.

## 2. Suppressed — JPQL-only (no SQL rewrite)

**Context:** Service has `@Query` without `nativeQuery = true`; only `MySQL8Dialect` in config.

**Agent output:**
```
No native @Query(nativeQuery=true) — dialect + JDBC only.
Skip function-translations; update PostgreSQLDialect + jdbc:postgresql URL.
Scan gate: expect exit 0 on .java without native SQL strings.
```

Do **not** rewrite JPQL `DATE_FORMAT` fragments — Hibernate translates.

## 3. Merge gate matrix

Emit when user asks "are we done?" or before MR handoff:

| Gate | Result |
|------|--------|
| Scan exit 0 | ☐ pass / ☐ fail |
| P0/P1 files rewritten | ☐ |
| Manual audit (timestamps, ENUM, case) | ☐ |
| Shadow compare (10–20 userIds) | ☐ |
| **Ready for MR** | **☐ yes / ☐ no** |

If any row fails → **not done**; cite [skill-contract.md](skill-contract.md) §9.
