# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Webhook event | Behavior |
|---|------------------|----------|
| 1 | Push to MR !482, `auto_post_authorized: true`, pr-review detects `full` mode, MR not draft | Inputs → Gatekeep → "review and post" → skip condition met → posted, no Phase 3 prompt |
| 2 | Push to MR !482, `auto_post_authorized: true`, pr-review detects `general-only` | Inputs → Gatekeep → Phase 3 always prompts (pr-review's own rule) → "Hold — don't post" → routed notification |
| 3 | Push to MR !482, `auto_post_authorized: true`, MR is a draft | Inputs → Gatekeep → draft-MR warning prompts → "Hold — don't post" → routed notification |
| 4 | Push to MR !482, `auto_post_authorized: false` | Inputs → Gatekeep → no post phrase supplied → Phase 3 prompts → "Hold — don't post" → routed notification |
| 5 | Push with `head_sha` == caller-supplied `last_processed_head_sha` for !482 (duplicate webhook delivery) | Inputs short-circuit — Gatekeep never runs, no second pr-review invocation |
| 6 | Push to a branch with no open MR | Inputs short-circuit — no-op |
| 7 | Label added / comment posted on !482 (not a push event) | Inputs short-circuit — pr-gatekeeper only reacts to push events |
| 8 | "Review this MR" typed in an interactive chat session | **Wrong skill** → pr-review (this skill doesn't auto-invoke; see `disable-model-invocation`) |
| 9 | pr-review's own `chat-only` mode detected (read-only GitLab MCP) | Phase 3 skipped entirely by pr-review's own rules; nothing posted; routed notification same as a Hold outcome |
| 10 | Push to MR !482 with 250 changed files | Early 200-file cap warning fires first → `proceed`; pagination then hits the 200-file cap at page 2 → "review the partial boundary as-is" |
| 11 | Push is the 35th commit since !482's last reviewed baseline | pr-review's baseline-staleness offer fires → "continue incrementally" → declines the full-re-review offer |
| 12 | Webhook dispatches for !482, but it was merged/closed between the handler's check and pr-review's own fetch | pr-review's merged/closed state-check stop fires → declines the post-merge-audit confirmation → no review |
| 13 | Push to MR !482 with a linked Jira ticket, `jira_write_available: true` | Phase 5 renders normally; Jira write-back offer declines; Slack/Teams notification offer (if any) also declines — pr-gatekeeper's own routing is the only notification sent |

---

### Scenario: Auto-posted — happy path

**Webhook:** push to MR !482, `auto_post_authorized: true`

**Agent:**

1. Inputs — new `head_sha`, resolves to open MR !482
2. Gatekeep — invokes pr-review with "review and post !482 in acme/backend"; pr-review detects `full`
   mode, MR is not draft → skip condition met, Phase 3 never prompts
3. pr-review posts inline threads + summary note; Phase 5 executive summary renders
4. Outcome: posted, no notification needed

---

### Scenario: Held — general-only mode

**Webhook:** push to MR !482, `auto_post_authorized: true`, project's GitLab MCP is the official
`general-only` server

**Agent:** pr-review's Phase 0 shows the ⚠️ general-only warning; Phase 3 **always** prompts regardless
of phrasing → automation replies `"Hold — don't post"` → pr-review completes Phase 5 in chat only →
pr-gatekeeper routes the rendered review via the configured notification.

**Expected fragment (routed notification — `Full review:` carries the pasted executive summary, since
nothing posted to link to):**

```
Subject: MR !482 review — Comment

Reviewed 2026-08-05T14:02:00Z on head 9f1a2c3.
Recommendation: Comment
Blocking: None
Summary: Two medium findings, no criticals.
MR: https://gitlab.example.com/acme/backend/-/merge_requests/482
Full review: [pasted Phase 5 executive summary — findings table, root-cause groups, evidence]
```

---

### Scenario: Held — not authorized

**Webhook:** push to MR !482, `auto_post_authorized: false` (default — maintainer hasn't opted the
project in yet)

**Agent:** Opening message omits "review and post" → pr-review's Phase 3 prompts regardless of mode →
`"Hold — don't post"` → routed notification, same shape as the general-only case above.

---

### Scenario: Cross-skill — wrong entry point

**Caller:** (human, typing in an interactive session) "Review MR !482"

**Agent:** This skill does not auto-invoke (`disable-model-invocation: true`); the request routes to
**pr-review** instead, per pr-review's own invocation table
([pr-review/examples.md § Invocation](../pr-review/examples.md)).
