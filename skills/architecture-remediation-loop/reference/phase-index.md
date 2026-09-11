# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `review_scope`, `repo_context`, `max_cycles`, `max_candidates_per_cycle` |
| **Discover** | [workflow/discover.md](../workflow/discover.md) | `candidate_ledger` |
| **Disposition** | [workflow/disposition.md](../workflow/disposition.md) | `dispositioned_ledger` |
| **Remediate** | [workflow/remediate.md](../workflow/remediate.md) | `batch_results` |
| **Converge** | [workflow/converge.md](../workflow/converge.md) | `architecture_remediation_report` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Situation | Phases |
|-----------|--------|
| First cycle, candidates found | Inputs → Discover → Disposition → Remediate → Converge (merge checkpoint → Gate B → Gate A) → (loop to Discover if not converged) |
| First cycle, zero candidates found | Inputs → Discover → Converge (no batches, merge checkpoint trivially clears, Gate A already clean) → run Gate B once to confirm, then report `converged: true` |
| Accepted batches' PRs not yet merged | Converge stops at the merge checkpoint, reports `stopped_reason: AWAITING_MERGE`; re-invoking after the merge resumes the same cycle |
| Later cycle, Gate B finds a new blocker | Converge routes it back through Disposition → Remediate in the same cycle before re-checking Gate A |
| Same finding/Gate B dimension unresolved two cycles running | Converge reports `stopped_reason: NO_MATERIAL_PROGRESS` |
| `max_cycles` reached, still non-zero | Converge reports `converged: false`, `stopped_reason: MAX_CYCLES_REACHED` |
| Missing `review_scope` / `repo_context` | Inputs HARD STOP — log and exit, no run |
