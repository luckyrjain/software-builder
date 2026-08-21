# Phase index

Role isolation remains the primary execution model. Batch 5.2C adds explicit lifecycle adapters around the role loop so shared review identity/evidence is machine-validated without merging Builder/Reviewer contexts.

| Context | Read now | Produces |
|---------|----------|----------|
| **Orchestrator** | [workflow/orchestrator.md](../workflow/orchestrator.md) + mandatory [workflow/orchestrator-lifecycle.md](../workflow/orchestrator-lifecycle.md) | task state, current `change_identity`, per-lens `review_generation`, dispatch packages, adjudication verdicts, completion report |
| **Builder** | [workflow/builder.md](../workflow/builder.md) | implementation diff, pull request, builder report |
| **Reviewer** | [workflow/reviewer.md](../workflow/reviewer.md) | reviewer report, lens verdict |
| **Reviewer evidence adapter** | [workflow/reviewer-evidence.md](../workflow/reviewer-evidence.md), after Orchestrator increments the returned lens generation and adjudicates | portable `review_evidence`, `reviewed_change_identity` for the adjudicated lens result |
| **Lifecycle gate** | [workflow/lifecycle-gate.md](../workflow/lifecycle-gate.md) | zero-error lifecycle validation before READY/COMPLETE/merge |

Reference loads: [lazy-load-index.md](lazy-load-index.md) · [review-lifecycle-contract.yaml](review-lifecycle-contract.yaml).

## Execution order

```
Orchestrator + lifecycle overlay: discover policy → select task
  → dispatch Builder (fresh context)
  → rebuild/validate current shared change_identity + current requirements_ref
  → dispatch Reviewer Lens A (fresh context)
  → increment Lens A review_generation exactly once for the returned result; clear prior Lens A isolation-exception fields
  → adjudicate Lens A proposed findings
  → normalize/validate Lens A review_evidence from adjudicated result
  → if Lens A has accepted findings: dispatch Builder remediation, rebuild current identity, invalidate stale lens evidence
  → dispatch Reviewer Lens B (fresh context) against the current identity
  → increment Lens B review_generation exactly once for the returned result; clear prior Lens B isolation-exception fields
  → adjudicate Lens B proposed findings
  → normalize/validate Lens B review_evidence from adjudicated result
  → if Lens B has accepted findings: dispatch Builder remediation and rebuild current identity
  → any content/conflict/requirements/third-party branch change invalidates affected review evidence
  → rerun every invalidated lens; each returned rerun increments that lens generation and clears its prior exception fields
  → repeat until both lenses are lifecycle-clean for the same current identity
  → verify authoritative checks for exact current head
  → refresh approvals/threads/integration/circuit-breaker state
  → refresh third-party branch-change evidence for the exact current head
  → run lifecycle gate against fresh current identity + requirements
  → set READY only on validator exit code 0
  → complete repository action only when separately authorized
  → rerun lifecycle gate immediately before merge/completion write
  → verify result → select next eligible task
```

Portable classification after adjudication:

- `defect` = accepted blocking findings that remain open for the reviewed identity; a rejected proposal is not a portable defect.
- `suggestion` = evidence-backed non-blocking improvements.
- `question` = unresolved evidence requests such as `NEEDS_EVIDENCE`; security-sensitive questions remain separately gated by `security_sensitive_needs_evidence_unresolved`.

Full workflow diagram: [SKILL.md § Workflow](../SKILL.md#workflow).
