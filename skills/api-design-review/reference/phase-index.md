# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `api_spec`, `previous_spec`, `system_design_context` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | compatibility, pagination, idempotency, error-semantics, versioning, authorization, and rate-limiting findings |
| **Report** | [workflow/report.md](../workflow/report.md) | `API_DESIGN_REVIEW_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `api_spec` (+ optional `previous_spec`, `system_design_context`) | Inputs → Analyze → Report → full verdict |
| `api_spec` absent | Inputs HARD STOP — ask, no Analyze |
| A check can't be completed (e.g. no `previous_spec` for a compatibility diff, or the spec omits an auth section) | Analyze records the gap → Report surfaces it as an explicit Unknown, not a silent Approved |
