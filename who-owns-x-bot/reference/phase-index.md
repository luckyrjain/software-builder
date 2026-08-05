# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `query`, `workspace_root` |
| **Lookup** | [workflow/lookup.md](../workflow/lookup.md) | `slack_reply` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `/who-owns api-disbursement` | Inputs → Lookup → Resolved reply |
| `/who-owns` (empty query) | Inputs HARD STOP → usage-hint reply, no Lookup |
| `/who-owns legacy-ledger` (known GitLab/Datadog conflict) | Inputs → Lookup → Ambiguous reply |
