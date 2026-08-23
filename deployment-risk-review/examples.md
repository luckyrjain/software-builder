# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|---------------|----------|
| 1 | "Assess deployment risk for: additive nullable column via online migration on `orders`, deployed to checkout-service, rollback is a feature-flag toggle, off-peak deploy with canary" | Inputs → Analyze → Report; verdict `Low` |
| 2 | "Assess deployment risk for: irreversible backfill dropping the legacy `orders.legacy_id` column, no rollback plan" | Inputs → Analyze → Report; verdict `Critical` |
| 3 | "Assess deployment risk for: irreversible partition-key change on `payments`, rollback plan is a full point-in-time restore" | Inputs → Analyze → Report; verdict `High` |
| 4 | "Assess deployment risk for: config-only change to `auth-service`, deploying at 9am weekday peak, no canary configured" | Inputs → Analyze → Report; verdict `High` (peak deploy, no canary) |
| 5 | "Assess deployment risk for: reversible column-add on `inventory`, rollback plan documented, blast radius limited to internal reporting" | Inputs → Analyze → Report; verdict `Moderate` |
| 6 | "Assess deployment risk" (no change description given) | Inputs HARD STOP — ask for `change_description` before Analyze |
| 7 | "Assess deployment risk for: schema migration on `billing`" (no `rollback_plan` supplied, none discoverable in repo) | Rollback complexity recorded as evidence gap; verdict floored at `High`; `deployment_confidence: LOW` |
| 8 | "Give me the full release go/no-go across all our repos for this week" | Wrong skill → **release-readiness-checker** (composed multi-repo sweep, not a single change) |
| 9 | "The deploy we did last night for `checkout-service` just broke prod, what happened?" | Wrong skill → **incident-triage-agent** (this deploy already shipped and something broke) |

### Scenario: Clean happy path

**Caller:** "Assess deployment risk for: additive nullable column via online migration on `orders`,
deployed to `checkout-service`, rollback is a feature-flag toggle, off-peak deploy with canary
coverage."

**Agent:**
1. Inputs — `change_description` supplied; `migration_steps`, `rollback_plan`, `traffic_pattern`
   all supplied; `affected_services` inferred as `checkout-service`.
2. Analyze — additive nullable column is reversible by default; rollback plan is a feature-flag
   toggle (fast, safe, and independent of the migration); blast radius contained to
   `checkout-service`; off-peak deploy with canary coverage; no dependency risk found.
3. Report — no evidence gaps on any of the five checks → verdict `Low`, `deployment_confidence:
   HIGH`.

**Expected fragment:**

```markdown
# Deployment Risk Review — orders.status nullable column

**Risk: Low**

## Migration risk

| Dimension | Finding |
|-----------|---------|
| Data/schema changes | Additive nullable column on `orders.status`, online migration |
| Reversibility | Reversible — additive, non-destructive; no down-migration required |

## Rollback complexity

| Dimension | Finding |
|-----------|---------|
| Rollback plan | Feature-flag toggle, independent of the migration |
| Speed / safety | Fast and safe |

## Confidence

**deployment_confidence: HIGH**

No evidence gaps — all five checks assessed from supplied inputs.
```

### Scenario: Worst-state verdict

**Caller:** "Assess deployment risk for: irreversible backfill dropping the legacy
`orders.legacy_id` column, no rollback plan."

**Agent:**
1. Inputs — `change_description` and `migration_steps` supplied; `rollback_plan` absent (defaults
   to "None stated"); `affected_services` inferred as `orders` service.
2. Analyze — dropping a column via backfill is irreversible (no down-migration path); rollback
   complexity records "None stated — evidence gap" since the field is genuinely absent, not just
   defaulted past a real plan.
3. Report — the absent `rollback_plan` is an evidence gap, not a confirmed "no rollback plan" —
   the `Critical` trigger requires the latter. An unresolved evidence gap on Rollback complexity
   instead floors the verdict at `High` per the precedence order, even though the migration itself
   is irreversible.

**Expected fragment:**

