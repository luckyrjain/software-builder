---
workflow_version: 1.1
phase: detect_conventions
produces:
  - test_framework
  - test_layout
  - mock_style
  - detection_confidence
consumes:
  - repo_root
  - test_framework_hint
---

# Detect conventions

Follow the canonical [test-creator common workflow](../../docs/skill-framework/shared/test-creator-common-workflow.md)
for shared detection behavior; the rules below are unit-level detection deltas.

Run [scripts/detect-test-framework.sh](../scripts/detect-test-framework.sh) against `repo_root` before
selecting or writing anything. Full marker-file table and confidence rules:
[reference/framework-detection.md](../reference/framework-detection.md).

```bash
scripts/detect-test-framework.sh <repo_root>
```

## 1. Interpret the result

| Script output | Action |
|----------------|--------|
| `STATUS: DETECTED` (exit 0) | One clear candidate — use `FRAMEWORK`/`TEST_LAYOUT` as-is |
| `STATUS: AMBIGUOUS` (exit 2) | See §2 |
| `STATUS: NONE_DETECTED` (exit 3) | See §3 |

`detection_confidence` is the script's `CONFIDENCE` field (`HIGH` — a framework config file present;
`MEDIUM` — inferred from a dependency manifest only, no dedicated config file).

## 2. Ambiguous detection — ask once, never guess

If `test_framework_hint` names one of the listed `CANDIDATES`, select it and proceed without asking —
the caller already resolved the ambiguity. Otherwise this is a live gate
([gate-policy.md §2](../reference/gate-policy.md#2-ambiguous-framework-detection)): list the candidates
exactly as printed and ask which one is actually in use. Never pick the first alphabetically, the most
common industry default, or the one this session "prefers."

## 3. No framework detected — ask before writing anything

A repo with zero markers has no established convention to match, so there is nothing to detect a
"correct" answer from ([gate-policy.md §3](../reference/gate-policy.md#3-zero-framework-markers-found)).
Ask the caller which framework/test command to use; never default silently to whatever this skill would
pick for a greenfield project.

## 4. Layout and mocking style

Beyond the framework name, note from the scan (or a quick follow-up read of 1–2 existing test files when
present):

- **Layout** — co-located (`foo.test.ts` beside `foo.ts`) vs. a mirrored `tests/`/`test/` tree vs.
  `test_*.py` naming — matched exactly in Generate tests, never introduced as a second convention.
- **Mock style** — an existing fixtures/mocks helper module, dependency-injection pattern, or stub
  library already in use (e.g. `unittest.mock`, `jest.mock`, a hand-rolled fake client). Reused in
  Generate tests rather than re-invented per file — this is what makes the isolation in
  [test-quality-deltas.md](../reference/test-quality-deltas.md) achievable without guessed behavior.

If no existing test files exist yet (a framework is configured but nothing written), layout/mock style
default to the framework's own idiomatic convention, stated explicitly in the report as inferred rather
than observed.
