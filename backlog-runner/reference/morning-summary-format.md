# Morning summary format (normative)

Always produced, regardless of `stopped_reason` — including the normal `QUEUE_EXHAUSTED` case.

```markdown
# Backlog run — <started_at> to <now>

**Stopped:** <stopped_reason> — <MAX_TASKS_REACHED | DEADLINE_REACHED | TOKEN_BUDGET_EXHAUSTED |
CONSECUTIVE_ESCALATION_BREAKER | QUEUE_EXHAUSTED>

## Shipped (<n> PRs opened, none merged)

| Ticket | PR | Notes |
|--------|----|----|
| <task_id> | <pull_request_url> | HUMAN_ACTION_REQUIRED — awaiting review/merge |

## Blocked (<n> escalated)

| Ticket | Reason | Escalation report |
|--------|--------|----|
| <task_id> | <one-line reason from loop-task-implementer's own §19 escalation report> | <escalation_ref> |

## Deferred (<n> — dependency unmet this run)

| Ticket | Waiting on |
|--------|------------|
| <task_id> | <dependency task_id, itself blocked/not attempted this run> |

## Skipped (<n> — already in progress)

| Ticket | Existing PR |
|--------|-------------|
| <task_id> | <pre-existing pull_request_url from a prior run> |
```

## Rules

- **Never state a task shipped if it only reached `HUMAN_ACTION_REQUIRED`** — say so plainly ("PR opened,
  awaiting review/merge"), never imply it was merged. This skill never merges anything, ever.
- **Blocked reasons come from loop-task-implementer's own escalation report** (§19 in
  [orchestrator.md](../../loop-task-implementer/workflow/orchestrator.md#19-escalation-report)) — link or
  paste it, never paraphrase away the specific finding/decision that's blocking.
- **Include the `Skipped` and `Deferred` sections even when empty** — an empty table still tells the
  reader nothing was silently dropped.
- One morning summary per run, sent to the configured notification target — see
  [SETUP.md](../SETUP.md) § Config.
