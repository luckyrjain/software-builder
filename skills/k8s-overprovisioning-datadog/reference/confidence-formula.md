# Confidence formula (deterministic)

Categorical bands (normative): [confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md)

After computing `ASSESSMENT_CONFIDENCE` / `RECOMMENDATION_CONFIDENCE`, map to HIGH / MEDIUM / LOW /
UNKNOWN using the **0.85 / 0.65 / 0.40** thresholds in the shared doc. Human Report displays band
+ factor list only — not raw categorical enum unless comparing across skills.

**Developer / internal reference.** Scores are **computed by formula** — never hand-assigned. Store
`arithmetic` on the graph for INV-07 validation.

**Human Report:** band + numeric + **Basis** bullets — no weighted-sum arithmetic.
**Technical Appendix (default):** band + numeric + factor names — no arithmetic.
Formula details: [workflow/report.md](../workflow/report.md).

Two separate scores — they measure different things and **both can coexist** (e.g. assessment 0.9,
replica recommendation 0.3).

## ASSESSMENT_CONFIDENCE

Overall trust in the assessment. Emitted in `ExecutiveDecision`.

```
ASSESSMENT_CONFIDENCE = round(
  0.35 × evidence_completeness +
  0.35 × evidence_quality +
  0.15 × contradiction_resolution +
  0.15 × telemetry_availability,
  1
)
```

| Input | Range | Computation |
|-------|-------|-------------|
| `evidence_completeness` | 0–1 | `present_required / total_required` for intent path |
| `evidence_quality` | 0–1 | Weighted mean quality (measured=1.0, inferred=0.8, unknown=0.5, missing=0) |
| `contradiction_resolution` | 0–1 | `1.0` all Resolved; `0.6` any Unresolved |
| `telemetry_availability` | 0–1 | ★5=1.0, ★4=0.95, ★3=0.85, ★2=0.75, ★1=0.70 |

### Example (graph storage — not default render)

```text
ASSESSMENT_CONFIDENCE: 0.9 (Very High)
  = 0.35×0.9 + 0.35×0.9 + 0.15×1.0 + 0.15×0.9
  = 0.315 + 0.315 + 0.150 + 0.135
  = 0.915 → 0.9
```

Default Human Report render:

```text
Assessment confidence: Very High (0.9)

Basis:
• Evidence completeness — all required signals present
• Evidence quality — measured utilization, not inferred
• Telemetry coverage — ★3 Datadog profile
• Contradiction resolution — avg vs p95 resolved in favor of p95
```

Default appendix render (abbreviated when Human Report already showed basis):

## RECOMMENDATION_CONFIDENCE

Per `REC_*` item. Emitted only on that recommendation — **not** interchangeable with assessment score.

```
RECOMMENDATION_CONFIDENCE = round(
  0.40 × support_completeness +
  0.30 × support_quality +
  0.15 × contradiction_resolution +
  0.15 × telemetry_availability,
  1
)
```

| Input | Range | Computation |
|-------|-------|-------------|
| `support_completeness` | 0–1 | Fraction of `Depends on` observations present (measured/inferred) |
| `support_quality` | 0–1 | Mean quality of supporting `OBS_*` rows |
| `contradiction_resolution` | 0–1 | Same as assessment |
| `telemetry_availability` | 0–1 | Same as assessment |

**Caps (apply after formula, before round):**

- `DEC_*` status `BLOCKED` on parent dimension → cut recommendations capped at **0.3**
- Telemetry ★ ≤ 3 → no recommendation confidence > **0.7**
- Missing critical `OBS_*` for a cut → floor at **0.3**

### Example

```text
RECOMMENDATION_CONFIDENCE: 0.3 (Very Low)  [REC_REPLICA_REDUCE]
  = 0.40×0.25 + 0.30×0.5 + 0.15×1.0 + 0.15×0.85
  = 0.100 + 0.150 + 0.150 + 0.128
  = 0.528 → capped 0.3 (DEC_REPLICAS BLOCKED)
```

## Bands (k8s display ↔ shared categorical)

| Numeric | Shared band | k8s Human Report label |
|---------|-------------|------------------------|
| 0.85–1.00 | HIGH | Very High |
| 0.65–0.84 | MEDIUM | Moderate |
| 0.40–0.64 | LOW | Low |
| < 0.40 | UNKNOWN | Insufficient |

Display: `0.9 (Very High)` — numeric + k8s label. **1 decimal max.** Blocked dimensions or missing
critical inputs → UNKNOWN regardless of partial arithmetic.

**Graph vs metadata:** The decision graph `band` field uses the k8s display label (`Very High`,
`Moderate`, `Low`, `Insufficient`). The `assessment_metadata` footer (cross-skill exchange format)
MUST use the **shared normative band** (`high`, `medium`, `low`, `unknown` — lowercase). This ensures
other skills can parse confidence without k8s-specific label knowledge.

Weights are fixed in this document — do not tune per report.
