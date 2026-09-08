---
workflow_version: 1.0
phase: frontier
produces:
  - frontier
consumes:
  - decision_tree
  - interaction_policy
---

# Frontier — compute which nodes are askable this round

Recompute the frontier every round from the current `decision_tree`; never reuse a stale frontier from an
earlier round.

## Frontier rule

A node belongs on the frontier when, and only when:

1. `status` is `unresolved`, and
2. every node named in its `depends_on` has `status: resolved` or `status: not_applicable`.

Independent nodes (`depends_on: []`) are always eligible once `unresolved`, and multiple independent
nodes may share one frontier round — ask them together rather than one at a time. A dependent node must
never appear on the same round's frontier as an unresolved prerequisite; it waits, silently absent from
that round, until its prerequisite resolves.

```
frontier = [ node for node in decision_tree
             if node.status == "unresolved"
             and all(dep.status in ("resolved", "not_applicable")
                     for dep in nodes_named_in(node.depends_on)) ]
```

## Materiality and stopping

Every node in `decision_tree` is material by construction — [workflow/tree.md](tree.md) creates a node
only when it materially affects `decision_scope`, so there is no separate "informational" tier to filter
out here. The frontier is empty, and the interview stops, exactly when every node is `resolved` or
`not_applicable`, or the user has explicitly left the remaining nodes unresolved for this session (see
[workflow/interaction.md](interaction.md)).

## Unattended composition

When `interaction_policy.unattended` is `true` (see [workflow/inputs.md](inputs.md)), a non-empty
frontier at the point the session must complete is a **BLOCKED** result: report the frontier — its
questions, options, and current recommendations — and stop. Never synthesize a decision, never pick the
recommended option on the user's behalf, and never mark a node `resolved` without an explicit human
answer, even under time or composition pressure. This is the same rule
[runtime-contract.md § Stopping conditions](../../docs/skill-framework/shared/runtime-contract.md)
expresses generically: a required input — here, a human decision — being unavailable is a `BLOCKED`
condition, not a `FAILED` or invented `SUCCESS` one.

## Recomputation after a decision

After [workflow/interaction.md](interaction.md) records a resolved or explicitly-deferred node, rebuild
the tree's `not_applicable` consequences (per [workflow/tree.md § Dependency edges](tree.md#dependency-edges))
before recomputing the next frontier. A node resolved in one round can change which nodes are eligible,
`not_applicable`, or newly reachable in the next.
