# Domain Overrides (optional)

Load when the repository or team is in a regulated / high-stakes domain **and no repo
`review-rules.yaml` was found** (see `reference/review-rules.md` — YAML is the preferred team customization).

Also check for a project-local override at `.cursor/skills/pr-review/domain-overrides.md` in the repo under review.

## Fintech / payments / platform (default override)

Raise the bar one severity notch for findings in:

- Payments, ledger/double-entry, refunds, settlements
- Money math — use exact decimal types, never `float`
- Idempotency keys on webhooks and payment handlers
- PII handling, PCI-adjacent data, auth/session flows
- Database migrations and public API surface changes

## How to apply

Treat matching paths as **production-critical** context (`reference/contextual-severity.md`) — not a
blind "+1 notch" on every finding. Examples:

- A missing timeout on a generic admin endpoint → **Low** (internal context).
- The same missing timeout on a payment webhook handler → **High** (production-critical).
- Missing logging on checkout capture → **High**; on admin dashboard → **Low** — same issue, different context.
- `float` for currency in a report → Low; in a ledger write → High or Critical.

## Payments output requirements

When payments domain or **Payments SME** persona is active, every **High** and **Critical** finding
must include:

| Field | Rule |
|-------|------|
| **Blast radius** | Who/what is affected — e.g. *All PDN notifications*, *Entire service* |
| **Business impact** | Plain-language customer/ops consequence — required in **Code blockers** table column |

Example Code blockers mapping:

| Technical issue | Business impact |
|-----------------|-----------------|
| Wrong transaction date | Customer notified on wrong day |
| Hikari churn | Payment failures under load |
| Retry fallback | Failed notification retries |
| Kafka endpoint | Unauthorized payment processing |

| **Thematic clustering** | Resilience, Jackson, payment-date manifestations → one finding each (`finding-pipeline.md` step 10) |
| **High bar** | ~4–5 High max on dense MRs — demote inference-heavy items to Medium (`finding-pipeline.md` step 7a) |

## Severity calibration (payments)

**High (merge-blocking code):**

- Wrong autodebit / transaction date (grouped)
- Resilience fallback on payment notification path
- Hikari / connection pool misconfig (OEDR)
- Confirmed embedded credential on diff line

**Medium (track — not inflated to High):**

- Jackson `TypeReference` / deserialization (OUR unless runtime failure verified)
- Bucket4j / rate-limit config mismatch
- STG or env yaml deleted — **Medium (High confidence)** unless diff shows app still imports deleted path
- Kafka/test controller without visible auth (OUR)

## Config / environment file deletion

When diff **deletes** `config/stg/…`, `application-*.yml`, or profile-specific paths:

1. **Observed:** file removed in diff.
2. Check whether changed startup/import code still references the path.
3. **Medium** — default; note *may be intentional consolidation*.
4. **High** — only when broken reference, failed profile load, or MR confirms STG still requires file.

Use **OEDR / OUR** per `reference/finding-evidence-model.md`.

Teams can replace this file or add repo-local overrides without editing the core checklist.
