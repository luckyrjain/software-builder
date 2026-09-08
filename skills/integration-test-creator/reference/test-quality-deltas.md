# Test quality — integration-specific deltas

The full checklist every test in this family must satisfy lives in
[test-creation-principles.md §2](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules)
— load that before [workflow/generate-tests.md](../workflow/generate-tests.md). This file adds only what's
different at the integration level; it does not repeat the shared checklist.

## Required, on top of the shared checklist

| Rule | Why |
|------|-----|
| The seam under test always talks to a **real** instance of its adjacent dependency | The entire reason this skill exists separately from unit-test-creator — a mocked dependency makes it a unit test wearing an integration test's directory |
| Deterministic despite being slower/less isolated than a unit test | Real infra is inherently slower and has more moving parts than an in-process mock — that's acceptable; flakiness is not. Use the orchestration tool's own readiness-wait/health-check mechanism (testcontainers' wait strategies, docker-compose healthchecks) — never a blind `sleep`-and-hope |
| Torn down after the run | A container/compose stack this phase started is torn down before the phase ends, via the tool's own lifecycle — never left running as a side effect |
| Auxiliary dependencies (a third system the seam under test doesn't touch) may still use the repo's existing mock/stub convention | Only the dependency **under test** is exempt from mocking — a payments-to-Postgres test may still stub an unrelated notifications call if the repo already does so |

## Forbidden, on top of the shared checklist

| Anti-pattern | Why wrong |
|--------------|-----------|
| Mocking the dependency under test to make a target "testable" when no orchestration mechanism was detected | Secretly turns the integration test into a unit test without saying so — the correct response is `NEEDS_INTEGRATION_ENV` ([gate-policy.md §5](gate-policy.md#5-zero-orchestration-mechanism-detected)), not a silent substitution |
| Using `sleep N` to wait for a container to become ready | Flaky by construction — use the orchestration tool's own wait strategy/healthcheck |
| Writing the test against an embedded/in-memory substitute (e.g. SQLite standing in for Postgres) when the production dependency is a different engine, without the repo already treating that substitute as its established integration convention | The substitute's behavior can diverge from the real dependency's (constraint semantics, type coercion, transaction isolation) — only acceptable when it *is* the repo's own documented integration-test convention, not an ad hoc shortcut this run invents |
| Asserting only that a call to the dependency "didn't throw" | Misses the actual round-trip behavior — assert on the data actually persisted/consumed/returned by the real dependency, not just the absence of an exception |
