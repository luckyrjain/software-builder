# Incremental re-review (dedupe logic)

Load this when Phase 1 step 3 recorded an incremental baseline (a prior summary note whose body starts
with `<!-- cursor-pr-review -->` plus a recorded `head_sha`). The re-run **decision table** is in
`workflow/phase-2-3-gate.md` — evaluate there once before Phase 3; dedupe rules live here.

**Cross-session detection:** Phase 1 step 3 scans **all** MR notes and discussion threads — not only
the current agent session — for prior review markers (`<!-- cursor-pr-review -->`, `review_metadata`
YAML footer, `**Reviewed:**` timestamp lines, `review_hash`). When any marker is found on the MR,
enter incremental mode and dedupe against prior findings even if this is a fresh Claude Code / Cursor
session.

Review only commits/files **after** the baseline SHA (`get_merge_request_commits`).

**Context cache:** reuse immutable repo context from the first Phase 1 on this `project_id` —
see `reference/session-context-cache.md`. Invalidate only when a cached file is in the incremental diff.

**Baseline staleness:** if `get_merge_request_commits` shows **> 30 commits** since the recorded
`head_sha` baseline, warn before proceeding incrementally — *"Prior review is significantly outdated (N
commits). Consider a full re-review instead of incremental."* — and offer the full re-review.

## Snippet hash (exact definition)

A **snippet hash** identifies a finding's anchor line across revisions. Compute it deterministically:

1. Take the changed line's content from the diff (without the leading `+`/`-`/space).
2. **Lowercase** it.
3. **Collapse all internal whitespace** (runs of spaces/tabs) to a **single space**, and strip leading/trailing whitespace.
4. Take the **first 80 characters** of the result (or the whole string if shorter).

Two findings match when they share the same `file:line` **and** the same snippet hash. Use this exact
definition everywhere dedupe is described — do not vary the casing or whitespace handling.

## Finding ID preservation (`PRR-{CAT}-{NNN}`)

When prior `review_metadata.findings[]` includes structured entries:

1. **Unchanged finding** — same primary `evidence[0]` (or `location`) **and** same snippet hash →
   **preserve** the prior `id` (e.g. `PRR-DATA-002` stays `PRR-DATA-002`); set `status: open`.
2. **Fixed finding** — problematic code gone or thread resolved → mark prior ID `status: fixed`; list
   under *Resolved since last review*; do not re-emit unless regressed.
3. **New finding** — no match in prior array → assign the next unused `PRR-{CAT}-{NNN}` for that
   **category only** (e.g. prior highest `PRR-SEC-003` → new security finding is `PRR-SEC-004`).
4. **Regressed finding** — same defect after fix → reuse original ID if known; note regression in
   summary; set `status: open`.

**Legacy IDs:** Prior flat `PRR-001` style IDs are preserved on match — do not migrate to
category-prefixed IDs mid-MR. New findings on the same MR after migration use `PRR-{CAT}-{NNN}`.

Emit the updated structured `findings[]` array in Phase 5 `review_metadata` — IDs are stable across
re-reviews for tracking dashboards and inline comment cross-reference.

## Snippet-hash dedupe (by posting mode)

Match new findings against the prior review so the same issue is never posted twice. Apply **semantic
dedupe** in addition to hash/line matching — skip a new finding when an existing open thread or prior
summary item already covers the **same location, root cause, call stack, or API misuse pattern** (see
`workflow/phase-2.md` §Finding dedupe and §Root cause grouping). One pattern → one comment/thread, not
one per occurrence.

- **`full` mode** — match new findings against prior **inline threads** by `file:line` + snippet hash.
  Same `file:line` with a **different** hash is a **new** finding (the line changed).
  **Line-shift fallback:** before concluding a prior finding with no exact `file:line` match is
  resolved, search the **same file** within a **±20 line window** of the prior line for a diff line
  whose snippet hash matches. A match there means the finding's anchor line shifted (e.g. an import or
  unrelated line was added/removed above it) — **preserve the prior ID and evidence**, update
  `file:line` to the new location, keep `status: open`. Only treat a finding as resolved when no
  matching snippet hash is found anywhere in the file (or the file was deleted/renamed — see below). A
  finding whose surrounding code changed enough that its exact snippet hash no longer appears anywhere
  is correctly treated as resolved, not lost — this fallback only recovers **unchanged code that moved**.
