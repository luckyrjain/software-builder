---
workflow_version: 1.1
phase: break
produces:
  - scenarios
  - adversarial_findings
consumes:
  - requirements_draft
  - source_material
  - mvp_scope
  - non_goals
  - risk_domains
  - depth
  - response_mode
  - critique_only
---

# Break — scenarios and adversarial review

## Draft under review

| Situation | Use as `requirements_draft` |
|-----------|------------------------------|
| After **Specify** | `requirements_draft` from Specify |
| **Review** + `critique_only` (Specify skipped) | `source_material` (the supplied PRD/spec) |
| **Review** after Specify | `requirements_draft` from Specify (may incorporate source PRD) |

Extract `non_goals` from the source PRD when Specify did not run.

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

Evaluate from the **original problem and requirements first**, then against the draft. Do not assume
a requirement is correct because it appears in the input.

Select relevant perspectives from [adversarial-review.md](../reference/adversarial-review.md).

**Mandatory when applicable:**

- **Security + Privacy** — PII, auth, sensitive data, external exposure
- **Legal / Compliance** — regulated or contractual obligations
- **Operations / SRE** — async, integrations, background jobs, manual recovery, availability
- **Risk / Fraud / Finance** — money movement, billing, financially exploitable behavior

## Rigorous security-sensitive products

When `risk_domains` includes security-critical behavior, run the security checklist in
[adversarial-review.md](../reference/adversarial-review.md) § Security-sensitive products.

## Output

Classify each finding: Critical | High | Medium | Low.

| Next phase | When |
|------------|------|
| **Repair** | PRD or full Review (not `critique_only`) |
| **Gate** | `critique_only` — pass findings to Gate as gap analysis + readiness inputs; skip Repair |
