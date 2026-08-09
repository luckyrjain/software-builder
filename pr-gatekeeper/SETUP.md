# pr-gatekeeper — Setup


## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | GitLab MCP (via pr-review), webhook receiver (host infra) |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
## Ambient discovery is deliberately disabled

Unlike pr-review, this skill sets `disable-model-invocation: true` — it does not auto-apply from a
human's natural-language chat turn. It's meant to be invoked explicitly, with a structured push-webhook
payload, by the automation described below. A human asking to review an MR interactively should keep
routing to **pr-review** directly.

## Install

```bash
cd software-builder
make install-pr-gatekeeper
```

This chains `make install-pr-review` first — pr-gatekeeper has no review logic of its own and is useless
without pr-review installed alongside it. Restart Cursor so both skills reload.

### Claude Code

```bash
cd software-builder
make install-claude-pr-gatekeeper
```

No restart needed. See [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/pr-gatekeeper.mdc` and `.kiro/steering/pr-gatekeeper.md`
point Cursor/Kiro at `pr-gatekeeper/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| pr-review installed and configured | GitLab MCP with write access for `full`/`summary-only` posting — see [pr-review/SETUP.md](../pr-review/SETUP.md) |
| A push-webhook handler | Registers the GitLab webhook and invokes an agent session with this skill — see § Integration contract |

## Integration contract (for whoever builds the webhook handler)

This repo ships **agent instructions**, not a running webhook receiver — same boundary as
who-owns-x-bot's Slack handler. The handler you build:

1. Registers a GitLab **Push Events** webhook on the project(s) you want auto-reviewed, pointed at your
   handler's endpoint.
2. On each delivery, resolves the pushed branch to an open MR (GitLab's push webhook payload does not
   always include the MR directly — you may need `GET /projects/:id/merge_requests?source_branch=...` to
   find it). No open MR → no-op.
3. **The handler owns `head_sha` dedupe state — pr-gatekeeper does not persist anything itself.** Track,
   per MR, the last `head_sha` you dispatched to pr-gatekeeper (a row in whatever store the handler
   already uses for webhook state). On each delivery, pass that stored value as
   `last_processed_head_sha` alongside `project`, `merge_request_iid`, the new `head_sha`, and
   `auto_post_authorized` — [workflow/inputs.md](workflow/inputs.md)'s short-circuit compares against
   whatever you pass here, it has no other source. After a run completes (posted or held — both count as
   "processed"), update your stored value to the new `head_sha`.
4. Implements the **deterministic-reply protocol** pr-gatekeeper's workflow depends on — see
   [reference/auto-post-policy.md § The protocol](reference/auto-post-policy.md#the-protocol-every-pr-review-ask-point-gets-one-deterministic-answer-never-a-hang)
   for the full, exhaustive numbered list (currently 7 items — the opening invocation itself plus 6
   stop-and-wait gates: merged/closed-MR stop, early 200-file cap warning, pagination-cap hit,
   baseline-staleness offer, Phase 3 posting confirmation, and the post-Phase-5 Jira/Slack offers): send
   the opening invocation, then answer **every** gate pr-review's session stops at with its one
   designated reply from that list. Never send any other reply, never
   invent an answer to a gate not on the list, and never leave a stopped session unanswered.
5. When the run reports a routed notification instead of a posted comment, deliver it to wherever
   § Config points (Slack channel, email, etc.) — pr-gatekeeper's own output is just text, the handler
   does the actual delivery, same division of labor as who-owns-x-bot's Slack `response_url` posting.
6. If your GitLab instance is known to redeliver the same webhook, debounce at the handler level too
   (skipping the agent invocation entirely is cheaper than relying on step 3's comparison alone).

## Config

| Setting | Where | Purpose |
|---------|-------|---------|
| `auto_post_authorized` | Handler config, per GitLab project, passed as input | Upfront human grant — never inferred. Off by default: a project only auto-posts once a maintainer explicitly turns it on. |
| Notification target | Handler config | Where a held (not auto-posted) review gets routed — reuses pr-review's own [manual-notify template](../pr-review/workflow/posting.md#manual-notify-template-no-slack-mcp) |

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against an MR
you're authorized to post to.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Every run ends in "Hold" even with `auto_post_authorized: true` | Check pr-review's own detected posting mode and draft state — `general-only` and drafts always hold, by pr-review's own design, regardless of authorization |
| Handler hangs waiting for a reply that never comes | Handler isn't answering every gate in the deterministic-reply protocol (§ Integration contract step 4) — a large MR or a stale incremental baseline stops pr-review just as surely as Phase 3 does |
| Re-reviews the same push repeatedly, or duplicate notifications | Handler isn't passing `last_processed_head_sha` (§ Integration contract step 3) — without it, `workflow/inputs.md` has nothing to compare the new `head_sha` against and can't short-circuit |
