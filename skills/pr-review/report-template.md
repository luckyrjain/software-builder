# PR Review — Report template index

Chat-first deliverable. The agent renders sections in this order during Phase 5 — do not bulk-load all
reference files; follow [workflow/phase-5.md](workflow/phase-5.md).

## Section map

| Order | Section | Reference | When |
|-------|---------|-----------|------|
| 1 | Re-review block | [comment-templates.md](reference/comment-templates.md) | Incremental only |
| 2 | Review findings | [finding-pipeline.md](reference/finding-pipeline.md) | Always |
| 3 | Coverage gaps | [workflow/phase-5.md](workflow/phase-5.md) §Coverage gaps | `review_evidence.inspection_status: partial|unable` or invalid finalized inspection state |
| 4 | Not raised (suppressed) | [not-raised.md](reference/not-raised.md) | When suppressions or cluster merges |
| 5 | Engineering improvements | [review-metrics.md](reference/review-metrics.md) §Repository maturity | When non-empty |
| 6 | Positive observations | [positive-observations.md](reference/positive-observations.md) | When ≥2 apply |
| 7 | Production risk | [production-risk.md](reference/production-risk.md) | Non-mechanical MRs |
| 8 | Architectural summary | [architectural-summary.md](reference/architectural-summary.md) | Non-mechanical MRs |
| 9 | Executive Summary | [executive-summary.md](reference/executive-summary.md), [gold-review-excerpt.md](reference/gold-review-excerpt.md) | Always (capstone) |
| 10 | Conclusion | [executive-summary.md](reference/executive-summary.md#conclusion) | Always |
| 11 | `review_metadata` YAML footer | [review-metrics.md](reference/review-metrics.md) | Always |

## Partial review

When review stops early or machine inspection coverage is incomplete
([workflow/phase-5.md](workflow/phase-5.md) §Partial review):

```markdown
## Partial review — stopped during analysis

<2 sentences: what was reviewed, why stopped>

### Evidence

- ⚠️ 14/38 changed files reviewed before stop
- ⚠️ Stop-search threshold reached (2 Critical · 3 High · 10 total)

**Confidence:** Medium *(capped — review incomplete)*

### Code blockers

| Finding | Severity | Blast radius | Business impact | Conf |
|---------|----------|--------------|-----------------|------|
| … | … | … | … | … |

### Decision gates

| Gate | Result |
|------|--------|
| Runtime correctness | ❌ |
| **Recommendation** | **💬 Comment** *(provisional)* |

### Technical blockers

| Gate | Status |
|------|--------|
| Critical findings | ⚠️ 2 |
| High findings | ⚠️ 3 |
| Review coverage | ⚠️ Partial (14/38) |

### Process blockers

| Gate | Status |
|------|--------|
| CI pipeline | ✅ Green |

**Reason:**
- Stop-search threshold reached / user requested stop / diff cap without continue
- Unreviewed: <list files or dimensions>

### Review findings
<findings emitted before stop — or "No actionable findings">
```

For Batch 5.2B inspection partial/unable output, use the same incomplete-review framing but render the
Coverage gaps block immediately after Review findings and before Not raised:

```markdown
### Coverage gaps

| Surface | Mandatory | Reason |
|---------|-----------|--------|
| `hidden_consumers` | Yes | repository consumer search unavailable |
```

Mandatory unavailable coverage means the review is not complete, cannot be presented as merge-ready, and does not
enter provider posting. Non-mandatory partial coverage is capped below Approve and requires explicit posting
confirmation. `inspection_status: unable` uses Confidence Low.

Do **not** present partial or unable output as a complete review.

## Canvas hint

When the findings table exceeds **~15 rows** or dimension scores benefit from layout, offer opening a
[canvas](~/.cursor/skills-cursor/canvas/SKILL.md) for severity distribution and score comparison.
See [post-action-templates.md](../docs/skill-framework/shared/post-action-templates.md) §6.

## Post-actions

| Action | Reference |
|--------|-----------|
| Jira comment / transition | [jira-writeback.md](reference/jira-writeback.md) |
| Slack / Teams notify | [workflow/posting.md](workflow/posting.md) §Slack / Teams notification |
