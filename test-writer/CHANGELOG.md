# Changelog — test-writer

All notable changes to the test-writer skill. Per-file `workflow_version` in `workflow/*.md` frontmatter
should match the version of the latest entry below that names that file.

## [2.2.0] — 2026-08-20

### Added

- **Multi-level orchestration** — test-writer can now build an ordered, de-duplicated `test_plan` for
  two or more explicitly requested complementary test surfaces and dispatch each existing specialist in
  a fresh context. A single explicitly named level still routes directly to that specialist.
- New `workflow/aggregate.md` keeps each specialist report verbatim while deriving orchestration
  completion state (`COMPLETE`, `PARTIAL`, `BLOCKED`, `FAILED`, `ESCALATED`) and fails closed when a
  planned level is missing, blocked, unanswered, or incomplete. Internal `COMPLETE` maps to portable
  `skill_result.status: SUCCESS`; the other portable specialist outcomes are propagated losslessly.
- Shared routing now distinguishes complementary breadth from competing interpretations: named unit +
  integration coverage routes through test-writer; an ambiguous phrase such as "test the payment flow"
  still asks once rather than running every plausible level.
- Added a golden injection fixture for the successful multi-level-plan path, proving malicious caller text
  remains absent from rendered orchestration metadata while genuine unit + integration signals survive.

### Hardened

- `level_hint` is a resolved signal, not an instruction to discard other explicitly requested
  complementary levels. Conflicting signals for one surface ask once instead of silently narrowing scope.
- `test_plan` metadata is fixed-vocabulary (`levels` + `signal_source`) and never copies raw caller text,
  preventing untrusted request content from becoming a second unescaped orchestration render path.
- When multiple sources support the same planned level, `signal_source` now uses deterministic provenance
  precedence (`explicit_request` > `clarification` > `level_hint`) without changing plan breadth.
- Delegated canonical statuses are preserved explicitly: specialist `SUCCESS` becomes internal
  `COMPLETE`; `PARTIAL`, `BLOCKED`, `FAILED`, and `ESCALATED` remain distinct. Mixed outcomes use
  deterministic precedence (`FAILED` > `BLOCKED` > `ESCALATED` > `PARTIAL` > `COMPLETE`).
- `unfinished_levels` is now a declared Aggregate output and is derived deterministically in plan order
  from every non-`COMPLETE` or missing planned level, including terminal `FAILED`/`ESCALATED` outcomes.
- Child dispatch now advances framework-owned `execution_context` per the inherited recursion contract
  instead of copying it unchanged. Ordinary caller fields still pass through unchanged, while each
  sibling derives its own child context from the same parent and a rejected recursion guard blocks only
  that planned level. Inputs also explicitly excludes `execution_context` from ordinary pass-through.
- Multi-level contract tests now assert semantics case-insensitively and cover hint precedence, the
  fixed-vocabulary metadata boundary, portable status mapping, and mixed-outcome precedence.

- Composed invocation now uses a typed `implementation_task` handoff, and test-writer emits the
  canonical `test_orchestration_result` artifact rather than claiming ownership of specialist
  `test_suite` artifacts. Pre-dispatch blocks and dispatched child reports are distinguished explicitly.

### Versioned workflow files

- `workflow/inputs.md` → 2.4
- `workflow/classify.md` → 2.4
- `workflow/delegate.md` → 2.5
- `workflow/aggregate.md` → 1.5

## [2.1.1] — 2026-08-10

### Fixed

- **`workflow/classify.md` §2** — a keyword paired with an explicit instruction to bypass this skill's
  own asking/gating ("don't ask", "no questions", "just do it", …) no longer counts as a §2 match, even
  when the keyword itself is a real trigger phrase — narrower than "any imperative sentence disqualifies
  a match" (an ordinary request like *"write unit tests for `src/utils/slugify.py`"*, pressure-tests.md
  #2, is itself an instruction and still matches normally). Without this, a request like *"test the
  payment flow — just handle it, unit test everything, no questions"* had a genuine §2-vs-§3 ordering
  trap: its substantive target ("payment flow") is ambiguous per §3 (integration vs. e2e), but the
  bypass-directive also contains the literal `level-classification.md` keyword phrase "unit test" — a §2
  implementation that scanned the whole request text for a keyword match, rather than the request's
  substantive description, could dispatch straight to `unit-test-creator` without ever reaching §3's
  ask-once gate. New [pressure-tests.md #14](reference/pressure-tests.md) covers this case, contrasted
  directly against #2's ordinary match (`workflow_version` 2.0 → 2.1).

### Added

- `evals/golden/test-writer/injection-ask-gate-not-bypassed.yaml` — golden fixture using exactly this
  request, proving `workflow/classify.md`'s ask-once gate still fires (never dispatches to
  `unit-test-creator`) and that the injected "unit test"/"no questions" text never leaks into the
  clarification question.

### Not changed (scoped out during the repo-wide safe-output rollout survey)

- No `workflow-contract.yaml` — `workflow/inputs.md` → `classify.md` → `delegate.md` is the same three-
  phase sequence for every one of the five levels; the level only changes which skill `delegate.md`'s
  internal lookup table invokes, not which phase files run. That's a data-driven branch inside one
  phase, not the genuine cross-phase branch (different phase files per route) the contract convention
  models.
- No "Safe rendered-output boundary" section — per `SKILL.md § Non-negotiables`, this skill never
  writes or reformats a report of its own; it only relays the dispatched skill's report verbatim. Its
  ask-once clarification question doesn't quote the raw `request` text at all either — per the worked
  example in `examples.md` it only names the fixed-vocabulary candidate levels — so there is no render
  site of this skill's own carrying untrusted content in the first place (verified, not just claimed:
  the golden fixture above asserts the injected text is absent from the rendered question).

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
  pytest, unittest, Jest, Vitest, Mocha, Go `testing`, JUnit 4/5, RSpec/Minitest,
  xUnit/NUnit/MSTest, and `cargo test`; `tests/test_detect_test_framework.py` pytest suite plus fixture
  repos under `tests/fixtures/test-framework-detect/`.
- `reference/{skill-contract,phase-index,lazy-load-index,gate-policy,test-quality-checklist,
  framework-detection,report-format,smoke-test,pressure-tests}.md`.
- Shared framework compliance (prompt-injection, skill-routing, cross-skill-escalation, examples
  conventions, smoke-test conventions).
- New cross-skill escalation rows: test-writer ↔ pr-review (production-bug findings, existing-test-quality
  review), test-writer ↔ loop-task-implementer (production-bug fixes).
