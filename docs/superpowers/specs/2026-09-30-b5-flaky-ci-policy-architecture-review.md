# Architecture review — B5: flaky-CI rerun budget and flake classification

**Decision: Approved with conditions**

Sound, narrowly-scoped addition to an existing, well-defined seam (`orchestrator.md` §15's two-branch CI
outcome), not a new subsystem — but the ticket's S-sizing understates it: the single decision that makes
this safe or dangerous (when a failure is even *eligible* for a rerun) is exactly the kind of load-bearing
judgment call this session's larger tickets (B1-B4) each found hiding under an apparently-simple surface.
Six conditions need closing before implementation.

## Architecture decision

One new, bounded branch inserted between the two existing terminal outcomes in `orchestrator.md` §15 "CI
handling" (`orchestrator.md:767-791`) — never replacing either "CI fails because of the pull request"
(`:776`) or "CI is an infrastructure or pre-existing failure" (`:783`), both of which remain the *only*
terminal classifications:

1. **A new, small rerun budget** (`max_ci_reruns`, following the existing `budgets:` block's own
   non-null-default / explicit-`unlimited`-opt-out convention already used by `max_dirty_reviews`/
   `max_fix_attempts_per_finding`) governing how many times a *failed* (never merely pending) required
   check may be re-triggered before the Orchestrator must commit to one of the two existing branches.
2. **An evidence-based eligibility gate, decided before any rerun is attempted** — not "retry once and see
   what happens." Only a failure whose own signature suggests transience (network error, timeout,
   rate-limit response, infrastructure-provisioning failure) is eligible; a failure with a clear,
   content-addressable test-assertion message is never eligible and goes straight to "CI fails because of
   the pull request," full stop, no rerun attempted at all.
3. **Populate the already-declared-but-inert `failure_classification` field** (`state-schema.yaml:147`,
   currently `null` forever, never enumerated or read anywhere) with a real value set.
4. **Record real evidence for every rerun attempt** — what was observed on the failed attempt and the
   rerun attempt, not a bare counter — so a human auditing later can see *why* something was classified as
   flaky.
5. **An explicit non-bypass guarantee**: a check failing on every attempt within budget, including the
   last, still lands in one of the two pre-existing terminal branches — never silently treated as passed,
   never silently skipped.
6. **A reason-code decision** for the rerun-budget-exhausted-and-still-failing case (reuse
   `CI_UNDIAGNOSABLE` or mint new vocabulary), made explicitly rather than left implicit.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| A loosely-defined eligibility rule ("just retry once on any failure, see if it goes green") would let a genuinely intermittent bug *introduced by the PR itself* — a race condition, a flaky test the PR's own change made flaky — get silently reclassified as "infrastructure" purely because a rerun happened to pass, with no evidence the failure was actually infrastructure-caused. This is the single most important risk in this design | Architecture decision / Failure modes | Blocking | See Conditions §1-2 |
