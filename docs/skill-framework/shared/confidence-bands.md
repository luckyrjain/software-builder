# Confidence bands (shared)

**Normative.** All skills MUST use these four categorical bands only: HIGH, MEDIUM, LOW, UNKNOWN.

**Consumers:** pr-review (`reference/executive-summary.md`), incident-rca (`reference/manual-scoring.md`, `reference/evidence-schema.md`), k8s (`reference/confidence-formula.md`), squad-map (`reference/squad-mapping.md`), domain-comprehension (`reference/confidence-rubric.md`), mysql-to-postgres-sql (`SKILL.md` priority tiers — see §2.1).

## 1. Purpose

One vocabulary across pr-review, incident-rca, k8s-overprovisioning-datadog, and squad-map so agents do not mix alternate labels ("High", "0.9", "Very High", "Confident", "Likely") inconsistently. When comparing findings across skills, translate to these four bands first.

## 2. Categorical definitions

| Band | Evidence rule |
|------|---------------|
| **HIGH** | Multiple independent sources agree; no unresolved contradictions; full window coverage |
| **MEDIUM** | Plausible but incomplete — single domain, partial window, fast-path scope, or competing hypothesis |
| **LOW** | Thin signal, heavy inference, truncation, stop-search triggered, or timing mismatch |
| **UNKNOWN** | Insufficient data to rank; use hypothesis + gaps, never assert cause |

### 2.1 domain-comprehension — `overall_confidence`

Map document-level confidence from `domain-comprehension/reference/confidence-rubric.md`:

```
overall_confidence = minimum(
  five_questions.q1..q5.confidence,
  weakest major section confidence,
  overall_confidence in manifest.yaml
)
```

| Manifest / section state | Max band |
|--------------------------|----------|
| All five questions COMPLETE with executable evidence | Per rubric (often HIGH on isolated claims) |
| Any question UNKNOWN or DRAFT in final delivery | Caps **overall** at UNKNOWN — do not ship DRAFT |
| Weakest section LOW (wiki-only, single comment) | Overall ≤ LOW |
| P2b runtime-only without code path | Section ≤ MEDIUM; does not alone raise overall to HIGH |

Display in `EXEC_SUMMARY.md` § Overall confidence using **HIGH | MEDIUM | LOW | UNKNOWN** only.

### 2.2 mysql-to-postgres-sql — risk tier ≠ confidence

**P0 / P1 / P2 / Portable** in this skill are **migration risk tiers** (compliance priority and rewrite
order), **not** evidence confidence bands.

| Label | Meaning | Maps to confidence band? |
|-------|---------|--------------------------|
| **P0** | Compliance / consent gates (e.g. SMS cooling) | **No** — use for scan checklist priority only |
| **P1** | Core read paths | **No** |
| **P2** | Legacy / deferred | **No** |
| **Portable** | Dialect-only change | **No** |

Use **HIGH | MEDIUM | LOW | UNKNOWN** only for:

- Shadow-compare parity (PG vs MySQL sample users)
- Scan gate completeness (all hits resolved vs partial audit)
- Handoff blocks to pr-review / incident-rca

**Anti-pattern:** "P0 confidence HIGH" or "P1 finding at MEDIUM" — write `migration_risk_tier: P0` and
`confidence: HIGH` as separate fields (see `assessment_metadata` in review-metadata-schema §8.5).

### 2.3 squad-map — owner confidence

Per-repo **Owner confidence** in `SQUAD_MAP.md` is normatively defined in
`squad-map/reference/squad-mapping.md` §Reconciliation — do not restate the table here; that file's
version is the one the skill's scoring script implements. In particular: an exact match is HIGH, a
**fuzzy alias match is LOW** (not HIGH — a fuzzy match is not the same as agreement), sources
disagreeing is MEDIUM + conflict flag (not LOW), and CODEOWNERS/git-log fallback with both MCPs ❌ is
LOW. **Never HIGH** when GitLab and Datadog disagree — cap at MEDIUM.

Overall mapping summary may cite HIGH/MEDIUM/LOW/UNKNOWN **counts** — not a single fleet-wide band unless
the user asks for a rollup (then use weakest row or conflict-aware rule in chat).

**incident-rca supplement:** integer hypothesis scores (0–100) in the **Ranked hypotheses** table compare
alternates within one RCA. Categorical bands remain normative for the primary conclusion and cross-skill
handoffs. See `incident-rca/reference/evidence-quality.md`.

## 3. Numeric mapping (0.0–1.0)

For k8s `ASSESSMENT_CONFIDENCE` and `RECOMMENDATION_CONFIDENCE` (computed per `reference/confidence-formula.md`):

