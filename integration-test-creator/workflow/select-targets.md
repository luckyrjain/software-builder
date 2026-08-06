---
workflow_version: 1.0
phase: select_targets
produces:
  - target_list
consumes:
  - target
  - test_framework
  - orchestration
---

# Select targets

Turn `target` into a concrete, bounded `target_list` of seams (a component boundary against one real
adjacent dependency) to write tests for.

## 1. Diff mode

Parse the diff named by `target.source` (an MR, a branch range, or the working tree). For each changed
function/module that talks to a real adjacent dependency (a DB call, a queue publish/consume, a cache
read/write, a call to another internal service):

- **Skip if the diff itself already includes a matching integration test change** (an `*.integration.
  test.*`/`*IT.java` file, a `tests/integration/` addition, or an edit alongside the source change that
  plausibly covers it) — tag `SKIPPED_ALREADY_COVERED`. Do not duplicate coverage the author already
  wrote.
- **Skip if an existing integration test clearly already exercises the changed seam** — only skip on a
  reasonably confident match (an existing test that calls the exact changed function/method against the
  real dependency, with assertions on its output); when uncertain whether existing coverage is adequate,
  keep the target rather than guess it's covered.
- Otherwise tag `NEW`.

Only source files whose changed logic actually touches a real adjacent dependency fall in scope — a
changed function that is pure/isolated belongs to **unit-test-creator**, not this skill (see
[SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation)). Never generate tests for the
diff's own test-file changes, config, or generated/vendored paths (see §3).

## 2. Backfill mode

Expand `target.scope` literally: a file entry is one target; a directory entry expands to every source
file under it, recursively, **that has an observable seam to a real adjacent dependency**. A file with no
such seam is not a target for this skill — flag it for **unit-test-creator** instead rather than silently
dropping it or fabricating an integration angle it doesn't have.

## 3. Exclusions (both modes)

Never select a target under a generated/vendored/build path — `node_modules/`, `vendor/`, `dist/`,
`build/`, `.venv/`, `target/` (Java/Rust build output), `__pycache__/`, `.git/`, or any directory the
repo's own `.gitignore` marks as generated. These are never hand-written source, so tests for them are
never useful.

## 4. Prioritize using domain-comprehension (optional)

If `<workspace_root>/RISK_MAP.md` exists, reorder the `NEW` list so targets whose repo/context appears in
its § Change risk table with a weak `Test signal` and high `Runtime critical?`/`Fan-out` come first —
determines survival order under §5's cap, not inclusion. If `<workspace_root>/DATA_OWNERSHIP.md` also
exists, use its authoritative-source-vs-replica/cache column as corroborating evidence for which side of
a seam must stay real when Generate tests builds the test — never a substitute for what the code itself
shows the seam actually is. Absent either file, skip this step. Full artifact table and precedence rules:
[domain-comprehension-integration.md](../../docs/skill-framework/shared/domain-comprehension-integration.md).

## 5. Cap and report overflow

Apply `max_files_per_run` (default 20) to the resulting `NEW` list, in prioritized order (§4) or
discovery order when §4 didn't apply. Anything past the cap is tagged `SKIPPED_MAX_FILES` — listed by
name in `INTEGRATION_TEST_REPORT.md`, never dropped silently (see
[gate-policy.md §7](../reference/gate-policy.md#7-maxfilesperrun-reached)).

## 6. Zero targets

If every candidate resolves to `SKIPPED_ALREADY_COVERED` (diff mode) or `target.scope` is empty after
expansion, or after excluding seam-less files (backfill mode), report that plainly instead of proceeding
to Generate tests with nothing to do: "No untested seams found" / "No source files with a real-dependency
seam under `<scope>`." This is a normal outcome, not a failure — and when the scope was entirely
seam-less, the report should say so and point at **unit-test-creator** instead.
