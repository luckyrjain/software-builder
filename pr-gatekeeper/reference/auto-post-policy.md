# Auto-post policy (normative)

**The one piece of new logic in this skill.** Everything else is pr-review's own. This file defines,
precisely, how pr-gatekeeper reconciles an unattended webhook run with pr-review's own Phase 3
confirmation gate ([pr-review/workflow/posting.md](../../pr-review/workflow/posting.md)) — **without
changing pr-review's rules**. It only ever supplies inputs pr-review's own docs already define as valid
(an initiating phrase, or one of the exact options pr-review's own Phase 3 prompt offers) — never a
synthetic bypass.

## The protocol — every pr-review ask-point gets one deterministic answer, never a hang

**pr-review stops and waits for a human reply at more than one point, not only Phase 3.** A
webhook-triggered session has no human to answer any of them — per
[pr-review/workflow/posting.md § User text input gates](../../pr-review/workflow/posting.md#user-text-input-gates),
pr-review never treats silence or a default as consent, so an unanswered wait hangs forever, at whichever
gate it happens to hit. pr-gatekeeper's calling automation (the webhook handler, per
[SETUP.md](../SETUP.md) § Integration contract) must therefore be scripted to recognize **every** gate
below and answer it with its one designated, deterministic reply — never leaving any of them unanswered.

1. **Opening message** — depends on `auto_post_authorized` (from [workflow/inputs.md](../workflow/inputs.md)):
   - `true` → invoke pr-review with **"review and post !`<merge_request_iid>` in `<project>`"** — the
     exact phrase pr-review's own Phase 3 skip condition checks for.
   - `false` → invoke pr-review with **"review !`<merge_request_iid>` in `<project>`"** (no post phrase).
   Use the project's **path form** (`group/repo`), not a bare numeric ID, when the webhook payload has
   both (GitLab's push payload includes `project.path_with_namespace`) — pr-review's own
   [inputs.md § Resolution branches](../../pr-review/workflow/inputs.md#resolution-branches) documents
   `!IID in group/repo`-shaped phrasing in its examples; a bare numeric project ID in that slot is
   unverified against any documented example and best avoided.
   **Always also pass `expected_head_sha: <head_sha>`** as a typed invocation field alongside the phrase
   ([pr-review/workflow/inputs.md § Typed invocation](../../pr-review/workflow/inputs.md#typed-invocation-skill-to-skill-callers)) —
   this skill's `head_sha` input was previously accepted only for its own webhook-retry dedupe
   (`last_processed_head_sha`) and never checked against the commit pr-review actually reviewed; a race
   between the webhook firing and pr-review's `get_merge_request` call could silently review (and, with
   `auto_post_authorized: true`, auto-post) a different commit than the one that triggered this run. See
   [workflow/gatekeep.md](../workflow/gatekeep.md) step 2 for the mismatch outcome.

2. **Merged/closed-MR stop** — per
   [pr-review/workflow/phase-1.md](../../pr-review/workflow/phase-1.md) step 1's state check: if the MR's
   `state` is `merged` or `closed`, pr-review stops and warns, proceeding only if the user confirms a
   **post-merge audit**. The webhook handler is only supposed to dispatch pr-gatekeeper for MRs it has
   already confirmed open ([SETUP.md](../SETUP.md) § Integration contract step 2), so this should be rare
   — but a merge/close race between that check and pr-review's own `get_merge_request` call is possible.
   **pr-gatekeeper's deterministic answer: decline** (do not confirm a post-merge audit). An unattended
   push-triggered run auditing a just-merged MR is a different, deliberate request a human can make to
   pr-review directly — not something pr-gatekeeper should silently opt into.

3. **Early 200-file cap warning** — per
   [pr-review/reference/phase-1-gather.md](../../pr-review/reference/phase-1-gather.md) §MR metadata
   sub-checks, when `changes_count` > 200, pr-review asks *"Proceed with full pagination, or narrow scope
   first?"* with documented replies `proceed` / `narrow scope` / `explicit paths` — **before any diff has
   been fetched, so "review the partial boundary as-is" is not a valid answer here (there is no boundary
   yet).** **pr-gatekeeper's deterministic answer: `proceed`** — full pagination, which then runs into the
   pagination cap below on its own terms.

4. **Pagination cap hit** — per
   [pr-review/workflow/phase-1.md](../../pr-review/workflow/phase-1.md) step 2, when the 20-page/200-file
   cap is actually hit mid-fetch, pr-review asks whether to "continue fetching, narrow scope (e.g.
   security paths only), or review the partial boundary as-is." **pr-gatekeeper's deterministic answer:
   "review the partial boundary as-is."** An unattended run should never expand or narrow scope on its
   own judgment — reviewing what was already fetched, with pr-review's own "diff truncated" note intact,
   is the one answer that doesn't require a human scope decision.

5. **Baseline staleness offer during incremental re-review** — per
   [pr-review/reference/incremental-rerun.md § Baseline staleness](../../pr-review/reference/incremental-rerun.md),
   when more than 30 commits have landed since the last reviewed `head_sha`, pr-review warns and "offers"
   a full re-review instead of incremental. **pr-gatekeeper's deterministic answer: decline the offer,
   continue incrementally.** A full re-review is a scope decision for a human to make deliberately (and
   remains available any time by asking pr-review directly, per [SKILL.md](../SKILL.md) § Cross-skill
   escalation) — an unattended run should never silently expand to a full review of a long-lived MR.

6. **Phase 3 posting confirmation** — **if and only if** pr-review's Phase 3 stops and shows a
   confirmation prompt (it may not — see the Outcome table below), the automation's designated reply is
   always the literal text **"Hold — don't post"** — one of pr-review's own offered options in every
   mode's prompt
   ([posting.md § Phase 3](../../pr-review/workflow/posting.md#phase-3-confirm-before-posting)). Never
   answer with a posting option on pr-gatekeeper's own initiative, even if it looks safe.

7. **Post-Phase-5 write-back/notification offers** — pr-review may still ask twice more, **after**
   Phase 5 renders:
   - **Jira write-back** ([pr-review/workflow/phase-5.md § Jira write-back](../../pr-review/workflow/phase-5.md#jira-write-back-optional)) —
     "offer to post a summary comment to Jira — proceed only if the user confirms."
   - **Slack/Teams notification** ([posting.md § Slack / Teams notification](../../pr-review/workflow/posting.md#slack-teams-notification-optional)) —
     "Offer to post a one-line summary — proceed only on user confirmation."
   **pr-gatekeeper's deterministic answer to both: decline.** Writing to Jira or Slack on pr-review's own
   initiative is a write action beyond GitLab posting — outside this skill's read-plus-GitLab-comment
   boundary (see [SKILL.md](../SKILL.md) § Prerequisites) — and pr-gatekeeper already has its own
   notification path ([workflow/gatekeep.md](../workflow/gatekeep.md) step 4) for the held-review case, so
   there's no need for pr-review's own offer to also fire.

No other pr-review prompt gets a reply beyond what's listed above. If a future pr-review version adds a
new ask-point not covered here, treat that as a gap in this policy to close, not something to guess an
answer for on the fly.

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
[manual-notify template](../../pr-review/workflow/posting.md#manual-notify-template-no-slack-mcp), with
one required adaptation: nothing was posted to GitLab in this path, so there is no "link to GitLab
summary note" — the template's `Full review:` line **must** use its other documented option, "paste
executive summary," populated with pr-review's actual Phase 5 executive summary text (not omitted, and
not just the one-sentence `Summary:` line above it). A notification missing the full findings/executive
summary defeats the point of routing it to a human at all — see [SKILL.md](../SKILL.md)'s "never silently
drop a completed review" rule.
