# Changelog — api-test-creator

All notable changes to the api-test-creator skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-06

### Added

- Initial skill release — generates black-box API test suites (Postman collections, run via Newman)
  against a real, reachable running API instance for a target repository.
- `workflow/inputs.md` — `target` (`diff` or `backfill` mode, `scope` as endpoint descriptors or file/dir
  paths), `repo_root`, `run_tests`, `max_files_per_run`, `deadline`, `session_token_budget`, `output_dir`
  parsing; HARD STOP on missing required fields.
- `workflow/detect-conventions.md` — runs `scripts/detect-postman-tooling.sh`; ask-once gate when 2+
  collection files exist with no clear canonical one, ask-before-writing gate on zero detected tooling.
- `workflow/select-targets.md` — diff-mode changed-endpoint selection, backfill-mode endpoint-descriptor
  and file/dir expansion, generated/vendored-path exclusions, optional domain-comprehension prioritization
  via `API_CATALOG.md`, `max_files_per_run` cap with explicit overflow reporting.
- `workflow/generate-tests.md` — request/response shape derived only from real, observed usage (the
  route-handler source, an OpenAPI/Swagger spec, or `API_CATALOG.md` as corroborating evidence only), never
  a guess; `NEEDS_OBSERVED_ENDPOINT` gate when none exists; `pm.test()` assertions on status/schema/
  headers; request chaining via Postman variables/environment for flows like create-then-fetch.
- `workflow/verify-and-iterate.md` — runs the collection via `newman` against a reachable API instance,
  distinguishes a test bug (fix and retry, capped at 3 attempts) from a probable production bug (wrong
  status/schema/header — never resolved by loosening the assertion); `NEEDS_API_ENV` gate when no reachable
  API instance exists this session.
- `workflow/report.md` — `API_TEST_REPORT.md` rendering rules; collection/newman context always shown in
  the header; never upgrades a status; always surfaces production-bug findings plainly.
- `scripts/detect-postman-tooling.sh` + `scripts/postman-markers.sh` — `*.postman_collection.json` and
  `newman` dependency detection, plus canonical-collection resolution (hint, `main`/`primary` naming
  convention, CI reference, then ask) when 2+ collection files exist; `tests/test_detect_postman_tooling.py`
  pytest suite plus fixture repos under `tests/fixtures/postman-detect/`.
- `reference/{skill-contract,phase-index,lazy-load-index,gate-policy,test-quality-deltas,
  framework-detection,report-format,smoke-test,pressure-tests}.md` — `skill-contract.md` and
  `test-quality-deltas.md` link the shared `docs/skill-framework/shared/test-creation-principles.md` for
  rules common to the whole `*-test-creator` family, stating only API-specific deltas.
  `lazy-load-index.md` and `workflow/select-targets.md` also link the shared
  `docs/skill-framework/shared/domain-comprehension-integration.md` for the optional `API_CATALOG.md`
  enrichment step.
- Shared framework compliance (prompt-injection, skill-routing, cross-skill-escalation, examples
  conventions, smoke-test conventions).
- Cross-skill escalation rows: api-test-creator ↔ unit-test-creator (in-process mocked test vs. black-box
  HTTP call), api-test-creator ↔ integration-test-creator (real-dependency-seam test vs. black-box HTTP
  call), api-test-creator ↔ contract-test-creator (interface agreement vs. live black-box assertion),
  api-test-creator ↔ e2e-test-creator (browser journey vs. raw HTTP request), api-test-creator ↔
  loop-task-implementer/pr-review (production-bug findings).
