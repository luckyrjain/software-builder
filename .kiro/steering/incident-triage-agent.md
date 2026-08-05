---
inclusion: manual
---

For paging-webhook-triggered incident triage (page fire) or postmortem drafting (incident resolved),
composing incident-rca and squad-map, read `incident-triage-agent/SKILL.md`. This skill does not
auto-invoke from ambient chat (`disable-model-invocation: true`) — a human asking for an RCA or an
ownership lookup conversationally should use `incident-rca/SKILL.md` or `squad-map/SKILL.md` instead.

Phase index: `incident-triage-agent/reference/phase-index.md`. Reference loads:
`incident-triage-agent/reference/lazy-load-index.md`.
Read-only — no remediation, no paging-system state changes, no live Jira/Slack/PagerDuty posts.
