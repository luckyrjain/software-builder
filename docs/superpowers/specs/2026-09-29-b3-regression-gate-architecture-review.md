# Architecture review — B3: bug-diagnosis → loop-task-implementer fail-before/pass-after regression gate

**Decision: Approved with conditions**

Sound, bounded scope: turn an already-existing, already-optional Reviewer practice into a real,
mandatory-for-this-one-handoff-path evidence requirement, backed by a genuinely new capability (checking
out and running a specific test at two distinct commits) that the Reviewer role doesn't have today. Five
conditions need closing before implementation — the most important being that the "fail-before" half of
the gate needs a real, bounded execution mechanism that doesn't blur the Reviewer's read-only boundary or
silently balloon its time/token budget.

## Architecture decision

Three coupled pieces, scoped narrowly to the `bug-diagnosis → loop-task-implementer` handoff path only
(not a change to every regression-test-bearing task, which would be scope creep beyond this ticket):

1. **A structured repro-test-identity field**, threaded from `bug_diagnosis_report.repro_evidence`
   (currently free-text) through `implementation_task`'s envelope (a new field, since `specialist_inputs`
   is an untyped bag) into the Reviewer's evidence requirements — carrying enough to programmatically
   re-run the specific reproducing test (file/test-name/command), when the repro is expressible that way.
2. **A genuinely new Reviewer capability**: check out the task's base commit (the value already tracked
   in `state-schema.yaml`'s `base_commit_at_start`) in a disposable location, run the identified test,
   confirm it fails; then confirm the same test passes at head. This does not exist anywhere in
   loop-task-implementer today — `change-identity.yaml`'s `base_sha`/`head_sha` are review-freshness
   fingerprints, not execution targets, and the existing revert-in-place-at-head practice
   (`reviewer.md:47,168`) never touches the real base commit.
