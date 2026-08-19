---
workflow_version: 1.8
phase: 2-3-gate
produces: {posting_decision: string}
consumes:
  required:
    findings: list
    review_metrics: object
    review_evidence: object
    change_identity: object
    inspection_plan: object
    incremental_baseline: object
    head_sha: string
    posting_mode: string
  optional: {}
  conditional: {}
---

# Phase 2 → 3 gate (re-run decision)

**Read this file** immediately after Phase 2 evidence finalization, before Phase 3. Evaluate **once** and branch;
Phase 3 must not re-evaluate `head_sha`.

Before any posting decision, require the successful machine validation performed by
`phase-2-evidence.md` using `pr-review/scripts/validate_review_coverage.py`. Re-check that the supplied
`review_evidence` is bound to the **current** `change_identity` and current requirements surface; never accept a
previous-run envelope merely because its findings still look relevant.

**Fail closed:**

- Invalid or stale `change_identity` / `review_evidence` → `posting_decision: skip`; render Phase 5 as
  partial/unable and state that review evidence is stale or invalid.
- `review_evidence.inspection_status: unable` → `posting_decision: skip`.
- **Any** `review_evidence.unable_to_inspect[]` entry with `mandatory: true` → `posting_decision: skip`,
  regardless of whether the envelope status is `partial` or `unable`. Mandatory unavailable coverage never
  reaches Phase 3/4.
- `inspection_status: complete` while any `review_evidence.unable_to_inspect[]` entry exists, or while any
  triggered `inspection_plan` surface is not `complete` → invalid coverage state; `posting_decision: skip`.
- `inspection_status: partial` may reach Phase 3 **only when every unavailable entry is non-mandatory**. Posting
  must not imply approval/readiness and always requires explicit Phase 3 confirmation even when the normal
  recommendation matrix would otherwise auto-skip a prompt.
- A pending mandatory surface in the finalized `inspection_plan` is equivalent to unavailable evidence: do not
  treat it as clean and do not post a complete review.

When the gate **blocks posting** (invalid/stale evidence, mandatory unavailable surface, unchanged `head_sha`,
`chat-only`, user Hold/Cancel), **skip Phase 3 and Phase 4** and proceed to **Phase 5** for the chat-only
executive summary.

Compare current `diff_refs.head_sha` to the baseline `head_sha` from Phase 1 step 3 (prior
`<!-- cursor-pr-review -->` summary, if any).

| Situation | Next step |
|-----------|-----------|
| Invalid/stale `review_evidence` or `change_identity` | **Stop posting path** — Phase 5 partial/unable summary; explain evidence invalidation |
| Mandatory triggered inspection surface unavailable/pending | **Stop posting path** — Phase 5 partial/unable summary with `unable_to_inspect` |
| Partial evidence with only non-mandatory unavailable surfaces | Phase 3 confirmation required; any post must state partial coverage and must not imply approval/readiness |
| `head_sha` unchanged since prior review | **Stop posting path** — render chat summary + Phase 5 executive summary; **skip Phase 3 AND Phase 4**: *"No new commits since last review."* |
| New commits, new findings | Phase 3 → post **re-review summary**; inline threads only for new `file:line` not in prior threads/summary |
| New commits, no new findings | Phase 3 → post short re-review summary — prior issues resolved or unchanged |
| **> 30 commits since baseline** | **Warn** (*"prior review significantly outdated — N commits"*) and **offer full re-review** before incremental (see `reference/incremental-rerun.md`) |
| User chose Hold / Cancel (earlier) | Chat review only; do not post |
| `chat-only` posting mode | Skip Phase 3 and Phase 4; proceed to Phase 5 if review output not yet complete |
| Prior `head_sha` missing from history | Full re-review (squash/force-push — `reference/incremental-rerun.md`) |
| First review (no prior baseline) | Continue to Phase 3 per posting mode, subject to evidence gates above |

When incremental, load `reference/incremental-rerun.md` for dedupe rules (snippet hash, resolved
threads, squash caveat). Use the re-review template from `reference/comment-templates.md` when posting.

Record `posting_decision`:

- `posting_decision: post` — the gate allows proceeding to Phase 3/4. Read **`workflow/posting.md`**
  next. (Phase 3 may still end without anything posted — e.g. the user chooses Hold — but that's
  `posting.md`'s own internal confirmation logic, not a second gate here.)
- `posting_decision: skip` — the "Stop posting path" / invalid evidence / mandatory unavailable surface /
  `chat-only` / Hold-Cancel-earlier / draft rows above. Read **`workflow/phase-5.md`** directly; Phase 3
  and Phase 4 never run this pass.
