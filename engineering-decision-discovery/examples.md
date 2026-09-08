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
| 12 | "Great, everything's decided — write the ADR for this now." | Declines; ADR authorship is a separate, explicitly authorized action outside this skill — `adr_write_action` stays `none` |

## Example: dependency tree gates D2 until D1 resolves, then the frontier recomputes

**Scope:** `candidate_id: ARCH-001`, "Should provider errors be translated at the charge module seam?"
bounded to `src/payments/charge.py` and its checkout callers.

**Tree:** D1 — translate at the seam or leave it to callers (`depends_on: []`). D2 — should the
translated error type be shared with checkout (`depends_on: [D1]`; only askable once D1 resolves). D3 —
should retries live inside the module or the caller (`depends_on: []`, independent of both D1 and D2).

**Round 1 (frontier = [D1] — D3 not yet reached, D2 correctly gated off this round):**

```
Frontier this round: D1
D1: Should provider errors be translated at the charge module seam?
  Recommended: A — Translate at the charge seam
  Rationale: checkout and its sibling caller both branch on provider error codes today (repo:src/checkout/checkout.py);
  central translation removes that duplicated branching. Confidence: MEDIUM — two callers observed, no ADR on file.
  Your decision?
```

**Result:** the user selects the recommended option A. D1 becomes `resolved`, attributed to the user, not
the skill — the report's `recommendations` entry for D1 still shows `approved: false`; selecting the
recommendation is not the same field as approving it. The frontier is then recomputed from the current
tree, not reused from round 1: D2 is now eligible because its only dependency resolved, and D3 — already
independently eligible but not yet asked — joins it. Round 2's frontier is `[D2, D3]`, matching
`evals/golden/engineering-decision-discovery/decision-record.yaml`'s snapshot at this exact point: D1
`resolved`, D2 and D3 both `unresolved`, `resolved_decisions: [D1]`, `unresolved_decisions: [D2, D3]`. D2
was never askable alongside its unresolved prerequisite; D3 was always independent of D1 and simply hadn't
come up yet — two different reasons a node can be absent from a round, and the tree keeps them distinct.

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

## Example: unresolved frontier in an unattended composition returns BLOCKED

**Scope:** a release-pipeline invocation with `interaction_policy: {human_available: false,
unattended: true}` composing this skill after `codebase-architecture-review`, one material decision still
unresolved after the skill reads the repository for evidence — matching
`evals/transcripts/engineering-decision-discovery/unattended-block.yaml`'s event order: the skill reads
the repository, computes the frontier, then reports the outcome, with no `human_decision` event anywhere
in between — there is no human turn to wait for this run.

**Result:**

```
status: BLOCKED
frontier_at_completion: [D1]
D1: Which retry policy should the payment adapter use on a translated timeout?
  Recommended: A — exponential backoff with jitter, capped at 3 attempts
  Rationale: repo:src/payments/adapter.py already imports a backoff helper unused elsewhere; no idempotency
  guarantee is documented, so a longer cap risks duplicate charges. Confidence: LOW — idempotency behavior unconfirmed.
```

No decision is synthesized to clear D1, and no source, configuration, or ADR is written. Composition time
pressure does not change the rule: the skill never auto-picks its own recommended option to unblock a
caller. The pipeline sees `BLOCKED` and the exact frontier — question, recommendation, rationale,
confidence — a human needs to resolve before this composition can proceed.

## Example: a repository fact is retrieved by the skill, not asked of the user

**Scope:** the same `ARCH-001` charge-module tree from the dependency example above, building the
recommendation for D2 ("Should the translated error type be shared with checkout?").

**Result:** rather than asking the user "does checkout already import the charge module's error types?" —
a fact the host can read for itself — the skill reads `src/checkout/checkout.py` directly and finds the
existing import before the frontier is ever presented. That repository fact becomes D2's rationale
verbatim: "Checkout already imports the module's typed errors; a second parallel type would fork the
contract," exactly as recorded in
`evals/golden/engineering-decision-discovery/decision-record-complete.yaml`. Per
[workflow/inputs.md § Repository evidence](workflow/inputs.md): missing or unreadable evidence is recorded
as a limitation or a lowered confidence band against the affected node — it is never turned into a
question for the user. The frontier round the user actually sees carries only the genuine decision (which
option to pick) plus the rationale already backed by that self-retrieved fact; it never carries a request
for the user to go look the fact up.

## Example: a requested ADR is correctly refused

**Scope:** the `ARCH-001` charge-module tree, now fully resolved — D1, D2, and D3 all `resolved`, frontier
empty, `status: SUCCESS`, matching
`evals/golden/engineering-decision-discovery/decision-record-complete.yaml`.

**Round:** the user says, "Great, everything's decided — go ahead and write the ADR for this now."

**Result:** the skill declines. ADR authorship is a separate, explicitly authorized action outside this
skill's boundary, not something a resolved decision record triggers automatically. The report still emits
normally — `resolved_decisions: [D1, D2, D3]`, every recommendation and rationale intact, `frontier: []`
— but `adr_write_action` stays `none` and no `write_adr` action is ever added to the payload. If the
resolved decisions concern one module's boundary, the report may separately offer
`recommended_next_skill: module-design` as a visible, human-authorized next step; that offer is a pointer
the user chooses to follow, not the skill writing anything itself, and it never substitutes for the ADR
the user actually asked for.

## Example: cross-skill handoff after resolution

**Scope:** decisions about one module's error-translation contract, resolved across two rounds.

**Result:** `resolved_decisions` fully describes the module's contract and seam decision. Because every
resolved decision concerns one concrete module's boundary, the report sets
`recommended_next_skill: module-design` as a visible, human-authorized offer — formalizing the contract
into a `MODULE_DESIGN_SPEC.md` is a separate invocation the user chooses to make, not something this
report performs itself.
