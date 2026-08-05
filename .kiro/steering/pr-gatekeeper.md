---
inclusion: manual
---

For webhook-triggered, unattended pr-review auto-runs on every push to an open GitLab MR (a structured
payload with `project`, `merge_request_iid`, `head_sha`, `auto_post_authorized`), read
`pr-gatekeeper/SKILL.md`. This skill does not auto-invoke from ambient chat
(`disable-model-invocation: true`) — a human asking to review an MR conversationally should use
`pr-review/SKILL.md` instead.

Phase index: `pr-gatekeeper/reference/phase-index.md`. Reference loads:
`pr-gatekeeper/reference/lazy-load-index.md`.
Read + comment only — no GitLab approve/merge, no remediation, no application source changes.