- **`summary-only` / `general-only`** — the prior **summary note** lists only `file:line` (no snippet
  text/hash), so the snippet hash is **not recoverable** from the note alone. **Fallback: dedupe on
  `file:line` only.** To recover the prior lines' snippet hashes you must reconstruct the diff **at the
  baseline `head_sha`** — note that `get_merge_request_diffs` returns the **current** MR diff (it is
  not revision-scoped), so use one of, in order:
  1. **MR diff-versions API**, if the server exposes it: `list_merge_request_versions` → pick the
     version whose `head_commit_sha` matches the baseline, then `get_merge_request_version`
     (`version_id`, `unidiff: true`) for that version's diff.
  2. **Ref comparison at the baseline SHA:** `get_branch_diffs` (or per-commit `get_commit_diff` over
     the `list_commits` range up to the baseline) to rebuild the baseline file diffs.
  3. Otherwise accept the **`file:line`-only** fallback — a changed line at the same `file:line` may be
     treated as the same finding; note this limitation in the re-review summary when it matters.

**Removed (`-`) lines:** if a finding was anchored to a removed line and that line no longer appears
anywhere in the new diff, treat it as **resolved**. If the same removal is still present (e.g.
re-introduced then removed again), use the removed-line content as the snippet.

## Resolved findings

When computing **feedback learning** signals (`reference/review-feedback-learning.md`), use resolution
timing and category from resolved vs open threads — not just dedupe.

- **`full` mode** — when reading `mr_discussions`, record each inline thread's `resolved` flag. Skip
  re-posting findings that match a **resolved** thread (`file:line` + snippet hash). If the same issue
  reappears after resolution, treat it as **new** and note *"Previously resolved — regressed or
  reintroduced"* in the re-review summary. For unresolved threads, dedupe as above; list a finding in
  *Resolved since last review* only when the diff shows the fix.

**Resolved-without-fix:** when a thread is `resolved: true` but code at the same `file:line` is
**unchanged**, increment `precision.false_positives_withdrawn`. On retrospective audits, validate
**correct** dismissals (e.g. GitLab Duo warnings) → increment `suppressions_validated` in footer and
note in **Not raised** — *"Correctly dismissed — execution path does not materialize."*

- **`summary-only` / `general-only`** — a prior finding is **resolved** when the diff no longer
  contains the problematic code at the same `file:line` (line changed or deleted). If the file was
  deleted or renamed, all its prior findings are resolved.

**Phase 1 step 3** may also parse the prior summary's **`review_metadata` YAML footer** (when present)
for baseline statistics, **`findings[]`** (ID + evidence matching), and **`review_hash`** — the
`- head_sha:` line remains the authoritative baseline SHA fallback.

**Auto-resolve:** the skill does **not** call a "resolve thread" API — thread resolution is the
author's action after addressing a finding. The re-review summary's *Resolved since last review*
section signals which threads the author can now resolve manually.

## Posting

- Post the re-review summary template from `reference/comment-templates.md`; never re-post identical
  comments.
- **Squash / force-push / rebase caveat:** if the recorded `head_sha` is absent from
  `get_merge_request_commits` (author rebased or squashed), the incremental baseline is invalid — fall
  back to a full review and note *"Prior SHA not found in commit history — full re-review performed."*
  A **force-push or rebase even without squash** rewrites every commit SHA while keeping identical
  logical changes, so the old SHA goes missing and a full re-review results. **This is expected
  behavior, not an error** — don't report it as a failure.

## Re-review output requirements (Phase 5)

