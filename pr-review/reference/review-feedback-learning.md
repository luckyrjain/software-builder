# Review feedback learning (MR history)

Load in **Phase 1 step 3** when **any** prior `<!-- cursor-pr-review -->` summary or bot inline thread
exists on this MR. Apply signals in **Phase 2** (finding frequency) and **Phase 5** (Confidence).
There is no separate persistence — learn only from **this MR's** GitLab history (notes, discussions,
commits).

## Optional workspace cache (cross-MR)

When the target repo has `.cursor/review-feedback-cache.yaml` at workspace root, load it in **Phase 1
step 3** **before** MR-only signals. Merge cache categories with MR history — MR signals take precedence
on conflict.

```yaml
# .cursor/review-feedback-cache.yaml (optional)
schema_version: 1
ignored_categories:   # categories authors consistently dismiss org-wide
  - STYLE
team_responsive: true
notes: "Payments squad fixes blocking findings within 1 commit on average"
```

Update the cache only when the user explicitly asks to remember a pattern across MRs — never auto-write.

## Goal

Human reviewers adapt: they trust teams that fix things quickly and stop nagging about categories
authors consistently ignore. Mirror that without a database.

## Phase 1 — collect signals

When scanning prior bot feedback (all `<!-- cursor-pr-review -->` notes, oldest → newest, plus
`mr_discussions` inline threads authored by the bot / marked in prior summaries):

### Resolved quickly (increases confidence)

A prior bot finding counts as **resolved quickly** when **all** apply:

1. The finding was **Critical or High** in a prior bot summary, **or** an inline thread with blocking severity.
2. It is **resolved** now — inline `resolved: true`, or absent from the diff at the same `file:line`, or listed under *Resolved since last review* on a subsequent bot pass.
3. **Turnaround ≤ 2 commits** on this MR between the review note's `head_sha` (or thread created_at) and the commit that fixed it (infer from `get_merge_request_commits` ordering, or from the next bot re-review showing resolved).

Record: `resolved_quickly: N`, `resolved_total_blocking: M`, `quick_resolution_rate = N/M` (when M > 0).

**Fast-fix streak:** if the **last 2+ bot review cycles** on this MR each show ≥80% of blocking items
resolved before the next bot pass, set `team_responsive: true`.

### Consistently ignored (reduces frequency)

A **category** is **ignored** on this MR when **either**:

| Signal | Threshold |
|--------|-----------|
| **Repeated without fix** | Same category raised in **≥2** prior bot summaries and still **open** (unresolved thread or same issue in latest diff) |
| **Stale threads** | **≥2** open bot threads in the same category older than **one review cycle** (no resolution, no author reply addressing it) |
| **Re-raised and dropped** | Bot re-posted the same category in a re-review summary **≥2 times** and the author merged or pushed without fixing (still open at current `head_sha`) |

**Categories** (match finding prefixes / Overall themes):

| Category key | Matches |
|--------------|---------|
| `security` | Critical/High security, secrets, auth, injection |
| `test` | `test ·` prefix, §8 gaps |
| `arch` | `arch ·` prefix, §16 |
| `rollback` | `rollback ·` prefix, §17 |
| `observability` | §9 logging/metrics/tracing gaps |
| `performance` | §4 DB/cache/queue/hot-path |
| `style-nit` | Nits, naming, formatting, minor readability |
| `scope` | Scope creep, MR size, unrelated files |
| `process` | MR template, missing ticket link, CODEOWNERS (non-security) |

Record: `ignored_categories: [ { key, evidence, cycles_open } ]`.

**Never treat as ignorable:** `security` findings at Critical; secrets; auth bypass; injection; unmet AC
on linked ticket.

## Phase 2 — apply learning

At **pipeline step 8** (`reference/finding-pipeline.md`) — after contextual severity, before value filter:

### Increase responsiveness (do not skip real defects)

When `team_responsive: true` or `quick_resolution_rate ≥ 0.8` (with M ≥ 2):

- Note in chat (one line): *"ℹ️ **Feedback learning:** this team resolves prior bot blocking findings quickly — confidence boosted."*
- Phase 5 **Confidence** may upgrade one tier (Medium→High) when diff coverage is otherwise complete.
- Do **not** skip new Critical/High defects — responsiveness earns trust, not a free pass.

### Reduce frequency for ignored categories

For each category in `ignored_categories`:

| Prior finding severity in ignored category | Action |
|------------------------------------------|--------|
| **Medium / Low / nit** | **Omit** new findings in that category unless the defect is **materially worse** than prior ones (new production path, higher blast radius, or Critical hard floor would apply). Mention once in chat: *"Feedback learning: `{category}` often ignored on this MR — omitted N low-value repeats."* |
| **High** (non-security) | **Downgrade to chat-only** (no post, no table row) unless regression or new hot path. |
| **Critical / security / AC** | **Always report** — never suppress |

When downgrading or omitting, list suppressed count in chat only — increment
`review_metrics.suppressed.feedback`. **Never** increment when a non-negotiable check would apply —
emit instead (`reference/finding-gates.md#non-negotiable-checks-pipeline-step-6`).

### First review on MR

On **first review**, do **not** apply feedback learning adjustments — use rubric baselines in
`reference/severity-rubric.md`. No prior bot history → skip this file's apply step; no learning signals.

## Phase 5 — Confidence field

Adjust **Confidence** in the executive summary:

| Signal | Confidence adjustment |
|--------|----------------------|
| `team_responsive: true` | +1 tier if not already High |
| `quick_resolution_rate ≥ 0.8` (M ≥ 2) | note *"team fixes bot findings quickly"* in Confidence evidence |
| `ignored_categories` non-empty and suppressions applied | note *"adapted: reduced `{keys}` frequency"*; do not lower Confidence solely for suppressing noise |
| Stop-search + ignored categories | Medium at most |

Example Confidence line: *High — full diff; team resolved 4/4 prior blocking items within 1 commit cycle.*

## Limits

- Default learning is **per MR** — bot-authored summaries + inline threads on this MR only.
- **Optional cross-MR:** `.cursor/review-feedback-cache.yaml` at repo root (user-maintained; load in Phase 1
  step 3). Never auto-write the cache.
- Human reviewer threads are informative but **bot-authored** feedback drives the counters.
- When uncertain whether a category was ignored vs deprioritised by the author intentionally, **prefer omit** over repeat (review principle).
