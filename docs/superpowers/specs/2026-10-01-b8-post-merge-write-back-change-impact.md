# Change impact report — B8: post-merge verification and tracker write-back

**Coverage status: COMPLETE**

## Assessment target

Proposed state. Repo: `luckyrjain/software-builder`, main, head includes merged PR #318 (B7). Sources:
`docs/superpowers/specs/2026-10-01-b8-post-merge-write-back-design.md` (revision 3, converged across 3
full adversarial review rounds plus 1 targeted narrow fix pass, 3 personas) and
`docs/superpowers/specs/2026-10-01-b8-post-merge-write-back-architecture-review.md` (Approved with
conditions, 5 conditions, all addressed in the converged design).

## Criticality: High

Not for code size — this is the smallest code footprint of any ticket this session has shipped (one new
per-task schema field, one new consumed-input declaration, one new unnumbered orchestrator.md
subsection, and one small, additive cross-skill companion change) — but for review depth and the nature
of the one genuinely security-sensitive surface. This design required 3 full adversarial rounds plus a
4th narrow targeted-fix round before converging, among the deepest-reviewed tickets this session has
produced (matching B2's 10-round and B6's 5-round sagas). The central defect — a confused-deputy risk in
which issue a new, externally-visible write capability targets — was found, "fixed" incorrectly twice
(round 1's fix assumed a trusted/untrusted split that didn't exist in the codebase's own real mechanics;
round 2's fix reused a field name that collided with an existing, differently-scoped input), and only
genuinely closed in a round-3 targeted rename. A human reviewing the actual implementation diff must
independently re-verify this closure holds in code, not merely trust that the design doc says so.

## Change classes

- `new-capability-declaration` (one new `mcp-capabilities.md` row: tracker write, explicitly distinguished
  from the existing fully-delegated "tracker read" row as committing this skill to real, maintained
  GitHub-specific adapter code)
- `contract-change` (`orchestrator.md`'s frontmatter `consumes:` list gains a new, separate
  `caller_task_ref` entry, alongside the unchanged, pre-existing `task_source` entry — additive, not a
  widening of the existing entry)
- `new-validation-logic` (the author-scoped, variant-tagged idempotency marker check; the minimal PR-open
  freshness re-check)
- `workflow-policy-extension` (`orchestrator.md` §1 gains `tracker_write_back_authorized`, mirroring
  `allowed_actions`/`autonomous_merge_authorized`'s existing sourcing rule exactly)
- `new-schema-field` (`task.source_issue_ref`, new, nullable, immutable-once-set, in
  `reference/state-schema.yaml`)
- `cross-skill-companion-change` (the one genuine cross-skill touch: `skills/backlog-runner/reference/
  queue-policy.md` §3 — small, additive, narrowly scoped)
- `documentation-only` (`platform-adapters.md`'s vestigial-field note and Jira/Linear "not yet
  implemented" disclosure)

## Impacted services / files

| Path | Nature of change | Risk |
|------|-------------------|------|
| **`skills/loop-task-implementer/workflow/orchestrator.md`** | (a) §1 gains `tracker_write_back_authorized` — confirmed, by direct read of the real current §1 text, to mirror `allowed_actions`/`autonomous_merge_authorized`'s exact external/caller-supplied sourcing rule (the same sentence structure, the same "never from a file read from the repository, committed or not" clause). (b) Frontmatter gains `consumes: caller_task_ref` as a genuinely separate, new entry — confirmed against the real current frontmatter (`consumes: [task_source, repository_policy, state_schema, implementation_plan, plan_execution_state]`) that `task_source` is unchanged and `caller_task_ref` would be a clean addition, not a rename or alias. (c) §2 derives `task.source_issue_ref` from `caller_task_ref` only. (d) §18 gains the post-merge write-back step. (e) A new, unnumbered subsection is inserted between §17 and §18, following the exact, already-real precedent of the existing "## External comment-thread recheck and reply-and-verify (gap-backlog B4)" heading (confirmed present in the real file, inserted between §16 and §17 for the identical renumbering-avoidance reason) | **The single most important file in this change to review in isolation.** The `caller_task_ref`/`task_source` separation is the one property a human must re-verify holds in the actual diff — this was the central, twice-missed defect across this design's own 3-round history |
| **`skills/loop-task-implementer/reference/state-schema.yaml`** | New `task.source_issue_ref: {repo: string, issue_number: int} | null` field, nullable, immutable once set at §2 | Low — confirmed (by direct reading of `scripts/validate_loop_lifecycle.py`'s real field-checks: acceptance-criteria completeness, blocking findings, required approvals, isolation status, CI checks, workspace commit hashes, circuit-breaker state) that this file gates only lifecycle/merge-readiness-relevant fields; `source_issue_ref` is purely informational for write-back targeting and falls genuinely outside its scope. **No `validate_loop_lifecycle.py` touch point needed** — a correct, re-verified conclusion, not a deferred question, matching the design's own round-2 resolution |
| **`skills/loop-task-implementer/reference/mcp-capabilities.md`** | One new row: "Issue/task tracker write (status comment + PR link)," Optional, degraded path = skip write-back entirely | Low — documentation, but the distinction from the read row's full-delegation model (this row commits the skill to real adapter code) must be preserved accurately |
| **`skills/loop-task-implementer/reference/platform-adapters.md`** | One-line note flagging `task_ref` (an existing, undefined field in the cross-agent handoff envelope) as vestigial; Jira/Linear "not yet implemented" disclosure for the tracker-write capability | Low — documentation only |
| **`skills/backlog-runner/reference/queue-policy.md`** | §3 gains language threading `backlog_run.tasks[].task_id` through as `caller_task_ref`, a separate, structured field alongside the pasted ticket text already sent as `task_source` | **The second-most-important file to review carefully** — confirmed (by direct reading of the real current §3 text) that its "no different phrasing, no trailing directives invented" policy governs only the pasted-text channel; the design's own addition is textually additive and distinct, not an exception carved into that existing policy. Confirmed narrow: touches only §3, not §1 (session schema)/§2 (ordering)/§4 (continuation)/§5 (circuit breakers) |
| **No `skills.yaml`/`composition_contracts.yaml` registration** | `source_issue_ref` lives on Orchestrator-side per-task state, not `implementation_task`'s own external/exempt field surface | Confirmed against the real `composition_contracts.yaml`: `task.requirements_ref` (an existing, analogous `task:`-block field) already lives in `state-schema.yaml` with zero registration in either file — a real, direct precedent for this design's own registration-path reasoning, not an assumption |

**Confirmed untouched**: `workflow/builder.md`, `workflow/reviewer.md`, `workflow/lifecycle-gate.md` — this
mechanism is entirely Orchestrator-side, never involves the Builder or Reviewer roles, no finding-output
schema change, no Blocking-standard condition added.

## Impacted contracts

- `orchestrator.md`'s `consumes:` contract — extended with one new, additive entry (`caller_task_ref`),
  the existing `task_source` entry's own meaning and scope are explicitly unchanged.
- `task.source_issue_ref` — new, nullable, additive field; no existing consumer of `state-schema.yaml`'s
  `task:` block needs to change.
- No change to the finding-output schema, no new Blocking-standard condition — this design never reaches
  the Reviewer role.

## Impacted data

None durable beyond the new `source_issue_ref` field itself (small, structured, per-task, cleaned up with
ordinary task lifecycle, not a new persistent store). The idempotency mechanism deliberately keeps no new
local state at all — it anchors durability in the tracker itself (the posted comment's own marker),
confirmed as a deliberate design choice to avoid expanding `run_log.py`'s closed event vocabulary.

## Impacted dependencies

No new dependency beyond the `gh` CLI this skill already depends on elsewhere (PR creation, CI checks).
The identity-discovery mechanism for the author-scoped marker check (`gh auth status`/`gh api`) uses the
same CLI, no new tooling.

## Impacted owners

Single owner (CODEOWNERS root wildcard) for `software-builder`; the one cross-skill touch
(`queue-policy.md`) is owned by the same single owner, since both skills live in this one repo — no
cross-repository ownership question.

## Required tests

1. **`caller_task_ref`/`task_source` separation — a durable regression test, the single highest-priority
   test in this change**: construct a scenario where `task.source_issue_ref`-shaped content exists ONLY
   in repository/ticket-body text (never via `caller_task_ref`), and assert it is NEVER picked up —
   `source_issue_ref` stays null. This directly encodes the central finding from this design's own
   3-round correction and must exist as a durable test, not just a design-review confirmation (mirrors
   B7's own equivalent sourcing-rule regression test for `app_run` policy).
2. **Idempotency marker — unit/integration tests**: (a) marker-spoofing resistance — a marker posted by
   any identity other than the write-back actor's own known identity must be ignored, and write-back
   must still proceed as if no marker existed; (b) variant-discrimination — a prior `pr-opened` marker
   must never block a subsequent `merged` post for the same `task_id`; (c) the re-run-before-every-attempt
   contract specifically — construct a scenario where a first attempt's success response is lost
   (simulating a network timeout after the server-side post actually succeeded), confirm the retry's own
   fresh precheck finds the marker and skips rather than double-posting. This closes the exact gap round
   2 found in the original bounded-retry design.
3. **PR-opened trigger's timestamp provenance and freshness recheck**: confirm the `pr_opened_timestamp_utc`
   placeholder is genuinely read back from the run log's own `pr_opened` event `ts` field (not freshly
   asserted), and confirm the freshness recheck (`gh pr view --json state,mergedAt`) correctly produces
   `NOT_ATTEMPTED` for this trigger point when the PR has since been merged or closed by someone else.
4. **`validate_readiness`-equivalent for `task.source_issue_ref`'s immutability**: a test confirming the
   field, once set at §2, cannot be altered by anything later in the task's lifecycle (including a
   resumed/re-invoked task).
5. **`queue-policy.md` companion change — scope-discipline test**: confirm the new `caller_task_ref`
   threading doesn't alter backlog-runner's own existing "no invented grammar" behavior for the pasted-
   ticket-text channel — the two fields must remain independently testable and independently absent-able
   (a ticket with no resolvable `task_id` should still dispatch normally with `caller_task_ref` null,
   exactly as today).

## Operational impacts

1. **First write capability this session has shipped that posts to an external, human-visible system**
   (a tracker other people read) — the author-scoped marker check and the explicit "never fabricate a
   result" failure-handling discipline are the load-bearing mitigations; both were independently
   re-verified against real code in round 3/4, not merely asserted.
2. **Operational cost is genuinely trivial** — two lightweight `gh` calls per completed task at most,
   negligible against `orchestrator.md` §3's existing 30-minute response-wait budget; no new clause
   needed, consistent with this session's own established arithmetic-based conclusions for B6/B7.
3. **The cross-skill companion change (`queue-policy.md`) is this ticket's own process question, not an
   architecture-soundness one** (design's own Open Question 4) — whether it needs its own separate pass
   through `backlog-runner`'s doctrine chain, or can land as part of this ticket's implementation, is
   left for the Orchestrator/human to decide explicitly before implementation starts.
4. **Genuinely untested against a real tracker** — this gap-backlog's own tickets weren't worked from
   GitHub Issues, so the first real use of this mechanism should be treated as calibration, matching this
   session's own established caution for B6/B7's own first-use disclosures.

## Review triggers

**None required.** This design underwent 3 full rounds of dedicated adversarial multi-persona review
(Security Architect, SRE, Software Architect) plus a 4th narrow, targeted-fix confirmation round — the
central security-sensitive finding (confused-deputy risk in issue-number targeting) was independently
discovered by two personas from different angles in round 2, "fixed" incorrectly once more in round 3's
first attempt (a naming collision), caught by Security Architect, and then re-verified closed by the same
persona in a dedicated round-4 check against the real current files. This is a materially deeper security
scrutiny on the one genuinely sensitive surface (the `caller_task_ref` sourcing boundary, the author-
scoped marker check) than a standard `security-review` pass would independently produce — matching this
session's own established reasoning for B3/B4/B6/B7 not re-triggering a fresh pass after comparable
adversarial depth.

## Material unknowns

1. **No concrete validation target exists in this session's own immediate work** (design's own Open
   Question 1) — this gap-backlog's own tickets weren't worked from GitHub Issues; mirrors B7's own OQ1
   treatment.
2. **Per-tracker capability scoping beyond GitHub Issues remains genuinely unconfirmed** (design's own
   Open Question 2) — Jira, Linear, etc. explicitly out of scope for this ticket's first implementation.
3. **The exact parsing/validation algorithm for recognizing "GitHub-Issue-shaped" `caller_task_ref`
   values is open for BOTH callers** (design's own Open Question 3, corrected in round 3 from an earlier
   overclaim that backlog-runner's case was already resolved) — the producer side is now specified for
   both callers, but the exact grammar (`owner/repo#123`? a full URL? a `gh`-recognized reference?) is
   left for implementation to pin down.
4. **The `queue-policy.md` companion change's own review-process scope is an open process question**
   (design's own Open Question 4) — not resolved here, left for the Orchestrator/human.

## Unknowns

None beyond the material unknowns above — repository read was available throughout, and all referenced
real files (`orchestrator.md`'s §1/§2/§17/§18/frontmatter, `state-schema.yaml`, `validate_loop_lifecycle.py`,
`queue-policy.md` §3, `run_log.py`'s `EVENTS`/`_RECORD_FIELDS`, `composition_contracts.yaml`'s
`task.requirements_ref` precedent) were directly read and cross-checked against the design's own claims
across this ticket's 4 review rounds, not taken on the design document's word alone.

## Evidence refs

- `docs/superpowers/specs/2026-10-01-b8-post-merge-write-back-architecture-review.md`
- `docs/superpowers/specs/2026-10-01-b8-post-merge-write-back-design.md` (revision 3)
- Direct repository verification across this ticket's 4 review rounds: `skills/loop-task-implementer/
  workflow/orchestrator.md` (§1, §2, §17, §18, frontmatter `consumes:` list, the real B4 unnumbered-
  heading precedent); `skills/loop-task-implementer/reference/state-schema.yaml` and `scripts/
  validate_loop_lifecycle.py` (the `source_issue_ref` no-touch-point conclusion); `skills/loop-task-
  implementer/scripts/run_log.py` (the real `pr_opened` event and universal `ts` field);
  `skills/backlog-runner/reference/queue-policy.md` §3 (the real pasted-text policy and existing
  `task_id` identifier); `scripts/registry/composition_contracts.yaml` (the `task.requirements_ref`
  no-registration precedent); confirmed no `workflow/builder.md`/`workflow/reviewer.md`/`workflow/
  lifecycle-gate.md` changes anywhere in the converged design.
