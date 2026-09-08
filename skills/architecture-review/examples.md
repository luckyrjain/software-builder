# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|---------------|----------|
| 1 | `proposal_text` + `design_description` for a well-specified proposal, no material risk in any check, alternatives stated and justified | Inputs → Analyze → Report → `ARCHITECTURE_REVIEW_REPORT.md`, **Decision: Approved** |
| 2 | Same, but with one minor non-blocking follow-up (e.g. "revisit sharding at 5x current write volume") | **Decision: Approved with conditions**, condition named explicitly |
| 3 | A failure mode (dependency outage) has no stated detection or recovery plan | **Decision: Needs rework** — material, unresolved risk |
| 4 | `design_description` proposes single-region deployment while `proposal_text` requires multi-region, with no stated mitigation | **Decision: Rejected** — hard constraint violated, unmitigated |
| 5 | `proposal_text` absent | Inputs **HARD STOP** — ask, no Analyze |
| 6 | `design_description` absent | Inputs **HARD STOP** — ask, no Analyze |
| 7 | `design_description` is a single sentence, too sparse to evaluate failure modes | Failure modes recorded `Unknown` with reason named; **Decision: at least Needs rework** — evidence gap on a required check, never silently `Approved` |
| 8 | No `diagram_description` supplied for a multi-service design with cross-boundary data flow | Security trust-boundary row recorded `Unknown — no diagram supplied`; if no other gap, surfaces as a named condition under **Approved with conditions** |
| 9 | `proposal_text` states no alternatives were considered | Alternatives considered section records `Unknown — no alternatives stated`; counted toward **Needs rework** |
| 10 | "Design the API schema and data model for the notifications service" | **Wrong skill** → system-design directly |
| 11 | "Write the PRD for this feature" | **Wrong skill** → prd-architect directly |
| 12 | "Review the code changes in PR #482" | **Wrong skill** → pr-review directly |
| 13 | Decision `Approved`, caller asks whether the trust-boundary concern needs a deeper look | **Escalation** → security-review, with the specific concern this skill already found |
| 14 | Decision `Approved`, no conditions, caller wants to start building | **Escalation** → loop-task-implementer |

---

### Scenario: Clean happy path — full approval

**Caller:** `proposal_text: "Add a notifications service so users get email/SMS alerts on order status
changes. Must handle our current 50 req/s peak with headroom to 200 req/s over the next year."`,
`design_description: "A stateless notification-worker service polls an outbox table in the primary
Postgres DB every 2s, batches up to 500 rows, and fans out to email/SMS provider APIs with per-provider
rate limiting and exponential-backoff retry. Failed sends after 5 retries move to a dead-letter table,
alerting on-call via existing PagerDuty integration. Considered a Kafka-based event stream instead, but
rejected it for this scale — the outbox-poll pattern reuses the existing Postgres HA setup and avoids a
new piece of run-time infrastructure the team would need to operate."`

**Agent:**

1. Inputs — `proposal_text` and `design_description` both present; no `diagram_description`/
   `repo_context` supplied, noted as absent (not blocking — single-service design, no cross-boundary
   check depends on them here)
2. Analyze — decision rationale captured; scale limits: outbox-poll at 2s/500-row batches comfortably
   covers 200 req/s; failure modes: provider outage has retry + dead-letter + PagerDuty detection/
   recovery; security: single trust boundary (outbound to provider APIs), least-data considered; operability:
   reuses existing Postgres HA and PagerDuty, no new infra; alternatives: Kafka considered and rejected
   with a stated reason
3. Report — no material risk, no evidence gaps, alternatives justified → **Decision: Approved**

**Expected fragment:**

```
# Architecture review — notifications service

**Decision: Approved**

## Architecture decision

Adds a stateless notification-worker polling an outbox table in the primary Postgres DB, fanning out to
email/SMS provider APIs with per-provider rate limiting and retry, to alert users on order-status
changes.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| None found | — | — | — |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Request rate | Comfortably covers the stated 200 req/s target at 2s/500-row batches | `design_description`: "polls...every 2s, batches up to 500 rows" |
```

---

### Scenario: Rejected — unmitigated hard-constraint violation

**Caller:** `proposal_text: "This service handles regulated payment data and must remain available
during a full regional outage — multi-region active-active is a hard requirement."`,
`design_description: "Single-region deployment on us-east-1, with nightly cross-region backups."`

**Agent:**

