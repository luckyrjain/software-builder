---
inclusion: manual
---

For generating consumer-driven contract (Pact-style) tests — either a consumer test (records
expectations, produces a pact file) or a provider verification test (replays existing pact files against
the real provider) — read `contract-test-creator/SKILL.md`. `target.role` (`consumer` or `provider`) is
required — always ask if it isn't stated, never infer it from file location or naming. A request for a
real running integration test against a live dependency routes to `integration-test-creator/SKILL.md`
instead; isolated mocked unit tests route to `unit-test-creator/SKILL.md` instead.

Phase index: `contract-test-creator/reference/phase-index.md`. Reference loads:
`contract-test-creator/reference/lazy-load-index.md`.
Detects the target repo's own Pact tooling and broker configuration before writing anything — never
introduces a second Pact library or fabricates one for a repo with none, without asking. Never fabricates
an interaction's request/response shape from a guess — it must trace to real, observed usage. Never
modifies production code, or loosens a pact file, to force a failing test/verification green.
