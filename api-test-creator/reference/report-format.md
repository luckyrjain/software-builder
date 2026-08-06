# API_TEST_REPORT.md — format

Written by [workflow/report.md](../workflow/report.md) to `output_dir`. Follows the shared skeleton in
[test-creation-principles.md §4](../../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton)
— this file adds the API-specific `Collection`/`Newman` header fields and the `NEEDS_OBSERVED_ENDPOINT` /
`NEEDS_API_ENV` statuses on top.

```markdown
# API Test Report

Mode: diff | backfill
Target: <source, or scope list>
Repo: <repo_root>
Collection: <resolved collection path> (<confidence>)
Newman: yes | no
Generated: <UTC timestamp>

## Summary

| Status | Count |
|--------|-------|
| Written & passing | N |
| Written — flags a production bug | N |
| Needs observed endpoint | N |
| Blocked — no reachable API instance | N |
| Needs human | N |
| Unverified | N |
| Already covered (skipped) | N |
| Skipped — over max_files_per_run | N |

## Targets

| Endpoint | Status | Request | Notes |
|----------|--------|---------|-------|
| `POST /api/orders` | WRITTEN_PASSING | `Orders > Create order` | Shape derived from `src/routes/orders.ts:18` |
| `GET /api/orders/:id` | WRITTEN_FAILING_PROD_BUG | `Orders > Get order by id` | Handler returns 500 on a valid id — see Findings section |

## Findings (production bugs surfaced)

Only present when at least one `WRITTEN_FAILING_PROD_BUG` target exists.

### `GET /api/orders/:id`

- **Expected:** `200` with a body containing `total_cents` (integer)
- **Actual:** `500 Internal Server Error` — the assertion and request were **not** loosened to match
- **Suggested next step:** hand to **loop-task-implementer** to fix, or **pr-review** to flag on the MR

## Skipped

Only present when targets were skipped. Lists every `SKIPPED_ALREADY_COVERED` and `SKIPPED_MAX_FILES`
target by name — never a bare count.

## Blocked — NEEDS_API_ENV

Only present when at least one target is blocked. States plainly that no reachable running API instance
existed this session, and names what would resolve it (local start command, staging URL, or preview
deployment) — never a guess at what a response would have been.

## Next step

One line: "Ready to open as an MR", "N targets need attention before merge — see the Targets section", or
"N targets blocked — supply a reachable API instance."
```

## Rules

- The `## Findings`, `## Skipped`, and `## Blocked — NEEDS_API_ENV` sections are omitted entirely when
  empty — never rendered as an empty header.
- Status values in the `## Targets` table are copied verbatim from `verify_result` / `target_list` — see
  [workflow/report.md §2](../workflow/report.md#2-never-upgrade-a-status).
- `Collection` and `Newman` in the header are always shown, even on a zero-target or fully-`UNVERIFIED`/
  `NEEDS_API_ENV` run.
- `NEEDS_OBSERVED_ENDPOINT` targets get a one-line reason in `Notes` (what was checked and found missing:
  no route-handler match, no spec, no catalog entry) — never a bare tag with no explanation.
