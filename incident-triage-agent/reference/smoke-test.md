# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a service incident-rca can investigate (≥1
observability MCP configured) and a workspace where squad-map already resolves that service.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation — Triage mode

> `event_type: page_triggered`, `service: <service>`, `triggered_at: <ISO-8601 UTC>`,
> `alert_title: <symptom>`, `severity: P2`

## Expected first output — Triage

1. **30-minute window announced**, UTC-suffixed, symmetric around `triggered_at`.
2. **incident-rca invoked** with the fast/no-Jira-search phrasing per
   [workflow/triage.md](../workflow/triage.md).
3. **Triage doc** per [reference/triage-doc-format.md](triage-doc-format.md) — owning team (or UNKNOWN),
   top hypothesis (or no-defensible-root-cause), Gaps section present even if empty.

## Invocation — Postmortem mode

> `event_type: incident_resolved`, `service: <service>`, `triggered_at: <ISO-8601 UTC>`,
> `resolved_at: <ISO-8601 UTC>`

## Expected first output — Postmortem

1. **Full incident window announced** (`triggered_at`–`resolved_at`, extended to ≥30 min if shorter).
2. **incident-rca invoked** at full thoroughness (no Jira-search skip) per
   [workflow/postmortem.md](../workflow/postmortem.md).
3. **Postmortem draft** per [reference/postmortem-format.md](postmortem-format.md) — incident-rca's full
   report with action-table Owner columns filled from squad-map (or left `<team>` with a Gaps note on
   UNKNOWN).

## Pass criteria (both modes)

- No application source modified; no remediation; no live Jira/Slack/PagerDuty posts.
- Every gate incident-rca or squad-map stops at is answered per
  [reference/unattended-gate-policy.md](unattended-gate-policy.md) — never left hanging.
- Owner never stated with more certainty than squad-map actually returned.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| No observability MCP configured for incident-rca | Doc still produced, states the MCP gap plainly (gate #4) |
| squad-map HARD STOPs (no config) | Doc still produced, owner `UNKNOWN`, noted in Gaps |
| Sparse signal / multi-site ambiguity | Doc still produced, confidence capped, ambiguity noted in Gaps |
