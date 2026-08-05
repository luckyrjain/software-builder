# Phase index

**One `workflow/` file per role** — never bulk-load role prompts into one context. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

This skill's "phases" are roles, not sequential stages — Builder and Reviewer each run in a fresh,
isolated context per dispatch, and the Orchestrator alone persists state across the whole task.

| Role | Read now | Produces |
|------|----------|----------|
| **Orchestrator** | [workflow/orchestrator.md](../workflow/orchestrator.md) | task state, dispatch packages, adjudication verdicts, completion report |
| **Builder** | [workflow/builder.md](../workflow/builder.md) | implementation diff, pull request, builder report |
| **Reviewer** | [workflow/reviewer.md](../workflow/reviewer.md) | reviewer report, lens verdict |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Execution order

```
Orchestrator: discover policy → select task
  → dispatch Builder (fresh context)
  → verify branch/diff
  → dispatch Reviewer Lens A (fresh context) → adjudicate
  → dispatch Reviewer Lens B (fresh context) → adjudicate
  → dispatch Builder remediation for accepted findings (fresh context)
  → rerun affected lenses
  → verify authoritative checks
  → complete repository action when authorized
  → verify result → select next eligible task
```

Full workflow diagram: [SKILL.md § Workflow](../SKILL.md#workflow).
