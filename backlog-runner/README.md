# backlog-runner

**Scheduled queue-management wrapper around loop-task-implementer.** Pulls up to N tickets from a
Jira/GitHub Issues query, works through them in dependency order overnight, opens a PR per task, never
merges anything. No new Builder/Reviewer/PR logic — a thin queue layer on top of a skill that already
handles safe, isolated, unattended implementation.

Unlike loop-task-implementer, this skill does **not** auto-invoke from ambient chat
(`disable-model-invocation: true`). It's called explicitly on a schedule per [SETUP.md](SETUP.md).

## What it does

1. **Fires on a schedule** (nightly cron, scheduled CI job) — not ambient chat, not a live webhook.
2. **Pulls up to `max_tasks_per_run` tickets** from a configured tracker query, skipping any that already
   have an in-progress branch/PR from a prior run.
3. **Orders them by declared dependency** — a prerequisite ticket runs before its dependent; an unmet
   dependency defers the dependent rather than attempting it out of order.
4. **Invokes loop-task-implementer once per ticket**, sequentially — `autonomous_merge_authorized` is
   never set to `true`, ever, for any ticket.
5. **`HUMAN_ACTION_REQUIRED` (PR opened, awaiting review) is the expected outcome for every ticket, every
   night** — it continues the run, it doesn't stop it. Only a session-level circuit breaker (task cap,
   deadline, token budget, or 3 consecutive escalations) stops the queue early.
6. **Produces one morning summary** — shipped (PR links), blocked (escalated + why), deferred (dependency
   unmet), skipped (already in progress).

## When to use

backlog-runner is for the **scheduled, unattended** case — a nightly cron or scheduled CI job pulling a
whole ticket queue and working through it while no one's watching. A human typing "implement issue 42" or
"work through these tasks" in an interactive session should route to **loop-task-implementer** directly —
it already handles both single- and human-driven multi-task invocation, and backlog-runner adds nothing to
that path but scheduling. Nothing here ever auto-merges — see the design spec's Non-goals. Full
routing table: [SKILL.md](SKILL.md#when-to-use-not-to-use).

## Invocation examples

```
tracker_query: project = BACKLOG AND status = "Ready for Dev", max_tasks_per_run: 5
tracker_query: is:issue is:open label:backlog-runner, max_tasks_per_run: 3, deadline: 2026-08-06T06:00:00Z
```

## What you get

One PR per completed ticket (loop-task-implementer's own deliverable, unedited) plus a morning summary —
what shipped, what's blocked, what's deferred, what was skipped as already in progress. Nothing is ever
merged automatically.

## Install

```bash
cd software-builder
make install-backlog-runner
```

Restart Cursor. Requires **loop-task-implementer** installed and configured (the make target chains it
automatically) — see [loop-task-implementer/reference/mcp-capabilities.md](../loop-task-implementer/reference/mcp-capabilities.md) —
plus an issue-tracker MCP (Jira or GitHub Issues) and the scheduling integration contract in
[SETUP.md](SETUP.md).

## Related skills

- **loop-task-implementer** — does the actual implementation; this skill only decides which ticket runs
  next and when to stop
- **who-owns-x-bot**, **pr-gatekeeper**, **incident-triage-agent** — the same "thin trigger-driven
  wrapper, deterministic session policy" pattern applied to other skills; this one is schedule-triggered
  rather than webhook-triggered, and wraps an already-unattended-safe skill rather than an interactive one

Agent instructions: [SKILL.md](SKILL.md).
