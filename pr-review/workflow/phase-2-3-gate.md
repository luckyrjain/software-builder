---
workflow_version: 1.4
phase: 2-3-gate
produces:
  - posting_decision
consumes:
  - findings
  - review_metrics
  - incremental_baseline
  - head_sha
  - posting_mode
---

# Phase 2 → 3 gate (re-run decision)

**Read this file** immediately after Phase 2, before Phase 3. Evaluate **once** and branch; Phase 3 must
not re-evaluate `head_sha`.

When the gate **blocks posting** (unchanged `head_sha`, `chat-only`, user Hold/Cancel), **skip Phase 3
and Phase 4** and proceed to **Phase 5** for the chat-only executive summary.

Compare current `diff_refs.head_sha` to the baseline `head_sha` from Phase 1 step 3 (prior
`<!-- cursor-pr-review -->` summary, if any).

| Situation | Next step |
|-----------|-----------|
| `head_sha` unchanged since prior review | **Stop posting path** — render chat summary + Phase 5 executive summary; **skip Phase 3 AND Phase 4**: *"No new commits since last review."* |
| New commits, new findings | Phase 3 → post **re-review summary**; inline threads only for new `file:line` not in prior threads/summary |
| New commits, no new findings | Phase 3 → post short re-review summary — prior issues resolved or unchanged |
| **> 30 commits since baseline** | **Warn** (*"prior review significantly outdated — N commits"*) and **offer full re-review** before incremental (see `reference/incremental-rerun.md`) |
| User chose Hold / Cancel (earlier) | Chat review only; do not post |
| `chat-only` posting mode | Skip Phase 3 and Phase 4; proceed to Phase 5 if review output not yet complete |
| Prior `head_sha` missing from history | Full re-review (squash/force-push — `reference/incremental-rerun.md`) |
| First review (no prior baseline) | Continue to Phase 3 per posting mode |

When incremental, load `reference/incremental-rerun.md` for dedupe rules (snippet hash, resolved
threads, squash caveat). Use the re-review template from `reference/comment-templates.md` when posting.

If the gate allows posting, **read `workflow/posting.md`** for Phase 3 and Phase 4.

If the gate skips posting but review is complete, **read `workflow/phase-5.md`**.
