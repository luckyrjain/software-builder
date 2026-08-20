# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `request`, `repo_root`, `level_hint` |
| **Classify** | [workflow/classify.md](../workflow/classify.md) | ordered, de-duplicated `test_plan` |
| **Delegate** | [workflow/delegate.md](../workflow/delegate.md) | per-level `level_reports` |
| **Aggregate** | [workflow/aggregate.md](../workflow/aggregate.md) | `COMPLETE` / `PARTIAL` / `BLOCKED` / `FAILED` / `ESCALATED` orchestration status + verbatim reports |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `unit and integration tests for the change` | Inputs → Classify (both are complementary) → Delegate both → Aggregate |
| `test the payment flow` | Inputs → Classify asks whether integration or e2e; no Delegate until resolved |
| Generic/ambiguous request + `level_hint: integration` | Inputs → Classify one-level integration plan → Delegate → Aggregate |
| Explicit unit + integration request + `level_hint: unit` | Inputs → Classify preserves both complementary levels → Delegate both → Aggregate |
| Request matches no level signal | Inputs → Classify asks once, no Delegate yet |
| One level explicitly named at top level | Route directly to that `*-test-creator`; preserve single-level compatibility |
| `request` or `repo_root` missing | Inputs HARD STOP — ask, no further phase runs |
