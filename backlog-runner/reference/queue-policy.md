# Queue policy (normative)

**The one piece of new logic in this skill.** Everything about implementing a task is
loop-task-implementer's own. This file defines the session-level concerns loop-task-implementer's own
`state-schema.yaml` explicitly doesn't cover (it's a *per-task* schema — see its own header comment) and
resolves one real ambiguity in loop-task-implementer's own documented workflow, rather than inheriting it
silently.

## 1. Session-level state (new — extends, never modifies, the per-task schema)

loop-task-implementer's `state-schema.yaml` is per-task; this skill tracks its own session object across
the whole run, alongside — not inside — each task's own state:

```yaml
backlog_run:
  started_at: "<ISO-8601>"
  tracker_query: "<JQL or GitHub Issues search>"
  max_tasks_per_run: <int>
  deadline: "<ISO-8601>" | null
  session_token_budget: <int> | null
  consumed_tokens: 0
  tasks:
    - task_id: "<from tracker>"
      dependencies: []          # other task_ids in this same pulled batch, if declared
      outcome: PENDING | SKIPPED_EXISTING | DEFERRED | HUMAN_ACTION_REQUIRED | ESCALATED
      pull_request_url: null    # set when loop-task-implementer opens one
      escalation_ref: null      # loop-task-implementer's own §19 escalation report, when ESCALATED
  stopped_reason: null          # MAX_TASKS_REACHED | DEADLINE_REACHED | TOKEN_BUDGET_EXHAUSTED | CONSECUTIVE_ESCALATION_BREAKER | QUEUE_EXHAUSTED
```

## 2. Queue pull and ordering

1. Run `tracker_query` against the configured issue tracker; take results up to `max_tasks_per_run` —
   never more, even if the query returns a larger backlog.
