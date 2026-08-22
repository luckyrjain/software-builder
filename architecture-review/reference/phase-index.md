# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `proposal_text`, `design_description`, `diagram_description`, `repo_context` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | decision rationale, scale-limit findings, failure-mode findings, security findings, operability findings, alternatives-considered findings |
| **Report** | [workflow/report.md](../workflow/report.md) | `ARCHITECTURE_REVIEW_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `proposal_text` + `design_description`, optional diagram/repo context | Inputs → Analyze → Report → full verdict |
| `proposal_text` or `design_description` missing | Inputs HARD STOP — ask, no Analyze |
| A required check can't be completed (e.g. design too sparse to evaluate failure modes, no diagram to verify trust boundaries) | Analyze records the gap → Report surfaces it as an explicit Unknown for that check, not a silent pass |
