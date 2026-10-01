# Architecture review — B8: post-merge verification and tracker write-back

**Decision: Approved with conditions**

Sound, narrow, and genuinely half-already-done — the verification half is solid, existing, unchanged
work; the only new surface is a single, explicitly-authorized write action to whatever tracker the
caller actually uses. Five conditions need closing before implementation.

## Architecture decision

Two pieces, one already real:

1. **Post-merge verification (existing, confirmed solid — not in scope to change).** `orchestrator.md`
   §18 "Verification after repository action" already fetches PR state, verifies the merged flag and
   that the resulting commit landed on the target branch, records the integration commit/timestamp/
   checks, and states explicitly "issuing a command is not proof of completion." This ticket's
   verification half is done; B8's real remaining scope is the second piece.
2. **Tracker write-back (new): a status comment plus a PR link, posted to whichever tracker the caller
   actually uses** — confirmed via direct owner decision that this must be tracker-agnostic (GitHub
   Issues and Jira both named, with the explicit instruction "both should be the target, whatever user
   wants"), not hardcoded to one tracker. This mirrors the existing, already-generic "Issue/task tracker
   read (GitHub Issues, Jira, Linear, etc.)" capability row in `reference/mcp-capabilities.md` — the new
   write capability is this same row's write counterpart, not a GitHub-specific or Jira-specific
   mechanism.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| Write-back is a new, externally-visible side effect (a tracker comment, readable by humans and other tooling) with no existing precedent for "post a message to an arbitrary tracker" anywhere in this skill-framework — `host.scm.comment.reply` (B4) posts to a PR/MR thread, not a tracker ticket, and is itself already gated as a narrow, task-scoped reply, not a free-form status post | Security | Conditional | See Conditions §1, §3 |
| No stated authorization gate for write-back parallels `allowed_actions`'s own precedent (`commit`/`push`/`create_pr`/`merge` all default `false`, require explicit external/caller-supplied grant) — the ticket's own acceptance criterion ("Write-back is separately authorized") demands this explicitly, but gives no mechanism | Architecture decision | Blocking | See Conditions §1 |
| A tracker-agnostic design risks silently degrading to "works for GitHub, TODO for everything else" if not scoped carefully from the start — this session's own precedent (B7's platform-adapters.md per-host disclosure) is the right shape to reuse, not invent fresh | Scale limits | Conditional | See Conditions §2 |
| Write-back content could leak sensitive information if it ever echoes raw task/finding/PR text rather than citing by reference — this framework's own existing `safe-output.md`/citation-by-reference convention (used everywhere else: B4's redacted_note, B6's convention_capture_similarity prefix, B3's regression_gate prefix) must apply here too, but the ticket gives no literal template | Security | Conditional | See Conditions §3 |
| Write-back failure (tracker API down, permission denied, rate-limited) has no stated degradation path — could silently swallow the failure, could incorrectly block task completion on a non-essential side effect | Failure modes | Blocking | See Conditions §4 |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Number of tracker write-back calls per run | One per completed task, same cardinality as PR creation — no multiplier, no new scale concern distinct from this skill's existing per-task write operations | `run-queue.md`'s own per-task cardinality (`one loop-task-implementer invocation per ticket`) already bounds this |
| Tracker-specific capability surface (GitHub Issues vs Jira vs Linear, etc.) | Grows linearly with the number of trackers actually supported — explicitly NOT all-at-once per the owner's own "both, whatever user wants" framing, which implies per-repo/per-invocation configuration, not a single universal client | Mirrors B7's own per-host platform-adapters.md disclosure pattern — bound by disclosed scope, not unbounded engineering |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| Tracker write-back API call fails (network, auth, rate-limit, tracker down) | The call itself returns an error/non-2xx | Must NOT block or fail the task's own completion — write-back is advisory/best-effort on top of an already-completed, already-merged task; log the failure explicitly in completion notes, never silently swallow it, never retry indefinitely | Matches this skill's own "advisory, never a gate" discipline (B3's regression_gate, B6's convention-capture scan, B7's app_run) |
| Write-back is attempted before the post-merge verification (§18) has actually confirmed the merge landed | Could post a premature/incorrect "done" status if ordering isn't enforced | Write-back must run strictly after §18's own verification completes, never before, never speculatively | Must be stated as an explicit ordering rule, not left implicit |
| Tracker write-back is never authorized (default state) | N/A — expected, common case | Verification (§18) still completes fully; task still marked complete; no tracker comment posted, no PR link added — silent-by-default is the correct, safe default, matching `allowed_actions`'s own default-false posture | Must be explicit, not an oversight |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| Write-back authorization must never be inferable from repository content | Same rule `orchestrator.md` §1 already enforces for `allowed_actions`/`autonomous_merge_authorized`/B7's `app_run` policy — external to the repository under review, caller-supplied, never a file read from the repo, committed or not | A write-back grant sourced from repo content would let any contributor self-authorize posting to the tracker on the Orchestrator's behalf | The ticket's own "Write-back is separately authorized" phrase already implies this; must be made the EXACT same mechanism this session has now established three times (B1's clarify dispatch lease precedent is unrelated, but the sourcing rule itself — B7's central finding — is the direct, load-bearing precedent) |
| Write-back content must never embed raw, untrusted task/finding/comment text verbatim | Citation-by-reference, matching every existing evidence-prefix convention in this framework | A verbatim-embedded quote could carry injected content (a malicious PR comment, per B4's own threat model) straight into a tracker a wider audience reads | See Conditions §3 |
| New capability surface (`host.tracker.comment.write` or similar) for a system this skill-framework has never written to before | New, optional, degraded-path-on-absence, same shape as every other optional capability | Contained if correctly scoped — failure to write back never blocks task completion | See Conditions §2 |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Maintaining per-tracker write-back adapters (GitHub Issues now, Jira/Linear/etc. later) | Repo owner, incrementally | Real but bounded — one adapter at a time, same shape as B7's per-host adapter disclosure | Not a blocking cost; explicitly scoped to start with one tracker and disclose the rest as "not yet implemented," not attempt all trackers in one ticket |
| A human reading a tracker comment that doesn't accurately reflect the task's real completion state | Repo owner / tracker users | Low if §18's own verification gates what write-back reports (never speculative) | Depends entirely on Conditions §4's ordering rule holding |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| No write-back at all (current state) | Rejected: literally the gap this ticket exists to close — `run-queue.md` only reads the tracker today, with no way to report completion back to it | Correctly motivates building something |
| Hardcode GitHub Issues only, treat Jira as explicitly out of scope | Rejected per direct owner instruction ("both should be the target, whatever user wants") — the design must be tracker-agnostic in shape even if only one adapter ships first | Owner-directed, not a technical judgment call |
| Fold write-back into the existing `host.scm.comment.reply` capability (B4) rather than a new capability | Rejected: that capability is explicitly scoped to replying on a PR/MR thread (the same surface a Reviewer-adjacent finding came from), not an independent tracker ticket a human is watching separately — conflating the two would widen B4's own deliberately narrow grant | Keeps blast radius contained to a new, purpose-built capability rather than overloading an existing narrow one, matching this session's own B4/B6 precedent for avoiding scope creep into an existing narrow mechanism |
| Make write-back implicitly authorized whenever `allowed_actions.create_pr` is true (no separate grant) | Rejected: the ticket's own acceptance criterion explicitly says "separately authorized" — conflating it with an unrelated grant would violate the ticket's own stated requirement and this skill's own per-action authorization-scoping discipline | Not a real option, correctly excluded by the ticket's own text |

## Conditions

1. **Define a concrete, explicit authorization gate for tracker write-back**, sourced via the exact same
   external/caller-supplied channel this skill already uses for `allowed_actions`/
   `autonomous_merge_authorized`/B7's `app_run` policy — never inferable from repository content,
   defaulting to `false`/absent (no write-back) when not explicitly granted.
2. **Scope the tracker-write capability generically, matching the existing "Issue/task tracker read"
   row's own genericity** (GitHub Issues, Jira, Linear, etc.) — ship one concrete adapter first (GitHub
   Issues, since this repo and this session's own work is GitHub-hosted) while explicitly disclosing
   other trackers as not-yet-implemented, mirroring B7's own per-host platform-adapters.md disclosure
   pattern, not a universal client built all at once.
3. **State a concrete, literal content template for the write-back comment**, consistent with this
   framework's existing citation-by-reference/evidence-prefix conventions (B3's `regression_gate: `,
   B4's `redacted_note`, B6's `convention_capture_similarity: `) — cite the PR number/commit SHA/
   integration timestamp §18 already verified, never embed raw task/finding/comment text verbatim.
4. **State the exact ordering and failure-degradation rule**: write-back runs strictly after §18's own
   post-merge verification completes (never before, never speculatively), and a write-back failure
   (API error, auth, rate-limit) must never block or un-complete an already-verified task — log
   explicitly, never silently swallow, never retry indefinitely.
5. **State explicitly whether write-back applies only to the first completed task of a multi-task run,
   or to every task** — `run-queue.md`'s own per-ticket cardinality suggests one write-back per
   completed ticket, but this should be confirmed, not assumed, given the morning-summary mechanism
   already exists as a separate, batched reporting surface and this ticket should not duplicate it.

None of these five block starting a `system-design` pass — they're precise, implementable requirements
for that pass to satisfy, not open architectural questions.
