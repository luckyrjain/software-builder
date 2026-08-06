# Changelog — test-writer

All notable changes to the test-writer skill. Per-file `workflow_version` in `workflow/*.md` frontmatter
should match the version of the latest entry below that names that file.

## [2.1.0] — 2026-08-06

### Added

- **api-test-creator** joins the dispatch family as a fifth level — black-box Postman/Newman
  request/response test suites against a real running API (no browser, no in-process mocking, no Pact
  consumer/provider agreement; see its own `README.md` for how it differs from the other four).
- `workflow/delegate.md`, `reference/level-classification.md`, and `SKILL.md`'s dispatch table updated
  with the `api` level and its keywords ("API test", "Postman", "Newman", "black-box API test").
- The "test the API" ambiguous-request example in `reference/level-classification.md` now lists `api` as
  a fourth candidate alongside unit/integration/contract, rather than defaulting to one of the original
  three.
- `make install-test-writer` now chains all five dispatch targets, not four.

## [2.0.0] — 2026-08-06

### Changed (breaking)

- **Rewritten from a generator into a thin router.** All framework detection, target selection, test
  generation, and verification logic moved out to four new focused skills: `unit-test-creator`,
  `integration-test-creator`, `contract-test-creator`, and `e2e-test-creator`. test-writer now only
  classifies a level-unspecified "write tests" request and dispatches to exactly one of them, relaying
  its report verbatim — mirrors the `who-owns-x-bot`/`release-readiness-checker` composition pattern.
- Removed: `scripts/`, `tests/` (framework-detection logic and its pytest suite — re-homed as
  `unit-test-creator`'s own artifact), `workflow/{detect-conventions,select-targets,generate-tests,
  verify-and-iterate,report}.md`, `reference/{gate-policy,test-quality-checklist,framework-detection,
  report-format}.md` (generation-specific content — shared parts now live in
  `docs/skill-framework/shared/test-creation-principles.md`, level-specific parts now live in each of the
  four skills' own `reference/`).
- Added: `workflow/classify.md` (ask-once level gate), `workflow/delegate.md` (dispatch + verbatim
  relay), `reference/level-classification.md` (keyword heuristics mirroring `skill-routing.md`).
- `SKILL.md`/`README.md`/`SETUP.md`/`examples.md`/`reference/{skill-contract,phase-index,
  lazy-load-index,smoke-test,pressure-tests}.md` rewritten for the router's much narrower scope.
- Callers who already know the level should invoke the matching `*-test-creator` skill directly and skip
  this router entirely — see `SKILL.md § When to use / NOT to use`.

## [1.0.0] — 2026-08-06

### Added

- Initial skill release — generates and backfills automated tests for a target repository.
- `workflow/inputs.md` — `target` (`diff` or `backfill` mode), `repo_root`, `run_tests`,
  `max_files_per_run`, `deadline`, `session_token_budget`, `output_dir` parsing; HARD STOP on missing
  required fields.
- `workflow/detect-conventions.md` — runs `scripts/detect-test-framework.sh`; ask-once gate on ambiguous
  detection, ask-before-writing gate on zero detected markers.
- `workflow/select-targets.md` — diff-mode changed-code selection (skipping targets already covered by
  the diff itself), backfill-mode scope expansion, generated/vendored-path exclusions, `max_files_per_run`
  cap with explicit overflow reporting.
- `workflow/generate-tests.md` — happy-path/edge-case/error-case coverage shape, fixture/mock reuse,
  untestable-without-fixture gate.
- `workflow/verify-and-iterate.md` — runs generated tests, distinguishes a test bug (fix and retry, capped
  at 3 attempts) from a probable production bug (never patched — surfaced as a finding instead).
- `workflow/report.md` — `TEST_WRITER_REPORT.md` rendering rules; never upgrades a status, always
  surfaces production-bug findings plainly.
- `scripts/detect-test-framework.sh` + `scripts/test-framework-markers.sh` — marker-file detection across
  pytest, unittest, Jest, Vitest, Mocha, Go `testing`, JUnit 4/5, RSpec, Minitest, xUnit/NUnit/MSTest, and
  `cargo test`; `tests/test_detect_test_framework.py` pytest suite plus fixture repos under
  `tests/fixtures/test-framework-detect/`.
- `reference/{skill-contract,phase-index,lazy-load-index,gate-policy,test-quality-checklist,
  framework-detection,report-format,smoke-test,pressure-tests}.md`.
- Shared framework compliance (prompt-injection, skill-routing, cross-skill-escalation, examples
  conventions, smoke-test conventions).
- New cross-skill escalation rows: test-writer ↔ pr-review (production-bug findings, existing-test-quality
  review), test-writer ↔ loop-task-implementer (production-bug fixes).
