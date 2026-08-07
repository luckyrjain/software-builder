# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `request`, `repo_root`, `level_hint` |
| **Classify** | [workflow/classify.md](../workflow/classify.md) | `level` (`unit`\|`integration`\|`contract`\|`e2e`) |
| **Delegate** | [workflow/delegate.md](../workflow/delegate.md) | `dispatched_report` (relayed verbatim) |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `request: "write tests for MR !123"`, level not stated | Inputs → Classify (asks if ambiguous) → Delegate |
| `request: ...`, `level_hint: integration` | Inputs → Classify (no asking, hint resolves) → Delegate |
| Request matches no level keywords | Inputs → Classify asks directly, no Delegate yet |
| Request already names a level explicitly | Should route directly to that `*-test-creator` skill — see [SKILL.md § When to use / NOT to use](../SKILL.md#when-to-use-not-to-use) |
| `request` or `repo_root` missing | Inputs HARD STOP — ask, no further phase runs |
