# System Design Spec — B8: post-merge verification and tracker write-back

**Readiness: Ready with open questions**

## Revision history

**Revision 1** (initial): a single session-level boolean grant (`tracker_write_back_authorized`),
write-back placed strictly inside `orchestrator.md` §18 (post-merge only), a flat no-retry policy, no
new `state-schema.yaml` field, write-back reported only through free-text completion notes.

Round 1 adversarial review (Security Architect, SRE, Software Architect — all three, fresh, in
parallel) converged hard on one central defect, found independently from three different angles, plus
one separate, severe finding from SRE alone. Fixed in **revision 2** (this revision):

- **The per-task "originating issue reference" has no home anywhere in this codebase today** (all
  three personas, independently — Security Architect via the confused-deputy angle, SRE and Software
  Architect via the schema-registration angle). Revision 1's own "no schema footprint" claim and its
  Open Question 2 directly contradicted each other: a boolean session-level grant needs no schema
  change, but the thing it gates (which issue to comment on) is inescapably per-task, and no existing
  field (`task.requirements_ref` — staleness-detection, not identity; `task_ref` in
  `platform-adapters.md` — undefined; `backlog_run.tasks[].task_id` — scoped to backlog-runner's own
  session state, never threaded into loop-task-implementer's) actually carries it. **Fixed**: a new,
  named per-task field, `task.source_issue_ref` (see Data model), added to `reference/state-schema.yaml`
  — revision 1's "Confirmed untouched" claim for that file is withdrawn.
- **Confused-deputy risk in issue-number targeting** (Security Architect): if `source_issue_ref` were
  derived by parsing the task's own ticket/PR *body text* (untrusted per `prompt-injection.md`'s own
  table for this skill), a bad-faith task could steer a convincing, real-PR-citing write-back comment
  onto an arbitrary issue. **Fixed**: `source_issue_ref` is derived once, at §2 task selection, from the
  caller-supplied `task_source` identifier used to select which ticket to work on — never by parsing the
  ticket's own description/body text for an issue reference — and is immutable from that point forward,
  never re-derived at write-back time.
- **Unpinned `--repo`** (Security Architect): the literal `gh issue comment` call never stated which
  repository the comment target lives in. **Fixed**: `source_issue_ref` is a structured `{repo,
  issue_number}` pair, with `repo` sourced from the Orchestrator's own already-verified repository
  context (§1), never from the tracker-reference string itself.
- **No corroborating verification that the write lands on the correct ticket** (Security Architect):
  **Fixed**: §18's write-back step re-reads the immutable `source_issue_ref` recorded at task selection
  immediately before posting, rather than any value derived fresh at write-back time — this is now
  stated as an explicit check, not implicit.
- **Write-back, as placed, structurally can never fire for `backlog-runner`** (SRE — the most severe
  single finding): `queue-policy.md` §3 states `autonomous_merge_authorized` is *never* passed `true` by
  backlog-runner; every backlog-runner-dispatched ticket terminates at `HUMAN_ACTION_REQUIRED` (PR
  opened, not merged), never reaching §18's "after an authorized merge" gate at all. Revision 1's own
  Capacity-section citation of `run-queue.md`'s cardinality was backwards — the real cardinality for
  backlog-runner was zero, silently. **Fixed**: write-back now has two trigger points with two distinct
  templates — post-merge (unchanged) and PR-opened/`HUMAN_ACTION_REQUIRED` (new) — so backlog-runner's
  own common-case termination state actually gets tracker write-back value, not none.
