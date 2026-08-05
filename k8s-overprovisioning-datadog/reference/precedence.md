# Precedence (when specs conflict)

Load during **REASON** and **BUILD_GRAPH** when confidence, thresholds, or gates disagree.

| Rank | Source | Wins over | Applies to |
|------|--------|-----------|------------|
| **1** | [stop-reasons.md](../workflow/stop-reasons.md) | All cut recommendations | `STOP_REASON` Critical/High → block or halt |
| **2** | [validate.md](../workflow/validate.md) gates | REASON ALLOW on same dimension | Projection, contradiction, delivery pointer, quota |
| **3** | [confidence-formula.md](confidence-formula.md) | Hand-assigned scores; recommendation-framework.md's deduction-from-1.0 walkthrough | `assessment.assessment_confidence` (INV-07), per-rec arithmetic (INV-11) — this is the **only** arithmetic that gets computed and stored |
| **4** | [recommendation-framework.md](../recommendation-framework.md) | Ad-hoc deductions | Supplies **inputs** to rank 3's formula only: deduction size feeding `support_quality`/`support_completeness`, and the keep-vs-cut 0.33× multiplier — not a second scoring pass |
| **5** | [thresholds.md](../thresholds.md) | Heuristic sizing guesses | Trim/keep numeric cutoffs (fleet p95 %, throttle %, peak proxy) |
| **6** | Dimension modules | Generic trim heuristics | CPU/memory/replica/workload-specific rules |

## Confidence conflicts

| Question | Rule |
|----------|------|
| Assessment band vs formula | **Formula wins** — store `factors` + `arithmetic`; Human Report shows band + Basis bullets only |
| Per-rec score vs framework deductions | One computation, not two: use [recommendation-framework.md](../recommendation-framework.md)'s deduction sizes and keep-vs-cut 0.33× multiplier to set the `support_quality`/`support_completeness` inputs, then compute `RECOMMENDATION_CONFIDENCE` once via [confidence-formula.md](confidence-formula.md)'s weighted sum. Never report recommendation-framework.md's illustrative deduction-from-1.0 number as the final score. |
| Stability blocker caps rec at 0.30 | **stop-reasons** rank 1 — applies before tier ordering |
| Unresolved contradiction | **validate.md** — no cut `REC_*` in READY; assessment confidence cap 0.60 |

## Sizing conflicts

| Signals | Resolution |
|---------|------------|
| Low 7d average vs high fleet p95 | Size on **p95** — contradiction gate Resolved |
| Seasonal weekday/weekend pattern | **DEFER/BLOCK** trim on blended average — [reason.md](../workflow/reason.md#seasonality-vs-overprovisioning) |
| VPA target above proposed cut | **BLOCK** cut — VPA recommends higher |
| VPA + HPA on same dimension | **STOP_REASON** `vpa_hpa_conflict_*` — no cuts until controller conflict resolved |

When still ambiguous after this table, prefer **KEEP / DEFER** over **READY** cut recommendations.
