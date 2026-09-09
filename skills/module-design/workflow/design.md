---
workflow_version: 1.0
phase: design
produces:
  - module_contract
  - module_design_options
  - evidence_gaps
consumes:
  - module_scope
  - repository_evidence
  - change_goal
---

# Design — derive one module boundary from evidence

Evaluate the scoped module against the shared
[codebase-design-principles.md](../../../docs/skill-framework/shared/codebase-design-principles.md). For each
item below, cite repository evidence, mark the reasoning as inference where appropriate, or create an
explicit unresolved question. Never silently omit a check.

1. **Scope and ownership** — identify the module's responsibility and public consumers; reject unrelated
   helper accumulation or a boundary chosen solely for directory symmetry.
2. **Depth and interface surface** — compare the knowledge callers must supply with the behavior the
   module hides. Identify whether the module is deep or shallow using contract surface and caller
   evidence, never file size.
3. **Deletion test** — state what disappears and what would scatter if the module or proposed abstraction
   were deleted. Reject a pass-through or mock-only seam whose complexity does not concentrate.
4. **Contract and invariants** — define inputs, outputs, side effects, error behavior, and conditions that
   must remain true for callers. Prevent caller leakage of incidental representation or vendor details.
5. **Dependency direction** — map dependencies and invert only where a stable consumer contract needs to
   isolate a lower-level detail; do not introduce an interface merely to make mocking possible.
6. **Seams and adapters** — retain or add a seam only for an observed variation, integration boundary, or
   production-observable test need. An adapter must translate or isolate a real contract; reject
   mock-only and pass-through abstractions. Evaluate the implementation depth and interface surface of
   proposed seams; apply the deletion test to determine whether the module earns its abstraction cost.
7. **Errors, state, and concurrency** — specify error taxonomy/ownership, state transitions, concurrency
   assumptions, idempotency/ordering where relevant, and recovery behavior. Say `not applicable` only
   with evidence.
8. **Performance and test surface** — state observable latency/throughput/resource constraints only from
   evidence; define tests through the production contract, including needed fakes for real external
   boundaries, rather than private implementation inspection.
9. **Migration** — list affected callers, compatibility steps, rollout/order, and removal criteria. If no
   change is justified, say so; this report never performs a migration.
10. **Alternatives** — record rejected alternatives and their evidence-based costs. When interface
    uncertainty exists, produce two materially different designs, not naming or packaging variants. Compare
    responsibility ownership, contract, dependency direction, caller migration, test surface, and ongoing
    abstraction cost, then recommend one or explicitly leave the decision unresolved.

If the evidence requires several modules, shared data ownership, event topology, or implementation
sequencing, offer `system-design`. If it requires an architecture-wide risk, scale, security, or trade-off
decision, offer `architecture-review`. Do not invoke either automatically.
