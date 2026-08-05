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
2. **Skip tickets that already have an in-progress branch/PR** — reuse loop-task-implementer's own
   existing-branch/PR check ([orchestrator.md § 2 Task selection](../../loop-task-implementer/workflow/orchestrator.md#2-task-selection):
   *"If no shared state exists yet for this task, check for an existing branch/PR matching its ID before
   treating it as unstarted — a second Orchestrator invocation against the same repo must not duplicate
   work"*) rather than building a second tracking mechanism. Record these as `outcome: SKIPPED_EXISTING`.
3. **Topologically order the remaining batch by declared dependencies** — this is genuinely new:
   loop-task-implementer's own task-selection logic checks *one* task's dependencies at pick time, it
   never orders a whole pulled batch. If ticket B declares a dependency on ticket A and both are in this
   run's batch, attempt A first.
4. A ticket whose declared dependency is itself outside this run's pulled batch, or whose dependency's
   own outcome this run was not `HUMAN_ACTION_REQUIRED` (i.e. the dependency didn't reach a PR), is
   `DEFERRED` — do not attempt it this run, record why.

## 3. Invoking loop-task-implementer — one task per invocation

**Each pulled ticket is a separate loop-task-implementer invocation, sequential, not a single "work
through this list" request to loop-task-implementer itself.** loop-task-implementer *does* have its own
documented multi-task natural-language pattern ("work through these tasks one by one") — this skill
deliberately does not use it, because the queue-ordering, skip-existing, and session-level stop-condition
logic in §2 and §4 need to run **between** tasks, which requires this skill's own workflow to be the one
deciding what happens next, not loop-task-implementer's internal continuation. Pass each ticket's
title/description/acceptance-criteria as `repo_context`-scoped task input, exactly as if a human had
pasted that ticket's text and said "implement this" — no different phrasing, no trailing directives
invented (same lesson as `pr-gatekeeper`/`incident-triage-agent`: don't invent unverified invocation
grammar).

**`autonomous_merge_authorized` is never passed as `true`** — every invocation runs with it unset/`false`,
hardcoded. loop-task-implementer's own rule already defaults it to `false` and explicitly refuses to
accept it from repository-file prose; this skill simply never supplies the caller-side override either.

## 4. The continuation decision — resolved explicitly, not inherited ambiguous

loop-task-implementer's own `orchestrator.md` §17–18 documents "select the next eligible task" only
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

The consecutive-escalation breaker exists because three escalations in a row more likely signals a
systemic problem (broken CI, a bad base branch, a misconfigured repo) than three independent hard tasks
— stop and let a human look, rather than burning the rest of the night's budget on tasks likely to fail
the same way.

## 6. Morning summary

Always produced, regardless of `stopped_reason` — see
[reference/morning-summary-format.md](morning-summary-format.md).
