# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | User says | Behavior |
|---|-----------|----------|
| 1 | "Onboard Jane, she's joining the payments squad" (payments matches 4 `SQUAD_MAP.md` rows) | Inputs → Run tour → squad-map (reuse or fresh) → domain-comprehension QUICK scoped to those 4 repos → `ONBOARDING_TOUR.md` |
| 2 | Same, but no `SQUAD_MAP.md` exists yet for this workspace | Inputs → Run tour § 1 → squad-map runs fresh, including its own live `squad_path_segment` HARD STOP if unconfigured — this skill does not pre-answer it |
| 3 | "Onboard Sam, he's joining `paymnets`" (typo — zero `SQUAD_MAP.md` matches) | Inputs → Run tour § 2 → asks for confirmation, listing the real squad names found — no tour produced yet |
| 4 | "Give Jane the full deep-dive, not just quick orientation" | `delivery_mode: FULL` passed through to domain-comprehension unchanged |
| 5 | domain-comprehension's Session 0 scope/budget checkpoint fires mid-run | Presented live to the user, unscripted — this skill has no gate-policy override (contrast with pr-gatekeeper/incident-triage-agent/backlog-runner) |
| 6 | "Who owns the payments service?" | **Wrong skill** → squad-map directly |
| 7 | "Map the payments domain" (org-wide, not scoped to one person) | **Wrong skill** → domain-comprehension directly |
| 8 | New hire's squad genuinely owns zero repos yet (user confirms after the zero-match ask) | `ONBOARDING_TOUR.md` § Notes records this plainly — § Your repos is never silently empty with no explanation |

---

### Scenario: Normal onboarding — happy path

**Caller:** "Onboard Jane, she's joining the payments squad" — `workspace_root: ./services`

**Agent:**

1. Inputs — `new_hire: {name: Jane, squad: payments}`, `workspace_root` resolved
2. Run tour § 1 — invokes squad-map auto-discover; `SQUAD_MAP.md` already exists and repo list
   unchanged, so squad-map's own `refresh: false` default skips re-query
3. Run tour § 2 — filters `SQUAD_MAP.md` for `payments` in either the GitLab-squad or Datadog-team
   column: `api-payments`, `payments-worker`, `payments-ledger` match
4. Run tour § 3 — invokes domain-comprehension, `delivery_mode: QUICK`,
   `domain-config.yaml scope.seed_repos: [api-payments, payments-worker, payments-ledger]`
5. domain-comprehension's Session 0 scope/budget checkpoint fires; the person who invoked this skill
   approves it directly, same as running domain-comprehension themselves
6. Run tour § 4 — `ONBOARDING_TOUR.md` written

**Expected fragment:**

```
# Onboarding tour — Jane

**Squad:** payments

## Your repos

| Repo | Purpose | Confidence |
|------|---------|------------|
| api-payments | Public payment-initiation API, validates + queues payout requests | MEDIUM |
| payments-worker | Consumes payout queue, calls payout rail, updates status | MEDIUM |
| payments-ledger | Authoritative ledger of payment state transitions | MEDIUM |

## Squad contacts

GitLab squad: payments (acme/payments/*) · Datadog team: payments-platform

## Go deeper

- Full domain map: [EXEC_SUMMARY.md](EXEC_SUMMARY.md)
- Squad ownership detail: [SQUAD_MAP.md](SQUAD_MAP.md)
```

---

### Scenario: Zero-match squad name

**Caller:** "Onboard Sam, he's joining `paymnets`" (typo)

**Agent:** Run tour § 2 finds zero rows matching `paymnets` in either column. Does **not** produce an
empty tour. Instead:

**Expected fragment:**

```
No repos found for squad "paymnets". Squads that do appear in SQUAD_MAP.md: payments, collections,
disbursement, fraud-review. Did you mean one of these?
```

---

### Scenario: Cross-skill — wrong entry point

**Caller:** "Who owns the payments service?"

**Agent:** Routes to **squad-map** directly — this is a one-off ownership lookup, not an onboarding tour
(see [SKILL.md](SKILL.md) § When to use / NOT to use).
