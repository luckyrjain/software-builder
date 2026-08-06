---
inclusion: manual
---

For generating or backfilling integration tests that exercise a real adjacent dependency (write an
integration test for an MR/branch/diff, or backfill integration coverage for a file/module against a real
database, queue, cache, or another internal service), read `integration-test-creator/SKILL.md`. A target
fully testable by mocking everything routes to `unit-test-creator/SKILL.md` instead; a consumer/provider
contract agreement routes to `contract-test-creator/SKILL.md` instead; a full browser user journey routes
to `e2e-test-creator/SKILL.md` instead.

Phase index: `integration-test-creator/reference/phase-index.md`. Reference loads:
`integration-test-creator/reference/lazy-load-index.md`.
Detects the target repo's base test runner *and* its real-dependency orchestration mechanism
(testcontainers, docker-compose, embedded DB) before writing anything — never introduces a second
framework/mechanism or fabricates one for a repo with none, without asking. Never mocks the dependency
under test — that is this skill's entire reason to exist, distinct from unit-test-creator. Never modifies
production code to force a failing test green.
