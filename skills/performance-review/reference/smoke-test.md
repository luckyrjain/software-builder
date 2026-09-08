# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a small real function or query with at least one
known performance issue (e.g. a loop issuing one query per iteration, an unbounded in-memory cache) so
the smoke test exercises a non-clean path, not only a trivial `Pass`.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `reviewed_content: <paste of a function/query/service with a known N+1 pattern>`

## A correct minimal output contains

1. Scope announcement — what was reviewed (`reviewed_content` source, whether `profiling_excerpts`
   was supplied, `scope_hint` if any).
2. All eight focus-area tables (Algorithmic complexity, DB behavior, N+1, Cache, Memory, Concurrency,
   Connection pools, Downstream fanout), each with a finding row or an explicit "None found" — never a
   silently-omitted section.
3. The N+1 pattern in the smoke-test input surfaced as a finding in the **N+1** table, not folded into
   **DB behavior** alone.
4. `PERFORMANCE_REVIEW_REPORT.md` produced per [report-format.md](report-format.md), with a verdict
   consistent with the derivation rule (a real N+1 finding → `Fail — regression risk` at minimum, or
   `Pass with findings` if assessed as low-severity — never a bare `Pass`).
5. Confirmation / next-step line naming the report file produced.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| `reviewed_content` absent | Inputs HARD STOP — ask for it, no Analyze/Report |
| `reviewed_content` is a description with no actual code/query text (e.g. "the checkout service is slow") | Recorded as an evidence gap across most areas → verdict `Blocked — insufficient evidence`, not a fabricated per-area finding |
| `profiling_excerpts` absent | Analyze proceeds on static analysis alone; areas that need runtime evidence (e.g. actual cache hit-rate, real contention) are recorded as evidence gaps, not silently assumed clean |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