When incremental baseline is recorded, the chat summary and posted note **must** include these blocks
(in order) — see `reference/comment-templates.md` re-review template:

1. **Baseline → Head** — SHAs, commit count, **Review lens** (persona)
2. **Incremental scope** — file count + `scope_category` + `scope_detail`
3. **Review scale** — commits, files, lines changed, reviewed fraction
4. **Statistics table** — Previous / Resolved / Remaining / New findings
5. **Regression check** — ✅ no reintroduction, or ❌ with `file:line`
6. **Coverage** — `changed_files_reviewed/total`, hunks, truncated, skipped
7. **Review status** — completed normally vs stop-search triggered (with count/reason)
8. **Review findings** — severity table with **ID**, **Conf**, **Evidence** columns (or **No actionable findings**)
9. **Engineering improvements** — repo maturity items (omit when empty; not MR defects)
10. **Resolved since last review** — explicit list (include metadata fixes when applied)
11. **Still open / new** — or *"No new actionable findings in incremental diff"*
12. **Executive Summary** — Evidence checklist, confidence line, Inference (re-review), gate matrix,
    **Reason**, review cost, **Blocking Issues: None** or Major/Must fix, P1/P2/P3 nice-to-haves
13. **Closing loop** — one paragraph suitable for EMs (approval pending CI/policies)
14. **`review_metadata` YAML footer** — machine-readable block with `review_hash`, structured
    `findings[]`, and v2 platform analytics (`history`, `precision`, `review_quality`, stub
    `repository_health`) for dashboards and future re-reviews

Do **not** re-review the full MR boundary unless baseline is invalid or user requested full re-review.
An empty incremental findings pass is **correct** — output **No actionable findings** (or *No new
actionable findings in incremental diff* in the re-review block); never invent feedback.

## Parsing prior metadata (v2 `history`)

When Phase 1 step 3 finds a prior `review_metadata` YAML footer, extract fields for incremental dedupe
**and** platform analytics blocks emitted in Phase 5.

**Scan order:** newest note first for `prior_review`; oldest parseable note for `first_review`.

| Prior field | Use in current review |
|-------------|----------------------|
| `head_sha` | Baseline SHA (authoritative over prose `- head_sha:` line) |
| `findings[]` | ID preservation, `precision.prior_total`, resolved/fixed diff |
| `findings_stats` | Fallback counts when `findings[]` sparse |
| `finished`, `recommendation` | Populate `history.first_review` / `history.prior_review` snapshots |
| `history.approval_iteration` | Increment → current `approval_iteration` |
| `review_hash` | Duplicate-review detection |

**Compute `history` for Phase 5 footer:**

1. **`approval_iteration`** — count of MR notes whose body contains parseable `review_metadata` + 1.
2. **`first_review`** — snapshot from earliest such note: `head_sha`, `finished`, `findings_count`
   (length of `findings[]`), `highest_severity`, `recommendation`.
3. **`prior_review`** — snapshot from the note immediately before current review (latest prior note).
4. **`regressions[]`** — for each prior finding with `status: fixed`, if problematic code reappears at
   same evidence anchor, append `{ id, location, prior_status: fixed, note }`; set
   `precision.regression_count` and `regression_rate`.

**Compute `precision`:**

| Field | Rule |
|-------|------|
| `prior_total` | Count prior `findings[]` entries (exclude `status: suppressed`) |
| `prior_resolved` | Prior entries now `fixed` or absent from incremental diff |
| `prior_resolved_pct` | `(prior_resolved / prior_total) × 100` when `prior_total > 0` |
| `false_positives_withdrawn` | Prior finding resolved via thread with no matching code fix (feedback learning) |
| `candidates`, `emitted`, `emission_rate` | From Phase 2 `review_metrics` |

**First review on MR:** omit `history`; set `precision.prior_*` and `regression_*` to zero.

Normative schema: [review-metadata-schema.md](../../docs/skill-framework/shared/review-metadata-schema.md).
