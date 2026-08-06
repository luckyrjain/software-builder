# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `rollup_manifest`, `staleness_warning_days` |
| **Run digest** | [workflow/run-digest.md](../workflow/run-digest.md) | `WEEKLY_SQUAD_DIGEST.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `rollup_manifest` with both paths set | Inputs → Run digest (read both, group by squad then metric_type, flag staleness, render) → digest |
| `rollup_manifest` with only one path set | Inputs → Run digest — the unset rollup is a Rollup gaps row, the digest still renders from the other |
| A rollup path is set but the file doesn't exist | Run digest § 1 records it in Rollup gaps — not a HARD STOP for the readable rollup |
| `rollup_manifest` has neither path set | Inputs HARD STOP — stop and log the error, no Run digest (no human to ask on a scheduled run) |
