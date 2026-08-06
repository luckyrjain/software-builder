# Changelog — contract-test-creator

All notable changes to the contract-test-creator skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-06

### Added

- Initial skill release — generates consumer-driven contract tests (Pact-style) for a target repository,
  as either a **consumer** test (records expectations, produces/updates a pact file) or a **provider
  verification** test (replays existing pact files against the real running provider).
- `workflow/inputs.md` — `target` (`diff` or `backfill` mode, plus a required `role: consumer|provider`),
  `repo_root`, `run_tests`, `max_files_per_run`, `deadline`, `session_token_budget`, `output_dir` parsing;
  HARD STOP on missing required fields, including `role`.
- `workflow/detect-conventions.md` — runs `scripts/detect-pact-tooling.sh`; ask-once gate on ambiguous
  detection, ask-before-writing gate on zero detected Pact tooling; role is never re-derived here.
- `workflow/select-targets.md` — diff-mode changed-interaction selection (consumer call sites or provider
  routes), backfill-mode scope expansion, generated/vendored-path and `pacts/`-directory exclusions,
  `max_files_per_run` cap with explicit overflow reporting.
- `workflow/generate-tests.md` — distinct consumer-side and provider-side generation logic; interaction
  shape derived only from real, observed usage (a call site, a client method, or a schema file), never a
  guess; `NEEDS_OBSERVED_INTERACTION` gate when none exists; broker-vs-local pact source handling.
- `workflow/verify-and-iterate.md` — runs generated tests, distinguishes a test bug (fix and retry, capped
  at 3 attempts) from a probable production bug — for a provider target, a verification failure against a
  real pact file is treated as a consumer-breaking finding, never resolved by loosening the contract.
- `workflow/report.md` — `CONTRACT_TEST_REPORT.md` rendering rules; role/broker always shown in the
  header; never upgrades a status; always surfaces production-bug findings plainly.
- `scripts/detect-pact-tooling.sh` + `scripts/pact-markers.sh` — marker detection across pact-js,
  pact-python, Pact JVM, pact-go, and Ruby pact, plus independent Pact Broker (CI config) detection;
  `tests/test_detect_pact_tooling.py` pytest suite plus fixture repos under
  `tests/fixtures/pact-detect/`.
- `reference/{skill-contract,phase-index,lazy-load-index,gate-policy,test-quality-deltas,
  framework-detection,report-format,smoke-test,pressure-tests}.md` — `skill-contract.md` and
  `test-quality-deltas.md` link the shared
  `docs/skill-framework/shared/test-creation-principles.md` for rules common to all four
  `*-test-creator` skills, stating only contract-specific deltas.
- Shared framework compliance (prompt-injection, skill-routing, cross-skill-escalation, examples
  conventions, smoke-test conventions).
- Cross-skill escalation rows: contract-test-creator ↔ integration-test-creator (live integration test vs.
  interface agreement), contract-test-creator ↔ loop-task-implementer/pr-review (production-bug
  findings).
