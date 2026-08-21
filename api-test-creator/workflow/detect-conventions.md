---
workflow_version: 1.1
phase: detect_conventions
produces:
  - collection_path
  - newman_present
  - environment_files
  - detection_confidence
consumes:
  - repo_root
  - test_framework_hint
---

# Detect conventions

Follow the canonical [test-creator common workflow](../../docs/skill-framework/shared/test-creator-common-workflow.md)
for shared detection behavior; the rules below are API-level detection deltas.

Run [scripts/detect-postman-tooling.sh](../scripts/detect-postman-tooling.sh) against `repo_root` (or the
target's own scoped directory in a monorepo) before selecting or writing anything. Full marker table and
the canonical-collection resolution order:
[reference/framework-detection.md](../reference/framework-detection.md).

```bash
scripts/detect-postman-tooling.sh <repo_root>
```

## 1. Interpret the result

| Script output | Action |
|----------------|--------|
| `STATUS: DETECTED` (exit 0) | One clear canonical collection (or, with zero collections, a `newman` dependency alone) — use `FRAMEWORK`/`CONFIDENCE`/`MARKER`/`COLLECTION_COUNT` as-is |
| `STATUS: AMBIGUOUS` (exit 2) | See §2 |
| `STATUS: NONE_DETECTED` (exit 3) | See §3 |

`detection_confidence` is the script's `CONFIDENCE` field (`HIGH` — a single collection file, or a
canonical one resolved by hint/naming-convention/CI-reference; `MEDIUM` — `newman` declared as a dependency
but no collection file exists yet). `newman_present` and `environment_files` are read on every branch,
including `NONE_DETECTED`, since they're informational rather than part of the detection gate.

## 2. Ambiguous canonical collection — ask once, never guess

This skill is single-tool (Postman/Newman) — unlike `unit-test-creator`'s multi-ecosystem or
`e2e-test-creator`'s multi-framework detection, ambiguity here is never "which tool," it's **which
collection file is the canonical target** when 2+ `*.postman_collection.json` files exist with no naming
convention (`main`/`primary`) or CI reference pointing at exactly one
([gate-policy.md §2](../reference/gate-policy.md#2-ambiguous-canonical-collection)). If
`test_framework_hint` names one of the printed `CANDIDATES` (by path or basename), select it and proceed
without asking — the caller already resolved the ambiguity. Otherwise list the candidates exactly as
printed and ask which one is the collection to extend. Never pick the first alphabetically or the one this
session "prefers."

## 3. Zero Postman/Newman tooling detected — ask before writing anything

A repo with zero collection files and no `newman` dependency has no established convention to match
([gate-policy.md §3](../reference/gate-policy.md#3-zero-postmannewman-tooling-detected)). Ask the caller
whether to create a new collection from scratch (and where) before writing anything — never default
silently to a collection layout this session would pick for a greenfield project.

## 4. Layout conventions

Beyond `COLLECTION_COUNT` and `NEWMAN`, note from the scan (or a quick follow-up read of the resolved
collection file when one exists):

- **Layout** — collection at repo root, `postman/`, or `tests/postman/` — matched exactly in Generate
  tests, never introduced as a second convention.
- **Folder structure inside the collection** — Postman collections group requests into folders; reuse the
  repo's existing folder-per-resource (or folder-per-flow) grouping rather than inventing a new one.
- **Environment file(s)** — `ENVIRONMENT_COUNT`/`environment_files` name which `*.postman_environment.json`
  file(s) exist; note which one the repo's own `newman run` invocation (in `package.json` scripts or CI)
  actually passes with `-e`, so Generate tests writes/reads variables against that one rather than a
  disconnected environment file nobody runs against.

If no existing collection exists yet (only a bare `newman` dependency), layout defaults to `postman/` at
`repo_root`, stated explicitly in the report as inferred rather than observed.
