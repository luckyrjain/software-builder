# Gate policy — every invoked child, normative

## pr-review always invoked posting held

Every dispatch of pr-review is a **typed invocation**, not a conversational exchange — the same
retrospective-audit pattern `release-readiness-checker` uses over pr-review's own real posting-gate
policy (see [pr-review/workflow/posting.md](../../pr-review/workflow/posting.md)):

- `review_mode: retrospective`, `audit_type: retrospective` — selects pr-review's retrospective audit
  path directly, so a merged-PR/MR stop and its confirmation ask never fire.
- `expected_head_sha` — the exact `head_sha` resolved in Inputs.
- `posting_policy: forbidden` — a typed field pr-review honors identically to a live "Hold — don't
  post" reply, guaranteeing nothing is ever posted regardless of which posting mode pr-review's own
  Phase 0 detects (`full`/`summary-only`/`general-only`/`chat-only`).

If a future pr-review version still renders a Phase 3 posting-confirmation prompt despite
`posting_policy: forbidden`, answer it **"Hold — don't post"** — redundant with, not a replacement for,
the typed field. Every other ask-point pr-review may still hit (baseline staleness offer, pagination
cap, post-Phase-5 Jira/Slack write-back offers) is answered per pr-gatekeeper's own enumerated
auto-post policy: decline every write-back offer, accept the partial-boundary review on a cap hit.

## No child receives merge, deploy, or rollback authority

Every child invocation in this skill stays inside that child's own read-only contract. This skill never
passes a caller-settable "authorized to merge/deploy/rollback" field to any child, and never itself
performs a merge, deploy, or rollback — the deliverable is `production_readiness_report`, nothing else.
A child that reports it *could* take such an action (e.g. a specialist noting an available auto-fix) is
recorded as a finding or a required action in the report, never executed.

## Never dispatch a specialist with a knowingly-incomplete mandatory input

Per [child-input-map.md](child-input-map.md), a specialist is invoked only once every one of its
mandatory input fields is fully assembled from real evidence. When a mandatory field cannot be
assembled — the repository doesn't expose it, the caller didn't supply it, and no evidence source
resolves it — that specialist is **not invoked at all**. The dimension is recorded `UNKNOWN` directly,
with the missing-field reason retained in `dispatch_log`. Inventing a placeholder value, dispatching
with a partial composite input (see child-input-map.md § Composite mandatory inputs), or silently
skipping the dimension without recording `UNKNOWN` are all violations of this rule.

## An embedded child's interactive question returns BLOCKED, never a live prompt mid-aggregation

This skill fans out to up to ten children to build **one** report; pausing for a live confirmation
inside any one of those invocations would turn one report into N interruptions, and a specialist
embedded mid-aggregation has no direct caller turn to answer it anyway. When a dispatched child would
otherwise render an interactive ask-question (an ambiguous scope, a missing-but-askable field, a
confirmation gate), it instead returns `BLOCKED` to this skill — never a rendered prompt the human
reviewing this skill's own output would have to answer out of context. Treat a `BLOCKED` return as that
dimension's outcome: `UNKNOWN`, with the block reason preserved in `evidence_refs`. This is an
escalation the report surfaces (a required action naming which specialist to run directly, per
[cross-skill-escalation.md](../../docs/skill-framework/shared/cross-skill-escalation.md)), not a
gate this skill silently answers on the child's behalf.

## Verdict precedence

Overall verdict derivation is fixed, four states, precedence `NOT_READY` > `UNKNOWN` > `CONDITIONAL` >
`READY` over every **required** dimension (`NOT_APPLICABLE` dimensions never count toward `PASS`):

- **`NOT_READY`** — any required dimension is `FAIL`.
- **`UNKNOWN`** — no `FAIL`, and any required dimension is `UNKNOWN` (an evidence gap, not a proven
  problem and not verified-safe).
- **`CONDITIONAL`** — no `FAIL`/`UNKNOWN`, and any required dimension is `CONDITIONAL`.
- **`READY`** — every required dimension is `PASS` or `NOT_APPLICABLE`.

Report the single highest-precedence state and list every contributing dimension, not just the one
that set the verdict — see [reference/report-format.md](report-format.md).

## Escalation, not override

If any child reaches a state this policy doesn't cover, treat it as genuine — this skill never bypasses
a child's own judgment. Record the anomaly in the relevant dimension and fall back to flagging it as
needing direct follow-up with that child, same as any other `UNKNOWN`/`BLOCKED` outcome.
