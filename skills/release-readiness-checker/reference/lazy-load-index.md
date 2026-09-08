# Lazy-load index

Load **one reference file at a time** when the active workflow phase points to it.

| When | Read |
|------|------|
| Run check — building `RELEASE_READINESS_REPORT.md` | [report-format.md](report-format.md) |
| Run check — incident-rca's own gates and this skill's scripted answers | [gate-policy.md](gate-policy.md) |
| Run check — pr-review's own posting-mode contract | [posting.md](../../pr-review/workflow/posting.md) |
| Run check — pr-review's own GitLab MCP tool capabilities | [mcp-capabilities.md](../../pr-review/reference/mcp-capabilities.md) |
| Run check — k8s-overprovisioning-datadog's own per-service resolution | [resolve-service.md](../../k8s-overprovisioning-datadog/workflow/resolve-service.md) |
| Run check — incident-rca's own Phase 1 checkpoint and partial-report path | [phase-1.md](../../incident-rca/workflow/phase-1.md) · [phase-5.md](../../incident-rca/workflow/phase-5.md) |
| Post-install check | [smoke-test.md](smoke-test.md) |

Framework: [confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md) ·
[cross-skill-escalation.md](../../docs/skill-framework/shared/cross-skill-escalation.md) ·
[prompt-injection.md](../../docs/skill-framework/shared/prompt-injection.md)
