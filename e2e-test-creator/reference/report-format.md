# E2E_TEST_REPORT.md — format

Written by [workflow/report.md](../workflow/report.md) to `output_dir`, following the shared skeleton in
[test-creation-principles.md §4](../../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton).
This file states only the e2e-specific deltas on top of that skeleton: **journey** in place of a
file-level target, and the `NEEDS_BROWSER_ENV` status.

```markdown
# E2E Test Report

Mode: diff | backfill
Target: <source, or journey list>
Repo: <repo_root>
Framework/tooling: <detected e2e framework> (<confidence>)
Generated: <UTC timestamp>

## Summary

| Status | Count |
|--------|-------|
| Written & passing | N |
| Written — flags a production bug | N |
| Needs human | N |
| Blocked — no reachable app instance | N |
| Unverified | N |
| Already covered (skipped) | N |
| Skipped — over max_files_per_run | N |

## Targets

| Journey | Status | Test file | Notes |
|---------|--------|-----------|-------|
| "user logs in and views their dashboard" | WRITTEN_PASSING | `e2e/login.spec.ts` | Selectors: role/accessible-name (repo's own convention) |
| "user completes checkout" | WRITTEN_FAILING_PROD_BUG | `e2e/checkout.spec.ts` | Expected confirmation page, got the cart page — see § Findings |

## Findings (production bugs surfaced)

Only present when at least one `WRITTEN_FAILING_PROD_BUG` journey exists.

### "user completes checkout"

- **Assertion:** URL is `/checkout/confirm` and the page shows an "Order confirmed" heading after a
  successful payment submission
- **Actual:** the app stays on `/cart` — the payment success handler never navigates away
- **Suggested next step:** hand to **loop-task-implementer** to fix, or flag on the MR via **pr-review**

## Skipped

Only present when journeys were skipped. Lists every `SKIPPED_ALREADY_COVERED` and `SKIPPED_MAX_FILES`
journey by name — never a bare count.

## Blocked — NEEDS_BROWSER_ENV

Only present when at least one journey is blocked. States plainly that no reachable running instance of
the app existed this session, and names what would resolve it (local start command, staging URL, or
preview deployment) — never a guess at what the UI would have shown.

## Next step

One line: "Ready to open as an MR", "N journeys need attention before merge — see § Targets", or "N
journeys blocked — supply a reachable app instance".
```

## Rules

- The `## Findings`, `## Skipped`, and `## Blocked — NEEDS_BROWSER_ENV` sections are omitted entirely
  when empty — never rendered as an empty header.
- Status values in the `## Targets` table must be copied verbatim from `verify_result` / `target_list` —
  see [workflow/report.md §2](../workflow/report.md#2-never-upgrade-a-status).
- Journey rows use the journey's own name (from `target.journeys[].name` in backfill mode, or the
  inferred name in diff mode) as the `Journey` column value — never a file path, since a journey may span
  more than one spec file and a spec file may cover only part of a journey.
