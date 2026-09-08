# Skill contract — non-negotiable

Load immediately after [SKILL.md](../SKILL.md). These rules override convenience shortcuts. Shared rules
for all four `*-test-creator` skills live in
[test-creation-principles.md](../../docs/skill-framework/shared/test-creation-principles.md) — this file
states only what's different for consumer-driven contract testing.

## Contract

1. **Scope** — write or modify test files (and the pact file(s) a consumer target produces) only. Never
   modify production/application code to make a failing test or verification pass; a failure that traces
   to production code is a finding to report and hand off, not something to silently patch
   ([test-creation-principles.md §3](../../docs/skill-framework/shared/test-creation-principles.md#3-refactor-limits),
   [gate-policy.md §6](gate-policy.md#6-verification-surfaces-a-probable-production-bug)).
2. **`target.role` is required** — never guess `consumer` vs. `provider` from file location or naming.
   HARD STOP at Inputs if absent ([gate-policy.md §1](gate-policy.md#1-missing-or-malformed-target-reporoot-or-role)).
3. **Detect before writing** — always run [workflow/detect-conventions.md](../workflow/detect-conventions.md)
   first. Never introduce a second Pact library alongside one the repo already uses, and never invent one
   for a repo with none, without asking.
4. **Never fabricate an interaction shape** — every request matcher and expected response must trace to
   real, observed usage (an actual call site, an existing client method, or an OpenAPI/GraphQL schema
   file already in the repo). No observed usage means `NEEDS_OBSERVED_INTERACTION`, never a guess
   ([test-creation-principles.md §1](../../docs/skill-framework/shared/test-creation-principles.md#1-test-first-evidence),
   [gate-policy.md §5](gate-policy.md#5-target-has-no-real-observed-interaction-to-derive-its-shape-from)).
5. **Real assertions only** — every test must satisfy
   [reference/test-quality-deltas.md](test-quality-deltas.md) on top of the shared
   [test-quality rules](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules);
   no tautological or always-pass tests.
6. **Gate, don't guess** — HARD STOP / ask per [reference/gate-policy.md](gate-policy.md) rather than
   guessing a Pact library, inventing an interaction shape, or resolving `target.role` on its own.
7. **Verify before claiming** — never report a test as passing without having run it in this session.
   When `run_tests: false` or no execution capability exists, mark every target `UNVERIFIED` explicitly.
8. **A provider verification failure is a finding, not a target to loosen** — never widen a matcher,
   delete an interaction, or otherwise edit a pact file to make a failing verification pass; that hides a
   real break from every consumer relying on it ([gate-policy.md §6](gate-policy.md#6-verification-surfaces-a-probable-production-bug)).
9. **No silent caps** — `max_files_per_run` or `deadline` overflow is always listed in the report by
   name, never dropped quietly.
10. **Never hide a failure** — no `.skip` / `xfail` / `@Disabled` / deleted assertion to force a suite
    green without flagging it in `CONTRACT_TEST_REPORT.md`.
11. **Deliverable** — emit [CONTRACT_TEST_REPORT.md](report-format.md) every run, even for a single-file
    backfill with one target.
12. **Lazy-load** — only the reference file(s) named for the current phase in
    [lazy-load-index.md](lazy-load-index.md); do not bulk-read all of `reference/`.
13. **Escalate, don't absorb** — a caller wanting a real running integration test rather than an interface
    agreement is out of scope here; route to **integration-test-creator**
    ([SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation)).

Routing: [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md).
