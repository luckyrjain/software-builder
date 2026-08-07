# Changelog — e2e-test-creator

All notable changes to the e2e-test-creator skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-06

### Added

- Initial skill release — generates and backfills full user-journey browser end-to-end tests for a target
  repository using Playwright, Cypress, or Selenium/WebDriver.
- `workflow/inputs.md` — `target` (`diff` or `backfill` mode), `repo_root`, `run_tests`,
  `max_files_per_run`, `deadline`, `session_token_budget`, `output_dir` parsing; HARD STOP on missing
  required fields, and on backfill mode with an absent/empty `target.journeys` list.
- `workflow/detect-conventions.md` — runs `scripts/detect-e2e-tooling.sh`; ask-once gate on ambiguous
  tooling detection, ask-before-writing gate on zero detected markers.
- `workflow/select-targets.md` — diff-mode journey inference from changed routes/pages/user-facing
  components, backfill-mode explicit `target.journeys` list, generated/vendored-path exclusions,
  `max_files_per_run` cap over journeys with explicit overflow reporting.
- `workflow/generate-tests.md` — journey → step sequence → user-visible-outcome-only assertions, selector
  convention rules (repo's own convention, else role/accessible-name default), no hard-coded
  `sleep`/fixed-wait, `NEEDS_BROWSER_ENV` gate when no reachable app instance exists.
- `workflow/verify-and-iterate.md` — runs generated tests against a reachable instance, distinguishes a
  test bug (including flaky selectors/timing — fix and retry, capped at 3 attempts) from a probable
  production bug (never patched — surfaced as a finding instead).
- `workflow/report.md` — `E2E_TEST_REPORT.md` rendering rules per the shared reporting skeleton; never
  upgrades a status, always surfaces production-bug findings plainly.
- `scripts/detect-e2e-tooling.sh` + `scripts/e2e-markers.sh` — marker-file detection across Playwright,
  Cypress, and Selenium/WebDriver (Node/Python/Java), plus layout-convention detection;
  `tests/test_detect_e2e_tooling.py` pytest suite plus fixture repos under
  `tests/fixtures/e2e-detect/`.
- `reference/{skill-contract,phase-index,lazy-load-index,gate-policy,test-quality-deltas,
  framework-detection,report-format,smoke-test,pressure-tests}.md`. `skill-contract.md` and
  `test-quality-deltas.md` link to the new shared
  [test-creation-principles.md](../docs/skill-framework/shared/test-creation-principles.md) for rules
  common to all four `*-test-creator` skills, stating only this skill's own deltas.
- Shared framework compliance (prompt-injection, skill-routing, cross-skill-escalation, examples
  conventions, smoke-test conventions).
- New cross-skill escalation rows: e2e-test-creator ↔ integration-test-creator (below-the-UI seam vs. full
  browser journey), e2e-test-creator ↔ unit-test-creator (function-level vs. journey-level),
  e2e-test-creator ↔ contract-test-creator (interaction agreement vs. browser flow), e2e-test-creator ↔
  loop-task-implementer / pr-review (production-bug findings).
