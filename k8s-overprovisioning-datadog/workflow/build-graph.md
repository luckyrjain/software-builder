---
workflow_version: 3.4
phase: build-graph
produces:
  - decision_graph
consumes:
  - observation_registry
  - evidence_registry
  - inferences
  - validated_decisions
  - computed_confidence
  - assessment_fingerprint
  - cost_gate
  - source_profile
---

# Build decision graph

**BUILD_GRAPH phase** — after VALIDATE (+ optional COST). **No markdown here.**

Assemble the typed `decision_graph` object per [decision-graph-schema.md](../reference/decision-graph-schema.md).

## Rules

1. **Think in objects**, not tables — YAML/JSON is the canonical form.
2. Populate `observations[]` and `evidence[]` from NORMALIZE outputs.
3. Populate `decisions[]` from REASON — use structured `reason` slugs + `explanation`.
4. Populate `recommendations[]` from validated rec candidates — link `depends_on.decisions`.
5. Compute `assessment.assessment_confidence` and each `recommendation_confidence` per [confidence-formula.md](../reference/confidence-formula.md); store `arithmetic` string.
6. Set `assessment.final_decision`, `severity`, `decision_history` when prior graph/report available.
7. Add `why_this_matters[]` entries for BLOCKED/DEFER `DEC_*` — reference IDs only.
8. Copy the complete `source_profile` to `metadata.source_profile`. Missing required routes is
   `INV-14`; do not render without the profile.
9. **Delivery pointer (INV-12):** for each `REC_*` with `status: READY` and actionable id (`*_REDUCE`,
   `*_INCREASE`, `*_ADJUST`, `REC_MANIFEST_RECONCILE`), set non-empty `delivery_pointer.path` before
   VALIDATE_INVARIANTS. Discover path from git MCP manifest/Helm/kustomize reads in COLLECT
   ([collect-metrics.md](collect-metrics.md)). If the path is unknown, set the recommendation to
   `DEFERRED` and ask the user to confirm it; never invent a path. A Git-observed or explicitly
   user-confirmed path sets `verified: true`. An unconfirmed candidate path may be retained only on a
   `DEFERRED` recommendation with `verified: false`. Gate detail:
   [validate.md § Delivery pointer gate](validate.md#delivery-pointer-gate).

## Do not

- Write markdown sections in this phase
- Duplicate observation values on decisions or recommendations
- Hand-assign confidence without `factors` + `arithmetic`

## Handoff

→ [validate-invariants.md](validate-invariants.md) → [render.md](render.md)

Example: [decision-graph.example.yaml](../reference/decision-graph.example.yaml)
