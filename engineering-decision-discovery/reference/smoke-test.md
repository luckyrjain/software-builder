
# Smoke test — engineering-decision-discovery

Run after install or any substantive edit. Use a real, bounded `decision_scope` with a question, its
repository context, at least one dependent decision, and at least one independent decision. The skill
remains read-only and interactive: inspect evidence, interview the user, and emit a report; never modify
the fixture repository or write an ADR.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `decision_scope: {question: <bounded question>, context: <paths>}`
> `interaction_policy: {human_available: true, unattended: false}`

Example: `decision_scope: {question: "Should provider errors be translated at the charge module seam?",
context: "src/payments/charge.py and its checkout callers"}` with repository evidence from the charge
module, its callers, and existing contract tests.

## A correct minimal output contains

1. A **BLOCKED** result if `decision_scope.question` or `decision_scope.context` is absent — no tree is
   built without a bounded scope.
2. A decision tree with at least one dependent node (`depends_on` non-empty) and one independent node,
   each with options, rationale, and evidence.
3. A frontier computed each round that never asks a dependent node ahead of its unresolved prerequisite.
4. A recommendation with rationale and confidence for every question actually asked, presented before the
   user is asked to decide.
5. Resolved decisions attributed to the user (or a narrowly scoped, verbatim-recorded delegation), kept
   distinct from unresolved decisions and from options rejected along the way.
6. `ENGINEERING_DECISION_RECORD.md` / `engineering_decision_record` emitted as a report only, with no
   source, repository, or ADR write, and `recommended_next_skill` set only when its trigger was met.

## Degraded paths

| Condition | Expected behavior |
|-----------|---------------------|
| `decision_scope` missing or unbounded ("decide everything about this repo") | BLOCKED; ask for a bounded question and context, do not build a tree |
| Repository evidence for a node is unavailable | Record the gap on that node's `evidence_refs`/limitations; lower confidence; never ask the user to fetch a fact the host can read |
| `interaction_policy.human_available: false` | Compute the frontier and recommendations; never ask; report the frontier as unresolved |
| `interaction_policy.unattended: true` and a material frontier remains at completion | `BLOCKED`, with the frontier and its recommendations attached; no decision synthesized |
| User explicitly defers a frontier node | Record it as `unresolved` with reason "explicitly deferred by the user"; move on without re-asking it |
| User answers a different question than the one asked | Treat the frontier node as still unresolved this round; do not infer a decision from an unrelated answer |
| `selected_candidate` handoff supplied | Treated as evidence feeding the tree, never as a pre-resolved decision |
| Evidence already settles the question | Zero-node tree is valid; report states why, without running an interview |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
