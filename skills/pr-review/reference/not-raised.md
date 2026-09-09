# Not raised — suppressed candidates (Phase 5)

Load when `review_metrics.suppressed` totals ≥ 1 **or** thematic clustering merged ≥ 2 candidates
into one finding. Documents reviewer discipline without recreating noise.

## Purpose

Show what was **considered and intentionally not reported** — distinct from findings table and
**Engineering improvements** (repo maturity, not `<review_target_noun>` defects; GitHub `PR`, GitLab
`MR`).

## When to include

| Condition | Include section |
|-----------|-----------------|
| `suppressed.guess + path + dedupe + feedback + value ≥ 1` | Yes |
| Clustering merged ≥ 2 candidates into one root-cause row | Yes — list merged manifestations |
| Zero suppressions and no clustering | **Omit** |

## Output format

After **Review findings**, before **Engineering improvements**:

```markdown
### Not raised (suppressed)

| Candidate | Reason |
|-----------|--------|
| Null-deref on `user.id` at `Handler.java:55` | No realistic path — all call sites guard null |
| Fallback signature (standalone) | Merged into PRR-RES-001 · Resilience fallback |
| Reactive retry mismatch (standalone) | Merged into PRR-RES-001 · Resilience fallback |
| Style nits (3) | Value filter — see Nice to have P3 |
```

**Rules:**

- Cap at **5 rows** + one summary line: *"+ N more suppressed (guess/path/dedupe)"* when over cap.
- Never list secret values or echo credentials.
- **Merged into group** rows document clustering — not failures.
- Do not repeat full finding prose — one-line reason only.

## Source fields

Populate from `review_metrics.suppressed`:

| Key | Typical reason label |
|-----|---------------------|
| `guess` | Insufficient evidence (don't-guess gate) |
| `path` | No realistic execution path |
| `dedupe` | Already raised on MR / duplicate |
| `feedback` | Category ignored per feedback learning |
| `value` | Fix effort > harm prevented |

Cross-ref: `reference/finding-gates.md#execution-path-gate-pipeline-step-4`,
`reference/finding-pipeline.md` step 10 clustering.
