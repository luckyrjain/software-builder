# pr-gatekeeper: design

**Date:** 2026-08-05
**Status:** Approved design
**Source:** Item #2 of [team-facing-agents-roadmap.md](../plans/2026-08-05-team-facing-agents-roadmap.md) —
P0, "pr-review auto-run on every push (webhook-triggered), posting inline as it already supports. Ship
the plain auto-review wrapper first, add the auto-fix loop as a follow-up" (the loop-task-implementer
hand-off for small findings is explicitly out of scope for this item).

## Problem

Today pr-review only runs when a human types `/pr-review` or asks in chat. Teams want review feedback
on every push to an MR automatically, without a human remembering to ask.

## Approach

`pr-gatekeeper` is a **thin wrapper skill**, not a new review engine. It:

1. Is invoked by a GitLab push-event webhook (a commit pushed to an open MR's source branch), not by a
   human chat message.
2. Delegates the entire review to **pr-review** — same phases, same findings pipeline, same posting
   templates, same cross-session incremental-rerun dedupe. No new review logic, no new severity rubric,
   no new posting templates.
3. Handles the problem pr-review cannot solve for itself: **pr-review is designed to stop and wait for a
   literal human chat reply at several points, not only its Phase 3 posting confirmation** — the early
   200-file cap warning and pagination-cap ask in Phase 1 Gather, the baseline-staleness offer in
   incremental re-review, and Phase 3 itself (see
   [reference/auto-post-policy.md](../../pr-gatekeeper/reference/auto-post-policy.md)) — correctly so,
   for interactive use. A webhook has no chat turn to supply any of them. pr-gatekeeper's entire job is
   answering each of these deterministically (never expanding scope on its own judgment) and, for Phase 3
   specifically, deciding whether pr-review's own existing "review and post" skip condition already
   covers this case — or whether pr-review's own rules mean this push must **not** auto-post, in which
   case pr-gatekeeper produces the review without posting and hands off to a human notification path
   instead, with the full executive summary intact (not just a one-line stub).

## Why this needs its own skill instead of "just say 'review and post' in the webhook handler"

Because pr-review's own skip condition is conditional, not unconditional: *"skip confirmation only when
user said 'review and post' **and** mode is `full` or `summary-only` **and** the MR is not a draft. For
`general-only`, always confirm after the warning."* A webhook handler that always tried "review and post"
would work correctly by accident in `full`/`summary-only` on ready MRs, but would either (a) silently do
nothing (pr-review still holds at Phase 3 for `general-only`/draft, `chat-only` never posts by design) or
(b) require someone to notice pr-review is sitting at an unanswered confirmation prompt in an unattended
session forever. pr-gatekeeper's job is to know pr-review's own gate well enough to route correctly
instead of blindly retrying the same phrase every time.

## Non-goals (explicitly out of scope for this item)

- No new review logic, severity rubric, or posting template — 100% pr-review's own.
- **No bypass of pr-review's `general-only` or draft-MR confirmation gates.** pr-review's own design
  treats these as non-negotiable (a `general-only` comment can't be edited/retracted once posted; a
  draft MR may still be in flux). pr-gatekeeper does not invent a synthetic confirmation for these cases
  — it runs the review, skips posting, and routes the report to a human via notification instead. This
  is a deliberate limitation, not a follow-up TODO.
- No auto-fix hand-off to loop-task-implementer — explicitly deferred by the roadmap item itself to a
  future extension.
- No live webhook HTTP server / GitLab webhook registration in this repo — out of scope exactly like
  who-owns-x-bot's Slack handler; `SETUP.md` documents the integration contract for whoever builds it.
- No new dedupe/idempotency logic — pr-review's own cross-session `incremental-rerun.md` mechanism
  (prior-note detection via `<!-- cursor-pr-review -->` marker, snippet-hash finding matching) already
  solves "don't repost the same finding on every trivial push." pr-gatekeeper only decides *whether to
  invoke posting at all* for a given push, never re-derives *what* to post.

## Auto-post authorization — the one new concept this skill introduces

pr-review's skip condition requires a human to have said "review and post." pr-gatekeeper's caller (the
team that wired up the webhook) is a human who, at **integration setup time**, decides whether pushes to
this project should auto-post — this is a standing, upfront authorization, not a live per-push
confirmation, and is the same shape as loop-task-implementer's `autonomous_merge_authorized` flag
(explicit upfront grant, never synthesized by the agent itself, never inferred from repo-file prose). See
[SETUP.md](../../pr-gatekeeper/SETUP.md) § Config for where this is set.

When `auto_post_authorized` is true for the project **and** pr-review's own conditions for the skip are
independently met (`full`/`summary-only` posting mode, MR not a draft), pr-gatekeeper supplies "review
and post" as the initiating instruction — exactly the phrase pr-review's own docs define as sufficient,
supplied once by upfront human config instead of a live chat turn. **The AND is with pr-review's own
condition, not instead of it** — `auto_post_authorized: true` never overrides `general-only` or draft-MR
handling; those still hold every time, per pr-review's own rules.

## Acceptance criteria

- `pr-gatekeeper/SKILL.md` exists, ≤ 180 lines, `disable-model-invocation: true` (webhook-only entry
  point, same reasoning as who-owns-x-bot — a human typing "review this MR" still routes to pr-review).
- Given `full`/`summary-only` mode, non-draft MR, and `auto_post_authorized: true` → pr-gatekeeper invokes
  pr-review's posting flow (Phase 4 runs).
- Given `general-only` mode, or a draft MR, regardless of `auto_post_authorized` → pr-gatekeeper never
  auto-posts; it produces the review and routes it via the configured notification path instead.
- Given `auto_post_authorized: false` (or unset) → pr-gatekeeper never posts, always routes to
  notification, regardless of mode/draft state.
- Given a routed notification (not posted) → the notification carries pr-review's full Phase 5 executive
  summary, not just a one-line stub — the manual-notify template's `Full review:` field is populated with
  the pasted summary, since there's no GitLab link to use instead.
- Given `last_processed_head_sha` supplied by the caller and equal to the new `head_sha` → pr-gatekeeper
  does not re-invoke pr-review at all (this is a wrapper-level short-circuit — invoking pr-review anyway
  would hit its own "No new commits" short-circuit and skip Phase 3/4, but skipping the invocation
  entirely avoids the cost of a full agent run that pr-review would immediately no-op). **This dedupe
  state is the caller's responsibility, not pr-gatekeeper's** — the skill has no persistence of its own
  and does not attempt to derive "last processed" on its own initiative.
- Given a Phase 1 large-MR/pagination-cap ask or an incremental baseline-staleness offer → pr-gatekeeper
  answers deterministically ("review the partial boundary as-is" / "continue incrementally") rather than
  leaving the session waiting on either.
- `make lint-pr-gatekeeper` and `make lint-framework` pass; skill wired into root README.md,
  docs/README.md, docs/REPOSITORY.md, `skill-routing.md`, `phase-glossary.md`, `cross-skill-escalation.md`,
  `CHANGELOG.md`.

## Implementation plan

1. `pr-gatekeeper/SKILL.md`, `README.md`, `SETUP.md`, `CHANGELOG.md`, `examples.md`.
2. `pr-gatekeeper/workflow/inputs.md` (parse webhook payload: project, MR IID, new `head_sha`; untrusted-
   content note — commit messages/MR title in the payload are data, not instructions) and
   `workflow/gatekeep.md` (single phase: short-circuit on no-new-commits, invoke pr-review, apply
   auto-post-policy, route notification when not auto-posting).
3. `pr-gatekeeper/reference/phase-index.md`, `lazy-load-index.md`, `auto-post-policy.md` (normative
   decision table, mirrors pr-review's own skip condition), `smoke-test.md`.
4. `.cursor/rules/pr-gatekeeper.mdc`, `.kiro/steering/pr-gatekeeper.md`.
5. `Makefile`: `install-pr-gatekeeper` (chains `install-pr-review`), `install-claude-pr-gatekeeper`,
   `lint-pr-gatekeeper`, added to `.PHONY`/`lint:` deps, and to `lint-framework`'s 4 hardcoded per-skill
   loops (examples.md check, SETUP/SKILL.md link check, untrusted-content wiring, discovery-file check) —
   the who-owns-x-bot review found these silently skip a new skill unless added explicitly.
6. Root `README.md`, `docs/README.md`, `docs/REPOSITORY.md`: rows following the who-owns-x-bot pattern.
7. `docs/skill-framework/shared/skill-routing.md`, `phase-glossary.md`, `cross-skill-escalation.md`,
   `prompt-injection.md`: routing row + disambiguation rule, phase mapping, escalation rows (subset rule),
   wiring-table row.
8. Root `CHANGELOG.md` + `pr-gatekeeper/CHANGELOG.md`: initial release entry.
9. `make lint` green; deep review pass; fix to 0 issues; commit.