| A timeout-shaped failure is genuinely ambiguous by signature alone — it could be real CI infrastructure slowness, or it could be a real performance regression/deadlock the PR introduced manifesting as a timeout under load. No purely signature-based eligibility rule can perfectly distinguish these | Failure modes | Conditional | See Conditions §2, §4 |
| A rerun that eventually passes must not be indistinguishable from a first-try clean CI pass in the recorded evidence, or this ticket's own "evidence recorded" acceptance criterion is unmet in substance even if a counter technically exists | Operability / Failure modes | Conditional | See Conditions §4 |
| The rerun budget silently double-spending the existing `max_ci_poll_minutes` active-polling budget (each rerun re-enters polling) — without explicit accounting, a flaky-rerun policy could make the existing, already-enforced 15-minute circuit breaker behave differently than documented elsewhere | Scale limits / Operability | Conditional | See Conditions §3 |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Number of reruns per failed check | Not itself a hard problem — a small budget (1-2) bounds this trivially, matching every other budget in this skill's `budgets:` block | `state-schema.yaml`'s existing budget fields are all small integers (2-3); no reason for this one to differ |
| Interaction with `max_ci_poll_minutes` (15 min, already enforced) | Breaks down if reruns are not charged against this same active-polling clock — a rerun that resets the poll-time budget to zero could let CI diagnosis run far longer than the documented 15-minute ceiling implies elsewhere in this skill | Not addressed by the ticket itself; must be stated explicitly (Condition §3) |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| A failure signature that looks transience-shaped (timeout, rate-limit) is actually a real regression the PR introduced | The eligibility gate is signature-based, not omniscient — this cannot be perfectly detected at design time | Mitigated, not eliminated, by Condition §4's mandatory evidence recording: even a "flaky, then green" outcome is disclosed with what was actually observed on the failed attempt, so a human reviewing the merged PR later can still see the ambiguous signal and re-open it if warranted — this is the honest, achievable guarantee, not perfect automatic discrimination | Must be stated as an accepted residual limitation, not silently assumed solved |
| A check that fails identically on every rerun within budget (a persistent, not transient, infrastructure outage) | Exhausts `max_ci_reruns` | Falls to the pre-existing "infrastructure or pre-existing failure" branch, exactly as it does today without this ticket — no new stuck state introduced | Sound, matches the ticket's own "never bypassed" criterion directly |
| A content-addressable test-assertion failure is mistakenly treated as rerun-eligible by an overly-broad eligibility rule | Requires the eligibility rule itself to be precise and narrow, per Condition §2 | None if the rule is wrong — this is exactly why Condition §2 is Blocking, not Conditional | The central risk this whole ticket exists to prevent, not incidental |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| Re-triggering a CI job is an existing, already-used capability (`gh run rerun`, exercised live by this session during B4's own merge) — this ticket adds a *policy* for when to use it, not a new capability or a new trust boundary | Unchanged — same CI system, same required-checks model | Unchanged | Not a new security surface; no new capability declaration needed |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Real CI compute cost of reruns (actual minutes/dollars on the CI provider) | Repo owner | Small and bounded by the small rerun budget, but real and worth naming rather than treating reruns as free | Not addressed by the ticket; should be a one-line acknowledgment, not a blocking gap |
| Evidence-recording overhead (what specifically distinguishes this from "just log the counter") | The Orchestrator's existing run-log/evidence machinery | Same class as every other evidence-recording obligation this skill already has (e.g. Reviewer evidence, regression-gate evidence) — not a new burden category | Reuse `run_log.py`'s existing `ci_polled` event, extending its payload rather than inventing a new event type |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| Keep the current binary policy (no rerun at all) | Rejected: this is literally the gap the ticket exists to fix, and this session directly hit it live during B4's own merge with no documented policy to follow | Correctly motivates building something |
| Blanket "always retry once on any CI failure, before classifying" (no eligibility gate) | Rejected: masks real, PR-introduced intermittent bugs as infrastructure flake with zero evidence basis for the reclassification — the single most important risk this review identifies | Correct rejection, not a strawman — this is the naive version of the feature and a real temptation given how simple "just retry it" sounds |
| A full flake-detection heuristic/ML system, or per-check historical flake-rate tracking | Rejected as disproportionate: this is an S-sized ticket in a solo-maintainer repo; a signature-based eligibility gate plus a small bounded budget and honest evidence recording is proportionate to actual scale, matching this session's own established discipline against over-engineering | Correct scoping decision, not a missed opportunity |

## Conditions

1. **Define the eligibility gate as an evidence-based, signature-driven rule, decided *before* any rerun is
   attempted** — never "retry once on any failure and see." State the concrete signature classes that make
   a failure rerun-eligible (network error, timeout, rate-limit response, infrastructure-provisioning
   failure) and state explicitly that a content-addressable test-assertion failure is never eligible,
   regardless of how few reruns the budget would otherwise allow.
2. **Acknowledge and disclose the irreducible ambiguity of a timeout-shaped failure** rather than assuming
   the eligibility gate perfectly separates real regressions from infrastructure flakiness — state that
   this is a best-effort, evidence-preserving classification, not a perfect one.
3. **State explicitly how the rerun budget interacts with the existing `max_ci_poll_minutes` active-polling
   budget** — reruns must be charged against that same clock, not reset it, so the documented 15-minute
   ceiling remains meaningful.
4. **Require real, comparative evidence for every rerun attempt** (what was observed on the failed attempt
   vs. the rerun attempt) — not a bare counter — and require this evidence to remain visible even when the
   rerun ultimately passes, so a "flaky, then green" outcome is never indistinguishable from a first-try
   clean pass in the audit trail.
5. **Confirm the non-bypass guarantee has a concrete mechanism**: a check failing on every attempt within
   budget, including the last, must land in one of the two pre-existing terminal branches — state exactly
   how this is enforced (not merely restated as intent).
6. **Make the reason-code decision explicit, with rationale**: state whether `CI_UNDIAGNOSABLE` is reused
   for the rerun-exhausted-still-failing case, or whether a distinct new code is warranted because it
   represents a materially different situation (ran out of retries with a classified-as-flaky signature,
   vs. never got a diagnosable signal at all) — either answer is acceptable, but it must be a stated
   decision, not an omission.

None of these six block starting a `system-design` pass — they're precise, implementable requirements for
that pass to satisfy, not open architectural questions. The ticket's own acceptance criterion (a "pressure
test for a flaky then green run") should be carried into the design phase as a concrete, named test
scenario, not left to implementation-time improvisation.
