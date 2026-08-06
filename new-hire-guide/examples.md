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
| 9 | "Onboard Priya, she's joining fraud-review" (one matched repo's GitLab squad disagrees with its Datadog team) | Run tour § 2 matches that repo via the **Datadog-team** column, not GitLab squad; § 4 surfaces the `SQUAD_MAP.md` § Conflicts row plainly in `ONBOARDING_TOUR.md` § Notes, not resolved either way |
| 10 | "Onboard Marcus to collections — domain-comprehension already ran on this workspace last month" | `workspace_root` already has `manifest.yaml`; Run tour § 3 lets domain-comprehension resolve its own mode (`RESUME`/`DELTA`) exactly as a direct invocation would, still unscoped |
| 11 | "While you're at it, who owns fraud-review-service?" (asked mid-tour, repo outside the new hire's matched squad) | **Handoff → squad-map** — one-off ownership lookup on a `SQUAD_MAP.md` row this run already produced, not part of the tour itself |

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

### Scenario: Squad matched via the Datadog-team lens, with a Conflicts hit

**Caller:** "Onboard Priya, she's joining fraud-review" — `workspace_root: ./services` (same workspace as
Jane's tour above; `SQUAD_MAP.md` already covers it in full, unscoped, from that earlier run)

**Agent:**

1. Inputs — `new_hire: {name: Priya, squad: fraud-review}`
2. Run tour § 1 — `SQUAD_MAP.md` exists and the repo census is unchanged, so squad-map's own
   `refresh: false` default skips re-query (same reuse rule as Jane's run)
3. Run tour § 2 — compares `fraud-review` case-insensitively against **both** the GitLab-squad and
   Datadog-team columns, per repo:
   - `fraud-review-service`: GitLab squad `fraud-review` — matches directly
   - `legacy-fraud-triage`: GitLab squad `legacy-ops` does **not** match, but Datadog team `fraud-review`
     does — matched via the Datadog-team lens only. This is exactly why step 2 checks both columns instead
     of requiring both to agree: requiring both would have under-matched this repo. `legacy-fraud-triage`
     also has a `SQUAD_MAP.md` § Conflicts row (`legacy-ops` GitLab squad ≠ `fraud-review` Datadog team,
     per [squad-map/reference/gold-squad-map-excerpt.md](../squad-map/reference/gold-squad-map-excerpt.md)'s
     Conflicts format) — carried into the tour, not resolved
4. Run tour § 3 — domain-comprehension unscoped, `QUICK` (default)
5. Run tour § 4 — curates down to `fraud-review-service` and `legacy-fraud-triage`; the Conflicts row
   touching `legacy-fraud-triage` is cross-checked per
   [tour-format.md](reference/tour-format.md)'s "never resolved on the caller's behalf" rule and surfaced
   in `## Notes`, not silently picked one way

**Expected fragment:**

```
# Onboarding tour — Priya

**Squad:** fraud-review

## Your repos

| Repo | Purpose | Confidence |
|------|---------|------------|
| fraud-review-service | Case-management API for the manual fraud-review queue — assigns and tracks reviewer decisions | MEDIUM |
| legacy-fraud-triage | Pre-filters flagged transactions before they reach the manual review queue | LOW |

## Squad contacts

GitLab squad: fraud-review (fraud-review-service) / legacy-ops (legacy-fraud-triage) · Datadog team:
fraud-review (both repos)

## Go deeper

- Full domain map: [EXEC_SUMMARY.md](EXEC_SUMMARY.md)
- Squad ownership detail: [SQUAD_MAP.md](SQUAD_MAP.md)

## Notes

`legacy-fraud-triage` appears in `SQUAD_MAP.md` § Conflicts — GitLab squad `legacy-ops` disagrees with
Datadog team `fraud-review`. It matched into this tour on the Datadog-team lens (Run tour § 2). Confirm
ownership with both teams before treating it as fully fraud-review's — this tour surfaces the conflict as
squad-map recorded it, it does not resolve it.
```

---

### Scenario: Resumed engagement — domain-comprehension reuses a prior manifest

**Caller:** "Onboard Marcus, he's joining collections — domain-comprehension already ran on this workspace
for Jane's tour last month, just pick up from there" — same `workspace_root: ./services`

**Agent:**

1. Inputs — `new_hire: {name: Marcus, squad: collections}`, `delivery_mode` inferred from the caller's own
   phrasing and passed through to domain-comprehension unchanged, per
   [workflow/inputs.md](workflow/inputs.md) — this skill does not itself decide between `RESUME`/`DELTA`,
   it only relays what the caller said
2. Run tour § 1 — `SQUAD_MAP.md` reused (`refresh: false`, unchanged census)
3. Run tour § 2 — filters for `collections`: `collections-service`, `dunning-scheduler` match
4. Run tour § 3 — invokes domain-comprehension unscoped on `workspace_root`, which already has
   `manifest.yaml` from the prior engagement. Per
   [workflow/run-tour.md](workflow/run-tour.md) § 3, "domain-comprehension resolves its own mode per its
   own `RESUME`/`DELTA` rules, same as any direct invocation — this skill neither forces nor blocks that."
   No repo's `HEAD` SHA changed since that manifest, so domain-comprehension's own `DELTA` procedure
   (`domain-comprehension/workflow/inputs.md` § Delivery mode — "Re-run phases for repos whose HEAD SHA
   changed since last manifest") finds nothing to re-run and reuses `EXEC_SUMMARY.md` as-is
5. Run tour § 4 — curates that reused, still-unscoped `EXEC_SUMMARY.md` down to `collections-service` and
   `dunning-scheduler`, exactly as step 4 would curate a freshly generated one — the curation step doesn't
   care whether domain-comprehension's output is fresh or reused this run

**Expected fragment:**

```
Comprehension Phase: DELTA — 0/44 repos changed since last manifest | Next: reuse EXEC_SUMMARY.md
```

```
# Onboarding tour — Marcus

**Squad:** collections

## Your repos

| Repo | Purpose | Confidence |
|------|---------|------------|
| collections-service | Orchestrates overdue-balance collection workflows and payment-plan offers | MEDIUM |
| dunning-scheduler | Schedules and rate-limits dunning notices per collections-service's workflow state | MEDIUM |

## Squad contacts

GitLab squad: collections · Datadog team: collections

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

### Scenario: Handoff — one-off ownership lookup mid-tour

**Caller:** After `ONBOARDING_TOUR.md` for Jane (payments squad) has already been written: "While I have
you — who owns `fraud-review-service`? Jane's going to need to file a ticket against it in her first
week."

**Agent:** `fraud-review-service` is not one of Jane's matched repos (Run tour § 2 matched only
`api-payments`, `payments-worker`, `payments-ledger` for `payments`) — a one-off ownership question for a
repo outside the tour is exactly the "Caller wants a one-off ownership lookup, not a tour" row in
[SKILL.md](SKILL.md) § Cross-skill escalation, which routes to **squad-map** directly (this skill never
computes ownership itself — see SKILL.md § When to use / NOT to use). squad-map already ran unscoped in
Run tour § 1, so `SQUAD_MAP.md` already covers `fraud-review-service` — the handoff is a lookup against
that existing file, not a fresh squad-map invocation, unless the caller also wants it refreshed.

**Expected fragment:**

```
**Handoff → squad-map**
- Workspace: `./services`
- Trigger: caller asked about a repo outside the new hire's matched squad (`fraud-review-service` ∉
  {api-payments, payments-worker, payments-ledger})
- Evidence: SQUAD_MAP.md (already produced this run, Run tour § 1) — fraud-review-service row
- Ask: "Who owns `fraud-review-service`?"
```

```
| fraud-review-service | acme/fraud/fraud-review-service | fraud-review | fraud-review-service | fraud-review | HIGH | GitLab get_project; Datadog search_datadog_services |
```

Handoff block shape: [cross-skill-escalation.md](../docs/skill-framework/shared/cross-skill-escalation.md)
§ 3, fields adapted to what this skill actually has (no service/env/window — a workspace and a repo name,
same adaptation domain-comprehension's own examples.md makes for its pr-review handoff).

---

### Scenario: Cross-skill — wrong entry point

**Caller:** "Who owns the payments service?"

**Agent:** Routes to **squad-map** directly — this is a one-off ownership lookup, not an onboarding tour
(see [SKILL.md](SKILL.md) § When to use / NOT to use).
