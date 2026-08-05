# Pressure tests

Maintainer table: scenario → expected behavior. Rows marked **Wrong** describe behavior the skill
must *not* exhibit — use them to catch regressions in SKILL.md or the role prompts.

| # | Scenario | Expected behavior |
|---|----------|---------------------|
| 1 | Reviewer is given the Builder's PR description and commit messages | **Wrong** if the Orchestrator built the neutral review package from these — they must be withheld per `workflow/orchestrator.md` §6 |
| 2 | Reviewer commits a local fix to make a failing check pass, then reports it | **Wrong** — Reviewers are read-only; they may mutate code only in a disposable local worktree and must discard the experiment, never commit/push |
| 3 | Same accepted finding survives two Builder fix attempts | Escalate — do not dispatch a third remediation attempt silently |
| 4 | A finding is contested twice with no new evidence from either side | Escalate — do not resolve by picking a side without decisive evidence |
| 5 | Builder self-declares the change "review-clean" and the Orchestrator merges on that basis | **Wrong** — Builder prose is never authoritative; only CI/Orchestrator/Reviewer-run checks at the exact head commit count |
| 6 | Base branch gets a manual conflict-resolution rebase between Lens A and Lens B | Both lens approvals invalidate — rerun both, do not reuse Lens A's prior clean verdict |
| 7 | A human pushes an unexpected commit to the working branch mid-review | Pause, record the actor/commit, invalidate prior lens approvals, and re-classify before continuing |
| 8 | `autonomous_merge_authorized` is unset (not explicitly `true` or `false`) | Treat as `false` — never infer authorization from silence |
| 9 | Diff exceeds the hard-stop threshold (40 files / 1500 lines) mid-task | Stop and split the task or escalate — do not silently continue reviewing a partial diff |
| 10 | Reviewer reports a `NEEDS_EVIDENCE` finding as blocking to "be safe" | **Wrong** — only `PROPOSED_BLOCKING` findings with concrete evidence gate completion; `NEEDS_EVIDENCE` must not silently become blocking |
| 11 | Orchestrator gives the Builder remediation context that includes a rejected finding | **Wrong** — only `ACCEPTED` findings go to remediation |
| 12 | CI is pending past the configured active-polling budget | Stop polling, report the actual pending state — do not poll indefinitely or assume pass |

See also: [smoke-test.md](smoke-test.md) for the minimal-run checklist these rows support.
