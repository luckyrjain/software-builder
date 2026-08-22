# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `reviewed_content`, `profiling_excerpts`, `scope_hint` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | per-area findings (complexity, DB behavior, N+1, cache, memory, concurrency, connection pools, fanout) |
| **Report** | [workflow/report.md](../workflow/report.md) | `PERFORMANCE_REVIEW_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `reviewed_content` with code/query/service text, no profiling data | Inputs → Analyze (static analysis of all eight areas) → Report → full verdict |
| `reviewed_content` plus `profiling_excerpts` | Inputs → Analyze (static + profiling-informed) → Report → full verdict, higher confidence |
| `reviewed_content` absent | Inputs HARD STOP — ask, no Analyze |
| A focus area can't be evaluated (e.g. no visibility into query plans) | Analyze records the gap → Report surfaces it as an explicit Unknown, not a silent pass |
