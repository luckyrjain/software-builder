# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | User says | Behavior |
|---|-----------|----------|
| 1 | "Onboard Jane, she's joining the payments squad" (payments matches 4 `SQUAD_MAP.md` rows) | Inputs → Run tour → squad-map (reuse or fresh) → domain-comprehension **unscoped** → curate down to those 4 repos → `ONBOARDING_TOUR.md` |
| 2 | Same, but no `SQUAD_MAP.md` exists yet for this workspace | Inputs → Run tour § 1 → squad-map runs fresh, including its own live `squad_path_segment` HARD STOP if unconfigured — this skill does not pre-answer it |
| 3 | "Onboard Sam, he's joining `paymnets`" (typo — zero `SQUAD_MAP.md` matches) | Inputs → Run tour § 2 → asks for confirmation, listing the real squad names found — no tour produced yet |
| 4 | "Give Jane the full deep-dive, not just quick orientation" | `delivery_mode: FULL` passed through to domain-comprehension unchanged |
| 5 | domain-comprehension's Session 0 scope/budget checkpoint fires mid-run (not guaranteed under `QUICK` — see Run tour § 3) | Presented live to the user, unscripted — this skill has no gate-policy override (contrast with pr-gatekeeper/incident-triage-agent/backlog-runner) |
| 6 | "Who owns the payments service?" | **Wrong skill** → squad-map directly |
| 7 | "Help me onboard to the payments subsystem" (no person named) | **Wrong skill** → domain-comprehension directly — subsystem onboarding, not a new-hire tour (see [skill-routing.md](../docs/skill-framework/shared/skill-routing.md)) |
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
4. Run tour § 3 — invokes domain-comprehension **unscoped**, `delivery_mode: QUICK`, no `seed_repos` —
   same census, same Session 0b squad-map call it would make on a direct invocation
5. domain-comprehension's Session 0 scope/budget checkpoint fires (if `QUICK`'s own rules trigger it);
   the person who invoked this skill approves it directly, same as running domain-comprehension themselves
6. Run tour § 4 — curates `EXEC_SUMMARY.md`/P0 census down to the 3 matched repos, writes
   `ONBOARDING_TOUR.md`

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