1. Inputs — both fields present
2. Analyze — architecture decision: single-region design against a stated multi-region hard requirement;
   scale limits: not the blocking issue here; failure modes: a full regional outage is unrecoverable
   within the proposal's own availability requirement — nightly backups mean up to 24h of data loss and
   full downtime during a region failure, with no stated mitigation; security/operability: not the
   blocking issue; alternatives: none stated for meeting the multi-region requirement
3. Report — a hard constraint (`proposal_text`'s own multi-region requirement) is violated with no
   feasible fix within the design's own scope → **Decision: Rejected**

**Expected fragment:**

```
# Architecture review — payment data service

**Decision: Rejected**

> `Rejected — single-region deployment violates the proposal's own multi-region active-active
> requirement; nightly-backup recovery implies up to 24h data loss and full downtime during a regional
> outage, with no stated mitigation; see Failure modes below.`

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| Full regional outage | Standard infra monitoring | Restore from nightly backup — up to 24h data loss, full downtime until restore completes | Violates `proposal_text`'s stated multi-region active-active hard requirement; no mitigation stated in `design_description` |
```

---

### Scenario: Needs rework — multiple unresolved findings

**Caller:** `proposal_text: "Add a batch export job so enterprise customers can pull nightly usage
reports."`, `design_description: "A cron job runs nightly, queries the analytics warehouse, writes a CSV
to S3, and emails a signed download link to the customer's registered contact."`

**Agent:**

1. Inputs — both fields present, no diagram/repo context
2. Analyze — decision rationale captured; scale limits: no stated data-volume ceiling, but not flagged as
   blocking at this stage; failure modes: warehouse query failure or S3 write failure has **no stated
   detection or recovery** — job just doesn't run, customer isn't notified; security: signed link
   expiry/scope not stated; operability: no named owner for the nightly job; alternatives: `proposal_text`
   states none were considered
3. Report — two material gaps (failure-mode detection/recovery, no alternatives stated) and one
   evidence gap (no named operability owner) → **Decision: Needs rework**, all three named

**Expected fragment:**

```
# Architecture review — nightly usage export

**Decision: Needs rework**

> `Needs rework — no detection/recovery plan for a failed warehouse query or S3 write (see Failure
> modes); no operability owner named (see Operability); no alternatives stated in proposal_text/
> design_description (see Alternatives considered).`

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| Warehouse query or S3 write fails | Unknown — not stated | Unknown — not stated | Job silently doesn't run; customer not notified |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Nightly export job | Unknown — no team named in `proposal_text`/`design_description` | Unknown | — |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| Unknown — no alternatives stated in proposal_text/design_description | — | — |
```

---

### Scenario: Degraded path — design too sparse to evaluate failure modes

**Caller:** `proposal_text: "Speed up our search results."`, `design_description: "Add a cache in front
of the search API."`

**Agent:** Inputs resolves both fields (present, so not a HARD STOP), but Analyze cannot evaluate scale
limits, failure modes, security, or operability meaningfully from one sentence — what's cached, the
eviction policy, cache-miss behavior, and the failure mode of a stale or unavailable cache are all
unstated. Each under-specified check is recorded as an explicit `Unknown`, not a silently clean "none
found," per [workflow/analyze.md § Evidence gaps](workflow/analyze.md#evidence-gaps).

**Expected fragment:**

```
# Architecture review — search result caching

**Decision: Needs rework**

> `Needs rework — design_description is too sparse to evaluate failure modes, security, or operability
> (cache eviction policy, cache-miss behavior, and staleness handling are all unstated); see Failure
> modes, Security, and Operability below.`

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| Cache unavailable or serves stale results | Unknown — eviction/staleness policy not stated | Unknown — cache-miss/fallback behavior not stated | `design_description` gives no detail beyond "add a cache" |
```

---

### Scenario: Cross-skill handoff — approved, ready for implementation-level design

**Caller:** Follow-up on the notifications-service scenario above, after `ARCHITECTURE_REVIEW_REPORT.md`
lands on **Decision: Approved**. Caller asks: "Great — what's next?"

**Agent:** Decision is `Approved` with no open conditions — this skill's own scope stops at the
architecture decision, not the API/data-model shape of the notification-worker. Per
[SKILL.md § Cross-skill escalation](SKILL.md#cross-skill-escalation), offers the handoff:

```
Architecture review complete — Decision: Approved. This skill's scope ends here; the next step is
implementation-level design (API/data-model/component shape for the notification-worker) via
system-design, or straight to build via loop-task-implementer if no further design work is needed.
Which would you like?
```
