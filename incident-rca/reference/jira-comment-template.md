# Jira comment template (RCA complete)

Shared normative patterns: [post-action-templates.md](../../docs/skill-framework/shared/post-action-templates.md) §1.

**Read-only:** offer this text for the user to paste. Do not auto-post unless the user explicitly requests and write tools are available.

## Comment body

```markdown
h3. RCA Summary — {{service}} {{window}}

*Primary hypothesis:* {{hypothesis}} ({{confidence}})
*Reason:* {{one_line_rationale}}
*Evidence gaps:* {{gaps_or_none}}

h4. Timeline
* {{time_1}} — {{event_1}}
* {{time_2}} — {{event_2}}

h4. Recommendations
# {{action_1}}
# {{action_2}}

h4. Follow-up
* Jira: {{inc_key_or_new}}
* Runbook: {{runbook_path_or_none}}
* MR review: {{mr_iid_or_none}}
```

## Ticket update fields

| Field | Value |
|-------|-------|
| Label | `rca-complete` |
| Priority | Unchanged unless P1 outage confirmed |
| Comment | Paste template above |
| Attachment | Optional — export `evidence.json` |

## Example (filled)

```markdown
h3. RCA Summary — neo-disbursement-service 2026-06-28 14:00–16:00 UTC

*Primary hypothesis:* deploy_regression (HIGH)
*Reason:* Prod deploy MR !482 at 14:20 UTC preceded 12% 5xx spike at 14:45; diff touched TransferMoneyHandler.
*Evidence gaps:* None

h4. Timeline
* 14:20 — Production deploy MR !482 (Jenkins #1234)
* 14:45 — 5xx spike on transfer-money (Datadog)
* 14:50 — INC-4521 opened

h4. Recommendations
# Roll back or hotfix MR !482 validation change
# Add integration test for transfer-money edge case

h4. Follow-up
* Jira: INC-4521
* Runbook: —
* MR review: !482
```
