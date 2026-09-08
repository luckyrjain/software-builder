# Phase 1 — Gather heuristics (CI, coverage, security scans, merge train)

Load this when running Phase 1 (`workflow/phase-1.md`). The workflow file keeps the step list; the
detailed rules for pipeline analysis live here.

## MR metadata sub-checks (Phase 1 step 1)

Run these from `get_merge_request` after the state check and size summary, before diff pagination:

- **Early 200-file cap warning (before any diff pagination).** If `changes_count` > **200**, warn and
  ask before fetching diffs — e.g. *"This MR has 312 changed files — this will hit the 200-file review
  cap. Proceed with full pagination, or narrow scope first?"* Do not start step 2 until the user
  responds (proceed / narrow scope / explicit paths). This is cheaper than discovering the cap
  mid-pagination.
- **MR template compliance.** From the MR `description` (and, if exposed, the project's
  `.gitlab/merge_request_templates/` — see step 7), detect whether a template was used. If the
  description is blank, the unedited default, or has expected sections left empty (e.g. *"Testing
  done"*, *"Rollback plan"*), note which sections appear unfilled (Low/Medium per
  `review-checklist.md` §11). If filled, say so briefly.
- **Fork check.** If `source_project_id ≠ target_project_id`, note it and treat review as **diff-only**
  via MCP — do not `git show` fork SHAs from the target checkout. If the user provides a fork remote
  URL, you may fetch that branch; otherwise state the limitation in the summary.

## CI failure analysis (required vs optional, related vs unrelated)

The pipeline heuristics in this section (CI failure analysis, security scans, coverage, merge train)
all key off the pipeline/job data from `get_merge_request_pipelines` (or equivalent) for the pipeline
whose `sha` matches `diff_refs.head_sha`. Classify absence using the pipeline taxonomy in
`reference/executive-summary.md`:

1. **❓ not configured** — no CI config file in repo (`.gitlab-ci.yml`, `.github/workflows`, etc.)
2. **❓ expected but missing** — CI config exists but no pipeline for `head_sha` (webhook/trigger gap)
3. **⏳ pending/running** — pipeline exists but not finished
4. **❓ unavailable** — MCP cannot fetch pipeline data

Do not use a generic *"no pipeline for head commit"* without one of the above labels. Cite the latest
MR pipeline only as labelled secondary context when it differs from head. Record status including
`running` / `pending` / `waiting_for_resource` — not just green/failed.

### Pipeline SHA explicitness (required in Phase 5 Evidence or Process blockers)

Always distinguish **head pipeline state** vs **last successful pipeline** when they differ:

```markdown
**Pipeline on head (`abc1234`):** ❓ no pipeline ran for this SHA
**Last successful pipeline:** `def5678` (2026-06-28, not head) — ✅ success
```

| Situation | Wording |
|-----------|---------|
| No pipeline for `head_sha` | *Pipeline on head (`<short_sha>`): ❓ no pipeline ran* — not "failed" |
| Pipeline failed on head | *Pipeline on head (`<short_sha>`): ❌ failed* — cite failing job |
| Pipeline success on head | *Pipeline on head: ✅ success* |
| Success on older SHA only | *Last successful pipeline: `<sha>` — not current head* |

Record `head_sha`, `pipeline_head_sha`, and `last_successful_pipeline_sha` in `review_metrics` when
available for footer / dashboards.

When the head pipeline has failed jobs, record the failing job names, then:

1. **Required vs optional.** Check whether each failing job is **required** (blocks merge,
   `allow_failure: false` — the GitLab default) or **optional** (`allow_failure: true`). A failing
   optional job does **not** affect the verdict.
2. **Flaky jobs.** If a flaky-list config exists at repo root (`.flaky-tests`, `.flaky-jobs`, or a
   similar file), load it. Treat a failing job whose name matches an entry as **"flaky —
   non-blocking unless it fails consistently"**: do **not** weight it like a genuinely related failure.
   Only escalate a flaky match if the same job is failing across multiple recent pipelines (consistent
   failure, not a one-off). Note the flaky classification explicitly in the verdict.
3. **Related vs unrelated.** Compare each remaining failing **required** job name against the changed
   file paths (the Phase 1 step 2 boundary). If the job name (e.g. `deploy-to-staging`,
   `integration-test-payments`) is unrelated to any changed path, label it *"likely unrelated"* and
   say why.
4. Only treat a required failure as **blocking** (→ Request Changes) when it plausibly relates to the
   changed code and is not classified flaky. **State the reasoning explicitly** — never silently
   downgrade a CI failure.

This analysis feeds the Phase 5 executive summary (Recommendation).

## Security scan artifacts

If any job name matches `sast`, `dependency_scanning`, `secret_detection`, `container_scanning`, or
`dast`, note whether it passed or failed. For MRs touching auth, payments, or dependency files, flag a
failing or missing security scan as **Medium** in the Phase 2 findings.

## Code coverage

Only act on coverage when the pipeline/MCP **actually exposes before/after percentages** (e.g. a
coverage job that reports the base-branch value and the MR value, or a coverage MCP field):

- **Both numbers available** and the MR drops coverage by **> 5%** from the base value → flag **Medium**.
- **Only the MR's own percentage** (no base value) or **no percentage** exposed → do **not** invent a
  delta. Note *"coverage delta unverifiable — no base/after percentages exposed by the pipeline"* and
  move on. Never fabricate before/after numbers.

## Merge train

If `get_merge_request` returned `merge_trains_enabled: true` for the project, note the MR's merge train
status. Do not Approve an MR that is not in the merge train queue when the target branch requires it —
record `merge_train_status` in the Phase 5 executive summary.

**Active train disruption warning (Phase 5):** when `merge_train_status` is `fresh`, `stale`, or
`merging`, the MR is on the merge train (queued or actively merging). Show:

> ⚠️ **Merge train:** This MR is currently on a merge train (`<status>`). Applying fixes (new commits)
> or changing approval states may remove it from the queue and derail the train.

This warns reviewers and authors before they push suggested fixes or toggle approvals mid-train.

## Merge-before-CI timing (retrospective audits)

When `review_mode: retrospective` or MR `state: merged`, compare merge time vs head pipeline success:

1. Read MR `merged_at` (or merge event timestamp when available).
2. Read pipeline for `diff_refs.head_sha` — pipeline `finished_at` when status is **success**.
3. If merge occurred **before** pipeline success on that SHA → set `merge_before_ci_green: true` in
   `review_metrics` and footer.

Emit as **process finding** (Medium/Low), not a code blocker:

```markdown
**Repository policy risk:** Merge completed ~{N}s before pipeline passed on head.

**Recommendation:** Require green pipeline before merge on payment branches.
```

See `reference/review-modes.md` §Post-merge.
