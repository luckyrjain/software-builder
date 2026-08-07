---
workflow_version: 1.0
phase: generate_tests
produces:
  - test_files_written
consumes:
  - target_list
  - pact_library
  - broker_configured
---

# Generate tests

For every `NEW` item in `target_list`, write tests that satisfy
[reference/test-quality-deltas.md](../reference/test-quality-deltas.md) (on top of the shared
[test-quality rules](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules))
in full — this phase does not restate those checklists, it enforces them. Consumer and provider
generation are **different code paths**; §1/§2 below are not interchangeable steps.

## 1. Consumer-side generation (`target.role: consumer`)

For each interaction:

1. Locate the real request-building code — the exact call site (HTTP client call, generated API-client
   method invocation) that produces this request in the consumer's own source.
2. Write a test that configures the mock provider with the request matcher and expected response shape
   derived from that real call site (see §3 — never fabricated), exercises the consumer's own code that
   makes the call, and **asserts on the consumer's own handling of the response** — not merely that a
   pact interaction was registered.
3. Running the test produces or updates a pact file (local `pacts/` directory, or published to a broker
   per §5) — this is a byproduct of the real assertion in step 2, not a separate deliverable to fabricate
   by hand.

## 2. Provider-side generation (`target.role: provider`)

For each interaction (or for the provider as a whole, when backfilling verification coverage):

1. Resolve the pact file(s) to verify against — every pact file this provider currently has, from the
   local `pacts/` directory or fetched from the Pact Broker (per §5), never a hand-picked subset (see
   [test-quality-deltas.md](../reference/test-quality-deltas.md)).
2. Write a provider verification test using the Pact library's own verifier against the **real running
   provider** (started per the repo's own existing test-setup convention) — this is not a mock; it exists
   specifically to catch the provider silently diverging from what its consumers actually expect.
3. The test must replay every interaction in scope, checking the full matcher set (status, headers, body
   shape) the pact file defines — never status-code-only.

## 3. Derive the interaction shape from real, observed usage only

This is this skill's specific instance of the shared test-first-evidence principle
([test-creation-principles.md §1](../../docs/skill-framework/shared/test-creation-principles.md#1-test-first-evidence)).
An interaction's request matcher and expected response shape must trace to one of:

- The consumer's actual request-building code (a real call site with real headers/body/params).
- An existing API client method's real, observed usage elsewhere in the codebase.
- An OpenAPI/GraphQL schema file already present in the repo, when the repo maintains one for this
  provider.

If none of these exist for a target, **do not invent a plausible-looking payload**. Tag the target
`NEEDS_OBSERVED_INTERACTION` with a one-line reason (what was checked and found missing) instead
([gate-policy.md §5](../reference/gate-policy.md#5-target-has-no-real-observed-interaction-to-derive-its-shape-from)).
A caller asking to "just invent a reasonable response shape" does not change this — see
[pressure-tests.md](../reference/pressure-tests.md) row 3.

## 4. Reuse, don't reinvent

Use the matcher helpers, mock-provider setup, and shared pact fixtures `detect-conventions` found already
in use for this repo. Introduce a new helper only when nothing existing covers the need, and place it
where the repo's own convention puts shared pact test utilities.

## 5. Broker vs. local pact source

When `broker_configured: yes`, write the provider verification test to fetch pacts from the broker (using
the CI invocation pattern Detect conventions noted) and, for a consumer target, publish the produced pact
file the same way the repo's existing CI does. When `broker_configured: no`, read/write the local
`pacts/` directory directly instead. Never introduce a broker dependency the repo doesn't already have
configured, and never silently switch a broker-configured repo to local-file-only.

## 6. Never touch production code here

This phase writes and edits test files (and pact files) only. If writing a test surfaces what looks like
a production bug, do not "fix" it inline to make the test pass — carry it forward to
[verify-and-iterate.md](verify-and-iterate.md), which is where that finding gets surfaced rather than
silently resolved.
