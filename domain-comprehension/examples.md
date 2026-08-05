# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | User says | Behavior |
|---|-----------|----------|
| 1 | "Comprehend disbursement in `/Users/me/Projects` — fintech-payout pack" | Session 0 → 0b (MCP) → full pipeline |
| 2 | "Map the payments domain — quick orientation only" | `QUICK` mode: Session 0 + P0 + draft five questions |
| 3 | "Resume domain comprehension" | Read `PROGRESS.md`; continue from Next action |
| 4 | "How does onboarding flow end-to-end?" (multi-repo) | Session 0 with generic five questions; FULL mode |
| 5 | "RCA for outage yesterday" | **Wrong skill** → incident-rca |
| 6 | "Review MR !482" | **Wrong skill** → pr-review |

---

## What a finished run looks like

`EXEC_SUMMARY.md` is the "start here" deliverable — five questions answered with evidence and
confidence, regardless of delivery mode. This is what a completed `QUICK` run produces (full shape:
[reference/gold-exec-summary-excerpt.md](reference/gold-exec-summary-excerpt.md)):

```
# Executive Summary — Disbursement Platform

**Overall confidence:** MEDIUM · **Delivery mode:** QUICK · **Last updated:** 2026-07-07

## Five questions

| # | Question | Answer | Confidence |
|---|----------|--------|------------|
| Q1 | What does this domain do? | Initiates and tracks loan disbursements to borrower accounts | MEDIUM |
| Q2 | Who owns the data? | `Disbursement` aggregate authoritative in `api-disbursement` | MEDIUM |
| Q3 | Critical path? | Create disbursement → validate → payout rail → status webhook | MEDIUM |
| Q4 | Biggest risks? | Dual-write between ledger and disbursement status (see RISK_MAP) | LOW |
| Q5 | What is unknown? | Fraud rule engine integration — no in-repo client | UNKNOWN |

## Engineering Leader Summary

Disbursement is a medium-complexity payments subdomain with clear service boundaries but incomplete
runtime validation for the payout rail. Safe for onboarding reads; do not change money movement without
P2b exercise evidence.
```

---

### Scenario: Fintech payout — Session 0 bootstrap

**User:** "Comprehend the disbursement subsystem in `/Users/luckyjain/Projects` using the fintech-payout domain pack. FULL first pass."

**Agent:**

1. Inputs — `workspace_layout: sibling-repos`, load [fintech-payout.md](reference/domain-packs/fintech-payout.md)
2. Session 0 — census ~44 repos, classify, keyword sweep, draft Q1–Q5 → `EXEC_SUMMARY.md`
3. Session 0b — invoke **squad-map** skill → `SQUAD_MAP.md` (GitLab squad + Datadog team)
4. Scope checkpoint — report tier counts; ask user to approve P0.5 mechanical scope
4. P0 → P5 per [phase-index.md](reference/phase-index.md); P2b validates flow against Datadog deps

**Expected Session 0 fragments:**

```
Comprehension Phase: Session 0 complete | Next: P0
Five questions: Q1 DRAFT, Q2 DRAFT, Q3 DRAFT, Q4 DRAFT, Q5 DRAFT
Repos: 12/44 scanned (inventory in progress)
```

```
### Q1 — What service actually moves money?
Evidence: (pending — top hits from hdfc-bank-service, disbursement-service grep)
Conclusion: (draft)
Confidence: LOW
```

```
Comprehension Phase: Session 0b complete | Next: P0
Repos: 38/44 squad-mapped (6 no Datadog service)
```

```
| api-disbursement | mpokket/disbursement/api-disbursement | disbursement | neo-disbursement-service | disbursement-platform | HIGH |
```

---

### Scenario: MCP degraded — GitLab only

**User:** "Build ground truth for the auth domain in this repo."

**Agent:** GitLab ✅, Datadog ❌ → GitLab squad column filled; Datadog team UNKNOWN; note in `SQUAD_MAP.md` header.

---

### Scenario: Monorepo auth domain

**User:** "Build ground truth for the auth domain in this repo."

**Agent:**

1. `workspace_layout: single-repo` or `monorepo`
2. Proposes generic five questions from [domain-config-schema.md](reference/domain-config-schema.md); user confirms
3. `domain-config.yaml` with `map_file: AUTH_MAP.md`

---

### Scenario: P2b — runtime architecture validation

**Context:** P2 happy path documents `api-disbursement → orchestration-disbursement → hdfc-bank-service`.

**Agent:**

1. `search_datadog_service_dependencies(service: "neo-disbursement-service", direction: downstream)`
2. Compare edges to P2 sequence + `critical_paths` from fintech-payout pack
3. Write `{map_file}` § Runtime validation — `CONFIRMED` / `RUNTIME_ONLY` / `CODE_ONLY` per hop

**Expected fragment:**

```
| api-disbursement → orchestration-disbursement | ✓ | ✓ | ✓ | CONFIRMED | HIGH | search_datadog_service_dependencies downstream |
```

---

### Scenario: Resume after P0.5

**User:** "Continue domain comprehension."

**Agent:**

1. Read `PROGRESS.md` — Last phase: P0.5 partial
2. Skip repos in `manifest.json` with matching branch+sha
3. Resume Tier 2 graphs → P1

---

### Scenario: Security finding handoff

After P3b flags hardcoded credentials in `api-disbursement`:

```
**Handoff → pr-review**
- Service: api-disbursement
- Trigger: hardcoded API key in config (P3b)
- Evidence: api-disbursement/src/.../application.yml (path only)
- Ask: "Review MR !{iid} for credential exposure in api-disbursement"
```

See [cross-skill-escalation.md](../docs/skill-framework/shared/cross-skill-escalation.md).
