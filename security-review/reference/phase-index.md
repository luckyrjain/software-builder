# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `review_target`, `scope_hint` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | per-category findings (authN, authZ/tenant isolation, secrets, injection, SSRF, data leakage, cryptography, dependency exposure) |
| **Report** | [workflow/report.md](../workflow/report.md) | `SECURITY_REVIEW_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `review_target` with code/config/design content | Inputs → Analyze → Report → full verdict |
| `review_target` absent | Inputs HARD STOP — ask, no Analyze |
| A category can't be checked (e.g. auth code out of scope, insufficient access) | Analyze records the gap → Report surfaces it as `Blocked — insufficient access` or an explicit per-section Unknown, not a silent Pass |
