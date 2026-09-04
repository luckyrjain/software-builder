# Smoke test — module-design

Run after install or any substantive edit. Use a real, bounded module with a path, at least one caller,
one test or observable behavior, and an adjacent dependency or error path. The skill remains read-only:
inspect and emit a report; do not modify the fixture repository.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `module_scope: <path or responsibility>` `repository_evidence: <paths/excerpts>` `change_goal: <optional>`

Example: `module_scope: src/payments/charge.py` with evidence from its public call sites, existing charge
tests, and gateway exception mapping.

## A correct minimal output contains

1. A HARD STOP if concrete scope or repository evidence is absent.
2. Evidence/callers labeled separately from inference, plus an explicit module contract and invariants.
3. Dependency direction plus a justified seam/adapter decision; no mock-only or pass-through interface.
4. Errors, state, concurrency, performance, test surface, migration, rejected alternatives, and unresolved
   questions — each populated, evidence-backed `Not applicable`, or explicit unknown.
5. `MODULE_DESIGN_SPEC.md` / `module_design_spec` emitted as a report only, with no source writes or
   automatic downstream invocation.

## Degraded paths

| Condition | Expected behavior |
|-----------|-------------------|
| Module is named but no callers/tests/implementation can be inspected | HARD STOP — request repository evidence; do not infer a contract from the name |
| A vendor SDK detail leaks through callers | Propose a translated module-owned contract only if the observed integration boundary earns it |
| Future variation is asserted but evidence cannot determine its shape | Compare two materially different designs and mark the selection unresolved or recommend from stated cost |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
