---
workflow_version: 1.0
phase: run-queue
produces:
  - morning_summary
consumes:
  - tracker_query
  - max_tasks_per_run
  - deadline
  - session_token_budget
  - repo_context
---

# Run queue — pull, order, loop, stop, summarize

**Goal:** Work through as much of the backlog as the session's stop conditions allow, one
loop-task-implementer invocation per ticket, and always produce a morning summary. No new
Builder/Reviewer/PR logic here — see [SKILL.md](../SKILL.md) Non-goals and
[reference/queue-policy.md](../reference/queue-policy.md).

## Steps

1. **Pull and order the queue** per
   [reference/queue-policy.md § 2](../reference/queue-policy.md#2-queue-pull-and-ordering) — run
   `tracker_query`, cap at `max_tasks_per_run`, skip tickets with an existing in-progress branch/PR,
   topologically order by declared dependency, defer tickets whose dependency is unresolved this run.

2. **For each ticket in order**, unless a stop condition already fired (Step 4):
   - Invoke loop-task-implementer once, per
     [reference/queue-policy.md § 3](../reference/queue-policy.md#3-invoking-loop-task-implementer-one-task-per-invocation) —
     `autonomous_merge_authorized` never supplied as `true`.
   - Record the outcome and apply
     [reference/queue-policy.md § 4](../reference/queue-policy.md#4-the-continuation-decision-resolved-explicitly-not-inherited-ambiguous) —
     `HUMAN_ACTION_REQUIRED` continues normally; `ESCALATED` defers this ticket and its dependents and
     continues to the next independent ticket.
   - Update `consumed_tokens` in the session state.

3. **After each ticket completes**, re-check the session-level stop conditions
   ([reference/queue-policy.md § 5](../reference/queue-policy.md#5-session-level-stop-conditions-circuit-breakers-new-distinct-from-loop-task-implementers-own-per-task-circuit-breakers))
   before starting the next one — `max_tasks_per_run`, `deadline`, `session_token_budget`, the
   3-consecutive-`ESCALATED` circuit breaker, or an exhausted queue. **Never abort a ticket already
   in-flight** — a stop condition reached mid-ticket lets that ticket finish its current step, then stops
   before starting the next.

4. **Assemble the morning summary** per
   [reference/morning-summary-format.md](../reference/morning-summary-format.md) — always produced, no
   matter which `stopped_reason` ended the run (including `QUEUE_EXHAUSTED`, the normal/expected case).

5. **Route the morning summary** to the configured notification path — see [SETUP.md](../SETUP.md) §
   Config.

## Read-only boundary

Same as loop-task-implementer: implementation + PR-create only. Never merges (Step 2's
`autonomous_merge_authorized` rule is absolute, not conditional), never bypasses any per-task circuit
breaker, never relaxes Builder/Reviewer isolation for speed.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| `morning_summary` | Returned to caller / routed notification | Shipped (PR links), blocked (escalated + reasons), deferred (dependency unmet), `stopped_reason` | Run queue incomplete |

## Completion summary (chat)

When run inside an interactive agent session (e.g. for testing), state: tickets pulled, skipped
(existing), attempted, shipped, escalated, deferred, and the `stopped_reason`.
