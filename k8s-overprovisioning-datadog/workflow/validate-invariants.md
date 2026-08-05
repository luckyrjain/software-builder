---
workflow_version: 3.0
phase: validate-invariants
produces:
  - validated_graph
consumes:
  - decision_graph
---

# Validate invariants

Run **after** [build-graph.md](build-graph.md), **before** [render.md](render.md).

Check every rule in [invariants.md](../reference/invariants.md).

## Procedure

For each INV-01 … INV-13:

1. Scan `decision_graph`
2. On failure → append to `invariant_violations[]` with `id`, `message`, `nodes`
3. Critical failure → **stop** — emit graph + violations; do not render markdown

## Quick checks

```
INV-01: ∀ rec ∈ recommendations → |rec.depends_on.decisions| ≥ 1
INV-03: ∀ obs ∈ observations → ∃! evid ∈ evidence : evid.observation_id == obs.id
INV-07: assessment.assessment_confidence.value == round(weighted_sum(factors), 1)
INV-08: ¬(rec.status == READY ∧ ∃ d ∈ rec.depends_on.decisions : decision[d].status == BLOCKED)
INV-12: ∀ rec ∈ recommendations where rec.status == READY ∧ rec.id is actionable change → non-empty rec.delivery_pointer.path
INV-13: ∀ assume_id ∈ (∪ rec.depends_on.assumptions) → ∃ assume ∈ assumptions : assume.id == assume_id
```

Actionable change ids: suffix `_REDUCE`, `_INCREASE`, `_ADJUST`, or `REC_MANIFEST_RECONCILE`. **Critical** — block RENDER until `delivery_pointer.path` is set (use `verified: false` when git MCP cannot confirm).

## Pass

Set `validated_graph` = graph with empty `invariant_violations` → proceed to RENDER.

## Recovery guidance

When `invariant_violations[]` is non-empty, apply the fix table below, then re-run
`VALIDATE_INVARIANTS`. **Do not emit a polished report until violations are cleared.**

| Violation | Likely cause | Fix |
|-----------|--------------|-----|
| **INV-01** — `REC_*` missing `depends_on.decisions` | REASON produced a recommendation before a decision object existed | Add the `DEC_*` that justifies the recommendation. If no decision was produced, demote `REC_*` to `status: DEFERRED`. |
| **INV-02** — `DEC_*` missing `supports` | Decision built without referencing backing observations | Add the `OBS_*` IDs that support this decision. If no observations back it, remove the decision. |
| **INV-03** — `OBS_*` has no matching `EVID_*` | Observation registered in NORMALIZE but evidence not collected | If metric was queried but returned no data: add `EVID_*` with `quality: missing`, `source: omit`. If metric was never queried: re-run COLLECT for that observation. |
| **INV-04** — `EVID_*` has empty `source` | Evidence created without recording its MCP | Set `source:` to the MCP that provided data (e.g. `datadog`, `kubesense`). If data was absent, set `quality: missing` and omit `source`. |
| **INV-05** — value on decision/rec/evidence | Values were placed on the wrong node | Move values to the corresponding `OBS_*` entry; remove from the violating node. |
| **INV-06** — wrong ID prefix | Node created with incorrect prefix | Rename: observations → `OBS_`, evidence → `EVID_`, decisions → `DEC_`, recommendations → `REC_`, assumptions → `ASSUME_`. |
| **INV-07** — confidence arithmetic mismatch | Confidence was hand-assigned or rounding diverged | Recompute per [confidence-formula.md](../reference/confidence-formula.md); store the `arithmetic` string. |
| **INV-08** — READY rec has BLOCKED decision | Recommendation marked READY while its decision is blocked | Set recommendation `status: BLOCKED`. |
| **INV-09** — cut rec with unresolved contradiction | Contradictions not resolved before cut recs were emitted | Resolve contradictions in `contradictions[]` (set `status: Resolved` with `resolution` prose), or remove the cut recommendation. |
| **INV-10** — dangling ID reference | A node references an ID that doesn't exist in the graph | Add the missing node, or remove the dangling reference from `supports`, `blocking`, `missing`, or `depends_on`. |
| **INV-11** — recommendation confidence mismatch | Per-rec confidence was hand-assigned | Recompute per [confidence-formula.md](../reference/confidence-formula.md) `RECOMMENDATION_CONFIDENCE` formula. |
| **INV-12** — READY actionable rec missing `delivery_pointer.path` | Change recommendation emitted without specifying where to apply it | Add `delivery_pointer.path` (helm values file, kustomize overlay, manifest path). If unknown, ask the user or set `verified: false` with a best-guess path — **do not render** until `path` is non-empty. |
| **INV-13** — dangling `ASSUME_*` reference | `depends_on.assumptions` references an ID absent from `assumptions[]` | Add the missing entry to `assumptions[]`, or remove the dangling reference from `depends_on.assumptions`. |

**After fixing:** re-run `VALIDATE_INVARIANTS` — proceed to RENDER only when `invariant_violations[]` is empty.
