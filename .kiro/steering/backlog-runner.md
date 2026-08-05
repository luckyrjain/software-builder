---
inclusion: manual
---

For scheduled, unattended overnight sweeps of a ticket queue via loop-task-implementer (a structured
payload with `tracker_query`, `max_tasks_per_run`, optionally `deadline`/`session_token_budget`,
`repo_context`), read `backlog-runner/SKILL.md`. This skill does not auto-invoke from ambient chat
(`disable-model-invocation: true`) — a human asking to implement one or several tasks conversationally
should use `loop-task-implementer/SKILL.md` instead, which already handles both patterns interactively.

Phase index: `backlog-runner/reference/phase-index.md`. Reference loads:
`backlog-runner/reference/lazy-load-index.md`.
Never merges — `autonomous_merge_authorized` has no input path in this skill.
