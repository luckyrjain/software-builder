# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `tracker_query`, `max_tasks_per_run`, `deadline`, `session_token_budget`, `repo_context` |
| **Run queue** | [workflow/run-queue.md](../workflow/run-queue.md) | `morning_summary` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Scheduler trigger | Phases |
|-----------------------|--------|
| Nightly cron, queue has eligible tickets within `max_tasks_per_run` | Inputs → Run queue → shipped/blocked/deferred summary |
| Nightly cron, queue empty after skip/defer | Inputs → Run queue → `QUEUE_EXHAUSTED` summary (empty, still produced) |
| 3 consecutive escalations mid-run | Inputs → Run queue → `CONSECUTIVE_ESCALATION_BREAKER` summary, remaining tickets never attempted |
| Missing `tracker_query` / `max_tasks_per_run` / `repo_context` | Inputs HARD STOP — log and exit, no run |
