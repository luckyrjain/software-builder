# System Design Spec — B5: flaky-CI rerun budget and flake classification

**Readiness: Ready with open questions**

Revision 4. Implements
[2026-09-30-b5-flaky-ci-policy-architecture-review.md](2026-09-30-b5-flaky-ci-policy-architecture-review.md)
("Approved with conditions", 6 conditions — the architecture review's closing paragraph also names a
"pressure test for a flaky then green run" acceptance criterion; this is the ticket's own criterion, not
a numbered 7th condition, and revision 1 mistakenly cited it as "(Condition 7)" in several places —
corrected throughout this revision).

## Revision history

**Revision 1** proposed: an eligibility gate inspecting a failed check's own output for a disqualifying
signal (test-framework failure marker) then a qualifying transience signal (rate-limit/timeout/network
error/5xx, matched as free text into a new `observed_signal` log field); a small rerun budget shared
against the existing `max_ci_poll_minutes` clock; a worked "canonical" example built from PR #315's
`install-engine-windows` flake.

Round 1 adversarial review (Security Architect, SRE, Software Architect, run in parallel) converged on
several real, code-grounded defects:

- **The free-text `observed_signal` field was wrong on two independent grounds that both point to the same
  fix.** Software Architect found it violates this exact log's own documented rule
  (`reference/run-log.md:42-44`: *"Ticket text, PR bodies and tool output are untrusted... and never go in
  `data`; use `changed_file_count`, not a file list"*) — CI failure output is tool output, and the design
  put it in verbatim. Security Architect found, independently, that this same free-text field is precisely
  what an adversarial PR author would need writable in order to defeat the eligibility gate at all: a test
  that swallows its own real (deterministic) failure in a `try/except` and prints attacker-chosen,
  transience-shaped text, or one that crashes before the test framework's own failure-reporter line is
  ever emitted (`SystemExit`/`os._exit` inside a pytest test body is a real, well-known way to abort a
  session without producing a `FAILED .../AssertionError` line), defeats "check the disqualifying pattern
  first" because the disqualifying markers were never conditioned on anything the *test process itself*
  is trusted to emit honestly. **One fix closes both**: restrict "qualifying" signals to a closed,
  CI-*platform*-emitted vocabulary (a runner/orchestration-layer message — "this step has timed out," "the
  operation was canceled," an HTTP-level error from the CI provider's own control plane failing to even
  schedule the job) — never anything the PR's own test process printed to its own stdout. A test process
  cannot forge a message the CI platform itself emits about its own infrastructure. `os._exit(1)` from
  inside a test still just looks like "step failed, exit code 1, no platform-level transience marker" —
  it falls into the pre-existing, unchanged `AMBIGUOUS` judgment call, never automatically into `QUALIFIED`.
- **The "no new capability" framing was false against the real capability declarations** (Security
  Architect and Software Architect, converging independently, same shape as B4's own precedent finding):
  `mcp-capabilities.md`'s only CI-related row covers *status* (PASS/FAIL/PENDING), never platform-level
  failure detail. Fixed below with an explicit new capability row and a fail-closed degraded path.
- **The evidence-preservation backstop was unreachable as described** (Security Architect): the design
  said "a human reviewing the merged PR later" can see the evidence trail, but `orchestrator.md:1074`
  forbids ever giving the run log to a Builder/Reviewer, a PR body, or a report. Reworded below to
  correctly describe this skill's actual, pre-existing evidence-access model (Orchestrator-only run log,
  inspectable by the repo owner directly — the same access model every other piece of Reviewer/adjudication
  evidence in this skill already uses, not a new gap B5 introduces).
- **Budget-sharing arithmetic didn't survive contact with this repo's own real CI history** (SRE, using
  live `gh api` data from PR #315's actual rerun): `gh run rerun` without `--failed` reruns the *entire*
  workflow, including already-passed required checks, not just the flaky one — re-consuming
  `max_ci_poll_minutes` on checks that already went green. Fixed below by mandating `--failed` specifically
  and stating the real worst-case arithmetic rather than asserting sharing is free.
- **The "canonical precedent" was invalid on its own terms** (SRE): `install-engine-windows` is
  *not* a required check (`docs/github-ruleset-main.json`'s `required_check_contexts` is
  `["lint-static", "lint-suites"]` only) — it never enters §15's logic at all, so it provides zero
  evidence for tuning a policy that only governs required checks. Removed as a "canonical" precedent;
  the honest state (no real required-check flake precedent exists yet) is now stated directly rather than
  contradicted by a worked example presented alongside it.
- **The Rollout plan's own file list would fail an existing, already-wired parity test** (SRE):
  `test_reference_documents_every_event_actor_outcome_reason_and_exit_code`
  (`tests/test_run_log.py:2803-2810`) asserts every `REASON_CODES` value appears in `run-log.md`'s
  reason-code enumeration sentence, not just the event-payload table. Fixed below by adding that edit to
  Phase 1's file list explicitly.
- **A resume/interruption gap in the "no reachable null" completeness claim** (Software Architect): if the
  Orchestrator's own session ends after dispatching a rerun but before observing its outcome, the design
  gave no rule preventing a second, duplicate rerun from being dispatched on resume, silently
  double-spending the budget. Fixed below by reusing ground-truth CI-platform data already available for
  exactly this purpose (SRE's own research quoted the real `run_attempt` field from `gh api`) — reconcile
  against the platform's own attempt count on resume, never trust a prose-tracked counter alone across an
  interruption boundary.
- Non-blocking, fixed inline: `attempt`/`eligible_for_rerun` should get real type validation, not just
  `failure_classification`; the "1:1 bullet-to-code lockstep" claim about `SKILL.md`'s circuit breakers was
  factually wrong (one bullet already covers two codes, `OTHER` has none) — corrected; `ci.status`'s
  pre-existing `TIMEOUT` value was never cross-referenced against the new `undiagnosed` classification —
  now stated explicitly; `ci_polled`/`budget_checked` overlap was checked and confirmed clean (no fix
  needed, now stated explicitly in the doc itself rather than left for a reviewer to re-verify).

**Round 2 adversarial review** (Security Architect, SRE, Software Architect, run in parallel against
revision 2) confirmed the evidence-access fix and the state-machine completeness fix both genuinely hold
under direct re-verification, and — independently, from two different angles — found the same real gap
in revision 2's own closed-enum fix:

- **Only 2 of the 7 `observed_signal` values have any real, non-spoofable structural data source.**
  Security Architect and SRE independently checked GitHub Actions' actual job/run API and found a job's
  `conclusion` field (`success | failure | cancelled | skipped | timed_out | action_required | neutral |
  stale | startup_failure`) is the only place a *platform*-authored (not test-process-authored) signal
  genuinely lives — and it only cleanly backs **`TIMEOUT`** (`conclusion: timed_out`) and
  **`PROVISIONING_FAILURE`** (`conclusion: startup_failure`). The other five values
  (`RATE_LIMIT`/`NETWORK_ERROR`/`DNS_FAILURE`/`HTTP_5XX`/`RUNNER_ABNORMAL_TERMINATION`) have no distinct
  API field at all — they would only be reachable by reading raw log/annotation text, which (per round 1's
  own finding) a test process can forge via an unauthenticated `::error::` workflow command, reopening the
  exact evasion attack revision 2 was written to close. `RUNNER_ABNORMAL_TERMINATION` additionally can't
  even be cleanly backed by `conclusion: cancelled`, since that same value also covers an operator
  cancelling the run or a superseded push — no distinct signal separates "runner died" from either of
  those. Fixed below: the enum is narrowed to exactly the two values with a real, named, structural field.
- **The rerun/query mechanism has no committed permission entry anywhere this skill actually ships**
  (SRE, a genuinely new finding this round, not a re-check of round 1): `.claude/settings.json` (the real,
  tracked, shared permission surface) has no `gh run rerun`, `gh run view`, or `gh api` entry at all — only
  `gh pr view/checks/diff`. The design's own "already used live by this session" framing was true only of
  this specific session's untracked, personal `.claude/settings.local.json`, not of anything the shared
  skill declares. Fixed below with an explicit Phase 1 permission-surface addition.
- **The `ci_polled` validation instruction would break the majority of the event's real traffic**
  (Software Architect): `ci_polled` fires on every CI status change (`orchestrator.md:1060`), including
  plain `PENDING` polls and a first-try clean `PASS` — the large majority of its real call sites, confirmed
  directly against `tests/test_run_log.py`, carry neither `observed_signal` nor `failure_classification` at
  all. Revision 2's instruction to validate these "the exact same pattern as `escalated.reason`" (an
  unconditional-required check) would raise `ValueError` on every one of those pre-existing, legitimate
  calls. Fixed below: both new closed-enum fields are validated **only when the key is present** in
  `data` — absence is always valid, a different (and necessary) rule from `escalated.reason`'s.
- One further precision fix (SRE): the Components-table claim that `--failed` "materially reduces" the
  poll-budget cost is only true when the *faster* required check (`lint-static`) is the one that flakes —
  when the *slower* one (`lint-suites`, this repo's actual bottleneck check) flakes, `--failed` and a bare
  whole-workflow rerun cost the same wall-clock time, since the two checks already run in parallel. The
  disclosed worst-case figure in Capacity was already accurate; only the causal claim about *why* `--failed`
  helps needed correcting. Fixed below.
- One further disclosure (Software Architect, non-blocking): the `run_attempt` resume-reconciliation check
  is scoped to this skill's own single-Orchestrator rerun path (confirmed no other code path in this repo
  calls `gh run rerun`) — a run retriggered entirely outside that path (e.g. a human using
  `workflow_dispatch`) would create a new `run_id` with its own fresh `run_attempt`, invisible to this
  reconciliation. This is the same class of out-of-band-human-action gap every other budget/counter in this
  skill already has (nothing stops a human from manually merging past `max_dirty_reviews` either) — stated
  as an accepted scope boundary, not a new risk, in Open questions below.

**Round 3 adversarial review** (SRE, final targeted re-check of revision 3) confirmed the narrowed 2-value
enum is now consistent everywhere in the document (zero stale references to the 5 dropped values outside
the revision-history/dropped-values explanation), but found two precise gaps in revision 3's own fixes,
both the same shape as round 2's findings, one level deeper:

- **The Components table and the Rollout permission item both conflated job-level and run-level
  `conclusion`**, contradicting the Data model table's own (correct) split: `TIMEOUT` is a **job**-level
  fact (`conclusion: timed_out` on a specific job), `PROVISIONING_FAILURE` is a **run**-level fact
  (`conclusion: startup_failure` — the run's jobs were never scheduled at all, so there is no job object to
  carry it). The Rollout Phase 1 permission item only named a run-level query
  (`gh run view --json conclusion,attempt`), which would give the Orchestrator `PROVISIONING_FAILURE`
  detection and resume-reconciliation, but no declared way to read the job-level `conclusion: timed_out`
  value `TIMEOUT` actually needs. Fixed below with an explicit second query shape and corrected wording
  throughout.
- **The "enforce only when present" validation rule was stated for `observed_signal`/`failure_classification`
  but only implied, never stated, for `attempt`/`eligible_for_rerun`** — the same bug class round 2 found,
  shifted to two different fields. An implementer following the Rollout Phase 1 line literally (as written,
  it attached no "only when present" qualifier to `attempt`/`eligible_for_rerun`) would reintroduce the
  round-2 `ValueError`-on-legitimate-traffic bug for these two fields instead. Fixed below by stating the
  rule applies to all four new fields uniformly, once, unambiguously.
- Minor, non-blocking (SRE): architecture-review Condition 6 demanded an explicit, stated rationale for
  reusing `CI_UNDIAGNOSABLE` vs. minting a new code — the design picked `CI_RERUN_EXHAUSTED` correctly but
  never once wrote down the comparison the condition asked for. Fixed below with one explicit sentence.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| **Eligibility gate** (revised again — narrower, precisely-sourced, job/run distinction now stated consistently) | Given a *failed* required check, first check for a disqualifying signal (a test-framework failure marker in the check's own reported output — `FAILED `, `AssertionError`, a named failing test, a lint/type error). If none, check two distinct structured sources, never log/annotation text: (a) the **job's own** `conclusion` field for `timed_out` → `TIMEOUT`; (b) the **run's own** `conclusion` field for `startup_failure` → `PROVISIONING_FAILURE` (a run-level fact only, since a never-scheduled run has no job object to carry it). Neither present → unchanged, existing judgment call (out of scope) | Orchestrator-only, read-only against the CI platform's own structured job-level *and* run-level metadata — **never log content** | Narrowed from a 7-value prose vocabulary to exactly the 2 values GitHub Actions' real API structurally distinguishes from anything a test process can emit — **round 3 correction**: these two values come from two different query levels (job vs. run), not one shared "conclusion field" as earlier phrasing implied; both query shapes are declared explicitly in the Rollout plan's permission item. `RATE_LIMIT`/`NETWORK_ERROR`/`DNS_FAILURE`/`HTTP_5XX`/`RUNNER_ABNORMAL_TERMINATION` are dropped from this design entirely (see Data model) — they have no structural field, and any log-text-based detection would reopen the exact evasion attack round 1 found |
| **New capability declaration** (`mcp-capabilities.md`) | Declares "CI job structured metadata (`conclusion` field) for the exact head" (distinct from the existing "CI status" row, which only covers PASS/FAIL/PENDING) — **explicitly scoped to structured fields, never log content**, closing round 2's finding that revision 2's row description didn't distinguish the two | Documentation only | Degraded path: absent → eligibility gate never runs → falls through to the existing, unchanged ambiguous-failure judgment call |
| **Permission/capability surface** (**new component, closes round 2's SRE finding**) | The rerun dispatch (`gh run rerun --failed`) and the `conclusion`/`run_attempt` query need an actual committed entry in this skill's real permission surface — round 2 found `.claude/settings.json` (the tracked, shared surface) has neither; the design's "already used live" framing rested on an untracked, personal `.claude/settings.local.json` | `.claude/settings.json` (or the equivalent per-host permission declaration, per `platform-adapters.md`, for non-Claude-Code hosts) | This is not documentation-only — it is a real, required Rollout Phase 1 change, not an assumption |
| **Rerun budget** (`max_ci_reruns`, unchanged from rev 1) | Bounds reruns per eligible failure | `state-schema.yaml`'s `budgets:` block | Default `1`, now **explicitly disclosed as unvalidated** against a real required-check precedent (see Capacity) rather than justified by an invalid worked example |
| **Rerun mechanism** (now specified precisely — was implicit in rev 1) | Re-trigger **only** the failed job(s), never the whole workflow | `gh run rerun --failed` specifically, not bare `gh run rerun` | Reduces CI *compute* cost unconditionally (1 job vs. up to 4). **Corrected, round 2 (SRE)**: its effect on *poll-budget wall-clock time* is conditional, not unconditionally "material" — this repo's two required checks run in parallel, so `--failed` only saves poll-budget time when the *faster* check (`lint-static`) is the one that flakes; when the *slower* bottleneck check (`lint-suites`) flakes, `--failed` and a bare whole-workflow rerun cost the same wall-clock time, since the parallel-bounded wait is unchanged either way. See Capacity's already-honest worst-case figure, unaffected by this correction |
| **`failure_classification` enum** (unchanged from rev 1) | Four values, see Data model | `ci:` block | Unchanged |
| **`ci_polled` payload extension** (revised) | `attempt` (validated `int >= 0`), `eligible_for_rerun` (validated `bool`), `observed_signal` (**revised: closed enum, not free text**), `failure_classification` (closed enum, unchanged) | `run_log.py`'s existing `ci_polled` event | All four new fields now get explicit validation in `_validate_event_data`, not just `failure_classification` |
| **Resume reconciliation** (**new component, closes the round-1 interruption gap**) | On any Orchestrator resume mid-rerun-cycle, before applying any §15 logic, query the CI platform's own ground-truth attempt count for the check (e.g. GitHub's real `run_attempt` field, already directly queryable and already used live by this session to verify PR #315's own history) and reconcile against the prose-tracked `max_ci_reruns` counter — never trust the prose counter alone across an interruption boundary | Orchestrator-only, read-only | Reuses data the CI platform already reports for exactly this purpose — no new mechanism, no new capability beyond what's already used to re-trigger and observe CI |
| **Non-bypass enforcement** (unchanged) | A check failing on every attempt within budget still lands in the pre-existing "infrastructure or pre-existing failure" branch | `orchestrator.md` §15 prose, unmodified branch structure | Unchanged |

## APIs

Not applicable in the conventional sense (unchanged from rev 1) — this is a prose-workflow extension plus
one small, real code-level extension to `run_log.py`'s event-validation function and one new
`mcp-capabilities.md` row.

## Events

| Event | Payload extension | Notes |
|-------|----------------------|-------|
| `ci_polled` (existing event, unchanged tuple entry) | `attempt` (int ≥ 0), `eligible_for_rerun` (bool), `observed_signal` (**closed enum, revised** — see Data model), `failure_classification` (closed enum, unchanged) | All four now validated in `_validate_event_data`, matching the module's own stated philosophy (`run_log.py:614`: *"Free prose is the injection channel, so the two events that invite it take codes, not sentences"*) — this design now actually follows that stated rule for `ci_polled` too, rather than exempting one new field from it |

## Data model

**`observed_signal` — now a closed, 2-value enum, precisely sourced** (round 1 closed the free-text
problem; round 2 found 5 of the resulting 7 values had no real structural backing and narrowed it further):

```
TIMEOUT | PROVISIONING_FAILURE
```

Each value maps to exactly one real GitHub Actions job `conclusion` value, never anything read from a
test process's own stdout/exit content or from log/annotation text:

| `observed_signal` value | Real API source | Query level |
|---|---|---|
| `TIMEOUT` | job `conclusion: timed_out` | **Job-level** — e.g. `gh api repos/{owner}/{repo}/actions/runs/{run_id}/jobs`, or `gh run view --json jobs` |
| `PROVISIONING_FAILURE` | run `conclusion: startup_failure` (the run itself could not be scheduled) | **Run-level** — e.g. `gh run view --json conclusion` |

These are genuinely two different query shapes, not one shared "conclusion field" query — the Rollout
plan's permission item (below) declares both explicitly, closing round 3's finding that an earlier phrasing
conflated them and left the job-level query undeclared.

**Dropped from this design entirely** (round 2 finding, both Security Architect and SRE independently):
`RATE_LIMIT`, `NETWORK_ERROR`, `DNS_FAILURE`, `HTTP_5XX` — none has a distinct job/run-level API field;
the only place that granularity would exist is raw log/annotation text, which a test process can forge via
an unauthenticated `::error::` workflow command, reopening the exact evasion attack round 1 found.
`RUNNER_ABNORMAL_TERMINATION` is also dropped — `conclusion: cancelled` is the closest candidate, but that
same value also covers an operator cancelling the run or a superseded push, with no distinct signal
separating the three. A future revision could reintroduce some of these, but only alongside an explicitly
declared, carefully-scoped log-content-read capability with its own stated trust model — not silently
folded into "platform-emitted" as revision 2 did.

This closes, precisely rather than aspirationally: (a) `run-log.md:42-44`'s "never store tool output as
prose, use an identifier" rule; (b) the free-text channel an adversarial PR author's own test code could
have written into; (c) the eligibility gate's content-blindness to anything the PR's own code can
produce — a value can now only be assigned from a field the CI platform's scheduler/runner service sets,
never from anything the job's own steps print or do.

**Validation rule, corrected — applies uniformly to all four new fields, stated once, unambiguously**
(closes round 2's Software Architect finding, and round 3's finding that this rule was left ambiguous for
two of the four fields): every one of `attempt`, `eligible_for_rerun`, `observed_signal`, and
`failure_classification` is validated in `_validate_event_data` as **enforce only when the key is present
in `data`; absence is always valid, for all four fields alike** — a different rule from `escalated.reason`'s
unconditional-required check, because `ci_polled` fires on every CI status change (`orchestrator.md:1060`),
including plain `PENDING` polls and a first-try clean `PASS`, the large majority of which legitimately
carry **none** of these four fields at all. This is not "two fields conditional, two fields required" —
round 3 found that framing left `attempt`/`eligible_for_rerun` ambiguous in every other section of this
doc; there is exactly one rule, applied to all four fields the same way. Concretely, in
`_validate_event_data`'s existing code shape:

```python
if event == "ci_polled":
    if "attempt" in data and not (isinstance(data["attempt"], int) and not isinstance(data["attempt"], bool) and data["attempt"] >= 0):
        raise ValueError("ci_polled.attempt, if present, must be a non-negative int")
    if "eligible_for_rerun" in data and not isinstance(data["eligible_for_rerun"], bool):
        raise ValueError("ci_polled.eligible_for_rerun, if present, must be a bool")
    if "observed_signal" in data and data["observed_signal"] not in {"TIMEOUT", "PROVISIONING_FAILURE"}:
        raise ValueError("ci_polled.observed_signal, if present, must be one of: TIMEOUT, PROVISIONING_FAILURE")
    if "failure_classification" in data and data["failure_classification"] not in {
        "regression", "infrastructure", "flaky_confirmed_transient", "undiagnosed"
    }:
        raise ValueError("ci_polled.failure_classification, if present, must be one of the four enum values")
```

**`failure_classification`** (unchanged from rev 1):

```yaml
ci:
  failure_classification: null  # null | regression | infrastructure | flaky_confirmed_transient | undiagnosed
```

- `regression` — disqualifying signal found, or the existing unchanged ambiguous-case judgment resolves as
  PR-caused.
- `infrastructure` — the existing unchanged ambiguous-case judgment resolves as environmental, **or** a
  qualifying (platform-level) signal was retried to budget exhaustion and still failed.
- `flaky_confirmed_transient` — a qualifying signal was retried within budget and passed.
- `undiagnosed` — polling never obtained a definitive `PASS`/`FAIL` at all (**cross-referenced explicitly,
  closing the round-1 gap**: `ci.status` is `TIMEOUT` — the pre-existing enum value at
  `state-schema.yaml:143` — whenever `failure_classification` is `undiagnosed`; this design does not add a
  new status value, only finally gives the existing `TIMEOUT` status a matching classification value it
  never had before).

**Reason-code decision, stated explicitly** (architecture review Condition 6 — round 3 found this was
never actually written down despite the design consistently using the right answer): mint **`CI_RERUN_EXHAUSTED`**
as a new code; do **not** reuse `CI_UNDIAGNOSABLE`. `CI_UNDIAGNOSABLE` (pre-existing, `run_log.py:152`,
paired with `orchestrator.md:785`'s "stop polling and report pending" branch) means "polling never
produced a definitive signal at all" — exactly the `undiagnosed` classification above. `CI_RERUN_EXHAUSTED`
means something materially different: the failure's own `conclusion` was clearly and structurally
diagnosed as `timed_out`/`startup_failure`, it was retried the configured number of times, and every
attempt still failed — a real diagnosis (transient-shaped but not actually transient, or a persistent
infrastructure outage) that `CI_UNDIAGNOSABLE` would misrepresent as "we don't know anything." Two distinct
codes for two distinct situations, per Condition 6's own explicit either-answer-acceptable requirement.

**Rerun budget** (unchanged field, revised justification):

```yaml
budgets:
  max_ci_reruns: 1   # per eligible-failure check. Deliberately unvalidated against a real required-check
                      # flake precedent (see Capacity) -- treat as a considered starting point, not an
                      # empirically-tuned value.
```

**Interaction with `max_ci_poll_minutes` — revised with real arithmetic** (closes the round-1 starvation
finding): reruns are charged against the same existing clock (unchanged from rev 1), but the mechanism is
now specified precisely: **`gh run rerun --failed`**, not bare `gh run rerun` — reruns only the check(s)
that actually failed, never already-passed required checks. Real worst-case arithmetic, using this
session's own directly-observed PR #315 data (a real `run_attempt: 2` history pulled via `gh api`): a
single required check's own runtime (this repo's `lint-suites` alone runs ~3 minutes) plus the initial
attempt's own wait, plus `gh run rerun`'s own dispatch/queue latency, plus the 30-second poll cadence
(`orchestrator.md:773`) can plausibly consume 40%+ of the 15-minute budget for a **single** rerun cycle in
the best case observed so far — and worse if the initial attempt was itself slow (queued runners, a larger
suite). This is stated as an **accepted, disclosed residual risk**, not solved: a genuinely slow required
check combined with a genuine transient failure can still exhaust `max_ci_poll_minutes` before the rerun
cycle completes, falling through to the existing (unchanged) "stop polling, report pending" outcome — this
is a *degradation*, not a *safety* failure, since it lands in an already-safe pre-existing branch, but it
should not be presented as free.

**Resume reconciliation rule** (**new, closes the round-1 interruption gap**): before applying any §15
eligibility/rerun logic, the Orchestrator queries the CI platform's own ground-truth attempt count for the
check in question (e.g. GitHub's `run_attempt` field via the same `gh api`/`gh run view` access already
used to observe CI status). If the platform's own attempt count is already higher than what the
prose-tracked `max_ci_reruns` counter believes has been spent, reconcile the counter upward to match
ground truth before deciding whether further reruns are permitted — never trust the prose counter alone
across a resume boundary, since a rerun can be in flight on the platform's side with no corresponding local
record if the session ended between dispatch and observation.

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| A required check's classification (per poll cycle, `ci.status` + `ci.failure_classification`) | `PENDING → {PASS, FAIL}`; `FAIL → [eligibility gate] → {DISQUALIFIED, QUALIFIED (conclusion ∈ {timed_out, startup_failure} only), AMBIGUOUS}`; `DISQUALIFIED → regression (terminal, status stays FAIL)`; `AMBIGUOUS → {regression, infrastructure} (terminal, existing unchanged judgment, status stays FAIL)`; `QUALIFIED → [rerun via --failed, ≤ max_ci_reruns, reconciled against platform ground truth on any resume] → {PASS → flaky_confirmed_transient (terminal, status becomes PASS), FAIL again → retry-or-exhausted → infrastructure (terminal, status stays FAIL)}`; `PENDING → [poll budget exhausted] → undiagnosed (terminal, status becomes TIMEOUT — the pre-existing enum value, now finally paired with a classification)` | Every transition into a terminal state sets both `ci.status` and `ci.failure_classification` — the previous revision's table stated only the new field; this revision states both explicitly, closing the round-1 completeness gap. The resume-reconciliation rule (Data model) is what makes "no reachable null, no reachable double-count" actually true across an interruption, not just within a single uninterrupted session |

## Consistency

Unchanged from revision 1 — the Orchestrator remains the sole mutator of official workflow state; no new
consistency primitive.

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `gh run rerun --failed` | Not naturally idempotent, but now explicitly reconciled against platform ground truth on resume (Data model) — closes the round-1 double-rerun risk | Capped at `max_ci_reruns` (default 1); **the eligibility gate, now restricted to platform-emitted signals, is the real guard against both pointless retries and adversarial evasion** — a disqualified or ambiguous failure is never retried at all |
| Eligibility-gate signal matching | Idempotent, and now content-blind to anything the PR's own test process can produce (Components/Data model) | N/A |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Additional CI compute cost | One extra job run (only the failed job, via `--failed`) per eligible failure, capped at `max_ci_reruns: 1` | Reduced from rev 1's implicit whole-workflow-rerun assumption |
| Additional active-polling time | Charged against the existing `max_ci_poll_minutes` clock — **real worst-case arithmetic now stated** (see Data model): a single rerun cycle can plausibly consume 40%+ of the 15-minute budget in this repo's own observed best case, more if the initial attempt was slow. Disclosed as an accepted residual degradation (falls to an already-safe existing branch), not solved |
| `max_ci_reruns: 1`'s validity | **Explicitly unvalidated** against a real required-check flake precedent — the only real precedent this session has observed (`install-engine-windows` on PR #315) governs a check that is not required and never enters this logic at all. Stated honestly as an open question (see below), not papered over with an invalid worked example |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| An adversarial PR author crafts test output to look transient-shaped (swallowed exception, forged message, or a crash before the test framework's own failure line) | **Closed by construction, not just evidence-preservation**: qualifying signals are restricted to CI-*platform*-emitted infrastructure messages, which the PR's own test process cannot produce regardless of what it prints or how it crashes — this class of failure now lands in `AMBIGUOUS` (existing, unchanged judgment call), never `QUALIFIED`, closing the round-1 Security Architect finding directly rather than relying on an unreachable audit trail as the only defense |
| A genuinely ambiguous timeout-shaped failure (architecture review Condition 2's accepted irreducible limitation) | Unchanged: an honest, disclosed limitation — but now bounded to platform-reported timeouts specifically (e.g. a runner-level "step timed out" message), a narrower and more trustworthy signal than any timeout-shaped string a test process itself could print |
| A persistent (not transient) infrastructure outage | Exhausts `max_ci_reruns`, classified `infrastructure`, escalates via `CI_RERUN_EXHAUSTED` — unchanged from rev 1 |
| The `ci_polled` payload extension is malformed | **All four new fields now validated** (`attempt: int >= 0`, `eligible_for_rerun: bool`, `observed_signal`/`failure_classification`: closed enums) — closes the round-1 gap where only `failure_classification` was checked |
| Orchestrator session ends mid-rerun-cycle (dispatched, not yet observed) | **New, closes round-1 gap**: resume reconciliation against the CI platform's own ground-truth attempt count, before any further §15 logic runs — prevents both a silently-lost rerun-in-flight and a duplicate, budget-double-spending rerun |
| `max_ci_poll_minutes` exhausted mid-rerun-cycle because a rerun took longer than expected | Falls to the existing, unchanged "stop polling, report pending" branch (`undiagnosed`/`TIMEOUT`) — a disclosed degradation, not a new unsafe state |

## Observability

Unchanged from revision 1, plus: `observed_signal`'s distribution (now a closed enum) gives a real,
queryable answer to *which* platform-level failure class is actually occurring most often — strictly more
useful than a free-text field would have been for this purpose too, alongside the security fix.

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 1 | `state-schema.yaml`: add `max_ci_reruns: 1`, extend `ci.failure_classification`'s comment with the 4-value enum. `run_log.py`: add the `_validate_event_data` branch for `ci_polled` covering all four new fields with the single "enforce only when present" rule (see Data model's exact code shape); add `CI_RERUN_EXHAUSTED` to `REASON_CODES`. `run-log.md`: extend `ci_polled`'s documented payload row **and** add `CI_RERUN_EXHAUSTED` to the reason-code enumeration sentence (`test_reference_documents_every_event_actor_outcome_reason_and_exit_code`, `tests/test_run_log.py:2803-2810`). `mcp-capabilities.md`: add the new "CI job/run structured metadata" capability row, explicitly scoped to structured fields, never log content, with its degraded path. `SKILL.md`: add the matching new circuit-breaker bullet. **Permission surface (round 2, corrected round 3):** add explicit `.claude/settings.json` allow-list entries for **both** query levels the design actually needs, not one shared entry — `gh run rerun --failed` (rerun dispatch); `gh api repos/{owner}/{repo}/actions/runs/{run_id}/jobs` or `gh run view --json jobs` (job-level `conclusion`, needed for `TIMEOUT`); `gh run view --json conclusion,attempt` (run-level `conclusion` and `run_attempt`, needed for `PROVISIONING_FAILURE` and resume-reconciliation) — this is real, required permission-surface work across two distinct query shapes, not one assumption; state the equivalent per-host declaration in `platform-adapters.md` for non-Claude-Code hosts | No flag — purely additive, except the permission-surface addition, which is a real capability grant, not a no-op |
| 2 | `orchestrator.md` §15: insert the eligibility gate (platform-signal-only), the `--failed`-specific rerun sub-flow, and the resume-reconciliation rule between the two existing branches; §3: add the `max_ci_reruns` budget bullet | Depends on Phase 1 |
| 3 | Pressure-test scenario (ticket's own acceptance criterion, not "Condition 7" — corrected citation) | Verification |

**Pressure-test scenario**, revised: the code-level regression test (reject-then-iterate-accept, matching
`test_escalated_and_run_completed_take_a_closed_set_of_codes`'s exact convention) now covers all four new
`ci_polled` fields, not just `failure_classification`. The documented worked example in `orchestrator.md`
§15 no longer presents `install-engine-windows`/PR #315 as "canonical" (it's not a required check and
provides no evidence for this policy) — instead, the section states plainly that no real required-check
flake precedent has been observed yet, and gives a constructed (not historical) example of a `lint-suites`
run failing with a platform-reported runner timeout, retried once via `--failed`, passing — illustrating
the mechanism without overclaiming empirical validation it doesn't have.

## Open questions

1. `max_ci_reruns: 1`'s correctness is genuinely unvalidated against a real required-check flake — carried
   forward honestly rather than resolved by an invalid precedent.
2. The now-narrowed 2-value qualifying vocabulary (`TIMEOUT`/`PROVISIONING_FAILURE`) is real and precisely
   sourced for GitHub Actions, but correspondingly narrow — most real transient CI issues (rate limits,
   network blips) will now fall to the existing, unchanged `AMBIGUOUS` judgment call rather than the new
   rerun path. This is the deliberate, safe trade-off round 2 forced (a smaller but honestly-verifiable
   `QUALIFIED` set, not a broader but spoofable one) — a future revision could widen it only alongside a
   genuinely new, carefully-scoped, explicitly-declared log-content-read capability, never by silently
   reclassifying log text as "platform-emitted."
3. The real worst-case budget arithmetic (Capacity) is disclosed but not resolved — reserving a carved-out
   sub-budget for reruns instead of pure sharing remains a live option for a future revision if this proves
   too tight in practice.
4. **New, round 2 (Software Architect):** the `run_attempt` resume-reconciliation check is scoped to this
   skill's own single-Orchestrator rerun path — a rerun triggered entirely outside that path (e.g. a human
   using `workflow_dispatch` directly) creates a new `run_id` with its own fresh `run_attempt`, invisible to
   this reconciliation. Accepted as an out-of-band-human-action gap, the same class every other
   budget/counter in this skill already has (nothing stops a human from manually merging past
   `max_dirty_reviews` either) — not a new risk this design introduces.
