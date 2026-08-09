---
workflow_version: 1.0
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
---

# Validate — challenge the premise

Skip detailed PRD work when the premise is **Fundamentally flawed** — emit a concise Validation-style
assessment unless the user still wants a full PRD.

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

Research only when external evidence could **materially** change the result ([global-rules.md](../reference/global-rules.md) §Research). Stop when decisions have sufficient evidence or remaining uncertainty can safely be an assumption.

## Mode-specific exit

| Mode | If Fundamentally flawed |
|------|-------------------------|
| Validation | Full 7-section assessment; stop |
| PRD | Concise Validation assessment by default; elaborate PRD only if user insists |
| Review | Note flawed premise in Material Changes; do not paper over with requirements |
