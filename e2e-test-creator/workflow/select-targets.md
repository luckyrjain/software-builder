---
workflow_version: 1.0
phase: select_targets
produces:
  - target_list
consumes:
  - target
  - test_framework
---

# Select targets

Turn `target` into a concrete, bounded `target_list` of **journeys** to write tests for — not files. A
journey is a named user flow ("user logs in and views their dashboard", "user completes checkout"), each
resolving to one or more browser-driven steps against a real running instance of the app.

## 1. Diff mode — infer journeys from what changed

Parse the diff named by `target.source` (an MR, a branch range, or the working tree). A new/changed
route, page, or user-facing component in the diff implies a journey needs coverage or updating — infer
the journey's name/description from the changed route/page itself (e.g. a new `checkout/confirm` page
implies the "user completes checkout" journey); the caller is never required to spell the journey out in
diff mode.

- **Skip if the diff itself already includes a matching e2e spec change** covering the same route/page —
  tag `SKIPPED_ALREADY_COVERED`. Do not duplicate coverage the author already wrote.
- **Skip if an existing e2e spec clearly already exercises the changed route/page** — only skip on a
  reasonably confident match (an existing spec that visits the exact changed route and asserts on its
  rendered content); when uncertain, keep the journey rather than guess it's covered.
- Otherwise tag `NEW`.

Only source/UI changes imply a journey — never generate a journey for the diff's own spec-file changes,
config, or generated/vendored paths (see §3).

## 2. Backfill mode — explicit journeys required

Use `target.journeys` literally, one journey per list entry. `target.journeys` is **required and
non-empty** for backfill mode (enforced as a HARD STOP at [inputs.md](inputs.md) already) — there is no
directory-expansion step the way a file-based backfill target would have, because a journey has no 1:1
mapping to a source path.

## 3. Enrich using domain-comprehension (optional)

If `<workspace_root>/BUSINESS_FLOWS.md` exists, match each journey (diff-inferred or caller-supplied)
against its Journey index by name or entry route. On a match: use that artifact's own journey name
instead of the inferred one, and let Generate tests draw the step sequence from its § Services (ordered)
and § Failure points tables rather than inferring steps from the route alone — a documented failure point
becomes a candidate edge-case assertion, not just the happy path. On no match, or when
`BUSINESS_FLOWS.md` doesn't exist, proceed with the journey exactly as inferred (§1) or supplied (§2) —
this step never blocks or renames a journey it can't match. Full artifact table and precedence rules:
[domain-comprehension-integration.md](../../docs/skill-framework/shared/domain-comprehension-integration.md).

## 4. Exclusions (both modes)

Never select a journey whose only surface is a generated/vendored/build path — `node_modules/`, `vendor/`,
`dist/`, `build/`, `.next/`, `.git/`, or any directory the repo's own `.gitignore` marks as generated.
These are never hand-authored routes/pages, so a journey through them is never meaningful.

## 5. Apply incremental backfill state (optional)

If `E2E_TEST_COVERAGE_STATE.yaml` exists at `output_dir` (a prior backfill run on this repo), drop any
`NEW` journey whose recorded `status` is `WRITTEN_PASSING` **and** whose `content_hash` (hashed over the
matched route/page source, or the supplied journey description when none matched) still matches — tag it
`SKIPPED_ALREADY_COVERED` ("per state file"). Any other recorded status (`NEEDS_HUMAN`,
`WRITTEN_FAILING_PROD_BUG`, `NEEDS_BROWSER_ENV`, `UNVERIFIED`) means the journey was never actually
resolved — never skip it on a hash match alone. A changed hash is treated as new outright, regardless of
recorded status. Move `pending_backlog` entries and every non-`WRITTEN_PASSING` recorded journey to the
front of the list, ahead of anything newly discovered this run. Absent the state file, skip this step
entirely. Full schema and precedence rules:
[test-creation-principles.md §6](../../docs/skill-framework/shared/test-creation-principles.md#6-incremental-backfill-state-optional).

## 6. Cap and report overflow

Apply `max_files_per_run` (default 20) to the resulting `NEW` list of journeys, in the order left by
§3/§5 (or discovery order when neither applied). Anything past the cap is tagged `SKIPPED_MAX_FILES` —
listed by name in `E2E_TEST_REPORT.md`, never dropped silently (see
[gate-policy.md §7](../reference/gate-policy.md#7-maxfilesperrun-reached)).

## 7. Zero targets

If every candidate resolves to `SKIPPED_ALREADY_COVERED` (diff mode), report that plainly instead of
proceeding to Generate tests with nothing to do: "No untested journeys found." This is a normal outcome,
not a failure. (Backfill mode can never reach this state — an empty `target.journeys` is already a HARD
STOP at Inputs, never a soft zero-target report here.)
