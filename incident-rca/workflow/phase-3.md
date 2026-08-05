---
workflow_version: 1.0
phase: 3
produces:
  - jira_issues
  - known_issue_matches
  - recurrence_history
  - query_signals
consumes:
  - from_time
  - to_time
  - service
  - symptom
  - jira_key
  - mcp_profile
---

# Phase 3 — Ticket / human context (Jira)

**Read this file** at the start of Phase 3.

> **Precondition — project keys:** `INC` and `OPS` in the JQL below are **example** keys. Before running
> JQL, ask the user for their incident/ops project keys when unknown. If a query returns zero results,
> do not give up — common alternatives: `INFRA`, `ONCALL`, `ALERT`, `P1`. Use the same confirmed keys for
> recurrence JQL in step 5.

1. `getAccessibleAtlassianResources` → `cloudId` (probe each Atlassian server if more than one).
2. `searchJiraIssuesUsingJql` (adjust project keys to your org):

```text
project IN (INC, OPS) AND created >= "<from_date>" AND created <= "<to_date>"
  AND (summary ~ "<symptom>" OR description ~ "<symptom>" OR labels = "<service>")
ORDER BY created DESC
```

3. If `jira_key` was provided, Phase 0b already anchored the window — still `getJiraIssue` for
   comments/status.
4. Collect into `jira_issues`.
5. **Recurrence check:** run a second JQL query over the last 90 days to detect systemic patterns:

```jql
project IN (INC, OPS) AND summary ~ "<symptom>" AND created >= -90d ORDER BY created DESC
```

If **3 or more** similar incidents are found, escalate the report severity to **"Systemic / requires architectural fix"** and add a `recurrence_history` field to the evidence JSON with the matched ticket keys and dates.

### Recurrence similarity filter (same failure mode)

JQL text match alone causes false positives (keyword overlap). Before counting toward the **3+ systemic**
threshold, confirm each matched ticket is the **same failure mode**:

| Criterion | Pass | Fail (exclude from count) |
|-----------|------|---------------------------|
| **Symptom match** | Summary/description mentions same error class (5xx on same endpoint, same OOM, same lag) | Generic keyword only ("timeout", "error") |
| **Service/component** | Same service, deployment, or consumer group | Different service, only shared infra keyword |
| **Signal overlap** | Ticket comments or description mention same stack trace / error message as current incident | Unrelated root cause in ticket body |

Require **≥2 of 3** criteria for a ticket to count. Record excluded tickets in Gaps with reason
(*"INC-123 excluded — different service"*). Only tickets passing the filter increment the systemic count.

## Query investigation (saturation / search / DB)

When Phase 1 `infra_signals` or the symptom indicate **query-engine saturation** (OpenSearch,
Elasticsearch, PostgreSQL, MySQL, Redis, thread-pool rejections, slow queries), run the full pipeline in
[reference/query-investigation.md](../reference/query-investigation.md) **before** Phase 4.

**OpenSearch/Elasticsearch:** Phase 1 already ran the required `aggregate_spans` pass (`service:elasticsearch`,
group by `resource_name` + `@base_service`) — reuse `query_signals[]`; Phase 3 continues with logs, DBM,
and engine slowlog gaps only.

Collect into `query_signals[]` (optional evidence field) and `evidence_links[]`. Do not leave immediate
trigger **Unknown** without documenting every investigation attempt.

Announce checkpoint:

> **Query investigation:** APM spans ✓/✗, log aggregation ✓/✗, DBM ✓/✗ — top query: `<summary or none>`.

## Phase 3 checkpoint (before Phase 4)

**Exit:** [phase-exit-criteria.md](../reference/phase-exit-criteria.md) §Phase 3 before Phase 4.

### Timeline assembly (required before Phase 4)

Merge signals from Phases 1–3 into chronological **timeline_events** for the report **Unified timeline**:

| Type | Source fields |
|------|---------------|
| `deploy` | `deploy_events[]` |
| `error_signal` | `error_signals[]` |
| `infra_signal` | `infra_signals[]` |
| `jira` | `jira_issues[]` |
| `remediation` / `recovery` | Jira comments, change stories, user input |

Sort by timestamp ascending. Assign **Evidence quality** per row — same rules as evidence matrix
([evidence-quality.md](../reference/evidence-quality.md)). Flag gaps (*"No remediation row — mitigation unknown"*)
rather than omitting the timeline section.

### Detection metadata (for Detection analysis section)

Record when discoverable:

| Field | Source |
|-------|--------|
| `detected_by` | customer report / pager / synthetic / Slack / on-call |
| `symptom_onset_at` | first error_signal timestamp |
| `first_alert_at` | Datadog monitor / PagerDuty / Jira created_at |
| `mttd_minutes` | first_alert_at − symptom_onset_at (or Unknown) |

Announce Jira/recurrence results. If Phases 1–3 combined still lack observability signals, remind user
Phase 4 will be blocked unless they want a partial report.

**Optional known-issues cross-check:** if the user points to a `KNOWN_ISSUES.md` (repo-relative), read
it and record `known_issue_matches`. Do not assume an absolute path or a file that may not exist.
