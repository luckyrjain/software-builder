# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `new_hire`, `workspace_root`, `delivery_mode` |
| **Run tour** | [workflow/run-tour.md](../workflow/run-tour.md) | `ONBOARDING_TOUR.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `new_hire: {name: Jane, squad: payments}` | Inputs → Run tour (squad-map auto-discover → filter → domain-comprehension QUICK scoped) → `ONBOARDING_TOUR.md` |
| `new_hire.squad` matches zero `SQUAD_MAP.md` rows | Inputs → Run tour § 2 asks for confirmation, listing real squad names — no tour produced yet |
| `new_hire.name` or `new_hire.squad` missing | Inputs HARD STOP — ask, no Run tour |
| `SQUAD_MAP.md` already exists and repo list unchanged | Inputs → Run tour § 1 — squad-map's own `refresh: false` default skips re-query |