- **No persisted per-task record of "did I already write back"** (SRE): a crash-resume or accidental
  re-invocation had no structured signal preventing a duplicate `gh issue comment` call. **Fixed**: a
  deterministic, invisible marker (`<!-- loop-task-implementer:write-back:<task_id> -->`) is embedded in
  every posted comment; before posting, the Orchestrator reads the target issue's existing comments and
  skips if a matching marker is already present — using the tracker itself as the idempotency source of
  truth, rather than inventing new local persisted state or expanding `run_log.py`'s closed, tightly-
  validated event vocabulary (a materially more invasive change this ticket doesn't need).
- **Flat no-retry was weaker than this file's own established pattern** (SRE): zero retry on a routinely-
  flaky external dependency (GitHub API rate-limiting) means routinely-missing write-back comments.
  **Fixed**: the marker-based idempotency check above makes a retry safe (a retry that finds its own
  marker already posted is a no-op), so one bounded retry (short backoff) is now permitted before
  logging `FAILED` — closing this without reopening the duplicate-comment risk revision 1 worried about.
- **Capability-row genericity overclaimed parity with its read counterpart** (Software Architect): the
  existing "Issue/task tracker read" row does zero tracker-specific work in this skill (fully delegated);
  the new write row commits this skill to real, maintained GitHub-specific adapter code. **Fixed**:
  stated explicitly in the Components table — the documentation *shape* matches, the delegation model
  does not.

Two items were independently confirmed sound and are unchanged: the authorization-gate sourcing
(`tracker_write_back_authorized` genuinely mirrors `allowed_actions`/`autonomous_merge_authorized`'s real
§1 text) and the literal citation-by-reference comment template's own non-leakage property (Security
Architect traced every placeholder's provenance and found none attacker-steerable — though the citation
of *which* section produces them is corrected below, per Security Architect's Finding 4).

**Round 2** adversarial review (same three personas, fresh, re-reviewing revision 2 against the real
current files) found that none of the four round-1 fixes were genuinely closed — two personas
(Security Architect and SRE, independently, from different angles) converged on the SAME central
unresolved defect, and a shared root-cause bug surfaced across two other "fixed" items. Fixed in
**revision 3** (this revision):

- **The confused-deputy fix had nothing to point at for the dominant caller** (Security Architect AND
  SRE, independently convergent — the most severe round-2 finding): revision 2's fix assumed a clean,
  caller-supplied `task_source` identifier distinct from untrusted ticket body text, but
  `skills/backlog-runner/reference/queue-policy.md` §3's own real text passes a backlog-runner-dispatched
  ticket's *entire* title/description/acceptance-criteria as pasted task text, with an explicit
  no-invented-grammar policy — there is no separate, structured identifier channel for this caller to
  derive `source_issue_ref` from. Backlog-runner's own session state DOES already carry a clean
  identifier (`backlog_run.tasks[].task_id: "<from tracker>"`), but it was never threaded through to
  loop-task-implementer's own per-task state. **Fixed**: a small, additive, explicitly-scoped companion
  change to `queue-policy.md` §3 — backlog-runner now passes its own already-existing `task_id` as a
  second, separate, structured field alongside (never derived from, never commingled with) the pasted
  ticket text. This is a genuine, narrow cross-skill touch, justified because without it the write-back
  mechanism's own core security property is false for the dominant batch caller — not scope creep for
  its own sake.
- **No verified-fact source for `pr_opened_timestamp_utc`, and no re-verification that the PR is still
  open** (Software Architect AND SRE, independently convergent): the new PR-opened template introduced a
  timestamp with nothing in `state-schema.yaml` recording it, and nothing re-confirms the PR hasn't been
  closed/merged by someone else since §5's own earlier, now-possibly-stale check. **Fixed**: the
  timestamp is now sourced from the run log's own already-existing, independently-recorded `pr_opened`
  event `ts` field (read back, never re-derived or model-asserted), and a single, minimal freshness
  re-check (`gh pr view --json state,mergedAt`) runs immediately before posting — the minimal version of
  §18's own "issuing a command is not proof of completion" discipline, scoped to just this one path's
  actual need, not a whole new parallel procedure.
- **Marker format had no trigger-point discriminator, silently suppressing the more authoritative
  "merged" confirmation behind a stale "pr-opened" one** (Security Architect): **Fixed**: the marker now
  embeds the variant (`merged` or `pr-opened`); only an identical variant is treated as a duplicate — a
  prior `pr-opened` marker never blocks a subsequent `merged` post for the same task.
- **Marker spoofing — any third party who can comment on the issue could pre-emptively post a fake
  marker and permanently, silently suppress real write-back** (Security Architect, new): **Fixed**: the
  idempotency check now only treats a marker as valid if it was posted by the write-back mechanism's own
  known actor identity (the `gh` token's associated account) — an unauthenticated marker from any other
  commenter is ignored.
- **The marker precheck was treated as a one-time gate rather than something re-run at every attempt**
  (SRE — the shared root cause behind two separate "fixed" items reopening): a flaky precheck read
  across multiple resumed invocations, or a retry that doesn't recheck before reposting, both reopen the
  exact duplicate-post risk the marker was built to prevent. **Fixed**: stated explicitly — the precheck
  (read + marker-scan, now with the author check) is re-run immediately before every individual post
  attempt: the first attempt, the one bounded retry, and any resumed/re-invoked attempt. None of these
  ever posts without a fresh precheck immediately first.
- **OQ2 cited the wrong precedent and deferred a question the codebase already answers** (SRE): revision
  2 cited B4's `plan_execution_state`/`EXECUTION_STATE_FIELDS` pattern, but that's the wrong file for a
  `task.*` field — the actually-relevant file is `scripts/validate_loop_lifecycle.py`, which gates
  lifecycle/merge readiness. Reading it directly: `source_issue_ref` gates nothing in lifecycle
  readiness — it's purely informational, used only for write-back targeting. **Fixed**: resolved now,
  not deferred — no `validate_loop_lifecycle.py` touch point is needed, stated as a conclusion with the
  correct citation.

Software Architect's one additional, non-blocking note (that `task_ref` in `platform-adapters.md` is
left undefined and now sits oddly next to the new, precisely-defined `source_issue_ref`) is addressed
with a one-line documentation note in Rollout.

**Round 3** (narrow, convergence-focused) confirmed the round-2 fixes hold against the real current
files — SRE and Software Architect both independently verified the `pr_opened`/`ts` provenance claim
against the real `run_log.py`, confirmed OQ2's resolution, and confirmed the precheck-re-run-per-attempt
fix, with no new findings. Security Architect found one real, narrow defect the other two rounds missed:
the companion `queue-policy.md` fix reused the name `task_source` for the new clean identifier, but
`orchestrator.md`'s own real `consumes:` declaration already defines `task_source` as the untrusted,
pasted-ticket-text channel — "a second, separate `task_source` value" was self-contradictory under one
name. Software Architect separately, independently noted the adjacent gap this same naming confusion was
masking: nothing in the design ever updated `orchestrator.md`'s own Inputs/`consumes:` declaration to
actually receive a second, structured identifier — the producer side (`queue-policy.md`) was specified,
the receiving side never was, for *either* caller, not just the standalone one as OQ3 previously implied.
**Fixed, in one targeted pass (not a full round 4, per all three personas' own "small, mechanical fix"
framing):**

- The new identifier is renamed to **`caller_task_ref`** (distinct from `task_source`, which keeps its
  existing meaning — the untrusted pasted-ticket-text channel, unchanged) and added as a new, separate
  entry in `orchestrator.md`'s own frontmatter `consumes:` list, alongside (not replacing) the existing
  `task_source` entry. §2's `source_issue_ref` derivation now reads explicitly from `caller_task_ref`,
  never from `task_source`. This single change closes both Security Architect's naming-collision finding
  and Software Architect's receiving-side-was-never-specified finding at once, since declaring the new
  `consumes:` entry IS the receiving-side specification that was missing.
- The new subsection's literal placement convention is now stated explicitly, citing the real,
  directly-reusable in-file precedent Software Architect found: `orchestrator.md`'s own existing
  unnumbered "## External comment-thread recheck and reply-and-verify (gap-backlog B4)" heading, inserted
  between §16 and §17 specifically to avoid a renumbering diff across ~51 cross-references. B8's own new
  subsection follows the identical pattern, inserted between §17 and §18 (since it triggers at §17's own
  terminal sentence, before any merge).

Security Architect's non-blocking suggestion (name the exact identity-discovery mechanism for the
author-scoped marker check, e.g. `gh auth status`, and require a dedicated service identity never shared
with anything that renders untrusted content into GitHub-authenticated actions) is folded into the
Components table below.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| `tracker_write_back_authorized` (session-level boolean, recorded in `orchestrator.md` §1) | Gates whether write-back is attempted at all, for the whole run | Orchestrator only, read once per run | Unchanged from revision 1 — sourced via the identical external/caller-supplied channel as `allowed_actions`/`autonomous_merge_authorized`/B7's `app_run` policy. Defaults `false` |
| `task.source_issue_ref` (new, per-task, in `reference/state-schema.yaml`) | `{repo: "owner/name", issue_number: int} \| null` — the one piece of per-task state this mechanism actually needs | Recorded once, immutably, at §2 task selection; never re-derived at write-back time | Derived from the new `caller_task_ref` consumed input (round-3 rename — see below), never from `task_source` (which keeps its existing, unchanged meaning: the untrusted pasted-ticket-text channel) and never from the ticket's own description/body text. `repo` is pinned from the Orchestrator's own already-verified repository context, never from the tracker-reference string |
| `orchestrator.md` frontmatter: new `consumes: caller_task_ref` entry (round-3 addition, closes both the naming-collision and the missing-receiving-side findings) | Declares, alongside the existing `consumes: task_source` entry (unchanged), a second, distinctly-named input: a clean, structured `{repo, issue_number}`-shaped identifier, never commingled with free-text `task_source` | Orchestrator's own Inputs contract | This single declaration is what was missing in revision 3 — the producer side (queue-policy.md) was specified, the receiving side never was, for either caller |
| `skills/backlog-runner/reference/queue-policy.md` §3 (**small, additive companion change — closes round 2's central finding**) | Backlog-runner now passes its own already-existing `backlog_run.tasks[].task_id` as the `caller_task_ref` input, alongside (never derived from or commingled with) the pasted ticket text it already sends as `task_source` | Backlog-runner's own existing session state, threaded one hop further | The one genuinely cross-skill touch in this design, justified because without it `source_issue_ref` stays null for every backlog-runner-dispatched task |
| `reference/mcp-capabilities.md` new row: "Issue/task tracker write (status comment + PR link)" | Declares the write capability | Documentation only | Optional; absent → skip write-back entirely. Unlike the existing "Issue/task tracker read" row (fully delegated, zero in-skill code), this row commits the skill to real, maintained GitHub-specific adapter code — stated explicitly, not implied as equivalent |
| GitHub Issues adapter (new helper the Orchestrator's write-back step calls) | `gh issue comment <issue_number> --repo <repo> --body <content>`, plus a pre-post idempotency check — read existing comments, keep only those authored by the write-back mechanism's own known actor identity (discovered via `gh auth status`/`gh api` against the authenticated account, round-3 addition — a dedicated service identity, never shared with any component that renders untrusted content into GitHub-authenticated actions), then look for this task's variant-tagged marker | Orchestrator, gated on `tracker_write_back_authorized` AND `task.source_issue_ref` being non-null | Jira/Linear/etc. explicitly disclosed as "not yet implemented," mirroring B7's own per-host disclosure pattern |
| `orchestrator.md` §18 (post-merge, unchanged slot) **and** a new, unnumbered subsection heading inserted between §17 and §18 — following the identical, already-established pattern of the existing "## External comment-thread recheck and reply-and-verify (gap-backlog B4)" heading (itself inserted between §16 and §17 specifically to avoid a renumbering diff across ~51 cross-references, round-3 citation per Software Architect) — triggered at §17's own terminal "stop at verified readiness and report the exact human action required" sentence | Posts one of two literal, variant-tagged templates (see Data model) depending on which path the task actually reached; the PR-opened path additionally re-reads the run log's own `pr_opened` event timestamp and does one minimal freshness re-check (`gh pr view --json state,mergedAt`) before posting | Orchestrator only | Fixes the backlog-runner-never-fires defect; explicitly does NOT duplicate §18's own multi-step re-verification procedure — borrows only the one fact (timestamp) and one check (still-open) this path actually needs |

**Confirmed untouched**: `workflow/builder.md`, `workflow/reviewer.md`, `workflow/lifecycle-gate.md` —
this mechanism remains entirely Orchestrator-side, never involves the Builder or Reviewer roles, no
finding-output schema change, no Blocking-standard condition. **Reversed from revision 1**:
`reference/state-schema.yaml` IS touched (one new per-task field, `source_issue_ref`).
**`scripts/validate_loop_lifecycle.py` is confirmed to need NO touch point** (resolved in round 2,
correcting revision 2's wrong-precedent deferral): read directly, every field that file checks gates
lifecycle/merge readiness; `source_issue_ref` gates nothing there — it's purely informational, used only
for write-back targeting. No `skills.yaml`/`composition_contracts.yaml` registration is needed —
`source_issue_ref` lives on the Orchestrator's own per-task state, not on `implementation_task`'s own
external/exempt-field surface, so it doesn't follow B7's `app_run` registration path.

## APIs

| Call | Contract | Consumer(s) | Notes |
|------|----------|-------------|-------|
| `gh issue comment <issue_number> --repo <repo> --body <content>` | Posts one comment to the specific, pinned `{repo, issue_number}` pair recorded in `task.source_issue_ref` | Orchestrator, at either write-back trigger point, after verification | Only attempted when (a) `tracker_write_back_authorized` is `true`, (b) `task.source_issue_ref` is non-null, (c) a FRESH idempotency pre-check (re-run immediately before THIS specific attempt — see Retries & idempotency) finds no existing same-variant marker for this task on that issue |
| `gh issue view <issue_number> --repo <repo> --comments` (idempotency pre-check) | Reads the target issue's existing comments, keeps only those authored by the write-back mechanism's own known actor identity (closes the marker-spoofing finding — a marker posted by any other commenter is ignored), then searches the kept set for `<!-- loop-task-implementer:write-back:<task_id>:<variant> -->` where `<variant>` is `merged` or `pr-opened` | Orchestrator, re-run immediately before every individual post attempt — the first attempt, the one bounded retry, and any resumed/re-invoked attempt — never treated as a one-time gate | A pure read; if it fails, treat as "marker not found" (fail toward attempting the post) |
| `gh pr view <pr_number> --json state,mergedAt` (new, PR-opened trigger point only) | A minimal freshness re-check confirming the PR is still open (not since closed/merged by someone else since §5's own earlier check) | Orchestrator, immediately before posting the `pr-opened`-variant comment | If the PR is no longer open, skip write-back for this trigger point entirely (the `merged` trigger point, if later reached, handles that case with its own §18 verification) |
| (Jira/Linear/etc. — not implemented) | N/A | N/A | Unchanged from revision 1 |

## Events

Still none — unchanged from revision 1's reasoning (reuses the Orchestrator's own existing completion-
report channel), but the idempotency mechanism now uses the tracker itself (the comment marker) as the
durable record, rather than relying on local state surviving a crash/resume — closing SRE's Finding C
without expanding `run_log.py`'s own closed event vocabulary.

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| `tracker_write_back_authorized` (session-level, boolean) | Unchanged from revision 1 | Orchestrator/run-level value | Caller |
| `task.source_issue_ref` (new, per-task, nullable) | `{repo: "owner/name", issue_number: int} \| null` | Recorded once at §2, read immutably at either write-back trigger point | Orchestrator, derived from the new `caller_task_ref` input (never `task_source`) |
| `caller_task_ref` (new, consumed input, round-3 rename) | A clean, structured, GitHub-Issue-shaped identifier, distinct from `task_source` | Declared in `orchestrator.md`'s own frontmatter `consumes:` list, alongside the existing `task_source` entry | Caller (standalone human instruction, or backlog-runner via the `queue-policy.md` companion change) |
| Write-back comment body — **two** literal templates now (closes SRE's Finding A) | Fixed structure per trigger point, cites only already-verified facts, embeds the idempotency marker | Rendered by the Orchestrator, posted via the GitHub Issues adapter | — |

**Literal content templates** (closes architecture-review Condition 3 — citation-by-reference only,
never raw task/finding/comment text; both now carry a variant-tagged marker, closing the marker-
collision finding):

Post-merge (§18, unchanged shape from revision 1):
```
Completed via loop-task-implementer.

PR: <pr_url>
Merged commit: <merge_commit_sha>
Verified on <target_branch> at <integration_timestamp_utc>

<!-- loop-task-implementer:write-back:<task_id>:merged -->
```

PR-opened / human-action-required (new, timestamp provenance fixed per round 2):
```
Ready for review via loop-task-implementer.

PR: <pr_url>
Opened against <target_branch> at <pr_opened_timestamp_utc>
Awaiting human merge decision.

<!-- loop-task-implementer:write-back:<task_id>:pr-opened -->
```

**`<variant>` discriminator** (closes Security Architect's round-2 marker-collision finding): a prior
`pr-opened` marker never blocks a subsequent `merged` post for the same `task_id` — only an identical
variant is treated as a duplicate. This prevents the more authoritative "merged" confirmation from ever
being silently suppressed by a stale "awaiting merge" one.

**Provenance correction** (closes Security Architect's round-1 Finding 4, and the round-2
`pr_opened_timestamp_utc` gap found independently by Software Architect and SRE): `pr_url` and
commit/branch identity trace back to §5's own independently-verified recording and GitHub-API-derived
facts, not task text; `target_branch` traces to §1's policy discovery (base branch);
`integration_timestamp_utc` traces to §18's own recording step. `pr_opened_timestamp_utc` is sourced
from the run log's own already-existing, independently-recorded `pr_opened` event's `ts` field (read
back, never re-derived or freshly asserted by the model at write-back time) — this routes through an
existing, already-trusted mechanism rather than inventing a new orchestrator.md verification step for a
fact that already exists elsewhere. Every placeholder remains non-attacker-steerable. No task
description, finding text, or PR/issue comment text is ever embedded, matching this session's own
citation-by-reference convention (B3's `regression_gate: `, B4's `redacted_note`, B6's
`convention_capture_similarity: `).

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| Write-back attempt (per completed task, per trigger point/variant) | `NOT_ATTEMPTED` (authorization absent, or `source_issue_ref` null, or PR-opened's freshness re-check finds the PR no longer open) → terminal; `SKIPPED_ALREADY_POSTED` (fresh idempotency pre-check finds a same-variant marker) → terminal; `ATTEMPTED -> POSTED` (call succeeds) → terminal; `ATTEMPTED -> FAILED -> [fresh pre-check re-run] -> ATTEMPTED -> POSTED` or `-> FAILED` (one bounded retry, closes SRE's round-1 Finding D — now correctly re-running the pre-check before the retry, closing round 2's finding that the original fix didn't) | At most one real post per task per trigger point/variant; attempted strictly after the triggering event (merge confirmed, or PR-opened-and-still-open confirmed); **the idempotency pre-check is re-run immediately before every single attempt in this state machine, including the retry** — never a one-time precondition | `FAILED` (after the one retry) is terminal — logged explicitly, never blocking or un-completing the task |

## Consistency

| Boundary | Model (strong / eventual) | Why |
|----------|-----------------------------|-----|
| Task completion vs. write-back | Unchanged from revision 1 — decoupled, write-back never feeds back into completion status | Core safety property, Condition 4 |
| `source_issue_ref` across a single task's lifetime | Strong, immutable once recorded at §2 | Prevents the confused-deputy risk — nothing after task selection can change which issue gets commented on |
| Idempotency across crash/resume/re-invocation AND across a single invocation's own retry | Strong, externally anchored (the tracker itself, via the author-scoped, variant-tagged comment marker) rather than locally anchored — **and now explicitly re-checked immediately before every individual post attempt**, closing round 2's finding that treating the pre-check as a one-time gate reopened duplicate-post risk under a flaky read (across invocations) or an un-rechecked retry (within one invocation) | The fresh-every-attempt re-check is what makes "externally anchored" actually hold under both failure shapes SRE identified, not just the crash-after-success happy path revision 2's claim was limited to |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `gh issue view --comments` (pre-check) | Yes — pure read | Re-run fresh immediately before every post attempt (not cached, not reused across attempts); a failed read is treated as "marker not found," failing toward attempting the post rather than silently going dark |
| `gh issue comment` | Not idempotent on its own, but made effectively idempotent by the pre-check **because the pre-check is re-run immediately before each attempt** (round-2 fix — revision 2 stated this safety property without actually re-running the check before the retry; this revision closes that gap explicitly) | **One bounded retry** after a short backoff on a transient failure, with the pre-check re-run immediately before that retry — if the first attempt actually succeeded server-side despite an apparent failure, the retry's own fresh pre-check finds the marker and skips, rather than posting a duplicate |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Write-back calls per run | Up to two calls per completed task (one pre-check read, one post) at each of up to two trigger points — still a small, bounded multiplier on task-completion cardinality, not a new scaling dimension | `run-queue.md`'s own per-ticket cardinality still bounds this; corrected from revision 1's backwards citation (this cardinality is now real for BOTH callers, standalone and backlog-runner) |
| Added wall-clock cost per task | Two lightweight `gh` calls, typically sub-second to a few seconds each, plus the bounded single retry's backoff in the rare failure case — still negligible against `orchestrator.md` §3's 30-minute response-wait budget | Unchanged conclusion from revision 1, re-confirmed against the slightly larger (two-call) footprint |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| `tracker_write_back_authorized` absent/false | `NOT_ATTEMPTED`; safe default, unchanged |
| `task.source_issue_ref` is null (task wasn't selected via a GitHub-Issue-shaped reference, or backlog-runner's own `queue-policy.md` companion change hasn't landed yet) | `NOT_ATTEMPTED`; logged as "no tracker reference, write-back skipped" |
| Idempotency pre-check finds an existing same-variant marker from the write-back actor's own identity | `SKIPPED_ALREADY_POSTED`; logged, not an error — expected on a resumed/re-invoked task |
| A marker exists but was posted by a different commenter (not the write-back actor's own identity) | Ignored — treated as "marker not found" per the author-scoping fix; prevents third-party marker-spoofing from permanently suppressing real write-back |
| PR-opened trigger's freshness re-check finds the PR no longer open | `NOT_ATTEMPTED` for this trigger point; the `merged` trigger point (if later reached) handles that case independently via its own §18 verification |
| `gh issue comment` fails once, transiently | Fresh pre-check re-run, then one bounded retry after short backoff |
| `gh issue comment` fails after the retry | `FAILED`; logged with a bare error category (matching B6's `ConventionCaptureFetchError` discipline); task completion wholly unaffected |
| Idempotency pre-check read itself fails | Treated as "marker not found" — fails toward attempting the post |
| Write-back attempted before either trigger condition is actually true | Prevented by construction |
| Tracker-write capability absent entirely | Skip write-back entirely for the whole run |

## Observability

| Signal | What's measured |
|--------|-------------------|
| `tracker_write_back: <outcome>` line in the task's completion notes | One of: not-attempted (authorization absent), not-attempted (no tracker reference), skipped (already posted), posted, failed (bare error category, post-retry) |

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 1 | `tracker_write_back_authorized` in `orchestrator.md` §1 (unchanged from revision 1) | No flag — default false, fully backward compatible |
| 2 | New `caller_task_ref` entry in `orchestrator.md`'s frontmatter `consumes:` list (alongside the existing, unchanged `task_source` entry); new `task.source_issue_ref` field in `reference/state-schema.yaml`, populated at §2 task selection from `caller_task_ref`, never from `task_source`/ticket body text | No flag — both null/absent by default |
| 3 | **Companion change**: `skills/backlog-runner/reference/queue-policy.md` §3 threads `backlog_run.tasks[].task_id` through as `caller_task_ref`, alongside the pasted ticket text it already sends as `task_source` | No flag — backlog-runner's own existing behavior is otherwise unchanged |
| 4 | New `reference/mcp-capabilities.md` row, with the delegation-model distinction from the read row stated explicitly; one-line note in `reference/platform-adapters.md` flagging the pre-existing, undefined `task_ref` field as vestigial now that `source_issue_ref` is the precisely-defined concept | Documentation only |
| 5 | New write-back logic: the author-scoped, variant-tagged idempotency pre-check (re-run before every attempt), the two trigger points (§18 post-merge; a new subsection sibling to §18 at §17's terminal sentence for PR-opened, including its own minimal freshness re-check and run-log-sourced timestamp), the two literal templates, the bounded-retry-with-recheck contract | Gated entirely by `tracker_write_back_authorized` AND `source_issue_ref` being non-null |
| 6 | Jira/Linear/etc. disclosed as "not yet implemented" | Documentation only |
| 7 | First real dry-run | **Open question** — see below |

## Open questions

1. **No concrete validation target exists in this session's own immediate work** (unchanged from
   revision 1's honest disclosure) — this gap-backlog's own tickets weren't worked from GitHub Issues.
   Mirrors B7's own OQ1 treatment.
2. **Per-tracker capability scoping beyond GitHub Issues remains genuinely unconfirmed** (unchanged from
   revision 1) — explicitly out of scope for this ticket's first implementation.
3. **The exact mechanism for deriving `task.source_issue_ref` from `caller_task_ref` is stated as a
   principle but not as a fully-specified parsing/validation algorithm** — e.g. what shapes are
   recognized as "GitHub-Issue-shaped" (a bare `owner/repo#123`? a full URL? a `gh` CLI-recognized
   reference?) is left for implementation to pin down concretely. This is now equally open for BOTH
   callers (corrected in round 3 — Software Architect found the round-2 claim that backlog-runner's case
   was already "resolved" overclaimed: the producer side was specified, but `orchestrator.md`'s own
   receiving-side contract wasn't declared until this round's `consumes: caller_task_ref` fix — the
   parsing/validation algorithm itself remains open for both).
4. **The `queue-policy.md` companion change's own review scope** — this design proposes a small, additive
   change to a file owned by a different skill (`backlog-runner`). Whether that change needs its own
   pass through `backlog-runner`'s own doctrine chain (or can land as part of this ticket's own
   implementation, given its small size and direct justification) is a process question for the
   Orchestrator/human to decide, not resolved here.

(The schema-registration question that was Open Question 2 in revision 2 — whether
`scripts/validate_loop_lifecycle.py` needs a touch point for the new `source_issue_ref` field — is
resolved, not open: no touch point is needed, per round 2's own direct reading of that file.)
