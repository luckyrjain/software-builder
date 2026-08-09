# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Phase | Read now | Produces |
|-------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `request`, `source_material`, `constraints` |
| **Classify** | [workflow/classify.md](../workflow/classify.md) | `response_mode`, `depth`, `risk_domains` |
| **Validate** | [workflow/validate.md](../workflow/validate.md) | `premise_verdict`, `problem_summary`, `alternatives_considered` |
| **Specify** | [workflow/specify.md](../workflow/specify.md) | `mvp_scope`, `non_goals`, `triggered_sections`, `requirements_draft` |
| **Break** | [workflow/break.md](../workflow/break.md) | `scenarios`, `adversarial_findings` |
| **Repair** | [workflow/repair.md](../workflow/repair.md) | `repaired_requirements`, `remaining_blockers` |
| **Gate** | [workflow/gate.md](../workflow/gate.md) | `final_artifact`, `build_readiness` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|--------------|--------|
| Rough feature idea, no existing PRD | Inputs → Classify (PRD) → Validate → Specify → Break → Repair → Gate |
| "Should we build an AI support chatbot?" | Inputs → Classify (Validation) → Validate → Gate (7-section output) |
| Existing PRD + "find gaps / assess readiness" | Inputs → Classify (Review) → Validate → Specify → Break → Repair → Gate |
| Existing PRD + `critique_only: true` | Inputs → Classify (Review) → Validate → Break → Gate (findings only) |
| Fundamentally flawed premise | Validate stops → Validation-style output unless user insists on full PRD |
