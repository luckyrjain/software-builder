# Task 2 Report — module-design

## Status

Completed. This change implements only Task 2: the complete `module-design` skill tree and the exact
module-design contract assertion in the existing foundation test. No registry, central routing, Make target,
evaluation, generated projection, or unrelated test was changed.

## Files changed

| File | Change |
|------|--------|
| `scripts/tests/test_codebase_architecture_foundation.py` | Added the exact required `test_module_design_contract_is_read_only_and_contains_required_boundaries` assertion. |
| `module-design/SKILL.md` | Added the ambient, repository-capable, read-only, report-only orchestrator (103 lines). |
| `module-design/README.md` | Added purpose, scope, and pipeline summary. |
| `module-design/SETUP.md` | Added read-only prerequisites, directory map, framework links, and smoke-test entrypoint. |
| `module-design/CHANGELOG.md` | Added the 1.0.0 initial-release entry. |
| `module-design/examples.md` | Added scoped, degraded, mock-only, interface-uncertainty, and escalation examples. |
| `module-design/workflow/inputs.md` | Added concrete-scope and repository-evidence resolution with HARD STOP rules. |
| `module-design/workflow/design.md` | Added evidence-backed module design checks and alternative comparison rules. |
| `module-design/workflow/report.md` | Added report-only emission rules for `MODULE_DESIGN_SPEC.md` / `module_design_spec`. |
| `module-design/reference/phase-index.md` | Added progressive Inputs → Design → Report loading. |
| `module-design/reference/lazy-load-index.md` | Added one-at-a-time reference loading, using the required `lazy-load-index.md` filename. |
| `module-design/reference/report-format.md` | Added the normative spec structure and safe rendered-output boundary. |
| `module-design/reference/smoke-test.md` | Added post-edit minimal and degraded-path checks. |
| `module-design/reference/pressure-tests.md` | Added boundary, state/migration, uncertainty, escalation, and prompt-injection pressure cases. |
| `.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-report.md` | Added this implementation and verification record. |

## Design decisions

- Followed the existing skill tree layout: a compact root `SKILL.md`, workflow phases, and lazily loaded
  reference material. `SKILL.md` is 103 lines, below the required 180-line cap.
- Linked the existing shared `codebase-design-principles.md` as normative doctrine; no doctrine was copied
  into the new skill.
- Made `module_scope` and `repository_evidence` mandatory HARD STOP inputs. The evidence rule requires
  implementation/callers/tests/dependency information, not just a ticket or a filename.
- Defined the sole outputs as report artifacts, `MODULE_DESIGN_SPEC.md` and `module_design_spec`, and
  explicitly prohibited source writes, commits, pushes, PRs, and automatic downstream invocation.
- Required contract/invariants, dependency direction, seams/adapters, errors, state, concurrency,
  performance, test surface, migration, rejected alternatives, and unresolved questions in the workflow
  and normative report format.
- Rejected mock-only and pass-through abstractions, and caller leakage. The exact required sentence is in
  `SKILL.md`: “Do not create an interface solely to enable mocking.”
- Required two materially different designs where interface uncertainty remains; comparisons must differ in
  ownership or contract/dependency shape, not cosmetic implementation packaging.
- Limited scope-expansion handoffs to `system-design` and `architecture-review`, offered but never invoked
  automatically.
- Linked shared prompt-injection, safe-output, and cross-skill-escalation guidance rather than duplicating
  those contracts.

## Commands and results

| Command | Status | Exact output / result |
|---------|--------|-----------------------|
| `pytest -q scripts/tests/test_codebase_architecture_foundation.py` | Environment limitation | `/bin/bash: line 1: pytest: command not found` |
| `python -m pytest -q scripts/tests/test_codebase_architecture_foundation.py` | Expected RED routing failures | `4 failed, 2 passed in 0.60s`, exit 1. The four failures are the preserved Task 0 routing assertions: existing-codebase owner, module-seam owner, architecture-review owner, and system-design owner. The shared-doctrine and new module-design contract assertions passed. |
| Local Python contract/tree/link/line-count check | PASS | `contract: PASS (11 assertions)`; `tree: PASS (13 required files)`; `links: PASS (48 local file links)`; `line-count: PASS (103 <= 180)` |
| `python -m pytest -q scripts/tests/test_codebase_architecture_foundation.py -k module_design` | PASS | `1 passed, 5 deselected in 0.04s` |
| `git diff --check` | PASS | No output; exit 0. |

## Concerns

- No Task 2 blocker remains.
- `pytest` is not installed as a standalone executable on `PATH`; the configured primary Python runtime
  supports `python -m pytest`, which was used successfully for the focused contract test.
- The four routing assertions remain RED by design and were not changed, per the task instruction. They
  require the later Task 4–5 registry/routing work and are outside Task 2 scope.
