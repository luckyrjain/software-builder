# Changelog — integration-test-creator

All notable changes to the integration-test-creator skill. Per-file `workflow_version` in
`workflow/*.md` frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-06

### Added

- Initial skill release — generates and backfills real integration tests (against a real adjacent
  dependency, never a mock of it) for a target repository.
- `workflow/inputs.md` — `target` (`diff` or `backfill` mode), `repo_root`, `test_framework_hint`,
  `run_tests`, `max_files_per_run`, `deadline`, `session_token_budget`, `output_dir` parsing; HARD STOP on
  missing required fields.
- `workflow/detect-conventions.md` — runs `scripts/detect-integration-setup.sh`; detects the base test
  runner, the real-dependency orchestration mechanism (testcontainers, docker-compose, embedded), and any
  integration-test naming/tag convention; ask-once gates on ambiguous detection, `NEEDS_INTEGRATION_ENV`
  gate when no orchestration mechanism is found.
- `workflow/select-targets.md` — diff-mode changed-seam selection (skipping targets already covered by the
  diff itself), backfill-mode scope expansion, generated/vendored-path exclusions, `max_files_per_run` cap
  with explicit overflow reporting.
- `workflow/generate-tests.md` — happy-path/edge-case/error-case coverage shape against the real
  dependency, fixture/testcontainers-setup reuse, never mocks the seam under test.
- `workflow/verify-and-iterate.md` — stands up the real dependency when an orchestration mechanism is
  available, runs generated tests, distinguishes a test bug (fix and retry, capped at 3 attempts) from a
  probable production bug (never patched — surfaced as a finding instead).
- `workflow/report.md` — `INTEGRATION_TEST_REPORT.md` rendering rules per the shared skeleton in
  [test-creation-principles.md §4](../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton),
  plus the level-specific `NEEDS_INTEGRATION_ENV` status.
- `scripts/detect-integration-setup.sh` + `scripts/integration-markers.sh` — two-dimension detection:
  base test runner (pytest, unittest, Jest, Vitest, Mocha, Go `testing`, JUnit 4/5, RSpec, Minitest,
  xUnit/NUnit/MSTest, `cargo test`) plus real-dependency orchestration (testcontainers, docker-compose,
  embedded-DB convention) plus an informational integration naming/tag convention signal;
  `tests/test_detect_integration_setup.py` pytest suite plus fixture repos under
  `tests/fixtures/integration-detect/`.
- `reference/{skill-contract,phase-index,lazy-load-index,gate-policy,test-quality-deltas,
  framework-detection,report-format,smoke-test,pressure-tests}.md` — the level-specific deltas link the
  new shared [test-creation-principles.md](../docs/skill-framework/shared/test-creation-principles.md)
  rather than restating its rules.
- Shared framework compliance (prompt-injection, skill-routing, cross-skill-escalation, examples
  conventions, smoke-test conventions).
- New cross-skill escalation rows: integration-test-creator ↔ unit-test-creator (target doesn't need a
  real dependency), integration-test-creator ↔ e2e-test-creator (caller wants the full UI journey),
  integration-test-creator ↔ contract-test-creator (caller wants an interface agreement, not a live
  dependency test), integration-test-creator ↔ loop-task-implementer/pr-review (production-bug findings).
