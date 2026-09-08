# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `program_manifest`, `staleness_threshold_days`, `state_path` |
| **Run rollup** | [workflow/run-rollup.md](../workflow/run-rollup.md) | `MIGRATION_PROGRAM_REPORT.md`, `migration_program_rollup.json` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `program_manifest` with 3 workspaces, `staleness_threshold_days: 14` | Inputs → Run rollup (parse each `MIGRATION_STATUS.yaml` + `SQUAD_MAP.md`, join, compute staleness against persisted state, rank/group) → report + rollup JSON |
| A workspace's `MIGRATION_STATUS.yaml` is missing | Run rollup § 1 records it in Workspace gaps — not a HARD STOP for the whole run |
| A workspace has no `SQUAD_MAP.md` | Run rollup § 1 joins those services as `squad: UNKNOWN`, notes the gap — squad-map is never invoked |
| `program_manifest` empty, or `staleness_threshold_days` absent | Inputs HARD STOP — ask, no Run rollup |
