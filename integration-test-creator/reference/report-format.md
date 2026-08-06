# INTEGRATION_TEST_REPORT.md — format

Written by [workflow/report.md](../workflow/report.md) to `output_dir`, following the shared skeleton in
[test-creation-principles.md §4](../../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton).

```markdown
# Integration Test Report

Mode: diff | backfill
Target: <source, or scope list>
Repo: <repo_root>
Framework/tooling: <base runner> (<confidence>) · orchestration: <testcontainers|docker-compose|embedded|none> (<confidence>)
Generated: <UTC timestamp>

## Summary

| Status | Count |
|--------|-------|
| Written & passing | N |
| Written — flags a production bug | N |
| Needs human | N |
| Needs integration env | N |
| Unverified | N |
| Already covered (skipped) | N |
| Skipped — over max_files_per_run | N |

## Targets

| Target | Status | Test file | Notes |
|--------|--------|-----------|-------|
| `src/payments/charge.py::apply_discount↔postgres` | WRITTEN_PASSING | `tests/integration/test_charge.py` | Happy path + unique-constraint edge case, run against a testcontainers Postgres |
| `src/payments/refund.py::process_refund↔postgres` | WRITTEN_FAILING_PROD_BUG | `tests/integration/test_refund.py` | Expected `refund.status == "completed"`, got `"pending"` — see § Findings |
| `src/orders/create.py::create_order↔queue` | NEEDS_INTEGRATION_ENV | `tests/integration/test_create_order.py` | No orchestration mechanism detected and no Docker daemon reachable this session — see § Findings |

## Findings

Only present when at least one `WRITTEN_FAILING_PROD_BUG` or `NEEDS_INTEGRATION_ENV` target exists. Each
entry says which kind it is.

### `src/payments/refund.py::process_refund` — production bug

- **Assertion:** `refund.status == "completed"` after a successful gateway call, verified by re-reading
  the row from the real database
- **Actual:** `"pending"` — the status update never happens on the success branch
- **Suggested next step:** hand to **loop-task-implementer** to fix, or flag on the MR via **pr-review**

### `src/orders/create.py::create_order` — needs integration env

- **Missing:** no testcontainers dependency, no docker-compose file, no reachable Docker daemon this
  session
- **What would unblock it:** add a `docker-compose.test.yml` bringing up the queue, or run this session
  with Docker available

## Skipped

Only present when targets were skipped. Lists every `SKIPPED_ALREADY_COVERED` and `SKIPPED_MAX_FILES`
target by name — never a bare count.

## Next step

One line: "Ready to open as an MR" or "N targets need attention before merge — see § Targets."
```

## Rules

- The `## Findings` and `## Skipped` sections are omitted entirely when empty — never rendered as an
  empty header.
- Status values in the `## Targets` table must be copied verbatim from `verify_result` /
  `target_list` — see [workflow/report.md §2](../workflow/report.md#2-never-upgrade-a-status).
- `NEEDS_INTEGRATION_ENV` is a level-specific status added on top of the shared vocabulary in
  [test-creation-principles.md §4](../../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton)
  — never renamed, and never merged into `NEEDS_HUMAN` (the fix is infrastructure, not a decision).
- `Framework/tooling` in the header always states both dimensions — a base runner alone is an incomplete
  header for this skill.