2. **Skip tickets that already have an existing branch/PR (open or merged)** — reuse loop-task-implementer's own
   existing-branch/PR check ([orchestrator.md § 2 Task selection](../../loop-task-implementer/workflow/orchestrator.md#2-task-selection):
   *"If no shared state exists yet for this task, check for an existing branch/PR matching its ID before
   treating it as unstarted — a second Orchestrator invocation against the same repo must not duplicate
   work"*) rather than building a second tracking mechanism. Record these as `outcome: SKIPPED_EXISTING`.
3. **Topologically order the remaining batch by declared dependencies** — this is genuinely new:
   loop-task-implementer's own task-selection logic checks *one* task's dependencies at pick time, it
   never orders a whole pulled batch. If ticket B declares a dependency on ticket A and both are in this
   run's batch, attempt A first.
4. **A ticket's dependency is satisfied — checked directly against the dependency's own current state,
   never only "this run's batch," and never assumed from mere existence of a branch/PR/closed ticket
   without checking it actually succeeded** — this skill runs nightly, and a dependency reaching
   `HUMAN_ACTION_REQUIRED` on a *prior* night (or done by a human entirely outside this skill) must still
   count as satisfied tonight, or a dependent ticket would stay `DEFERRED` forever the moment its
   prerequisite's ticket ages out of `tracker_query` (once a PR exists, or once the ticket is closed, it
   commonly no longer matches a "ready for dev"-style query — it can never again appear "in this run's
   batch"). Look up the dependency ticket's own current state directly — **regardless of whether this
   skill ever pulled it itself** — and treat it as satisfied when **any** of:
   - It's in this run's batch and reached `HUMAN_ACTION_REQUIRED` this run, **or**
   - It has an existing **open or merged** branch/PR (whether from a prior run of this skill or opened by
     a human directly — the check is the same one rule 2 uses, per-ticket-ID, and doesn't care who opened
     it; `SKIPPED_EXISTING` **is** satisfaction evidence, not a reason to keep deferring the dependent —
     and a human merging a prior run's PR directly, without also separately closing the tracker ticket, is
     satisfaction too, exactly as §4's outcome table's `MERGED` row already anticipates), **or**
   - The dependency ticket itself is closed **as done/resolved/merged** in the tracker (the strongest
     signal — query the tracker for the dependency ticket's own current state when it's not in this run's
     batch at all, don't assume "not pulled" means "not done").

   **None of these count when the outcome was unsuccessful** — a PR that was opened and later closed
   *without* merging (abandoned/rejected), or a ticket closed as won't-fix/invalid/duplicate/cancelled,
   is **not** satisfaction evidence; treat that dependency as unresolved (`DEFERRED`, same as no evidence
   at all) rather than building on top of work that didn't land. Checking the tracker's own
   resolution/closure reason, not just "is it closed," is required here — a bare "closed" boolean is not
   enough to distinguish the two. Concretely: Jira exposes this as its native `resolution` field (`Done`/
   `Fixed` vs. `Won't Fix`/`Duplicate`/`Invalid`); GitHub Issues has no native resolution field — use the
   `state_reason` API field (`completed` vs. `not_planned`) or, if absent, a `wontfix`/`duplicate`/`invalid`
   label convention. **If neither signal is present** (an older or loosely-maintained tracker with a closed
   issue and no `state_reason`/label), this degrades to "closure reason unknown," same as
   [SETUP.md](../SETUP.md)'s unrecognized-dependency-field precedent — treat the ticket's closure as *not*
   satisfaction evidence and fall through to `DEFERRED` rather than guessing done vs. abandoned; an
   existing open-or-merged PR (bullet 2) remains available as an independent, unambiguous satisfaction
   path even when the ticket's own closure reason is unreadable.

   A dependency satisfying none of the successful-outcome bullets is `DEFERRED` — do not attempt its
   dependent this run, record why, and re-check next run (this is the one case that legitimately needs
   another night).

## 3. Invoking loop-task-implementer — one task per invocation

**Each pulled ticket is a separate loop-task-implementer invocation, sequential, not a single "work
through this list" request to loop-task-implementer itself.** loop-task-implementer *does* have its own
documented multi-task natural-language pattern ("work through these tasks one by one") — this skill
deliberately does not use it, because the queue-ordering/skip-existing/dependency logic in §2 and the
session-level stop-condition logic in §5 need to run **between** tasks, which requires this skill's own
workflow to be the one deciding what happens next, not loop-task-implementer's internal continuation.
Pass each ticket's title/description/acceptance-criteria as `repo_context`-scoped task input, exactly as
if a human had pasted that ticket's text and said "implement this" — no different phrasing, no trailing
directives invented (same lesson as `pr-gatekeeper`/`incident-triage-agent`: don't invent unverified
invocation grammar).

**`autonomous_merge_authorized` is never passed as `true`** — every invocation runs with it unset/`false`,
hardcoded. loop-task-implementer's own rule already defaults it to `false` and explicitly refuses to
accept it from repository-file prose; this skill simply never supplies the caller-side override either.

**Known interaction risk this skill cannot fully resolve from documentation alone:**
loop-task-implementer's own `orchestrator.md` §2 gates task selection partly on *"its declared
dependencies are complete"* — but loop-task-implementer's own `state-schema.yaml` only marks a task
`COMPLETE` after an **authorized merge** (§18), which never happens under this skill. It's not
documented whether that same-task eligibility check still applies when the caller (this skill) has
already named one specific ticket to implement, rather than asking loop-task-implementer to pick from a
pool. **Mitigation, not a guaranteed fix:** when a ticket's dependency was satisfied per rule 4 above via
the `SKIPPED_EXISTING`/closed-ticket paths (not literally `COMPLETE` in loop-task-implementer's own
sense), **prepend** one line to that ticket's *description* (the same field its acceptance criteria and
body text already go in per §3 above — not a separate field) — e.g. *"Depends on
`<dependency_task_id>`, already addressed: `<pull_request_url or 'ticket closed'>`."* This gives
loop-task-implementer's own Orchestrator the evidence to proceed if it does re-check dependencies; if it
doesn't, the note is harmless extra context. **If loop-task-implementer still escalates a dependent
ticket on this ground**, treat the escalation as genuine (per §4 below) rather than silently
overriding it — this skill never bypasses loop-task-implementer's own safety judgment, even one this
skill suspects is a false positive.

## 4. The continuation decision — resolved explicitly, not inherited ambiguous

loop-task-implementer's own `orchestrator.md` §18 documents "select the next eligible task" only
*after an authorized merge* — since this skill never authorizes merge, that instruction never fires
inside any single loop-task-implementer invocation. That's expected, not a gap: **this skill's own
workflow is the layer that decides the next task**, across separate invocations, not
loop-task-implementer's internal continuation logic.

| Task outcome (`completion.repository_action` / `task.status`) | This skill's action |
|-------------------------------------------------------------------|-------------------------|
| `HUMAN_ACTION_REQUIRED` (verified-ready, PR opened, not merged) | **Expected, normal outcome — continue to the next queued task.** This is what "opens PRs by morning" means; never treat it as a stop condition |
| `ESCALATED` | Defer/skip this task and any queued dependent (§2 rule 4); record loop-task-implementer's own §19 escalation report as `escalation_ref`; **continue to the next independent task** unless the circuit breaker below fires |
| `MERGED` (only possible if a human separately merged a prior run's PR and this is a re-pull of the same ticket) | Treat as already complete — `SKIPPED_EXISTING` at the pull step (§2 rule 2), never re-run |

## 5. Session-level stop conditions (circuit breakers — new, distinct from loop-task-implementer's own per-task circuit breakers)

Stop **pulling new tasks** — an in-flight task always finishes its current step, never aborted
mid-Builder-dispatch — when any of:

| Condition | `stopped_reason` |
|-----------|---------------------|
| `max_tasks_per_run` tasks attempted this run | `MAX_TASKS_REACHED` |
| Wall-clock reaches `deadline` (if set) | `DEADLINE_REACHED` |
| `consumed_tokens` reaches `session_token_budget` (if set) | `TOKEN_BUDGET_EXHAUSTED` |
| **3 consecutive `ESCALATED` outcomes** (systemic-failure signal — distinct from any single task's own per-task circuit breakers, which stay loop-task-implementer's own and unchanged) | `CONSECUTIVE_ESCALATION_BREAKER` |
| Queue (after skip/defer/order) is empty | `QUEUE_EXHAUSTED` |

**"Consecutive" is counted over attempted tickets only** — `SKIPPED_EXISTING` and `DEFERRED` outcomes
don't reset or advance the count, since they were never actually attempted; only `HUMAN_ACTION_REQUIRED`
(resets the count to 0) and `ESCALATED` (increments it) affect it. A sequence like `ESCALATED, DEFERRED,
ESCALATED, DEFERRED, ESCALATED` — plausible given rule 4's dependency-deferral behavior — **does** trip
the breaker at the third escalation, even though the raw queue order interleaves deferrals between them.

The consecutive-escalation breaker exists because three escalations in a row more likely signals a
systemic problem (broken CI, a bad base branch, a misconfigured repo) than three independent hard tasks
— stop and let a human look, rather than burning the rest of the night's budget on tasks likely to fail
the same way.

## 6. Morning summary

Always produced, regardless of `stopped_reason` — see
[reference/morning-summary-format.md](morning-summary-format.md).
