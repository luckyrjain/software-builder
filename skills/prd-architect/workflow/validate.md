---
workflow_version: 1.3
phase: validate
produces: {premise_verdict: string, problem_summary: object, alternatives_considered: list, validation_blockers: list}
consumes:
  required: {request: string, source_material: content, constraints: list, response_mode: string, depth: string, critique_only: boolean, user_insists_on_full_prd: boolean}
  optional: {}
  conditional: {}
---

# Validate — challenge the premise

## Understand

Document:

- problem, affected users, current behavior / workaround
- frequency / severity where known
- user and business impact
- desired outcome and proposed solution
- constraints ([global-rules.md](../reference/global-rules.md))

## Challenge

Answer internally:

- Is the problem real? Important enough?
- Root cause vs symptom?
- Is software required? Could process solve it?
- Simpler solution?
- What assumption must be true? What would invalidate the idea?
- What evidence would justify **not** building?

## Premise verdict

| Verdict | Meaning |
|---------|---------|
| **Strong** | Problem and approach well supported |
| **Reasonable but unvalidated** | Plausible; key assumptions need validation |
| **Weak** | Significant premise gaps |
| **Fundamentally flawed** | Wrong problem or approach — recommend alternative |

## Alternatives

When meaningful, compare material dimensions only:

- do nothing
- process change
- partial automation / extend existing / reuse internal
- integrate / buy / build

For **Validation** mode, alternatives are primary output. For **PRD/Review**, record the chosen path and
why others were rejected or deferred.

## Research

Research only when external evidence could **materially** change the result
([global-rules.md](../reference/global-rules.md) § Research). Generalize queries — do not expose
confidential names, metrics, or unreleased details unless authorized.

## Route after Validate (mandatory)

Do **not** continue to Specify by default. Follow [phase-index.md](../reference/phase-index.md) §
Pipeline routing:

| Condition | Next |
|-----------|------|
| `response_mode` = **Validation** | → **Gate** — emit 7-section Validation output. **Stop.** Do not run Specify, Break, or Repair. |
| `response_mode` = **PRD** and premise **Fundamentally flawed** | → **Gate** — emit Validation-style output unless user explicitly requested a full PRD. **Stop.** |
| `response_mode` = **Review** and premise **Fundamentally flawed** | → **Gate** — emit Validation-style output unless `user_insists_on_full_prd` is true. **Stop.** |
| `response_mode` = **Review**, premise is not Fundamentally flawed, and `critique_only` = true | → **Break** — use `source_material` as the draft under review. Skip Specify and Repair. |
| `user_insists_on_full_prd` = true after a Fundamentally flawed PRD or Review verdict | → **Specify** → Break → Repair → Gate; this explicit override takes precedence over `critique_only`. |
| `response_mode` = **PRD** or non-flawed **Review** (default) | → **Specify** → Break → Repair → Gate |
