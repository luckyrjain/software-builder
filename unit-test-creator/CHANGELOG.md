# Changelog — unit-test-creator

All notable changes to the unit-test-creator skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-06

### Added

- Initial skill release — generates and backfills isolated, fast unit tests for a target repository,
  every external dependency mocked or stubbed.
- `workflow/inputs.md` — `target` (`diff` or `backfill` mode), `repo_root`, `run_tests`,
  `max_files_per_run`, `deadline`, `session_token_budget`, `output_dir` parsing; HARD STOP on missing
  required fields.
- `workflow/detect-conventions.md` — runs `scripts/detect-test-framework.sh`; ask-once gate on ambiguous
  detection, ask-before-writing gate on zero detected markers.
- `workflow/select-targets.md` — diff-mode changed-code selection (skipping targets already covered by
  the diff itself), backfill-mode scope expansion, generated/vendored-path exclusions, `max_files_per_run`
  cap with explicit overflow reporting.
- `workflow/generate-tests.md` — happy-path/edge-case/error-case coverage shape, mandatory mocking of
  every network call/database/filesystem I/O/wall-clock dependency/randomness source, fixture/mock reuse,
  untestable-without-fixture gate escalating to **integration-test-creator**.
- `workflow/verify-and-iterate.md` — runs generated tests, distinguishes a test bug (fix and retry, capped
  at 3 attempts) from a probable production bug (never patched — surfaced as a finding instead).
- `workflow/report.md` — `UNIT_TEST_REPORT.md` rendering rules per the shared skeleton in
  `docs/skill-framework/shared/test-creation-principles.md` §4; never upgrades a status, always surfaces
  production-bug and untestable-without-fixture findings plainly.
- `scripts/detect-test-framework.sh` + `scripts/test-framework-markers.sh` — marker-file detection across
  pytest, unittest, Jest, Vitest, Mocha, Go `testing`, JUnit 4/5, RSpec, Minitest, xUnit/NUnit/MSTest, and
  `cargo test`; `tests/test_detect_test_framework.py` pytest suite plus fixture repos under
  `tests/fixtures/test-framework-detect/`. Re-homed from test-writer's own original detection logic —
  the underlying "what framework does this repo's tests use" problem is identical at unit scope.
- `reference/{skill-contract,phase-index,lazy-load-index,gate-policy,test-quality-deltas,
  framework-detection,report-format,smoke-test,pressure-tests}.md`. `skill-contract.md` and
  `test-quality-deltas.md` link `docs/skill-framework/shared/test-creation-principles.md` for rules
  shared across the whole test-creator family rather than restating them.
- Shared framework compliance (prompt-injection, skill-routing, cross-skill-escalation, examples
  conventions, smoke-test conventions).
- Cross-skill escalation rows: unit-test-creator → integration-test-creator (a target needing a real
  adjacent dependency), unit-test-creator ↔ pr-review (production-bug findings, existing-test-quality
  review), unit-test-creator ↔ loop-task-implementer (production-bug fixes), test-writer → unit-test-creator
  (level dispatch).
