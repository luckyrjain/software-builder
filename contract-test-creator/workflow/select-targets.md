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

Expand `target.scope` literally: a file entry is one target (one client call site for `consumer`, one
route/handler for `provider`); a directory entry expands to every candidate interaction under it,
recursively, scoped by the file types relevant to `target.role`.

## 3. Exclusions (both modes)

Never select a target under a generated/vendored/build path — `node_modules/`, `vendor/`, `dist/`,
`build/`, `.venv/`, `target/`, `__pycache__/`, `.git/`, or any directory the repo's own `.gitignore` marks
as generated. Never select the `pacts/` directory itself as a target — it's the skill's own output/input,
not a thing to write a test for.

## 4. Cap and report overflow

Apply `max_files_per_run` (default 20) to the resulting `NEW` list, in the order interactions were
discovered. Anything past the cap is tagged `SKIPPED_MAX_FILES` — listed by name in
`CONTRACT_TEST_REPORT.md`, never dropped silently (see
[gate-policy.md §7](../reference/gate-policy.md#7-maxfilesperrun-reached)).

## 5. Zero targets

If every candidate resolves to `SKIPPED_ALREADY_COVERED` (diff mode) or `target.scope` is empty after
expansion (backfill mode), report that plainly instead of proceeding to Generate tests with nothing to
do: "No untested consumer interactions found" / "No provider routes under `<scope>`." This is a normal
outcome, not a failure.
