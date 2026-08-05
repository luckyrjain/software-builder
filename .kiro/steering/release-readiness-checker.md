---
inclusion: manual
---

For a release go/no-go report (composing pr-review, k8s-overprovisioning-datadog, and incident-rca over a
`release_manifest`), read `release-readiness-checker/SKILL.md`. Reviewing one specific MR routes to
`pr-review/SKILL.md` instead; one service's rightsizing question routes to
`k8s-overprovisioning-datadog/SKILL.md` instead; a full root-cause investigation routes to
`incident-rca/SKILL.md` instead.

Phase index: `release-readiness-checker/reference/phase-index.md`. Reference loads:
`release-readiness-checker/reference/lazy-load-index.md`.
Read-only throughout — pr-review runs `chat-only` (never posts to GitLab), k8s and incident-rca are
already read-only. No manifest changes, no merges, no Jira/Slack write-back.
