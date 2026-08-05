# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Scheduler sends | Behavior |
|---|--------------------|----------|
| 1 | `tracker_query` returns 5 tickets, `max_tasks_per_run: 3`, no dependencies declared | Inputs → Run queue → 3 attempted in tracker order, 2 never pulled |
| 2 | Ticket B depends on ticket A, both in the pulled batch | Inputs → Run queue → A attempted first; if A reaches `HUMAN_ACTION_REQUIRED`, B is attempted next |
| 3 | Ticket B depends on ticket A, A is `ESCALATED` | Inputs → Run queue → B is `DEFERRED`, not attempted, recorded with its reason |
| 4 | First 3 tickets all `ESCALATED` in a row | Inputs → Run queue → `CONSECUTIVE_ESCALATION_BREAKER` fires, remaining tickets never attempted, summary produced |
| 5 | A pulled ticket already has an open PR from last night's run | Inputs → Run queue → `SKIPPED_EXISTING`, not re-attempted |
| 6 | `deadline` reached while a ticket is mid-review | Inputs → Run queue → that ticket finishes its current step, no new ticket starts, `DEADLINE_REACHED` |
| 7 | Every attempted ticket reaches `HUMAN_ACTION_REQUIRED` | Inputs → Run queue → `QUEUE_EXHAUSTED` (normal, expected outcome) — N PRs opened, none merged |
| 8 | "Implement issue 42" typed in an interactive chat session | **Wrong skill** → loop-task-implementer (this skill doesn't auto-invoke; see `disable-model-invocation`) |
| 9 | "Work through these tasks one by one" typed in an interactive session | **Wrong skill** → loop-task-implementer (already a first-class pattern there) |

---

### Scenario: Normal overnight run — happy path

**Scheduler:** `tracker_query: project = BACKLOG AND status = "Ready for Dev"`, `max_tasks_per_run: 3`

**Agent:**

1. Inputs — all required fields present
2. Run queue — pulls 3 tickets, none pre-existing, no declared dependencies among them; invokes
   loop-task-implementer 3 times sequentially, each without `autonomous_merge_authorized`
3. All 3 reach `HUMAN_ACTION_REQUIRED` — 3 PRs opened
4. `stopped_reason: QUEUE_EXHAUSTED`; morning summary sent

**Expected fragment:**

```
# Backlog run — 2026-08-05T23:00:00Z to 2026-08-06T02:14:00Z

**Stopped:** QUEUE_EXHAUSTED

## Shipped (3 PRs opened, none merged)

| Ticket | PR | Notes |
|--------|----|----|
| BACKLOG-101 | https://github.com/acme/backend/pull/482 | HUMAN_ACTION_REQUIRED — awaiting review/merge |
```

---

### Scenario: Dependency ordering + one escalation

**Scheduler:** `tracker_query` returns `BACKLOG-201` (depends on `BACKLOG-200`) and `BACKLOG-200` itself,
`max_tasks_per_run: 2`

**Agent:** Orders `BACKLOG-200` first. It escalates (`ESCALATED` — e.g. missing access). `BACKLOG-201` is
`DEFERRED` since its dependency didn't reach `HUMAN_ACTION_REQUIRED` this run — never attempted out of
order.

**Expected fragment:**

```
## Blocked (1 escalated)

| Ticket | Reason | Escalation report |
|--------|--------|----|
| BACKLOG-200 | Missing access: production database credentials | see escalation_ref |

## Deferred (1 — dependency unmet this run)

| Ticket | Waiting on |
|--------|------------|
| BACKLOG-201 | BACKLOG-200 |
```

---

### Scenario: Cross-skill — wrong entry point

**Caller:** (human, typing in an interactive session) "Work through these tasks one by one and stop when
each is ready to merge"

**Agent:** This skill does not auto-invoke (`disable-model-invocation: true`); the request routes to
**loop-task-implementer** directly, per loop-task-implementer's own invocation table
([loop-task-implementer/examples.md § Invocation](../loop-task-implementer/examples.md)).
