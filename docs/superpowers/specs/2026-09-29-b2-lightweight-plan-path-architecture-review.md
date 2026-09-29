# Architecture review — B2: lightweight ticket → plan path for small tasks

**Decision: Approved with conditions**

Direction sound: keep `implementation-planner` in the loop (plan identity/DAG/traceability/resume
intact) instead of duplicating the existing ungoverned `implementation_task` bypass. But the design as
submitted leaves the single highest-risk question unanswered — what makes a task eligible — as open
self-assessment ("caller judges small enough"), which is exactly the shape of gap that let real
architectural work slip through unreviewed. Five conditions close this before implementation.

## Architecture decision

Add a bounded "lightweight plan path": for a task the caller (Orchestrator) asserts is small,
`implementation-planner` accepts a minimal, non-blocking STUB for each of the three currently-mandatory
report keys (`system_design_spec`, `architecture_review_report`, `change_impact_report`) — never an
omission, since the code structurally requires all three keys present with a non-`UNKNOWN`/non-blocking
status (confirmed: `_BLOCKING_SOURCE_STATUSES`, `implementation_plan.py:380-402`). The stub asserts "no
material design/architecture/impact-analysis decision applies to this task" — a caller-supplied claim,
evidence the same way any other supplied report is evidence, never a judgment `implementation-planner`
makes itself. This preserves the skill's documented "read-only leaf... does not invoke design/review
skills" boundary. Eligibility gates on a reused, repurposed constant: the existing 40-files/1500-lines
`SIZE_HARD_STOP` (`orchestrator.md:319-322`), applied here as a pre-planning *estimate* rather than its
native mid-execution *measurement* — a genuine repurposing that needs its own justification, not an
activation of dormant logic for this exact purpose.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| "Small enough" has no defined criteria — as submitted it's open caller self-assessment, the same actor that later dispatches the Builder the stub unblocks. A self-certifying loop with no independent check | Failure modes | Blocking | See Conditions §1 |
| The stub's central claim ("no material decision applies") is unverified at the moment it's made — nothing in the design says what facts ground that claim, or what happens if it's wrong | Security / Failure modes | Blocking | See Conditions §2 |
| Reusing the 40-files/1500-lines constant as a pre-implementation *estimate* is a different measurement than its native mid-execution *actual diff size* — no diff exists yet at planning time, so the number is a guess, not a measurement, and the design doesn't say whose guess or how it's derived | Scale limits | Conditional | See Conditions §5 |
| No audit trail distinguishing "legitimately trivial, correctly fast-tracked" from "routinely dodging review" — formalizing an informal pattern this session already used ad hoc (F2-followup) removes the friction that made each prior skip a visible, reasoned judgment call | Operability | Conditional | See Conditions §4 |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Underestimated task scope | The estimate is wrong and the actual diff exceeds 40 files/1500 lines mid-execution | Not a hard failure — `loop-task-implementer`'s own `SIZE_HARD_STOP` circuit breaker (`orchestrator.md:319-322`) still fires during Builder/Reviewer dispatch regardless of which planning path produced the task, since this ticket only touches what happens *before* that loop starts. This is a genuine existing safety net, not something to reinvent — but the design must say so explicitly (Conditions §3) rather than leave the "what if wrong" case unaddressed |
| Volume of lightweight-routed tasks over time | No stated bound — nothing in the design limits how often the path is invoked | Real but not blocking; addressed by requiring an auditable record (Conditions §4) rather than a hard cap, since a hard cap wasn't asked for and isn't evidenced as needed yet |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| A task with real architectural implications is misjudged "small," routed through the lightweight path, and ships with zero design/architecture/impact review | None today — the stub's claim is asserted, not checked | Depends entirely on `loop-task-implementer`'s own two review lenses catching the problem at implementation time, after the fact, with no upstream design record to check against | Root cause of the blocking risk above; see Conditions §1–2 |
| Estimated scope undershoots actual diff size | `SIZE_HARD_STOP` circuit breaker fires mid-execution | Existing, already-tested escalation path — sound, contingent on being named explicitly (Conditions §3) | Not a gap to fix, a fact to state |
| Lightweight path becomes the default even for genuinely ambiguous tasks, eroding this session's own established doctrine (full chain unless a reasoned exception applies) | Only visible retrospectively, if at all, without a record | None automatic | See Conditions §4 |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| Caller-asserted "no material decision applies" stub → accepted by `implementation-planner` as non-blocking evidence → real `implementation_plan` → real Builder dispatch (repository-write) | An unverified self-assessment crossing directly into a write-capable pipeline, with no independent check between assertion and consequence | Whatever the resulting task's Builder dispatch can do — the same blast radius as any other implementation-planner-sourced task, but reached with strictly less upstream scrutiny than every other path this session has used | Structurally similar to B1's untrusted-ticket-text concern, but here the weak link is the *caller's own unverified estimate*, not external ticket content — still needs an explicit, named mitigation, not an assumption that "the caller is the Orchestrator, so it's fine" (Conditions §1–2) |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Auditable record of lightweight-path usage | Repo owner / Orchestrator | Needs explicit design — currently unaddressed | See Conditions §4 |
| Threshold-estimate provenance (how the pre-planning number is derived) | Repo owner | Needs explicit design — currently unaddressed | See Conditions §5 |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| Do nothing — keep every task on the full architecture-review/system-design/change-impact chain regardless of size | Rejected: this session already informally fast-tracked a trivial 9-line config change (F2-followup) without the full chain — B2's actual value is formalizing a pattern already in ad hoc use, with an auditable record, rather than leaving it as an undocumented judgment call each time | Correctly motivates building something, not a strawman |
| Route small tasks through the existing "legacy `implementation_task`" bypass instead of a new lightweight path in `implementation-planner` | Rejected: that path skips `implementation-planner` entirely — no plan identity, DAG, execution waves, or resume-compatibility. Confirmed structurally different capability, not a duplicate | Correct rejection, grounded in direct code read of `composition_contracts.yaml:103-119` and `normalize_input:1316-1320` |
| Invent a new, purpose-built size-estimation mechanism instead of reusing `orchestrator.md`'s existing 40-files/1500-lines constant | Rejected in favor of reuse: the constant is the one real, already-precedented "how big is too big" number in this repo, cited independently in multiple docs — reusing it (as an estimate, explicitly distinguished from its native measurement use) avoids inventing parallel, potentially inconsistent thresholds | Reuse is directionally right, contingent on the estimate/measurement distinction being stated explicitly (Conditions §5) |

