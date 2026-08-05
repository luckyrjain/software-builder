# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Webhook event | Behavior |
|---|------------------|----------|
| 1 | `page_triggered`, service resolves cleanly, squad-map resolves cleanly | Inputs → Triage → 30-min window RCA + owner → triage doc |
| 2 | `page_triggered`, incident-rca finds no observability MCP | Inputs → Triage → doc states the MCP gap plainly (gate #4), still produced |
| 3 | `page_triggered`, squad-map HARD STOPs (no config) | Inputs → Triage → owner UNKNOWN, noted in Gaps, doc still produced |
| 4 | `page_triggered`, multi-site Datadog ambiguous | Inputs → Triage → queries all sites, confidence capped MEDIUM, ambiguity in Gaps |
| 5 | `page_triggered`, sparse signal | Inputs → Triage → "continue" answer, thinness noted in Gaps |
| 6 | `incident_resolved`, full window, Jira project keys configured | Inputs → Postmortem → full-thoroughness RCA (incl. Jira search) + owner-filled action tables |
| 7 | `incident_resolved`, Jira project keys unknown | Inputs → Postmortem → Jira search skipped, gap noted, draft still produced |
| 8 | `incident_resolved`, incident lasted 12 minutes | Inputs → Postmortem → window extended to 30 min per the width guarantee |
| 9 | Paging event `acknowledged` or `escalated` | Inputs short-circuit — no-op, neither mode fires |
| 10 | Missing `service` on any event | Inputs HARD STOP — log and exit, no guess |
| 11 | "RCA for neo-disbursement-service 14:00–16:00 UTC" typed in an interactive session | **Wrong skill** → incident-rca (this skill doesn't auto-invoke; see `disable-model-invocation`) |
| 12 | "Who owns neo-disbursement-service?" typed in an interactive session | **Wrong skill** → squad-map |

---

### Scenario: Triage — happy path

**Webhook:** `event_type: page_triggered`, `service: neo-disbursement-service`,
`triggered_at: 2026-08-05T14:22:00Z`, `alert_title: "5xx spike on transfer-money"`, `severity: P1`

**Agent:**

1. Inputs — all required fields present
2. Triage — window `14:02:00Z`–`14:32:00Z`; invokes incident-rca with its unmodified canonical phrasing;
   Phase 2's checkpoint fires and gets the `"skip Phase 3"` reply, jumping straight to Phase 4; invokes
   squad-map for `neo-disbursement-service`
3. incident-rca returns a HIGH-confidence `deploy_regression` hypothesis; squad-map returns `disbursement`
   squad, HIGH confidence
4. Assembles and routes the triage doc

**Expected fragment:**

```
# Triage — neo-disbursement-service — P1

**Page:** 5xx spike on transfer-money (PagerDuty alert ...)
**Window investigated:** 2026-08-05T14:02:00Z – 2026-08-05T14:32:00Z UTC
**Owning team:** disbursement (HIGH)

## Likely cause

Deploy regression (HIGH) — MR !482 introduced an NPE on the transfer-money validation path...
```

---

### Scenario: Postmortem — owner substitution

**Webhook:** `event_type: incident_resolved`, `service: neo-disbursement-service`,
`triggered_at: 2026-08-05T14:22:00Z`, `resolved_at: 2026-08-05T15:40:00Z`

**Agent:** Full-window RCA (incl. Jira search); squad-map resolves `disbursement`; incident-rca's
Corrective/Preventive-actions `<team>` placeholders and Post-RCA-actions' `<team/person>` placeholders
(Follow-up Jira, Update runbook rows only — not the PR review row's `<reviewer>`) get replaced with
`disbursement` — see [reference/postmortem-format.md](reference/postmortem-format.md) for the exact
per-table mapping.

---

### Scenario: Cross-skill — wrong entry point

**Caller:** (human, typing in an interactive session) "RCA for neo-disbursement-service 14:00–16:00 UTC"

**Agent:** This skill does not auto-invoke (`disable-model-invocation: true`); the request routes to
**incident-rca** directly, per incident-rca's own invocation table
([incident-rca/examples.md § Invocation](../incident-rca/examples.md)).
