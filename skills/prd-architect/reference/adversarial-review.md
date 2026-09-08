# Adversarial review

## Perspectives

Select only perspectives relevant to this product. Candidates:

| Perspective | Focus |
|-------------|-------|
| Product | Problem fit, scope, outcomes |
| Engineering | Feasibility, ambiguity, testability |
| Architecture | Dependencies, boundaries, consistency |
| UX | Flows, states, error experience |
| End User | Value, confusion, harm |
| QA | Testability, acceptance criteria gaps |
| Operations / SRE | Async, recovery, observability, availability |
| Security | AuthZ, exposure, abuse |
| Privacy | PII, retention, consent |
| Legal / Compliance | Regulation, contracts |
| Risk / Fraud / Finance | Money movement, exploit paths |
| Data | Integrity, lineage, quality |
| Finance | Unit economics, cost |
| Accessibility | Inclusive access |
| Support | Diagnosis, escalation, tooling |

## Mandatory perspectives

| When | Required |
|------|----------|
| PII, auth, sensitive data, external exposure | Security + Privacy |
| Regulated or contractual obligations | Legal / Compliance |
| Async processing, integrations, background jobs, manual recovery | Operations / SRE |
| Money movement, lending, payments, billing, financial exploit | Risk / Fraud / Finance |

## Finding types

Look for concrete failures:

- wrong problem
- unsupported premise
- missing requirement
- contradictory rule
- hidden assumption
- invalid state transition
- missing failure behavior
- data integrity risk
- security vulnerability
- abuse path
- operational blind spot
- untestable requirement
- hidden dependency
- scope creep

## Security-sensitive products (Rigorous)

When security-critical behavior is in scope, identify:

- protected assets
- trust boundaries
- privileged actors
- privileged operations
- external attack surface
- realistic attacker goals
- abuse paths
- security invariants
- blast radius

Translate material risks into product/security requirements. Do not add generic security boilerplate.

## Severity

| Severity | Definition |
|----------|------------|
| **Critical** | Plausible severe financial, regulatory, security, data-integrity, systemic, or user harm |
| **High** | Major use case or safe implementation compromised |
| **Medium** | Meaningful usability, reliability, operational, scale, or maintainability weakness |
| **Low** | Useful but non-material improvement |

Pass findings to [workflow/repair.md](../workflow/repair.md).
