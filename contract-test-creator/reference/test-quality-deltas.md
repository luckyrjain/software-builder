# Test quality deltas — contract tests

Every rule in the shared
[test-creation-principles.md §2](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules)
applies unchanged. This file adds only what's different for a consumer-driven contract test — load this
before [workflow/generate-tests.md](../workflow/generate-tests.md); it does not restate the shared
checklist.

## Additional required rules

| Rule | Why |
|------|-----|
| The interaction's request matcher and expected response shape trace to real, observed usage — an actual call site, an existing client method, or a schema file already in the repo | The shared "test-first evidence" principle's contract-specific instance: a guessed shape is a contract with nothing real behind it — see [gate-policy.md §5](gate-policy.md#5-target-has-no-real-observed-interaction-to-derive-its-shape-from) |
| A **consumer** test asserts on the consumer's *own* handling of the response — not merely that a pact file was written | The pact file is a byproduct of a real assertion on the consumer's parsing/branching logic, never the only thing under test |
| A **provider verification** test verifies the provider against *every* pact file for that provider currently in scope, not a hand-picked subset | Skipping an inconvenient consumer's pact silently narrows the guarantee the verification is supposed to give |
| Matchers (type/regex/array-like matchers, not literal value equality) are used exactly as the repo's existing pact tests already use them — never introduced as a stricter or looser convention per file | Consistency keeps the contract's flexibility predictable across the whole pact file |

## Additional forbidden

| Anti-pattern | Why wrong |
|--------------|-----------|
| Inventing a plausible-looking request/response body because no real call site or schema was found | This is exactly the case [gate-policy.md §5](gate-policy.md#5-target-has-no-real-observed-interaction-to-derive-its-shape-from) exists to catch — tag `NEEDS_OBSERVED_INTERACTION` instead |
| Widening a matcher or deleting an interaction from an existing pact file to make a failing provider verification pass | Hides a real consumer-breaking regression from every consumer that relies on it — see [gate-policy.md §6](gate-policy.md#6-verification-surfaces-a-probable-production-bug) |
| A provider verification that only checks HTTP status code, ignoring the pact file's body/header matchers | Passes trivially and verifies nothing about the actual contract |
| Publishing/updating a pact file to a broker without the run that produced it actually having passed | A pact file only means something if it reflects a real, currently-passing consumer expectation |
