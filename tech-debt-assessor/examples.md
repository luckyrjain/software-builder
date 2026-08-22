# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `debt_items` with 5 well-described items, mixed severity | Inputs → Analyze → Report → full ranked verdict list, mix of `Now`/`Next`/`Later`/`Won't-fix now` |
| 2 | An item touching a payments/compliance path with clear exposure | Analyze scores `business_impact = 5` → Report's `Now` override fires regardless of computed score |
| 3 | An item with moderate scores across the board (`priority_score` ≈ 12) | Report derives `Next` |
| 4 | An item that's small, isolated, low-risk, high-effort | Report derives `Won't-fix now` |
| 5 | A backlog with one item scoring in the `Later` band (`priority_score` ≈ 5) | Report derives `Later` |
| 6 | `debt_items` absent or an empty list | Inputs HARD STOP — ask for the backlog, no Analyze |
| 7 | An item whose description is too vague to score engineering drag or operational risk | Analyze records `Unknown` for that dimension → Report shows `Priority: Unknown — insufficient evidence`, not a guessed score |
| 8 | "Is checkout-api overprovisioned?" | **Wrong skill** → cost-optimization-sprint-planner directly |
| 9 | "Plan the migration off the legacy billing service" | **Wrong skill** → migration-program-manager directly |
| 10 | A "Now" item's description reveals it's actually a multi-service migration, not a fixable debt item | Report flags it in Notes; caller offered handoff to **migration-program-manager** |

---

### Scenario: Mixed backlog — happy path

**Caller:** `debt_items: [{description: "Legacy auth module still uses deprecated MD5-based password
hashing", affected_area: "auth-service"}, {description: "Dead feature-flag branch left in payments
config, never cleaned up", affected_area: "payments"}, {description: "Shared logging util has a
known memory leak that's paged us twice this quarter", affected_area: "platform-logging"}]`

**Agent:**

1. Inputs — 3 items parsed, no `repo_context` supplied, `effort_unit` defaults to T-shirt size
2. Analyze — auth item: business_impact 5 (password hashing, compliance-adjacent), engineering_drag 2,
   operational_risk 3, effort 2 (M); payments item: business_impact 1, engineering_drag 1,
   operational_risk 1, effort 1 (S); logging item: business_impact 3, engineering_drag 4,
   operational_risk 5 (two pages this quarter), effort 4 (L)
3. Report — verdicts derived, ranked table built

**Expected fragment:**

```
# Tech debt assessment — 2026-08-22

**Backlog assessed:** `3 items` · **Priority score formula:** `business impact × engineering drag ×
operational risk ÷ effort`

## Ranked backlog

| Item | Business impact | Engineering drag | Operational risk | Effort | Priority score | Priority |
|------|------------------|-------------------|--------------------|--------|-----------------|----------|
| `Legacy MD5 password hashing (auth-service)` | 5 | 2 | 3 | 2 | 15.0 | Now |
| `Logging util memory leak (platform-logging)` | 3 | 4 | 5 | 4 | 15.0 | Now |
| `Dead feature-flag branch (payments)` | 1 | 1 | 1 | 1 | 1.0 | Won't-fix now |
```

Note: both `Now` verdicts are override-driven, not computed-score-driven — the auth item via the
`business_impact = 5` override and the logging item via the `operational_risk = 5` override; both
items' computed scores (15.0 each) would otherwise only reach `Next` (`8 <= priority_score < 20`).

---

### Scenario: Severe compliance exposure — worst state via override

**Caller:** `debt_items: [{description: "Customer PII stored unencrypted at rest in the analytics
warehouse, flagged in last compliance audit", affected_area: "analytics", ticket_ref: "COMPL-881"}]`

**Agent:**

1. Inputs — 1 item parsed
2. Analyze — business_impact 5 (confirmed compliance-audit finding involving PII), engineering_drag 1
   (isolated to the warehouse job), operational_risk 2, effort 4 (L, cross-team encryption-at-rest work).
   Raw computed score = (5×1×2)/4 = 2.5 — would land in `Later` on score alone.
3. Report — `business_impact = 5` override fires regardless of the low computed score

**Expected fragment:**

```
## Ranked backlog

| Item | Business impact | Engineering drag | Operational risk | Effort | Priority score | Priority |
|------|------------------|-------------------|--------------------|--------|-----------------|----------|
| `Unencrypted PII at rest (analytics)` | 5 | 1 | 2 | 4 | 2.5 | Now |

## Rationale

| Item | Rationale |
|------|-----------|
| `Unencrypted PII at rest (analytics)` | Confirmed compliance-audit finding (`COMPL-881`) — `Now` via the business-impact override, independent of the low 2.5 computed score. |
```

---

### Scenario: Later-band item — a different enum state

**Caller:** `debt_items: [{description: "Internal admin dashboard uses an outdated charting library
with no known vulnerabilities, just annoying to maintain", affected_area: "internal-tools"}]`

**Agent:**

1. Inputs — 1 item parsed
2. Analyze — business_impact 2 (internal tool, no customer/revenue path), engineering_drag 3
   (touched occasionally, minor friction), operational_risk 1 (no incident history), effort 3 (M/L).
   Score = (2×3×1)/3 = 2.0
3. Report — `Later` band

**Expected fragment:**

```
## Ranked backlog

| Item | Business impact | Engineering drag | Operational risk | Effort | Priority score | Priority |
|------|------------------|-------------------|--------------------|--------|-----------------|----------|
| `Outdated charting library (internal-tools)` | 2 | 3 | 1 | 3 | 2.0 | Later |
```

---

### Scenario: Degraded path — evidence gap on one dimension

**Caller:** `debt_items: [{description: "Payment retry logic needs a refactor at some point",
affected_area: "payments"}]` — no `notes`, no `ticket_ref`, no `repo_context` supplied.

**Agent:**

1. Inputs — 1 item parsed; description is thin (no specifics on frequency, failure mode, or history)
2. Analyze — business_impact 3 (payments-adjacent, but no concrete exposure cited), effort 3 (M);
   engineering_drag and operational_risk cannot be scored — no churn/incident signal available and no
   corroborating `repo_context` was supplied to check. Both recorded `Unknown` rather than guessed.
3. Report — `priority_score: Unknown`, item never enters the Now/Next/Later/Won't-fix-now ladder

**Expected fragment:**

```
## Ranked backlog

| Item | Business impact | Engineering drag | Operational risk | Effort | Priority score | Priority |
|------|------------------|-------------------|--------------------|--------|-----------------|----------|
| `Payment retry logic refactor (payments)` | 3 | Unknown | Unknown | 3 | Unknown | Unknown — insufficient evidence |

## Notes

- `Payment retry logic refactor (payments)`: engineering drag and operational risk could not be scored
  — description names no specific failure mode or frequency, and no `repo_context`/`ticket_ref` was
  supplied to corroborate. Supply repo access or a linked ticket with incident history to resolve.
```

---

### Scenario: Cross-skill handoff — a "Now" item is really a migration

**Caller:** `debt_items: [{description: "The billing service is still on the old monolith and needs
to move to the new microservice platform before we can retire the monolith entirely", affected_area:
"billing"}]`

**Agent:**

1. Inputs — 1 item parsed
2. Analyze — business_impact 4, engineering_drag 4, operational_risk 3, effort 5 (XL). Score =
   (4×4×3)/5 = 9.6 → `Next` band on the ladder, but the description itself describes a multi-service
   migration program, not a fixable-in-place debt item
3. Report — item scored and ranked as usual, but flagged in Notes per
   [SKILL.md § Cross-skill escalation](SKILL.md#cross-skill-escalation): this is really a migration
   program, not a single remediable debt item

**Expected fragment:**

```
## Ranked backlog

| Item | Business impact | Engineering drag | Operational risk | Effort | Priority score | Priority |
|------|------------------|-------------------|--------------------|--------|-----------------|----------|
| `Billing service monolith-to-microservice move (billing)` | 4 | 4 | 3 | 5 | 9.6 | Next |

## Notes

- `Billing service monolith-to-microservice move (billing)`: description describes a multi-service
  migration, not a single fixable-in-place debt item. This priority score/verdict describe the
  cost-of-inaction only — recommend handing off to **migration-program-manager** to plan the actual
  migration execution.
```

**Handoff prompt offered to the caller:** "This item looks like a multi-service migration rather than a
fixable-in-place debt item — want me to hand off to migration-program-manager to plan the migration
itself?"
