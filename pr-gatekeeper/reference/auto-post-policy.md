# Auto-post policy (normative)

**The one piece of new logic in this skill.** Everything else is pr-review's own. This file defines,
precisely, how pr-gatekeeper reconciles an unattended webhook run with pr-review's own Phase 3
confirmation gate ([pr-review/workflow/posting.md](../../pr-review/workflow/posting.md)) — **without
changing pr-review's rules**. It only ever supplies inputs pr-review's own docs already define as valid
(an initiating phrase, or one of the exact options pr-review's own Phase 3 prompt offers) — never a
synthetic bypass.

## The protocol — exactly two messages, never a hang

pr-review's Phase 3 either (a) auto-skips when the user said "review and post" **and** mode is
`full`/`summary-only` **and** the MR isn't a draft, or (b) stops and **waits for the user's next message**
containing an explicit choice — per
[pr-review/workflow/posting.md § User text input gates](../../pr-review/workflow/posting.md#user-text-input-gates),
it never treats silence or a default as consent. A webhook-triggered session has no human to answer that
wait — so pr-gatekeeper's calling automation (the webhook handler, per [SETUP.md](../SETUP.md) §
Integration contract) must be scripted to always supply exactly one deterministic reply if Phase 3 ever
does stop and wait, so the run always terminates:

1. **Opening message** — depends on `auto_post_authorized` (from [workflow/inputs.md](../workflow/inputs.md)):
   - `true` → invoke pr-review with **"review and post !`<merge_request_iid>` in `<project>`"** — the
     exact phrase pr-review's own skip condition checks for.
   - `false` → invoke pr-review with **"review !`<merge_request_iid>` in `<project>`"** (no post phrase).
2. **If and only if pr-review's Phase 3 stops and shows a confirmation prompt** (it may not — see the
   table below), the automation's one designated reply is always the literal text **"Hold — don't
   post"** — one of pr-review's own offered options in every mode's prompt
   ([posting.md § Phase 3](../../pr-review/workflow/posting.md#phase-3-confirm-before-posting)). Never
   answer with a posting option on pr-gatekeeper's own initiative, even if it looks safe — "Hold" is the
   only reply pr-gatekeeper's automation is ever scripted to send.

No third message. No retry loop. No waiting past that.

## Outcome table

| `auto_post_authorized` | pr-review's own posting mode + draft state | What happens | Posted? |
|--------------------------|----------------------------------------------|--------------|---------|
| `true` | `full`/`summary-only`, non-draft | Skip condition met — pr-review posts without a Phase 3 prompt at all | **Yes** |
| `true` | `general-only` (any draft state) | Phase 3 **always** prompts regardless of phrasing — automation replies "Hold" | No |
| `true` | `full`/`summary-only`, **draft MR** | Draft-MR warning always prompts — automation replies "Hold" | No |
| `true` or `false` | `chat-only` | Phase 3 skipped entirely (no write tools exist) — review renders in chat, nothing to reply to | No (never possible in this mode) |
| `false` | any mode with write tools | No "review and post" phrase supplied → Phase 3 prompts — automation replies "Hold" | No |

**`auto_post_authorized: true` never overrides `general-only` or a draft MR** — those two conditions are
pr-review's own non-negotiable rules (see design spec Non-goals); pr-gatekeeper's automation always
answers "Hold" there, with no exception.

## When posting didn't happen

Whether by explicit "Hold" or `chat-only`'s no-prompt render, pr-review still completes Phase 5 and
produces its full chat-rendered review (findings, executive summary, recommendation) — Phase 5 always
runs "after Phase 4 (or if posting was skipped)"
([posting.md](../../pr-review/workflow/posting.md)). pr-gatekeeper takes that rendered output and routes
it via the notification path in [workflow/gatekeep.md](../workflow/gatekeep.md) instead of a GitLab
comment — reusing pr-review's own
[manual-notify template](../../pr-review/workflow/posting.md#manual-notify-template-no-slack-mcp) so a
human still sees the same recommendation/severity summary they would have gotten from a posted comment.
