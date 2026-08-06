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

Expand `target.scope` literally: a file entry is one target; a directory entry expands to every source
file under it, recursively.

## 3. Exclusions (both modes)

Never select a target under a generated/vendored/build path — `node_modules/`, `vendor/`, `dist/`,
`build/`, `.venv/`, `target/` (Java/Rust build output), `__pycache__/`, `.git/`, or any directory the
repo's own `.gitignore` marks as generated. These are never hand-written source, so tests for them are
never useful.

## 4. Cap and report overflow

Apply `max_files_per_run` (default 20) to the resulting `NEW` list, in the order files were discovered.
Anything past the cap is tagged `SKIPPED_MAX_FILES` — listed by name in `UNIT_TEST_REPORT.md`, never
dropped silently (see [gate-policy.md §7](../reference/gate-policy.md#7-maxfilesperrun-reached)).

## 5. Zero targets

If every candidate resolves to `SKIPPED_ALREADY_COVERED` (diff mode) or `target.scope` is empty after
expansion (backfill mode — e.g. a directory with no source files), report that plainly instead of
proceeding to Generate tests with nothing to do: "No untested changes found" / "No source files under
`<scope>`." This is a normal outcome, not a failure.