```markdown
# Deployment Risk Review — drop orders.legacy_id backfill

**Risk: High**

## Migration risk

| Dimension | Finding |
|-----------|---------|
| Data/schema changes | Irreversible backfill dropping `orders.legacy_id` |
| Reversibility | Irreversible — column drop, no down-migration path |

## Rollback complexity

| Dimension | Finding |
|-----------|---------|
| Rollback plan | None stated — evidence gap |
| Speed / safety | Unknown — no rollback mechanism identified |

## Confidence

**deployment_confidence: LOW**

Rollback complexity is an evidence gap on an irreversible migration; the gap floors the verdict at
`High` per the fixed precedence order — it does not escalate to `Critical`, which requires a
confirmed absence of a rollback plan rather than an unresolved gap.
```

### Scenario: Multi-finding High verdict

**Caller:** "Assess deployment risk for: config-only change to `auth-service`'s session-timeout
value, deploying at 9am weekday peak, no canary configured, rollback is a config revert (fast)."

**Agent:**
1. Inputs — all fields supplied; `migration_steps` = "None" confirmed by `change_description`
   (config-only, no schema change).
2. Analyze — no migration, so Migration risk is clean; rollback plan is fast/safe; blast radius
   covers `auth-service` broadly (all authenticated sessions) — a critical/customer-facing path;
   traffic pattern is peak with no canary coverage.
3. Report — two independent `High` triggers apply (critical-path blast radius with a rollback plan,
   and peak deploy with no canary) — both listed, verdict `High`.

**Expected fragment:**

```markdown
# Deployment Risk Review — auth-service session-timeout config change

**Risk: High**

## Blast radius

| Dimension | Finding |
|-----------|---------|
| What breaks if this is wrong | All authenticated sessions across `auth-service` — critical/customer-facing path |

## Traffic risk

| Dimension | Finding |
|-----------|---------|
| Deploy timing vs. peak traffic | Peak — 9am weekday |
| Canary / staged-rollout coverage | Not covered |

## Confidence

**deployment_confidence: MEDIUM**

Two independent `High` triggers: critical-path blast radius (rollback plan in place, so not
`Critical`) and peak-traffic deploy with no canary coverage.
```

### Scenario: Degraded path — evidence gap

**Caller:** "Assess deployment risk for: schema migration on `billing` adding a composite index."
(No `rollback_plan` supplied; nothing discoverable in the repository either.)

**Agent:**
1. Inputs — `change_description` and `migration_steps` supplied; `rollback_plan` absent, defaults
   to "None stated" per [workflow/inputs.md](workflow/inputs.md).
2. Analyze — adding a composite index is reversible (a drop-index is straightforward), but Rollback
   complexity cannot be assessed at all — no `rollback_plan` supplied and nothing found in the
   repository's runbooks/migration tooling. This is recorded as an explicit evidence gap, not
   assumed safe.
3. Report — the Rollback-complexity gap floors the verdict at `High` per
   [reference/report-format.md § Rules](reference/report-format.md#rules), even though the
   migration itself is reversible; `deployment_confidence` capped at `LOW`.

**Expected fragment:**

```markdown
# Deployment Risk Review — billing composite index migration

**Risk: High**

## Rollback complexity

| Dimension | Finding |
|-----------|---------|
| Rollback plan | None stated — evidence gap; not discoverable in repository runbooks |
| Speed / safety | Unknown |

## Confidence

**deployment_confidence: LOW**

Rollback complexity is an evidence gap on a schema-migration change — verdict floored at `High`
until a rollback plan is supplied or found, even though the migration itself is reversible.
```

### Scenario: Cross-skill handoff

**Caller:** "Assess deployment risk for: the `checkout-service` payment-retry change we shipped
last night — actually, it already broke prod this morning, can you tell me what happened?"

**Agent:**
1. Inputs — `change_description` supplied, but the caller's own text reveals the deploy already
   happened and an incident is already in progress.
2. Analyze — this skill only assesses risk **before** shipping; it does not investigate confirmed
   incidents. No Analyze/Report is run for a post-incident question.
3. Report — skill declines to produce a pre-ship risk verdict for an already-shipped, already-
   broken change and offers the cross-skill handoff per
   [SKILL.md § Cross-skill escalation](SKILL.md#cross-skill-escalation).

**Expected fragment:**

```markdown
This deploy already shipped and something broke — that's a job for **incident-triage-agent**, not
a pre-ship risk review.

**Handoff → incident-triage-agent**
- Service: `checkout-service`
- Trigger: payment-retry change shipped last night, incident reported this morning
- Ask: "RCA for `checkout-service` — payment-retry deploy regression"
```