3. **A mandatory (not "you may") evidence requirement**, scoped specifically to tasks whose origin is a
   bug-diagnosis handoff (identifiable by the new structured field's presence) — a blocking Reviewer
   finding when the gate can't be satisfied, not a new machine-enforced `validate_loop_lifecycle.py`
   check (smaller blast radius; stays consistent with the existing evidence-requirements-are-Reviewer-owned
   model rather than reopening the lifecycle validator).

The escalation matrix (`cross-skill-escalation.md:138,199`) gets its existing rows' text updated to
reference the new required field/gate — documentation only, per the matrix's own stated convention that
rows are "optional handoff offers, not enforcement mechanisms"; the gate itself is enforced inside
loop-task-implementer's Reviewer workflow, not in the matrix.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| Checking out and executing code at an EARLIER commit than the one under review is a materially different action than anything the Reviewer's current "read-only, disposable local mutations" grant (`reviewer.md:39-47`) was written to describe — risks either being read too narrowly (blocking a legitimate gate) or too broadly (an implicit license creep into arbitrary historical-commit execution) | Security / Operability | Blocking | See Conditions §1 |
| Running a full checkout-and-test cycle at a second commit doubles part of the Reviewer's runtime for this handoff path, against this skill's own existing response-wait/time/token circuit breakers | Scale limits / Operability | Conditional | See Conditions §2 |
| `repro_evidence` is free-text today; not every diagnosed bug has a repro expressible as a single automated test command (e.g., manual repro, external-system state) — a design that assumes 100% coverage will either silently skip the gate or wrongly block tasks with a legitimately non-automatable repro | Failure modes | Blocking | See Conditions §3 |
| A test failing at the base commit doesn't by itself prove it fails *for the diagnosed reason* — environment drift between base and head (dependency versions, migration state) could produce an unrelated failure that a naive gate would misread as confirming the bug | Failure modes | Conditional | See Conditions §4 |
| Scoping the mandatory gate to "tasks originating from a bug-diagnosis handoff" requires a real, checkable signal for that origin — if the signal is soft/inferrable rather than a structured field, the gate's mandatory-vs-optional boundary becomes fuzzy exactly where the ticket wants it sharp | Architecture decision | Conditional | See Conditions §5 |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Number of bug-diagnosis-originated tasks in one multi-task plan | Not a hard failure, but each one now costs roughly 2x the Reviewer's test-execution time (base + head) versus a non-gated task — a real, cumulative operability cost across a busy plan, not addressed by the ticket's own acceptance criteria and worth naming explicitly rather than discovering it later | Not stated in the ticket; the existing per-task response-wait budget (`orchestrator.md`'s circuit breakers) already bounds the worst case per task, but the aggregate cost across many such tasks in one run is new |
| Repro tests requiring non-trivial setup (a running service, seeded database, specific env vars) at a HISTORICAL commit whose setup requirements may differ from head | Breaks down when base-commit setup fails independent of the diagnosed bug — the checkout-and-run step itself could error before ever reaching the test, a failure mode distinct from "test ran and didn't fail" | Not addressed by the ticket; must be a named, detectable failure mode (Conditions §4) |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| Repro isn't expressible as a single automated test/command | The structured field is absent or explicitly marked non-automatable | Falls through to the existing generic, optional practice (`reviewer.md:168`) rather than blocking the task on an impossible requirement | Must be explicit, not an assumed 100%-coverage design (Conditions §3) |
| Base-commit checkout/setup itself fails, independent of the bug | The Reviewer's own execution attempt errors before reaching a pass/fail test result | Distinguish "setup failed" from "test passed unexpectedly" — the former is inconclusive, not a green light; escalate rather than silently treat as satisfied | New failure class this ticket introduces; must be named (Conditions §4) |
| The identified test fails at base for a reason unrelated to the diagnosed root cause (environment drift) | Requires the Reviewer to check the failure's content/message against the diagnosis's own stated root cause, not just a pass/fail boolean | Treat as `NEEDS_EVIDENCE`, not a satisfied gate | Sound as proposed, contingent on this being stated explicitly rather than left to the Reviewer's own unguided judgment (Conditions §4) |
| A non-bug-diagnosis-originated task accidentally trips the new mandatory gate because the origin signal is ambiguous | Depends entirely on whether the origin field is structured/reliable | Over-broad enforcement blocking unrelated tasks, or under-broad enforcement silently skipping the ticket's own core value-add | See Conditions §5 |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| Reviewer executes code at a historical commit it didn't independently choose (the task's own recorded `base_commit_at_start`) — same trust model as executing code at head today, but at a point the Reviewer has less foreknowledge of | Local, disposable execution only — no broadened write/network capability requested or implied by the design | Contained to the Reviewer's own disposable local environment, same as its existing head-commit execution rights | Not a new class of risk versus what the Reviewer already does at head, provided the mechanism is explicitly scoped to "the task's own recorded base commit," never an arbitrary caller-supplied commit (Conditions §1) |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Doubled Reviewer runtime for bug-diagnosis-originated tasks | Repo owner / the Orchestrator's existing budget machinery | Needs explicit accounting against existing circuit breakers | See Conditions §2 |
| New structured field maintenance (bug-diagnosis's report format, implementation_task's envelope, Reviewer's evidence-requirements doc) | Repo owner | Same "curated, can drift" cost class as every other typed field in this repo | Not a new burden category, matches existing practice |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| Leave the gate generic and optional for every regression-test-bearing task (current state) | Rejected: this is literally the state the ticket exists to fix — a real, mandatory gate specifically for the one handoff path where a structured repro exists to make it checkable | Correctly motivates building something, not a strawman |
| Make the mandatory fail-before/pass-after gate apply to every task type, not just bug-diagnosis-originated ones | Rejected: over-broad — no other handoff path currently supplies a structured, checkable repro-test identity, so mandating this everywhere would either be unenforceable prose or require inventing that structure for every producer skill, well beyond this ticket's scope | Correct rejection, keeps blast radius to the one path that actually has the evidence to support a real gate |
| Build a separate, dedicated verification sub-role/skill to run the dual-commit test cycle, instead of extending the Reviewer's own capabilities | Rejected: the Reviewer already has local-mutation/execution rights and a disposable-worktree model; extending it with a second, historical-commit checkout is a natural in-role capability, not a new coupling or role | Reuse over new machinery, consistent with this session's own established preference (matches B1's "use the existing skill, don't build a parallel mechanism" reasoning) |

## Conditions

1. **Define the base-commit checkout mechanism precisely, and its boundary.** State exactly how the
   Reviewer obtains the base commit's code without disturbing its own working state or the shared
   repository (e.g., a disposable secondary worktree/clone at `base_commit_at_start`, never a caller- or
   task-text-supplied arbitrary commit). Confirm this stays inside the Reviewer's existing "read-only
   toward shared state, disposable local mutations only" boundary — it may execute code, but must never
   commit, push, or otherwise mutate anything outside its own disposable checkout.
2. **State explicitly how the gate's cost is charged against existing budgets** (response-wait/time/token
   circuit breakers), so a plan with several bug-diagnosis-originated tasks can't silently exceed them
   without the accounting being visible.
3. **Define the fallback when a repro isn't expressible as a single automated test/command.** The
   structured field must support an explicit "not automatable" state (not just absence, which could be
   mistaken for an oversight), and the gate must fall through to the existing generic/optional practice in
   that case, not block on an impossible requirement.
4. **Require the Reviewer to confirm the base-commit failure matches the diagnosed root cause, and to
   distinguish setup failure from an inconclusive/unexpected pass**, not just record a bare boolean. Name
   both failure modes (unrelated base-commit failure, setup failure before the test even runs) explicitly
   as `NEEDS_EVIDENCE`-class outcomes, never a silently-satisfied gate.
5. **Define the "originates from a bug-diagnosis handoff" signal as a concrete, structured field** (not an
   inferred/soft signal), so the mandatory-vs-optional boundary the ticket wants is actually checkable, and
   state that its absence means the task falls under the existing generic/optional practice, never the new
   mandatory one by default.

None of these five block starting a `system-design` pass — they're precise, implementable requirements
for that pass to satisfy, not open architectural questions.
