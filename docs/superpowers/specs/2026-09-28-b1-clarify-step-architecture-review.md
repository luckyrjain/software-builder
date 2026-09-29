# Architecture review — B1: optional clarify step in loop-task-implementer's task selection

**Decision: Approved with conditions**

Sound direction — reusing `engineering-decision-discovery`'s existing frontier/interview model rather
than building a parallel one inside `orchestrator.md` is the right call, and it correctly turns a
would-be full-stop escalation into a bounded, resolvable interruption for the common case. Five
conditions need closing before implementation, the most important being a real state-persistence gap:
as proposed, a resolved clarification has nowhere durable to live, so a resumed session could re-ask
the same question indefinitely.

## Architecture decision

Insert a new branch into `orchestrator.md`'s §2 task-selection precondition ("acceptance criteria are
sufficiently concrete," currently a bare gate with no dedicated failure path). When a candidate task fails
that check and interaction is available, the Orchestrator invokes `engineering-decision-discovery` as a
bounded sub-step — confirmed net-new coupling, not an existing cross-skill edge — scoped to the task's own
underspecified acceptance criteria, capped at N questions, falling through to the existing generic §19
escalation path if the sub-step itself returns `BLOCKED`/`PARTIAL` or the question budget is exhausted
without resolution. In an "unattended" context — a concept that doesn't exist inside `orchestrator.md`
today (its only prior use of the word routes callers to the separate `backlog-runner` skill entirely) and
must be newly defined as an `orchestrator.md` input — the clarify step is skipped and the existing
escalation path is taken directly, matching `engineering-decision-discovery`'s own
`unattended=true -> BLOCKED, never synthesize` semantics. A new Tier-2 fixture (the first ever to exercise
§2's task-selection logic) closes out the ticket's acceptance criteria.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| A resolved clarification has no durable home — `engineering-decision-discovery` is explicitly report-only (writes `ENGINEERING_DECISION_RECORD.md`, never touches `plan_execution_state`/`state-schema.yaml`), so a session that resumes a plan later has no way to know a task's acceptance criteria were already clarified | Failure modes | Blocking | See Conditions §1 |
| "Unattended" is currently a *different, unrelated* concept in this repo (a routing boundary to `backlog-runner`) — reusing the word for a new `orchestrator.md`-internal mode without a precise, separate definition risks confusing the two | Failure modes | Conditional | See Conditions §2 |
| Ticket acceptance-criteria text is untrusted, and the clarify step turns that text into *questions put to a human* — a manipulated ticket could shape a clarifying question to social-engineer an approval that then feeds a real Builder dispatch (repository-write), a higher-consequence pipeline than `engineering-decision-discovery`'s own report-only blast radius on its own | Security | Blocking | See Conditions §4 |
| The clarify step's own token/time cost is unbudgeted relative to the Orchestrator's existing per-task/session budgets (§3) — could silently consume budget meant for actual implementation work | Operability | Conditional | See Conditions §5 |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Number of simultaneously-underspecified tasks in one multi-task plan | Not a hard failure, but a real operability cost — N questions × however many eligible-but-underspecified tasks exist could turn an otherwise-autonomous multi-task run into a question-per-task interactive slog | Not stated in the design as submitted; the ticket itself scopes this to loop-task-implementer's interactive, human-driven mode (unattended/bulk runs go through the separate `backlog-runner` skill instead, per this repo's own routing table), which bounds but doesn't eliminate the cost |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| A task's clarification is resolved in session A, but session B resumes the same plan later and re-selects the same task | None today — nothing tracks "this task was already clarified" | Re-ask the same question(s), wasting the human's time and the question budget a second time, or (worse) risk the interview producing a *different* answer the second time if the decision tree rebuilds differently | Root cause of the blocking risk above; see Conditions §1 |
| Clarify sub-step exhausts its N-question budget without resolving the ambiguity | The sub-step's own return status (`BLOCKED`/`PARTIAL`) | Falls through to the existing §19 escalation path — correctly reuses infrastructure that already exists, doesn't need to be reinvented | Sound as proposed, contingent on N and the fallthrough being explicit (Conditions §3) |
| A manipulated ticket shapes a clarifying question to extract an unsafe approval | None automatic — depends entirely on whether `engineering-decision-discovery`'s own safe-rendering rules are actually inherited by this integration, not assumed | The human reads a rendered, escaped/fenced question, same protection the standalone skill already has | Must be explicitly restated as part of this integration's own docs, not assumed to carry over silently (Conditions §4) |
| Clarify step's own cost isn't tracked against a budget | Only visible after the fact, if a legitimate task starves for budget because an earlier task's clarify step consumed it | None automatic | See Conditions §5 |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| Ticket/acceptance-criteria text (untrusted) → clarify-step question text (rendered to a human) → human's answer → potentially feeds task selection and eventually a real Builder dispatch (repository-write) | Untrusted repo/ticket content crossing into human-facing prompts that gate a write-capable pipeline | Whatever the human is talked into approving, then whatever the Builder that answer unblocks can do | This composition is new — `engineering-decision-discovery` alone never reaches repository-write, but composed into `loop-task-implementer`'s flow it now sits upstream of one. See Conditions §4 |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Clarify-step budget accounting | Repo owner / the Orchestrator's existing budget machinery | Needs explicit design — currently unaddressed | See Conditions §5 |
| Keeping the new fixture registered and passing as `orchestrator.md` evolves | Repo owner | Same "curated, can drift" cost class as every other fixture in this repo | Not a new burden, matches existing practice |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| Do nothing — keep the current "exclude from selection, generic §19 escalate" behavior for any underspecified task | Rejected: every underspecified task today produces a full-stop escalation even when a quick, bounded clarification would unblock it without stopping the whole workflow — B1's actual value is turning a hard stop into a resolvable interruption for the common case | Correctly motivates building something, not a strawman |
| Build a new, lightweight inline ask-N-questions mechanism directly inside `orchestrator.md`, instead of invoking `engineering-decision-discovery` | Would duplicate logic (frontier computation, recommend-then-ask, resolved-vs-deferred bookkeeping) that already exists and is already tested in the standalone skill | Correct rejection — reuse is the right call, contingent on the composition risks above being closed |

