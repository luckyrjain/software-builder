---
workflow_version: 1.0
phase: detect_conventions
produces:
  - test_framework
  - test_layout
  - selector_convention
  - detection_confidence
consumes:
  - repo_root
  - test_framework_hint
---

# Detect conventions

Run [scripts/detect-e2e-tooling.sh](../scripts/detect-e2e-tooling.sh) against `repo_root` before selecting
or writing anything. Full marker-file table and confidence rules:
[reference/framework-detection.md](../reference/framework-detection.md).

```bash
scripts/detect-e2e-tooling.sh <repo_root>
```

## 1. Interpret the result

| Script output | Action |
|----------------|--------|
| `STATUS: DETECTED` (exit 0) | One clear candidate — use `FRAMEWORK`/`LAYOUT` as-is |
| `STATUS: AMBIGUOUS` (exit 2) | See §2 |
| `STATUS: NONE_DETECTED` (exit 3) | See §3 |

`detection_confidence` is the script's `CONFIDENCE` field (`HIGH` — a dedicated config file present;
`MEDIUM` — inferred from a dependency manifest only, no dedicated config file — this is the normal case
for Selenium, which has no single canonical config file the way Playwright/Cypress do).

## 2. Ambiguous detection — ask once, never guess

Two or more candidates at comparable top confidence — most commonly a repo mid-migration with both
`playwright.config.*` and `cypress.config.*` present. If `test_framework_hint` names one of the listed
`CANDIDATES`, select it and proceed without asking — the caller already resolved the ambiguity. Otherwise
this is a live gate ([gate-policy.md §2](../reference/gate-policy.md#2-ambiguous-browser-tooling-detection)):
list the candidates exactly as printed and ask which one is actually in use. Never pick the first
alphabetically, the most common industry default, or the one this session "prefers."

## 3. No browser tooling detected — ask before writing anything

A repo with zero markers has no established convention to match, so there is nothing to detect a
"correct" answer from ([gate-policy.md §3](../reference/gate-policy.md#3-zero-browser-tooling-markers-found)).
Ask the caller which framework/test command to use; never default silently to whatever this skill would
pick for a greenfield project.

## 4. Layout and selector convention

Beyond the framework name, note from the scan's `LAYOUT` field (or a quick follow-up read of 1–2 existing
spec files when present):

- **Layout** — the script reports the directory convention it found (`e2e/`, `tests/e2e/`,
  `cypress/e2e/`, `playwright-tests/`) or the framework's own default when none exists yet — matched
  exactly in Generate tests, never introduced as a second convention.
- **Selector convention** — how the repo's own existing specs (if any) locate elements: role/accessible-
  name queries, `data-testid` attributes, or another established pattern. Reused in Generate tests rather
  than re-invented per file. If the repo has **no** existing selector convention, default to role/
  accessible-name-based selectors (the most resilient default across Playwright/Cypress/Selenium) and
  state that explicitly in the report as a default, not an observed convention.

If no existing spec files exist yet (tooling is configured but nothing written), layout/selector
convention default to the framework's own idiomatic convention, stated explicitly in the report as
inferred rather than observed.
