# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `workspace_root`, `repos`, `ownership_config` |
| **Phase 0** | [workflow/phase-0.md](../workflow/phase-0.md) | `mcp_profile` |
| **Phase 1** | [workflow/phase-1.md](../workflow/phase-1.md) | `SQUAD_MAP.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| User asks | Phases |
|-----------|--------|
| Map squads for workspace | Inputs → Phase 0 → Phase 1 |
| Refresh squad map | Inputs → Phase 0 → Phase 1 (overwrite stale rows) |
| Who owns `<repo>`? | Inputs (single repo) → Phase 0 → Phase 1 |
