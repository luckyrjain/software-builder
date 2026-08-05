# Review modes (lifecycle-aware)

**Normative.** Load in Phase 1 when MR state is known; apply through Phase 5 executive summary.
Three modes — different recommendation strategy, same finding pipeline.

| Mode | Trigger | `review_metadata.review_mode` |
|------|---------|-------------------------------|
| **Pre-merge** | Open MR (`state: opened`) | `pre_merge` |
| **Incremental** | Open MR + prior bot review on same MR | `incremental` |
| **Post-merge (retrospective)** | `state: merged` + user confirms audit | `retrospective` |

Also set `audit_type: retrospective` when `review_mode: retrospective` (dashboard alias).

## Phase 1 — merged MR gate

When `get_merge_request` returns `state: merged` or `closed`:

| User intent | Action |
|-------------|--------|
| No explicit audit request | Warn and **stop** — *"MR already merged. Pass an open MR, or confirm post-merge audit."* |
| User says *post-merge audit*, *review merged MR*, *retrospective*, or confirms after prompt | Set `review_mode: retrospective`, `audit_type: retrospective`, continue full diff review |

Record `review_mode: retrospective`, `audit_type: retrospective`, and:

```yaml
review_context:
  mode: retrospective
  lifecycle: post_merge
  merge_blocking: false
```

through Phase 5. Do not use `merge_blocking: true` on retrospective audits.

Also record: `merge_before_review: true`, `mr_state: merged`, `merged_at` when available.

## Pre-merge mode

**Goal:** Prevent defects from shipping.

Emit footer:

```yaml
review_context:
  mode: full
  lifecycle: pre_merge
  merge_blocking: true
```

| Rule | Behavior |
|------|----------|
| Recommendation | ✅ Approve · 💬 Comment · 🔴 Request changes (deterministic matrix) |
| Severity | Full rubric + **High certainty gate** (step 7a) — ~4–5 High max on dense payment MRs |
| Production readiness | Not ready when High/Critical code blockers open |
| Posting | Normal Phase 3–4 when user confirms |

## Incremental mode

**Goal:** Verify fixes, detect regressions, validate resolved-without-fix.

| Rule | Behavior |
|------|----------|
| Recommendation | Same as pre-merge + re-review block |
| Prior findings | Preserve IDs; `history` + `precision` in footer |
| Footer | `review_context: { mode: incremental, lifecycle: pre_merge, merge_blocking: true }` |
| Suppression validation | Note when prior threads were **correctly dismissed** — e.g. *"GitLab Duo division-guard threads validated — execution path does not materialize."* |
| Resolved-without-fix | Flag in re-review when thread `resolved: true` but code unchanged → `precision.false_positives_withdrawn` |

## Post-merge (retrospective) mode

**Goal:** Audit quality, process, and follow-up improvements — **not** merge gating.

### Recommendation

**Never** 🔴 Request changes as a merge gate — code is already on the target branch.

| Highest emitted severity | Display verdict | `review_metadata.recommendation` |
|--------------------------|-----------------|----------------------------------|
| Critical / High (rare — incident material only) | 📋 **Retrospective observation** | `retrospective_observation` |
| Medium / Low / None | 📋 **Retrospective observation** | `retrospective_observation` |

Prose after Decision gates:

> **Post-merge audit** — no action required unless a follow-up MR is planned.

Do **not** label retrospective audits as generic 💬 Comment — use **Retrospective observation** in the
Decision gates **Recommendation** row and narrative.

### Severity calibration

| Rule | Behavior |
|------|----------|
| Inflate High? | **No** — reserve High/Critical for genuine incident / rollback material |
| Process findings | Medium/Low — merge-before-CI, missing Jira, MR template gaps |
| Code quality | Medium/Low when implementation appears correct but tests/docs/process gap |
| Code blockers table | May show *Code blockers: None* with process-only findings elsewhere |

### Confidence

Split **technical** review quality from **traceability**:

```markdown
**Confidence:** High — full diff reviewed; payment hot path verified; pipeline timeline inspected.

**Traceability:** Medium — no linked Jira ticket (does not reduce technical review confidence).
```

| Band | Retrospective rule |
|------|-------------------|
| **High** (technical) | Full boundary reviewed; hot paths verified; pipeline/merge timeline inspected |
| Traceability note | Missing Jira/ticket → separate line — **do not cap** technical confidence to Medium |

Set `review_metadata.confidence: high` when full diff reviewed regardless of Jira.

### Production readiness

When **zero runtime code blockers** (no High/Critical on hot path):

```markdown
**Production readiness:** Ready · Operational improvements recommended
```

Not *Not ready* — code is already deployed; frame as ops/process follow-up.

Optional **Operational readiness** table (replaces qualitative-only scores when useful):

| Area | Status |
|------|--------|
| Payment correctness | ✅ |
| Resilience | ✅ |
| Security | ⚠️ |
| Deployment readiness | ⚠️ |
| Testing | ⚠️ |

### Process findings — merge-before-CI

When merge timestamp precedes pipeline success on head:

```markdown
**Repository policy risk:** Merge completed ~24s before pipeline passed on head.

**Recommendation:** Require green pipeline before merge on payment branches.
```

Record `merge_before_ci_green: true` in footer when detected (Phase 1 — compare `merged_at` vs pipeline
`finished_at` for head SHA).

See `reference/phase-1-gather.md` §Merge-before-CI timing.

### Suppression validation

In **Not raised** or **Inference**, explicitly validate prior dismissals when applicable:

> GitLab Duo division-guard threads were **correctly dismissed** — `divide(..., 6, HALF_UP)` avoids
> BigDecimal scale exception on the changed path.

Builds trust: *"I saw it · I evaluated it · I confirm the dismissal was correct."*

### Test gap finding (retrospective)

Use **Risk / Current implementation / Evidence / Gap** — don't imply implementation is wrong:

```markdown
**Risk:** Future regressions on LPC percentage edge cases.

**Current implementation:** Appears correct — no behavior regression observed in diff.

**Evidence:** `divide(..., 6, HALF_UP)` handles scale; happy path covered by manual verification in MR.

**Gap:** Parameterized edge-case tests missing — recommend table-driven cases in follow-up MR.
```

### Engineering improvements vs platform follow-ups

| Section | Content |
|---------|---------|
| **Engineering improvements** | Actionable for **this repo/MR** — tests, CI policy, parameterized matrix example |
| **Platform follow-ups** | Org-wide — Sonar exclusions, bot rule tuning — **omit** or one line under Engineering improvements with *(platform — not MR-specific)* |

Example parameterized test matrix (Engineering improvements):

```text
LPC Outstanding | charged=2 | pct=50 | expected=66.6667
LPC Partial     | charged=1 | pct=50 | expected=33.3333
...
```

### Footer fields (retrospective)

```yaml
review_mode: retrospective
audit_type: retrospective
merge_before_review: true
merge_before_ci_green: true|false
code_blockers_found: 0
process_findings: 1
suppressions_validated: 2
recommendation: retrospective_observation
```

## Decision gates (retrospective)

| Gate | Typical retrospective |
|------|-------------------------|
| Runtime correctness | ✅ when no code defects |
| Payment correctness | ✅ when payment logic verified |
| Security | ⚠️ or ✅ |
| CI / process | ⚠️ when merge-before-green |
| **Recommendation** | **📋 Retrospective observation** |

## Posting (Phase 3–4)

Retrospective audits may post summary notes; inline threads optional. Warn: *"MR is merged — comments
are for follow-up tracking, not merge gate."*

Cross-ref: `reference/executive-summary.md`, `reference/review-metrics.md`, `reference/incremental-rerun.md`.
