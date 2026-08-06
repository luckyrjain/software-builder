# UNIT_TEST_REPORT.md — format

Written by [workflow/report.md](../workflow/report.md) to `output_dir`. Follows the shared skeleton in
[test-creation-principles.md §4](../../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton)
— this file is the normative per-field spec for the unit level, not a second, different shape.

```markdown
# Unit Test Report

Mode: diff | backfill
Target: <source, or scope list>
Repo: <repo_root>
Framework/tooling: <detected framework> (<confidence>)
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
| `src/payments/charge.py::apply_discount` | WRITTEN_PASSING | `tests/test_charge.py` | Happy path + zero-amount edge case; gateway client mocked |
| `src/payments/refund.py::process_refund` | WRITTEN_FAILING_PROD_BUG | `tests/test_refund.py` | Expected `refund.status == "completed"`, got `"pending"` — see the Findings section |
| `src/payments/webhook.py::verify_signature` | UNTESTABLE_WITHOUT_FIXTURE | — | Calls the live signing service directly, no existing mock convention in the repo — see the Findings section |

## Findings

Only present when at least one `WRITTEN_FAILING_PROD_BUG` or `UNTESTABLE_WITHOUT_FIXTURE` target exists,
or a testability refactor was applied.

### `src/payments/refund.py::process_refund`

- Assertion: `refund.status == "completed"` after a successful gateway call
- Actual: `"pending"` — the status update never happens on the success branch
- Suggested next step: hand to loop-task-implementer to fix, or flag on the MR via pr-review

### `src/payments/webhook.py::verify_signature`

- Reason untestable in isolation: exercising this function meaningfully requires the live signing
  service; the repo has no existing mock/stub for it
- Suggested next step: integration-test-creator — this target needs a real adjacent dependency, not a
  unit-level mock

## Skipped

Only present when targets were skipped. Lists every `SKIPPED_ALREADY_COVERED` and `SKIPPED_MAX_FILES`
target by name — never a bare count.

## Next step

One line: "Ready to open as an MR" or "N targets need attention before merge — see the Targets section."
```

## Rules

- The `## Findings` and `## Skipped` sections are omitted entirely when empty — never rendered as an
  empty header.
- Status values in the `## Targets` table must be copied verbatim from `verify_result` /
  `target_list` — see [workflow/report.md §2](../workflow/report.md#2-never-upgrade-a-status).
- No extra unit-specific statuses beyond what the whole test-creator family already shares: the five
  named in
  [test-creation-principles.md §4](../../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton)
  (`WRITTEN_PASSING`, `UNVERIFIED`, `NEEDS_HUMAN`, `SKIPPED_ALREADY_COVERED`, `SKIPPED_MAX_FILES`), plus
  `WRITTEN_FAILING_PROD_BUG` and `UNTESTABLE_WITHOUT_FIXTURE` — both common to every skill in the family
  (see the escalation rows in
  [cross-skill-escalation.md](../../docs/skill-framework/shared/cross-skill-escalation.md)), not a
  unit-only invention. Unit scope has no execution-environment status of its own (contrast
  `NEEDS_INTEGRATION_ENV`/`NEEDS_PACT_ROLE`/`NEEDS_BROWSER_ENV`, which are genuinely level-specific to
  their own skills) — a unit test either runs in-process or it isn't a unit test.
