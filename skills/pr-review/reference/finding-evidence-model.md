# Finding evidence model

**Normative for Phase 2 judge output.** Load with `reference/finding-pipeline.md` step 7a–7b and
`reference/finding-gates.md#execution-path-gate-pipeline-step-4` when production exposure depends on
config, profile, or runtime state not visible in the diff.

## Three formats

| Format | Use when |
|--------|----------|
| **OEDR** (Observed / Expected / Difference / Risk) | Config or numeric comparison — expected value is known from convention, docs, or industry norm |
| **OUR** (Observed / Unknown / Risk) | Security or exposure inferred — production profile/gateway protection **not confirmed** in diff |
| **OAR** (Observed / Assumption / Risk) | Legacy alias for OUR — prefer **Unknown** over Assumption for auth/profile gaps |

Review-level **Evidence** vs **Inference** (`reference/executive-summary.md`) stays at executive
summary scope. These models apply **per finding**.

---

## OEDR — config and comparison defects

Use when **Expected** is defensible without guessing author intent:

```markdown
**Observed:** max-lifetime = 3000
**Expected:** ~1800000 ms (30 min — Hikari default / ops norm)
**Difference:** 3 seconds vs 30 minutes
**Risk:** Connection pool churn → payment failures under load
```

Confidence: **High** when Observed is on the diff line and Expected is standard.  
Severity: **High** when on production-critical path (pool, payment path).

| Field | Rule |
|-------|------|
| **Observed** | Value or code on cited diff line only |
| **Expected** | Norm, default, or spec — cite source briefly when non-obvious |
| **Difference** | One line — quantify gap |
| **Risk** | Tie to blast radius and business impact |

---

## OUR — security and unconfirmed exposure

Use when production exposure is **not confirmed** in the diff. Prefer **Unknown** (not Assumption) —
avoids overstating.

```markdown
**Observed:** No authentication annotations on `KafkaTestController`.
**Unknown:** Whether controller is excluded from production or protected by gateway/profile elsewhere.
**Risk:** If exposed outside dev → unauthorized PDN processing.
```

Default: **Overall Medium**, **Confidence Medium** — not High unless profile proves production exposure
in the same diff.

| Situation | Format | Typical Overall |
|-----------|--------|-----------------|
| Missing auth on test/dev controller | OUR | Medium |
| Missing auth on production handler (no guards in diff) | OUR or OAR | Medium–High |
| Feature flag off in prod, MR does not enable | OUR | Medium or suppress |
| Generic deserialization / TypeReference erasure | OUR | **Medium** |
| Bucket4j + Redis — startup depends on runtime | OUR | **Medium** |
| `max-lifetime: 3000` on changed line | OEDR | **High** |
| Clear logic error on changed line | cite line | **High** |
| Resilience4j fallback signature mismatch visible | OEDR/direct | **High** |

When **Unknown** is non-empty → default **Confidence: Medium**; do **not** default Overall to High.

---

## Severity × confidence (normative)

| Finding | Overall | Confidence |
|---------|---------|------------|
| Payment date / autodebit wrong day (grouped) | **High** | High |
| Resilience fallback signature on diff | **High** | High |
| `max-lifetime: 3000` on diff line | **High** | High |
| Embedded credential on diff line | **High** | High |
| Jackson TypeReference / erasure | **Medium** | Medium |
| Bucket4j config mismatch | **Medium** | Medium–High |
| STG `config/stg/…` deleted, no broken import | **Medium** | High |
| Kafka/test controller, no visible auth | **Medium** | Medium |

**Anti-pattern:** High severity + High confidence on every important row; eight Highs on one MR.

---

## Integration

| Step | Action |
|------|--------|
| Pipeline step 7a | Apply High certainty gate before emit |
| Pipeline step 7b | Assign confidence per table above |
| Pipeline step 12 | Optional `observed`, `expected`, `difference`, `unknown`, `risk` fields |
| Inline comment | OEDR or OUR block after Evidence line |
| Code blockers table | Only **High/Critical** rows — Mediums in findings table only |

Cross-ref: `reference/domain-overrides.md`, `reference/detection-vs-judgment.md`.