## Conditions

1. **Design where a resolved clarification durably lives before implementation starts.** Either the
   resolved answer gets written back into the task's own acceptance-criteria text in the plan (so a later
   read sees it as already-concrete), or a new tracked field is added to `plan_execution_state`
   recording "task X's ambiguity was resolved as Y, at generation Z." Without this, a resumed session has
   no way to avoid re-asking, and no way to distinguish "never asked" from "already resolved."
2. **Define "unattended" precisely as a new, `orchestrator.md`-local `interaction_policy`/
   `human_available`-style input**, explicitly distinct from this repo's existing, unrelated use of the
   word to route callers to `backlog-runner`. State the distinction in the doc itself so a future reader
   doesn't conflate the two.
3. **Define N concretely** (a specific bounded number, not "some cap") **and the exact fallthrough
   behavior at exhaustion** (falls through to §19 escalation — state this explicitly rather than leaving
   it implied).
4. **Restate `engineering-decision-discovery`'s safe-rendering rules explicitly as part of this
   integration's own docs**, and name the amplified-consequence risk plainly: a clarifying question
   derived from untrusted ticket text now sits upstream of a real repository-write pipeline, not just a
   report-only one. Don't assume the existing skill's own protections carry over silently just because
   the same skill is being invoked.
5. **State explicitly whether/how the clarify step's own token/time cost is charged against the
   Orchestrator's existing budgets** (§3), so it can't silently starve budget meant for implementation
   work across a multi-task plan.

None of these five block starting a `system-design` pass — they're precise, implementable requirements
for that pass to satisfy, not open architectural questions.
