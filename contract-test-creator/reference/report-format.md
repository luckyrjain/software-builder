# CONTRACT_TEST_REPORT.md — format

Written by [workflow/report.md](../workflow/report.md) to `output_dir`. Follows the shared skeleton in
[test-creation-principles.md §4](../../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton)
— this file adds the contract-specific `Role` header field and the `NEEDS_OBSERVED_INTERACTION` status on
top.

```markdown
# Contract Test Report

Mode: diff | backfill
Role: consumer | provider
Target: <source, or scope list>
Repo: <repo_root>
Pact library: <detected library> (<confidence>)
Broker: yes | no
Generated: <UTC timestamp>

## Summary

| Status | Count |
|--------|-------|
| Written & passing | N |
| Written — flags a production bug | N |
| Needs observed interaction | N |
| Needs human | N |
| Unverified | N |
| Already covered (skipped) | N |
| Skipped — over max_files_per_run | N |

## Targets

| Target | Status | Test file | Notes |
|--------|--------|-----------|-------|
| `consumer: orders-service calling GET /orders/:id on orders-provider` | WRITTEN_PASSING | `test/pact/orders.pact.test.ts` | Shape derived from `src/clients/ordersClient.ts:42` |
| `provider: orders-provider verifying orders-consumer's pact` | WRITTEN_FAILING_PROD_BUG | `test/pact/verify.pact.test.ts` | Provider no longer returns the expected field — see Findings section |

## Findings (production bugs surfaced)

Only present when at least one `WRITTEN_FAILING_PROD_BUG` target exists.

### `provider: orders-provider verifying orders-consumer's pact`

- **Interaction:** `GET /orders/:id` — consumer expects `total_cents` (integer) in the response body
- **Actual:** field renamed to `totalCents` on the provider — the pact file was **not** edited to match
- **Suggested next step:** hand to **loop-task-implementer** to fix, or **pr-review** to flag on the MR

## Skipped

Only present when targets were skipped. Lists every `SKIPPED_ALREADY_COVERED` and `SKIPPED_MAX_FILES`
target by name — never a bare count.

## Next step

One line: "Ready to open as an MR" or "N targets need attention before merge — see the Targets section."
```

## Rules

- The `## Findings` and `## Skipped` sections are omitted entirely when empty — never rendered as an
  empty header.
- Status values in the `## Targets` table are copied verbatim from `verify_result` / `target_list` — see
  [workflow/report.md §2](../workflow/report.md#2-never-upgrade-a-status).
- `Role` in the header is always exactly `consumer` or `provider` — never blank, never both (a run covers
  one role at a time, per [workflow/inputs.md](../workflow/inputs.md)).
- `Broker` reflects the `BROKER` field from [scripts/detect-pact-tooling.sh](../scripts/detect-pact-tooling.sh)
  — informational, never itself a status.
- `NEEDS_OBSERVED_INTERACTION` targets get a one-line reason in `Notes` (what was checked and found
  missing: no call site, no client method, no schema file) — never a bare tag with no explanation.