| Numeric | Categorical | Display label (k8s Human Report) |
|---------|-------------|----------------------------------|
| 0.85–1.00 | HIGH | Very High |
| 0.65–0.84 | MEDIUM | Moderate |
| 0.40–0.64 | LOW | Low |
| <0.40 | UNKNOWN | Insufficient |

Missing inputs or blocked dimensions → UNKNOWN regardless of partial arithmetic.

## 4. pr-review per-finding mapping

| Finding Conf (table) | Overall executive Conf | Typical numeric equivalent |
|----------------------|------------------------|----------------------------|
| High | High | ≥0.85 |
| Medium | Medium | 0.65–0.84 |
| Low | Low | <0.65 |

Per-finding confidence is **independent** of overall review confidence (docs-only MR may have High per-finding on few items but Medium overall due to truncation or stop-search).

Map pr-review display labels to shared bands when handing off:

| pr-review label | Shared band |
|-----------------|-------------|
| High | HIGH |
| Medium | MEDIUM |
| Low | LOW |
| (no data / cannot assess) | UNKNOWN |

## 5. incident-rca hypothesis bands

From `reference/manual-scoring.md` and correlator output — apply guardrails from `reference/evidence-schema.md`:

- Single signal source → cap at **MEDIUM** regardless of raw score
- **LOW/UNKNOWN** → report as hypothesis + gaps, not confirmed cause
- Normalized score 0–1 maps to the same categorical table as §3
- `slo_breach` without corroborating error spike → cap at **MEDIUM**
- Signal outside incident window → cap at **LOW**

## 6. Display rules

- Always include **Reason** or factor bullets with the label
- k8s Human Report: band + factors only (hide weighted sum by default; store `arithmetic` in graph for INV-07)
- pr-review: per-finding Conf column + one-line **Confidence:** reason immediately after **Evidence** in
  executive summary (no separate "Confidence reason" subsection — see `pr-review/reference/executive-summary.md`)
- incident-rca: confidence badge on primary hypothesis + evidence table; list gaps explicitly

### pr-review example

```markdown
**Confidence:** Medium — stop-search at 14 of 38 changed files; core payment paths reviewed. Per-finding
High on `PRR-SEC-001` (signature check) does not raise overall confidence.
```

### incident-rca example

```markdown
**Primary:** deploy_regression (**HIGH**) — deploy at 14:20 UTC + error spike at 14:45; diff touches TransferMoneyHandler.
**Gaps:** Log samples sparse after 15:30 — ranking from metrics + change story only.
```

### k8s example

```markdown
**Assessment confidence:** Moderate (0.72)

Derived from:
• Evidence completeness — 7d CPU/memory series present
• Evidence quality — measured utilization, inferred peak proxy
• Telemetry coverage — ★4 Datadog profile
```

## 7. Anti-patterns

| Anti-pattern | Correct behavior |
|--------------|------------------|
| Label HIGH after one Datadog query | Cap at MEDIUM; list gaps |
| Emit numeric 0.9 without factor list | Include `arithmetic` / Reason bullets in graph; Human Report shows band + factors |
| Use "Confident", "Likely", "Probably" | Map to MEDIUM or LOW with Reason |
| pr-review High overall on truncated MR | Per-finding High allowed; overall may be Medium |
| k8s shows `0.35×0.9 + …` in Human Report | Band + factor list only; formulas in appendix/graph |
| rca asserts root cause at LOW/UNKNOWN | Hypothesis + gaps; never state as fact |
| mysql handoff uses P0/P1 as confidence | Separate `migration_risk_tier` from `confidence` band |
| domain overall HIGH with DRAFT question | Cap at UNKNOWN until five questions COMPLETE |
| squad-map HIGH when GitLab ≠ Datadog | LOW + conflict row |

## 8. Handoff translation rules

When escalating between skills, translate confidence at the handoff boundary:

| From skill | From representation | To skill | To representation |
|------------|---------------------|----------|-------------------|
| incident-rca | `MEDIUM` hypothesis | k8s | Start assessment; expect 0.65–0.84 if evidence complete |
| incident-rca | `HIGH` deploy_regression | pr-review | Per-finding review; security/deploy findings may be High |
| k8s | `0.72` assessment | incident-rca | State as **MEDIUM** in handoff block |
| k8s | `0.90` assessment | pr-review | Equivalent to **HIGH** for cross-skill comparison |
| pr-review | Overall Medium | incident-rca | Do not inflate; pass MR link + window only |
| pr-review | Per-finding High on resource-down | k8s | Trigger rightsizing assessment; k8s computes its own score |

Always pass **Reason** or evidence links in the handoff block — the receiving skill recomputes confidence from its own formula; do not copy numeric scores into rca hypothesis ranks without re-validation.
