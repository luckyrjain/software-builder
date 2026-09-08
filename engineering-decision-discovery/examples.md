# Examples — engineering-decision-discovery

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

Invoke `engineering-decision-discovery` ambiently to interrogate a bounded plan, module design, or
architecture for the decisions it has not yet made. It is read-only, report-only, and interactive: it
inspects the bounded `decision_scope`, interviews the user one frontier at a time, and never changes
repository state, writes an ADR, or implements anything itself.

| # | Caller sends | Behavior |
|---|---------------|----------|
| 1 | "Grill me on this architecture decision." | Inputs → Tree → Frontier → Interaction → Report; asks the user to bound the decision if no scope is attached |
| 2 | "Challenge my plan and question my assumptions." | Builds a tree from the plan's stated and implied choices; recommends and interviews rather than critiquing prose |
| 3 | "Stress-test this engineering decision." | Same pipeline; a single decision may still expand into dependent sub-questions the plan did not separate |
| 4 | "What decisions are missing before we implement this design?" | Tree-building surfaces unresolved nodes the design's prose glossed over; each becomes a frontier question, not a rhetorical list |
| 5 | "Help me decide between these module designs." | Frontier round presents each option's rationale, then asks — never silently picks the recommended design |
| 6 | "Here's a codebase-architecture-review candidate — CAR-003 — help me decide whether to take it." | `selected_candidate: {candidate_id: CAR-003, evidence_refs: [...]}` feeds the tree as evidence; the candidate's own analysis is not re-run |
| 7 | "Run this unattended as part of the release pipeline; block if anything's unresolved." | `interaction_policy.unattended: true`; a remaining material frontier returns `BLOCKED` with the frontier attached, never a synthesized answer |
| 8 | "Decide everything about how this repository should be built." | No bounded question or context — BLOCKED; ask for a scoped `decision_scope` instead of auditing the whole repository |
| 9 | "What does this checkout module actually do today?" | Wrong scope — use `domain-comprehension` to reconstruct current behavior; this skill decides, it does not document as-is behavior |
| 10 | "Is this proposed event-driven architecture safe at our scale?" | Wrong scope — use `architecture-review` for a verdict on a proposed architecture's risk and trade-offs |
| 11 | "Implement the design we already agreed on." | Wrong scope — use `loop-task-implementer` / `system-design`; this skill is for unresolved decisions, not settled ones |

## Example: dependent decision waits for its prerequisite

**Scope:** "Should provider errors be translated at the charge module seam?" bounded to
`src/payments/charge.py` and its checkout callers.

**Tree:** D1 — translate at the seam or leave it to callers (independent). D2 — which error taxonomy the
translation uses, `depends_on: [D1]` (only matters if D1 selects translation).

**Round 1 (frontier = [D1] only):**

```
Frontier this round: D1
D1: Should provider errors be translated at the charge module seam?
  Recommended: A — Translate at the charge seam
  Rationale: checkout and its sibling caller both branch on provider error codes today (repo:src/checkout/checkout.py);
  central translation removes that duplicated branching. Confidence: MEDIUM — two callers observed, no ADR on file.
  Your decision?
```

**Result:** the user picks option A. D1 becomes `resolved`; D2 is now eligible and appears on round 2's
frontier — it was never asked in round 1 alongside its unresolved prerequisite.

## Example: user overrides the recommendation

**Scope:** whether a proposed `NotificationChannel` seam is justified.

**Round:** the skill recommends "reject as mock-only" with rationale citing the deletion test and no
observed second implementation. The user answers: "We're adding SMS next quarter, keep the seam."

**Result:** `resolved_decisions` records `selected_option: keep-seam`, decided by the user, with the
user's stated reason ("adding SMS next quarter"). `recommendations` still shows the reject recommendation
for context — the report never rewrites the recommendation to match the user's choice after the fact.

## Example: explicit deferral, no infinite interview

**Scope:** three independent decisions about a caching layer's eviction policy, invalidation trigger, and
metrics surface.

**Round 1:** the user resolves the eviction-policy question, then says "let's leave the other two for
next sprint."

**Result:** the eviction node moves to `resolved_decisions`; the remaining two move to
`unresolved_decisions` with reason `explicitly deferred by the user`, each still carrying its
recommendation and rationale. The skill stops there — it does not keep re-asking, does not treat the
deferral as approval of its own recommendations, and emits the report with both decisions honestly open.

## Example: unattended composition, material frontier remains

**Scope:** a release-pipeline invocation with `interaction_policy: {human_available: false,
unattended: true}` and one dependent decision still unresolved after evidence review.

**Result:**

```
status: BLOCKED
frontier_at_completion: [D2]
D2: Which retry policy should the payment adapter use on a translated timeout?
  Recommended: A — exponential backoff with jitter, capped at 3 attempts
  Rationale: repo:src/payments/adapter.py already imports a backoff helper unused elsewhere; no idempotency
  guarantee is documented, so a longer cap risks duplicate charges. Confidence: LOW — idempotency behavior unconfirmed.
```

No decision is synthesized to clear D2, and no source, configuration, or ADR is written — the pipeline
sees `BLOCKED` and the exact frontier a human needs to resolve.

## Example: cross-skill handoff after resolution

**Scope:** decisions about one module's error-translation contract, resolved across two rounds.

**Result:** `resolved_decisions` fully describes the module's contract and seam decision. Because every
resolved decision concerns one concrete module's boundary, the report sets
`recommended_next_skill: module-design` as a visible, human-authorized offer — formalizing the contract
into a `MODULE_DESIGN_SPEC.md` is a separate invocation the user chooses to make, not something this
report performs itself.
