---
workflow_version: 1.0
phase: break
produces:
  - scenarios
  - adversarial_findings
consumes:
  - requirements_draft
  - mvp_scope
  - non_goals
  - risk_domains
  - depth
---

# Break — scenarios and adversarial review

Attempt to break the proposed product with realistic scenarios and multi-perspective review.

## Scenario simulation

Choose the **smallest set** covering the material failure surface — normally **3–8** scenarios. For each:

| Field | Content |
|-------|---------|
| Actor | Who initiates |
| Preconditions | Starting state |
| Trigger | Event |
| Expected behavior | Product policy |
| Resulting state | System state after |
| User-visible outcome | What the user sees |
| Recovery | How the product or operator recovers |

**Scenario classes** (use only when credible for this product): normal success; invalid input;
abandonment; retry; duplicate processing; concurrency; partial failure; dependency timeout;
stale/conflicting data; lost/out-of-order events; unauthorized access; privilege misuse; abuse/fraud;
load spike; migration; operator recovery.

Do not analyze categories with no plausible product-specific failure.

## Adversarial review

Evaluate from the **original problem and requirements first**, then against the draft PRD. Do not assume
a requirement is correct because it appears in the input.

Select relevant perspectives from [adversarial-review.md](../reference/adversarial-review.md).

**Mandatory when applicable:**

- **Security + Privacy** — PII, auth, sensitive data, external exposure
- **Legal / Compliance** — regulated or contractual obligations
- **Operations / SRE** — async, integrations, background jobs, manual recovery, availability
- **Risk / Fraud / Finance** — money movement, billing, financially exploitable behavior

Look for: wrong problem; unsupported premise; missing/contradictory requirements; hidden assumptions;
invalid state transitions; missing failure behavior; data integrity risk; security vulnerability; abuse
path; operational blind spot; untestable requirement; hidden dependency; scope creep.

## Rigorous security-sensitive products

When `risk_domains` includes security-critical behavior, run the security review checklist in
[adversarial-review.md](../reference/adversarial-review.md) § Security-sensitive.

## Output

Classify each finding: Critical | High | Medium | Low. Pass to Repair.
