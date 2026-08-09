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

## Pipeline routing

After **Validate**, follow exactly one path based on `response_mode`, `premise_verdict`, and
`critique_only`. **Do not** run Specify → Break → Repair unless this table says so.

| Condition | Phases to run |
|-----------|---------------|
| `response_mode` = **Validation** | Validate → **Gate** (7-section output only) |
| `response_mode` = **PRD** and `premise_verdict` = **Fundamentally flawed** | Validate → **Gate** (Validation-style output) unless user explicitly requests a full PRD |
| `response_mode` = **PRD** (otherwise) | Validate → Specify → Break → Repair → Gate |
| `response_mode` = **Review** and `critique_only` = true | Validate → Break (`source_material` as draft) → **Gate** (findings only; skip Specify and Repair) |
| `response_mode` = **Review** (default) | Validate → Specify → Break → Repair → Gate |

## Quick paths (examples)

| Caller sends | Phases |
|--------------|--------|
| Rough feature idea, no existing PRD | Inputs → Classify (PRD) → Validate → Specify → Break → Repair → Gate |
| "Should we build an AI support chatbot?" | Inputs → Classify (Validation) → Validate → **Gate** (7-section output) |
| Existing PRD + "find gaps / assess readiness" | Inputs → Classify (Review) → Validate → Specify → Break → Repair → Gate |
| Existing PRD + `critique_only: true` | Inputs → Classify (Review) → Validate → Break → Gate (findings only) |
| Fundamentally flawed premise (any mode) | Validate → Gate with Validation-style output unless user insists on full PRD |
