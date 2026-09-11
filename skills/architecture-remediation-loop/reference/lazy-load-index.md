# Lazy-load index

Load **one reference file at a time** when the active workflow phase points to it.

| When | Read |
|------|------|
| Discover — building/deduplicating the ledger | [candidate-ledger.md](candidate-ledger.md) |
| Disposition — applying the disposition contract | [candidate-ledger.md § Disposition contract](candidate-ledger.md#disposition-contract) |
| Remediate — batching accepted candidates | [pr-batching-policy.md](pr-batching-policy.md) |
| Converge — gate status, anti-gaming, circuit breakers | [convergence-gates.md](convergence-gates.md) |
| Converge — emitting the final artifact | [report-format.md](report-format.md) |
| Either phase — codebase-architecture-review's own contract | [codebase-architecture-review/SKILL.md](../../codebase-architecture-review/SKILL.md) |
| Either phase — engineering-decision-discovery's own contract | [engineering-decision-discovery/SKILL.md](../../engineering-decision-discovery/SKILL.md) |
| Either phase — module-design's own contract | [module-design/SKILL.md](../../module-design/SKILL.md) |
| Either phase — loop-task-implementer's own contract | [loop-task-implementer/SKILL.md](../../loop-task-implementer/SKILL.md) |
| Either phase — production-readiness-review's own contract | [production-readiness-review/SKILL.md](../../production-readiness-review/SKILL.md) |
| Post-install check | [smoke-test.md](smoke-test.md) |

Framework: [cross-skill-escalation.md](../../../docs/skill-framework/shared/cross-skill-escalation.md) ·
[prompt-injection.md](../../../docs/skill-framework/shared/prompt-injection.md)
