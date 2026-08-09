---
workflow_version: 1.1
phase: validate
produces:
  - premise_verdict
  - problem_summary
  - alternatives_considered
  - validation_blockers
consumes:
  - request
  - source_material
  - constraints
  - response_mode
  - depth
  - critique_only
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
| `response_mode` = **Review** and `critique_only` = true | → **Break** — use `source_material` as the draft under review. Skip Specify and Repair. |
| `response_mode` = **PRD** or **Review** (default) | → **Specify** → Break → Repair → Gate |
