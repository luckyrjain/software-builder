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

Turn `target` into a concrete, bounded `target_list` of functions/classes to write unit tests for.

## 1. Diff mode

Parse the diff named by `target.source` (an MR, a branch range, or the working tree). For each
changed function or method:

- **Skip if the diff itself already includes a matching test change** (a `.test.` file, `tests/`
  addition, or edit alongside the source change that plausibly covers it) — tag `SKIPPED_ALREADY_COVERED`.
  Do not duplicate coverage the author already wrote.
- **Skip if an existing test file clearly already exercises the changed lines** — only skip on a
  reasonably confident match (an existing test that calls the exact changed function/method with
  assertions on its output); when uncertain whether existing coverage is adequate, keep the target rather
  than guess it's covered.
- Otherwise tag `NEW`.

Only source files fall in scope — never generate tests for the diff's own test-file changes, config, or
generated/vendored paths (see §3).

## 2. Backfill mode

Expand `target.scope` literally: a directory entry expands to every source file under it, recursively; a
file entry expands to every function/method it defines — the same function/method granularity `target_list`
uses everywhere else in this skill (diff mode, the `report-format.md` target identifier, and the
incremental-state schema all key on `path.py::function_name`, never a bare file path). A file with no
functions/methods worth testing (a pure constants/config module) contributes no targets, not one
whole-file target.

## 3. Exclusions (both modes)

Never select a target under a generated/vendored/build path — `node_modules/`, `vendor/`, `dist/`,
`build/`, `.venv/`, `target/` (Java/Rust build output), `__pycache__/`, `.git/`, or any directory the
repo's own `.gitignore` marks as generated. These are never hand-written source, so tests for them are
never useful.

## 4. Prioritize using domain-comprehension (optional)

If `<workspace_root>/RISK_MAP.md` exists (domain-comprehension already ran), reorder the `NEW` list so
targets whose repo/context appears in its § Change risk table with a weak `Test signal` and high
`Runtime critical?`/`Fan-out` come first — this determines *which* targets survive the §5 cap when
`target_list` is larger than `max_files_per_run`, not whether a target is included at all. Absent
`RISK_MAP.md`, skip this step entirely — no prioritization, no note in the report. Full artifact table
and precedence rules: [domain-comprehension-integration.md](../../docs/skill-framework/shared/domain-comprehension-integration.md).

## 5. Apply incremental backfill state (optional)

If `UNIT_TEST_COVERAGE_STATE.yaml` exists at `output_dir` (a prior backfill run on this repo), drop any
`NEW` target whose recorded `status` is `WRITTEN_PASSING` **and** whose `content_hash` still matches its
current source — tag it `SKIPPED_ALREADY_COVERED` ("per state file"). Any other recorded status
(`NEEDS_HUMAN`, `WRITTEN_FAILING_PROD_BUG`, `UNTESTABLE_WITHOUT_FIXTURE`, `UNVERIFIED`) means the target
was never actually resolved — never skip it on a hash match alone. A target whose hash has changed since
`last_attempted` is treated as new outright, regardless of its recorded status. Move `pending_backlog`
entries and every non-`WRITTEN_PASSING` recorded target to the front of the list, ahead of anything newly
discovered this run, so a repeated backfill works through unresolved targets before starting fresh
ground. Absent the state file, skip this step entirely — no filtering, no reordering, no note in the
report. Full schema and precedence rules:
[test-creation-principles.md §6](../../docs/skill-framework/shared/test-creation-principles.md#6-incremental-backfill-state-optional).

## 6. Cap and report overflow

Apply `max_files_per_run` (default 20) to the resulting `NEW` list, in the order left by §4/§5 (or
discovery order when neither applied). Anything past the cap is tagged `SKIPPED_MAX_FILES` — listed by
name in `UNIT_TEST_REPORT.md`, never dropped silently (see
[gate-policy.md §7](../reference/gate-policy.md#7-maxfilesperrun-reached)).

## 7. Zero targets

If every candidate resolves to `SKIPPED_ALREADY_COVERED` (diff mode) or `target.scope` is empty after
expansion (backfill mode — e.g. a directory with no source files), report that plainly instead of
proceeding to Generate tests with nothing to do: "No untested changes found" / "No source files under
`<scope>`." This is a normal outcome, not a failure.