## Conditions

1. **Define concrete, checkable eligibility criteria for the lightweight path — not open self-assessment.**
   Either a bounded allowlist of change classes (e.g., single-file config value change, doc-only edit,
   dependency version bump with no behavior change, additive test-only change) or objective proxies
   derivable from the task itself (e.g., target_paths count ≤ a stated small N, no new cross-skill
   coupling, no schema/contract touch) — concrete enough that a reader could check whether a given task
   actually qualifies, not a vibe. Ambiguous or borderline cases must default to the full chain (fail
   safe), matching this session's own established doctrine.
2. **Ground the stub's "no material decision applies" claim in something checkable, and state what
   happens when it's wrong.** At minimum: name the fact pattern that must hold for the claim to be true
   (tying back to Condition 1's eligibility criteria), and confirm `implementation-planner` performs no
   new judgment of its own — it only accepts a caller-supplied claim as evidence, identical in kind to how
   it already treats any other supplied report.
3. **State explicitly that the existing `SIZE_HARD_STOP` circuit breaker (`orchestrator.md:319-322`) is
   the safety net for an underestimated task**, firing during the normal Builder/Reviewer loop regardless
   of which planning path produced the task. No new retroactive-escalation machinery is required — say so
   as a design decision, not an implicit assumption.
4. **Design a minimal, durable record of lightweight-path usage** (e.g., a field on the emitted
   `implementation_plan` or a log entry) capturing which eligibility criterion applied and who/what
   asserted it, so a later audit can distinguish legitimate fast-tracking from routine review-dodging.
5. **State the estimate/measurement distinction explicitly**: the reused 40-files/1500-lines number is
   applied at planning time as a caller-derived *estimate* (grounded in target_paths / acceptance
   criteria), structurally different from its native mid-execution *actual diff measurement* use. Define
   what happens when the caller cannot produce a confident estimate — default to full chain, not to
   lightweight-path eligibility.

None of these five block starting a `system-design` pass — they're precise, implementable requirements
for that pass to satisfy, not open architectural questions.
