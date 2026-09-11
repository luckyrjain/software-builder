---
workflow_version: 1.0
phase: converge
produces:
  - architecture_remediation_report
consumes:
  - batch_results
---

# Converge — holistic gate, reconverge, or stop

**Goal:** confirm the cumulative change is clean from every angle, then decide whether another cycle is
needed. No new review logic here — production-readiness-review's own dispatch/aggregate workflow is
authoritative (it already composes pr-review plus the applicable specialist reviews); this step only reads
its verdict and drives the outer loop.

## Steps

1. Invoke **production-readiness-review** against the cumulative branch state from this cycle's batches
   (Gate B). It is read-only and never merges.
2. Read `production_readiness_report.verdict` and `blockers`. Every `BLOCKER`/`HIGH`/`MEDIUM`/actionable
   `LOW`-equivalent finding it reports becomes a new candidate: add it to the ledger with `source: holistic`
   and send it back through Disposition → Remediate in the **same** cycle before re-checking Gate A — do
   not let a holistic-review fix wait for the next Discover pass.
3. Once Gate B's blockers are all resolved (verdict `READY`, or `CONDITIONAL` with only caller-accepted
   waivers), re-run **Discover** (a genuinely fresh codebase-architecture-review pass against the new
   state — never "ask if the old findings were fixed").
4. **Gate A** passes when the fresh codebase-architecture-review retains zero `Strong` and zero
   `Worth exploring` candidates, and every `Speculative` candidate either resolves to
   `ALREADY SATISFIED`/`REJECT`/`OUT OF SCOPE` or survives grilling with recorded evidence limits (never
   silently dropped to reach zero — see
   [reference/convergence-gates.md § Anti-gaming](../reference/convergence-gates.md#anti-gaming)).
5. **Converged** when Gate A and Gate B both pass in the same cycle with no new candidates opened. Emit
   `architecture_remediation_report` per [reference/report-format.md](../reference/report-format.md) and
   stop.
6. **Not yet converged** and `max_cycles` not reached: start a new cycle at Discover.
7. **Not yet converged** and `max_cycles` reached: stop, emit the report with `converged: false` and the
   still-open ledger rows — never claim convergence that did not happen.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| `architecture_remediation_report` | Returned to caller | `converged`, `cycles_run`, full candidate ledger with terminal dispositions, every batch's PR link, final Gate A / Gate B status | Converge incomplete — do not report success |

## Completion summary (chat)

State: cycles run, candidates by terminal disposition, PRs opened (links), and whether both gates are
clean. If not converged, state exactly which gate is still non-zero and why the loop stopped.
