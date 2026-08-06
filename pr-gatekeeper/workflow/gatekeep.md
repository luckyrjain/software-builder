---
workflow_version: 1.0
phase: gatekeep
produces:
  - review_outcome
consumes:
  - project
  - merge_request_iid
  - head_sha
  - auto_post_authorized
---

# Gatekeep — invoke pr-review, apply auto-post policy

**Goal:** Get pr-review to review this push, let its own rules decide whether posting happens, and route
the result correctly either way. No new review logic here — see
[SKILL.md](../SKILL.md) Non-goals and [reference/auto-post-policy.md](../reference/auto-post-policy.md).

## Steps

1. **Invoke pr-review** on `<merge_request_iid>` in `<project>`, per the opening-message rule in
   [reference/auto-post-policy.md § The protocol](../reference/auto-post-policy.md#the-protocol-every-pr-review-ask-point-gets-one-deterministic-answer-never-a-hang):
   `"review and post !<merge_request_iid> in <project>"` when `auto_post_authorized` is `true`,
   otherwise `"review !<merge_request_iid> in <project>"`. **Also pass `expected_head_sha: <head_sha>`**
   (this skill's own webhook-supplied input, per [workflow/inputs.md](inputs.md)) as a typed
   invocation field — [pr-review/workflow/inputs.md § Typed invocation](../../pr-review/workflow/inputs.md#typed-invocation-skill-to-skill-callers)
   compares it against the MR's actual `diff_refs.head_sha` in its own Phase 1 step 1 and stops with an
   anomaly if they differ, rather than silently reviewing whatever commit happens to be current. Without
   this, `head_sha` was accepted by this skill's own Inputs (for webhook-retry dedupe against
   `last_processed_head_sha`) but never checked against the commit pr-review actually reviewed — a second
   push landing between the webhook firing and pr-review's own `get_merge_request` call would review and
   potentially auto-post a review of a commit different from the one that triggered this run, with nothing
   in the output flagging the mismatch. Let pr-review run its own
   Inputs → Phase 0 → Phase 1 → Phase 2 → Phase 2–3 gate unchanged.

2. **On an `expected_head_sha` mismatch** (pr-review stops and reports the anomaly per its own Phase 1
   step 1 check): do not treat this as a normal Hold/decline outcome — route it through step 5's
   notification path with an explicit note that the review target moved mid-run (old SHA vs. the MR's
   actual current head) and that this run should be considered stale; a fresh webhook event for the new
   head will trigger its own run. Never retry silently within the same invocation.

3. **Answer every gate pr-review stops at, deterministically** — the full enumerated list is
   [reference/auto-post-policy.md § The protocol](../reference/auto-post-policy.md#the-protocol-every-pr-review-ask-point-gets-one-deterministic-answer-never-a-hang):
   merged/closed-MR stop → decline the post-merge audit; early 200-file cap warning → `proceed`;
   pagination-cap hit → "review the partial boundary as-is"; merge-conflict stop → decline (never ask
   to review the conflicted state); baseline-staleness offer → "continue incrementally"; Phase 3 (if it
   stops) → `"Hold — don't post"`. Never answer any gate with anything
   else, and never treat pr-review's continued silence past that as license to guess — only these
   designated replies. If a gate doesn't fire for this push, there is nothing to reply to at that
   point — continue.

4. **Let pr-review finish** through Phase 4 (if it ran) and Phase 5 — its own executive summary and
   `recommendation` (Approve/Comment/Request changes) always render, whether or not posting happened.
   **After Phase 5**, pr-review may still offer a Jira write-back and/or a Slack/Teams notification —
   decline both, per [reference/auto-post-policy.md § The protocol](../reference/auto-post-policy.md#the-protocol-every-pr-review-ask-point-gets-one-deterministic-answer-never-a-hang)
   item 7 — pr-gatekeeper's own notification path (step 5 below) is the only notification this run sends.

5. **Route the outcome:**
   - **Posted** (Phase 4 ran, skip condition was met) — done. pr-review's own posted thread/summary note
     is the deliverable; no further action.
   - **Not posted** (Hold reply, or `chat-only` render) — take pr-review's rendered chat output (findings
     summary, recommendation, Critical-finding banner if any) and send it via the configured notification
     path, reusing pr-review's own
     [manual-notify template](../../pr-review/workflow/posting.md#manual-notify-template-no-slack-mcp) —
     **populate its `Full review:` line with the pasted executive summary** (there is no GitLab link to
     use instead, since nothing posted — see
     [reference/auto-post-policy.md § When posting didn't happen](../reference/auto-post-policy.md#when-posting-didnt-happen)).
     See [SETUP.md](../SETUP.md) § Config for where the notification target is configured. **Never**
     silently drop a completed review, or send a notification stub without the executive summary, just
     because it didn't post — a human still needs to see the actual review.
   - **Stale (`expected_head_sha` mismatch)** — per step 2 above.

## Read-only boundary

Same as pr-review: read + comment only. Never approve, merge, unapprove, or run remediation
(deploy/rollback/scale) — pr-gatekeeper inherits this boundary unchanged, it does not relax it.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| `review_outcome` | Returned to caller | `posted: bool`, pr-review's `recommendation`, notification sent (if not posted) | Gatekeep incomplete |

## Completion summary (chat)

When run inside an interactive agent session (e.g. for testing), state: MR, `auto_post_authorized` used,
posting mode pr-review detected, whether posting happened, and where the notification went if not.
