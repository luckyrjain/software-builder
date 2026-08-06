---
workflow_version: 2.0
phase: delegate
produces:
  - dispatched_report
consumes:
  - level
  - request
  - repo_root
---

# Delegate — dispatch and relay

## 1. Invoke the matching skill

| `level` | Invoke |
|---------|--------|
| `unit` | **unit-test-creator** |
| `integration` | **integration-test-creator** |
| `contract` | **contract-test-creator** |
| `e2e` | **e2e-test-creator** |
| `api` | **api-test-creator** |

Pass `repo_root` and every other field the caller supplied (`target`, `run_tests`,
`max_files_per_run`, `deadline`, `session_token_budget`, `output_dir`, and — for `contract` — `role`;
for `e2e` — `journeys`) through **unchanged**. This router does not translate, rename, or add fields; the
dispatched skill's own [workflow/inputs.md](../../unit-test-creator/workflow/inputs.md)-equivalent owns
parsing and validation, including its own HARD STOPs (e.g. `contract-test-creator` asking for `role` if
absent — that gate belongs to it, not to this router).

## 2. Relay the report verbatim

The dispatched skill produces its own report (`UNIT_TEST_REPORT.md`, `INTEGRATION_TEST_REPORT.md`,
`CONTRACT_TEST_REPORT.md`, `E2E_TEST_REPORT.md`, or `API_TEST_REPORT.md`) per
[test-creation-principles.md §4](../../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton).
This router does not reformat, summarize, or re-derive a status from it — relay it as-is. If the
dispatched skill's own report contains a production-bug finding, its own suggested next skill
(loop-task-implementer / pr-review) applies unchanged; this router adds nothing on top.

## 3. Dispatched skill hits its own gate

If the dispatched skill asks a question of its own (ambiguous framework, missing role, no journeys,
etc.), that question is relayed as-is too — this router never pre-answers a gate that belongs to the
skill it dispatched to.
