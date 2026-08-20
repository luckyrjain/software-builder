# Phase index

Role isolation remains the primary execution model. Batch 5.2C adds explicit lifecycle adapters around the role loop so shared review identity/evidence is machine-validated without merging Builder/Reviewer contexts.

| Context | Read now | Produces |
|---------|----------|----------|
| **Orchestrator** | [workflow/orchestrator.md](../workflow/orchestrator.md) + mandatory [workflow/orchestrator-lifecycle.md](../workflow/orchestrator-lifecycle.md) | task state, current `change_identity`, dispatch packages, adjudication verdicts, completion report |
| **Builder** | [workflow/builder.md](../workflow/builder.md) | implementation diff, pull request, builder report |
| **Reviewer** | [workflow/reviewer.md](../workflow/reviewer.md) | reviewer report, lens verdict |
| **Reviewer evidence adapter** | [workflow/reviewer-evidence.md](../workflow/reviewer-evidence.md) | portable `review_evidence`, `reviewed_change_identity` for the returned lens |
| **Lifecycle gate** | [workflow/lifecycle-gate.md](../workflow/lifecycle-gate.md) | zero-error lifecycle validation before READY/COMPLETE/merge |

Reference loads: [lazy-load-index.md](lazy-load-index.md) · [review-lifecycle-contract.yaml](review-lifecycle-contract.yaml).

## Execution order

```
Orchestrator + lifecycle overlay: discover policy → select task
  → dispatch Builder (fresh context)
  → rebuild/validate current shared change_identity + current requirements_ref
  → dispatch Reviewer Lens A (fresh context)
  → normalize/validate Lens A review_evidence → adjudicate
  → dispatch Reviewer Lens B (fresh context)
  → normalize/validate Lens B review_evidence → adjudicate
  → dispatch Builder remediation for accepted findings (fresh context)
  → any content/conflict/requirements/third-party branch change invalidates affected review evidence
  → rerun invalidated lenses
  → verify authoritative checks for exact current head
  → refresh approvals/threads/integration/circuit-breaker state
  → run lifecycle gate against fresh current identity + requirements
  → set READY only on zero errors
  → complete repository action only when separately authorized
  → rerun lifecycle gate immediately before merge/completion write
  → verify result → select next eligible task
```

Full workflow diagram: [SKILL.md § Workflow](../SKILL.md#workflow).
