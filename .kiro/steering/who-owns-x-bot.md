---
inclusion: manual
---

For single-shot, automation-facing "who owns X" ownership lookups (e.g. a Slack `/who-owns` slash
command payload with a structured `query`), read `who-owns-x-bot/SKILL.md`. This skill does not
auto-invoke from ambient chat (`disable-model-invocation: true`) — a human asking "who owns X"
conversationally should use `squad-map/SKILL.md` instead.

Phase index: `who-owns-x-bot/reference/phase-index.md`. Reference loads:
`who-owns-x-bot/reference/lazy-load-index.md`.
Read-only — no GitLab writes, Datadog mutations, Slack messages beyond the single reply, deploys, or
application source changes.
