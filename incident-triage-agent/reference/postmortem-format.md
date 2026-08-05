# Postmortem draft format (normative)

incident-rca's own [report-template.md](../../incident-rca/report-template.md) **verbatim**, in its own
mandatory section order — this skill adds nothing to the report body itself. The only original
contribution:

## Owner-column substitution

**The exact placeholder string differs by table** (report-template.md's actual text, not a uniform
`<team>` across all three — verify against the live template if it changes):

| Table | Owner-column placeholder | Substitute? |
|-------|---------------------------|--------------|
| **Corrective actions** | `` `<team>` `` | Yes — every row |
| **Preventive actions** | `` `<team>` `` | Yes — every row |
| **Post-RCA actions**, "Follow-up Jira" / "Update runbook" rows | `` `<team/person>` `` | Yes — those two rows only |
| **Post-RCA actions**, "PR review" row | `` `<reviewer>` `` | **No** — this is a named-person reviewer slot, not a team assignment; leave it as-is |

Replace the applicable placeholder with squad-map's resolved squad name for `service` — or leave it
unchanged **only** when squad-map returned `UNKNOWN`, with a note in the report's own
Gaps/investigation-follow-up section: *"Owning team could not be resolved (squad-map: UNKNOWN) — action
items need manual owner assignment."*

Never invent an owner squad-map didn't actually return, and never apply a different team than the one
squad-map resolved for `service` even if the report references other services in passing (e.g. a
downstream dependency) — owner substitution applies only to the primary `service` this postmortem is for.

## Header addition

Prepend one line above incident-rca's Executive summary section, not part of incident-rca's own template:

```markdown
> Postmortem draft — incident-triage-agent, <timestamp>. Investigation: incident-rca. Ownership:
> squad-map (<squad> / UNKNOWN, <confidence>). Full incident window: <triggered_at> – <resolved_at> UTC.
```

## Post-report offers

Same handling as triage mode — decline any live Jira/Slack/Confluence post incident-rca offers; append
the paste-ready blocks it would have posted as sections in this draft instead, per
[unattended-gate-policy.md § Post-report offers](unattended-gate-policy.md#post-report-offers-both-skills-always-declined).

## Rules

- **Never alter incident-rca's own findings, hypotheses, confidence, or conclusion** — this skill's only
  edit right is the Owner-column substitution and the header line above.
- One postmortem draft per `incident_resolved` event.
