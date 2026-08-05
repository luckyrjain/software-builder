# Lazy-load index

Read reference files **one at a time** when the active workflow phase says to — never bulk-load.

| When | Also load |
|------|-----------|
| Inputs — multi-repo scope | [workspace-scope.md](workspace-scope.md) |
| Phase 1 — after boundary built | [fast-path.md](fast-path.md), [capability-discovery.md](capability-discovery.md) |
| Phase 1 — step 7 local context | [session-context-cache.md](session-context-cache.md) |
| Phase 1 — prior bot reviews on MR | [review-feedback-learning.md](review-feedback-learning.md) |
| Phase 1 — MR state / mode | [review-modes.md](review-modes.md) — when merged or incremental |
| Phase 1 — CI / merge train | [phase-1-gather.md](phase-1-gather.md) |
| Phase 1 — repo rules | [review-rules.md](review-rules.md) (+ repo `review-rules.yaml` if present) |
| Phase 1 — regulated paths (no YAML) | [domain-overrides.md](domain-overrides.md) |
| Phase 2 — review | `finding-gates` → `finding-pipeline` → `finding-evidence-model` → `severity-rubric` → `review-checklist` → others only when triggered (see `workflow/phase-2.md`) |
| Phase 2 — §16 triggered | [architecture-lens.md](architecture-lens.md) |
| Phase 2→3 — incremental | [incremental-rerun.md](incremental-rerun.md) |
| Phase 3–4 — posting | [comment-templates.md](comment-templates.md); `full` also [gitlab-inline-comments.md](gitlab-inline-comments.md) |
| Phase 5 — closeout | [gold-review-excerpt.md](gold-review-excerpt.md) (format few-shot), [production-risk.md](production-risk.md), [architectural-summary.md](architectural-summary.md), [positive-observations.md](positive-observations.md), [not-raised.md](not-raised.md), [executive-summary.md](executive-summary.md), [report-template.md](../report-template.md) |
| Phase 5 — Jira offer | [jira-writeback.md](jira-writeback.md) |
| MCP ambiguity | [mcp-capabilities.md](mcp-capabilities.md) |
| Install / smoke test | [SETUP.md](../SETUP.md), [smoke-test.md](smoke-test.md) |
| Maintainer edits | [pressure-tests.md](pressure-tests.md) |

[examples.md](../examples.md) is for humans — never required during a live review.
