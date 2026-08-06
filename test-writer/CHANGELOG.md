# Changelog — test-writer

All notable changes to the test-writer skill. Per-file `workflow_version` in `workflow/*.md` frontmatter
should match the version of the latest entry below that names that file.

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
