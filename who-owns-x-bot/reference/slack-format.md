# Slack reply format

**Normative.** The exact three reply shapes `workflow/lookup.md` must produce. Plain text with Slack
`mrkdwn` (`*bold*`, `` `code` ``) — no Block Kit JSON required, though a caller may wrap these strings in
a `section` block if it prefers rich formatting.

## Resolved

```
:white_check_mark: *<query>* → *<squad>* squad (<confidence> confidence)
<evidence, one line — e.g. "GitLab namespace acme/disbursement/api-disbursement; Datadog team disbursement-platform">
```

Example:

```
:white_check_mark: *api-disbursement* → *disbursement* squad (HIGH confidence)
GitLab namespace acme/disbursement/api-disbursement; Datadog team disbursement-platform
```

## Ambiguous

Two sub-cases, same shape — a short list, never a silent pick:

```
:warning: *<query>* — ownership is unclear, need a human to confirm:
<bulleted list of up to 3 candidates, each with its own confidence/evidence>
```

Conflict example (GitLab squad ≠ Datadog team for the same repo):

```
:warning: *legacy-ledger* — GitLab and Datadog disagree, need a human to confirm:
• GitLab squad: *payments* (namespace acme/payments/legacy-ledger)
• Datadog team: *collections* (service tag on legacy-ledger-svc)
```

Multiple-match example:

```
:warning: *ledger* matched more than one repo — which did you mean?
• legacy-ledger → payments squad (HIGH)
• ledger-service → collections squad (HIGH)
• ledger-archive → UNKNOWN
```

## Unknown

Never fabricate a squad name. Say plainly that it's unknown and point at a human fallback (the fallback
channel/contact is configured per Slack workspace — see [SETUP.md](../SETUP.md) § Config).

```
:grey_question: Couldn't find ownership for *<query>*. <fallback_contact from SETUP.md config>
```

Example:

```
:grey_question: Couldn't find ownership for *some-typo-repo*. Try #ask-platform.
```

## Usage hint (empty `query`)

Not one of the three shapes above — this is the Inputs HARD STOP reply, produced before Lookup runs:

```
Usage: /who-owns <repo-or-service-name>
```

## Rules

- Never include raw MCP tool names, internal squad-map phase names, or confidence-band jargon the
  requester wouldn't recognize — "HIGH confidence" is fine, "Phase 1 reconciliation" is not.
- Never post more than one message per invocation — this is a single-shot reply, not a thread.
- LOW confidence is folded into **Unknown**, not **Resolved** — see
  [workflow/lookup.md](../workflow/lookup.md) Step 3.
