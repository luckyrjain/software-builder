# Lazy-load index

Load **one reference file at a time** when the active workflow phase points to it.

| When | Read |
|------|------|
| Run sweep — every live k8s-overprovisioning-datadog gate and its scripted answer | [gate-policy.md](gate-policy.md) |
| Run sweep — the sweep loop's own session-level state, ordering, and stop conditions | [sweep-policy.md](sweep-policy.md) |
| Run sweep — building the report | [report-format.md](report-format.md) |
| Run sweep — the shared rollup-item schema this skill implements | [org-rollup-schema.md](../../docs/skill-framework/shared/org-rollup-schema.md) |
| Run sweep — `SQUAD_MAP.md`'s own column/reconciliation semantics | [squad-mapping.md](../../squad-map/reference/squad-mapping.md) |
| Run sweep — the namespace/deployment waste-ranking query definitions | [queries.md § Namespace / cluster ranking](../../k8s-overprovisioning-datadog/queries.md#namespace-cluster-ranking-scalar-7d) |
| Run sweep — `decision_graph`'s own field semantics | [decision-graph-schema.md](../../k8s-overprovisioning-datadog/reference/decision-graph-schema.md) |
| Post-install check | [smoke-test.md](smoke-test.md) |

Framework: [confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md) ·
[cross-skill-escalation.md](../../docs/skill-framework/shared/cross-skill-escalation.md) ·
[prompt-injection.md](../../docs/skill-framework/shared/prompt-injection.md)
