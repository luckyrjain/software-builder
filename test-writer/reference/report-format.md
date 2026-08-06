# TEST_WRITER_REPORT.md — format

Written by [workflow/report.md](../workflow/report.md) to `output_dir`.

```markdown
# Test Writer Report

Mode: diff | backfill
Target: <source, or scope list>
Repo: <repo_root>
Framework: <detected framework> (<confidence>)
Generated: <UTC timestamp>

## Summary

| Status | Count |
|--------|-------|
| Written & passing | N |
| Written — flags a production bug | N |
| Needs human | N |
| Untestable without fixture | N |
| Unverified | N |
| Already covered (skipped) | N |
| Skipped — over max_files_per_run | N |

## Targets

| Target | Status | Test file | Notes |
|--------|--------|-----------|-------|
| `src/payments/charge.py::apply_discount` | WRITTEN_PASSING | `tests/test_charge.py` | Happy path + zero-amount edge case |
| `src/payments/refund.py::process_refund` | WRITTEN_FAILING_PROD_BUG | `tests/test_refund.py` | Expected `refund.status == "completed"`, got `"pending"` — see § Findings |

## Findings (production bugs surfaced)

Only present when at least one `WRITTEN_FAILING_PROD_BUG` target exists.

### `src/payments/refund.py::process_refund`

- **Assertion:** `refund.status == "completed"` after a successful gateway call
- **Actual:** `"pending"` — the status update never happens on the success branch
- **Suggested next step:** hand to **loop-task-implementer** to fix, or flag on the MR via **pr-review**

## Skipped

Only present when targets were skipped. Lists every `SKIPPED_ALREADY_COVERED` and `SKIPPED_MAX_FILES`
target by name — never a bare count.

## Coverage delta

Only present when a coverage tool ran. Before/after percentage for touched files.

## Next step

One line: "Ready to open as an MR" or "N targets need attention before merge — see § Targets."
```

## Rules

- The `## Findings` and `## Skipped` sections are omitted entirely when empty — never rendered as an
  empty header.
- Status values in the `## Targets` table must be copied verbatim from `verify_result` /
  `target_list` — see [workflow/report.md §2](../workflow/report.md#2-never-upgrade-a-status).
- `## Coverage delta` is best-effort per
  [workflow/report.md §4](../workflow/report.md#4-coverage-delta-best-effort-only) — omit, don't
  zero-fill, when no coverage tool ran.
