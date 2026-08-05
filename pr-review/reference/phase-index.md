# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Phase 2 emits findings
only through `finding-pipeline.md`. Re-review skips Inputs and Phase 0 unless **MCP reconnected** or
**target branch / MR target changed** (re-resolve in Inputs when the review target changes).

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | `workflow/inputs.md` | `{ project_id, merge_request_iid }` |
| **Phase 0** | `workflow/phase-0.md` | `posting_mode`, `jira_write_available` |
| **Phase 1** | `workflow/phase-1.md` | review boundary, `capability_profile`, baseline, CI, Jira AC |
| **Phase 2** | `workflow/phase-2.md` | findings, `review_metrics`, root-cause groups |
| **Phase 2→3 gate** | `workflow/phase-2-3-gate.md` | continue / skip posting / stop |
| **Phase 3–4** | `workflow/posting.md` | posted threads + summary note |
| **Phase 5** | `workflow/phase-5.md` | executive summary (final) |

> **Note:** Phases 3 and 4 share a single workflow file (`posting.md`) rather than separate
> `phase-3.md` / `phase-4.md` files. This is intentional — Phase 3 (confirmation gate) and Phase 4
> (post comments) are tightly coupled: both depend on `posting_mode` and execute as a single
> confirm-then-post sequence. Splitting would force artificial state passing between files with no
> independent utility. The 2→3 gate is separate because it has distinct stop/skip semantics.

Reference loads: [lazy-load-index.md](lazy-load-index.md). Report layout: [report-template.md](../report-template.md). Quick paths:

| Scenario | Phases |
|----------|--------|
| First review | Inputs → 0 → 1 → 2 → 2→3 gate → 3–4 → 5 |
| Re-review | 1 → 2 → **2→3 gate** → 3–4 → 5 *(Inputs + Phase 0 if MCP reconnected or target branch/MR changed)* |
| Partial review (stop mid Phase 2) | 1 → 2 *(partial)* → 5 — skip 3–4 unless user asks to post |
| Phase 3 cancel before Phase 4 | … → 3 confirm → user cancel → 5 chat-only |
| List MRs only | Inputs → stop |
| Draft MR | Full path; draft gate in `workflow/posting.md` |
| Persona review (SRE, Security, …) | Same path; persona in Phase 2 |
| Post-merge audit | User confirms on `state: merged` → `review_mode: retrospective` — full path; see [review-modes.md](review-modes.md) |

Tool routing: GitLab MR → `/pr-review`; local diff → `/review-bugbot`; security local → `/review-security`;
GitHub PR → `/review-bugbot` / `gh pr view`. See [SETUP.md](../SETUP.md).
