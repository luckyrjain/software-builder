# PR Review — Evidence + gate matrix (executive summary tightening)

**Status:** Implemented  
**Branch:** `cursor/skill-improvements-r3`

## Problem

The executive summary split **Verification** and **Confidence reason** into parallel subsections, making
the capstone verbose and duplicative. EMs needed a faster scan: observed facts, one confidence line, judgment
separated from evidence, and a compact gate table before the recommendation.

## Design

### Evidence (replaces Verification checklist + Confidence reason)

Single `### Evidence` block with checkmarks and concrete counts (`N/N` files, commands run, truncation).
Immediately followed by one line:

```markdown
**Confidence:** High — full boundary reviewed; ticket linked; no truncation.
```

No separate **Confidence reason** subsection.

### Inference

Short block **after** Evidence — 2–4 bullets, clearly labeled `### Inference`. Required on incremental
re-reviews; optional on first review. Judgment only (regressions, scope category, merge risk).

### Gate matrix

Compact table immediately **before** `**Reason:**`. Final row is **Recommendation**. Normative mapping:
`workflow/phase-5.md`, `reference/review-metrics.md` §Recommendation matrix.

| Gate | Status |
|------|--------|
| Critical findings | ✅ None / ⚠️ N |
| High findings | ✅ None / ⚠️ N |
| CI | ✅ Green / ⏳ Pending / ❌ Failed / ❓ Not configured |
| Regression | ✅ None / ⚠️ … / N/A |
| Review coverage | ✅ Complete (N/N) / ⚠️ Partial (N/M) |
| CODEOWNERS | ✅ Satisfied / ⚠️ Pending *(when applicable)* |
| Prior findings *(re-review)* | ✅ N/N resolved / ⚠️ N remaining |
| **Recommendation** | **✅ Approve / 💬 Comment / 🔴 Request changes** |

Gate matrix does **not** replace the `review_metadata` YAML footer.

### Emission order (inside `## Executive Summary`)

1. Narrative  
2. Evidence + confidence line  
3. Inference  
4. Gate matrix  
5. Reason  
6. Review cost, blocking issues, scores, pipeline  

## Files changed

- `pr-review/workflow/phase-5.md`
- `pr-review/reference/executive-summary.md`
- `pr-review/reference/comment-templates.md`
- `pr-review/report-template.md`
- `pr-review/examples.md`
- `pr-review/reference/pressure-tests.md`
- `pr-review/reference/incremental-rerun.md`
- `pr-review/reference/review-metrics.md` (confidence pairing note)

## Verification

- `make lint-pr-review`
- `make lint-framework`
- No header-only tables (`Field | Value` or `Gate | Status` without rows)
