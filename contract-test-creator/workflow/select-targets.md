---
workflow_version: 1.0
phase: select_targets
produces:
  - target_list
consumes:
  - target
  - pact_library
---

# Select targets

Turn `target` into a concrete, bounded `target_list` of interactions to write consumer or provider
verification tests for — the same `target.role` resolved at Inputs applies to every item in the list; a
single run never mixes consumer and provider targets.

## 1. Diff mode

Parse the diff named by `target.source` (an MR, a branch range, or the working tree).

- **`role: consumer`** — for each changed request-building call site (a new/modified HTTP client call, a
  new method on an existing API client) to the provider under test, this is a candidate interaction.
- **`role: provider`** — for each changed route/handler on the provider side, this is a candidate
  interaction that any existing consumer pact(s) covering it should re-verify.

For either role:

- **Skip if the diff itself already includes a matching pact-test change** (a `.pact.test.` file edit
  alongside the source change that plausibly covers it) — tag `SKIPPED_ALREADY_COVERED`. Do not duplicate
  coverage the author already wrote.
- **Skip if an existing pact test clearly already exercises the changed interaction** — only skip on a
  reasonably confident match; when uncertain, keep the target rather than guess it's covered.
- Otherwise tag `NEW`.

## 2. Backfill mode

Expand `target.scope` literally: a file or directory entry expands to every candidate interaction it
contains — one client call site per interaction for `consumer`, one route/handler per interaction for
`provider` (a single file commonly defines several) — recursing into a directory, scoped by the file
types relevant to `target.role`.

## 3. Exclusions (both modes)

Never select a target under a generated/vendored/build path — `node_modules/`, `vendor/`, `dist/`,
`build/`, `.venv/`, `target/`, `__pycache__/`, `.git/`, or any directory the repo's own `.gitignore` marks
as generated. Never select the `pacts/` directory itself as a target — it's the skill's own output/input,
not a thing to write a test for.

## 4. Prioritize using domain-comprehension (optional)

If `<workspace_root>/RISK_MAP.md` exists, reorder the `NEW` list so interactions whose repo/context
appears in its § Change risk table with a weak `Test signal` and high `Runtime critical?`/`Fan-out` come
first — determines survival order under §5's cap, not inclusion. If
`<workspace_root>/DATA_OWNERSHIP.md` or `BOUNDED_CONTEXTS.md` also exist, use them as corroborating
evidence (never sole evidence —
[gate-policy.md §5](../reference/gate-policy.md#5-target-has-no-real-observed-interaction-to-derive-its-shape-from)
still requires a real observed interaction) for which service is the actual provider of an entity when
resolving `role: provider` targets. Absent these files, skip this step. Full artifact table and
precedence rules:
[domain-comprehension-integration.md](../../docs/skill-framework/shared/domain-comprehension-integration.md).

## 5. Apply incremental backfill state (optional)

If `CONTRACT_TEST_COVERAGE_STATE.yaml` exists at `output_dir` (a prior backfill run for this `role` on
this repo), drop any `NEW` target whose recorded `status` is `WRITTEN_PASSING` **and** whose
`content_hash` still matches its current source — tag it `SKIPPED_ALREADY_COVERED` ("per state file").
Any other recorded status (`NEEDS_HUMAN`, `WRITTEN_FAILING_PROD_BUG`, `NEEDS_OBSERVED_INTERACTION`,
`UNVERIFIED`) means the target was never actually resolved — never skip it on a hash match alone. A
target whose hash has changed since `last_attempted` is treated as new outright, regardless of its
recorded status. Move `pending_backlog` entries and every non-`WRITTEN_PASSING` recorded target to the
front of the list. Absent the state file, skip this step entirely — no filtering, no reordering, no note
in the report. Full schema and precedence rules:
[test-creation-principles.md §6](../../docs/skill-framework/shared/test-creation-principles.md#6-incremental-backfill-state-optional).

## 6. Cap and report overflow

Apply `max_files_per_run` (default 20) to the resulting `NEW` list, in the order left by §4/§5 (or
discovery order when neither applied). Anything past the cap is tagged `SKIPPED_MAX_FILES` — listed by
name in `CONTRACT_TEST_REPORT.md`, never dropped silently (see
[gate-policy.md §7](../reference/gate-policy.md#7-maxfilesperrun-reached)).

## 7. Zero targets

If every candidate resolves to `SKIPPED_ALREADY_COVERED` (diff mode) or `target.scope` is empty after
expansion (backfill mode), report that plainly instead of proceeding to Generate tests with nothing to
do: "No untested consumer interactions found" / "No provider routes under `<scope>`." This is a normal
outcome, not a failure.
