# Skill contract — non-negotiable

Load immediately after [SKILL.md](../SKILL.md). These rules override convenience shortcuts. Shared rules
for the whole test-creation family live in
[test-creation-principles.md](../../docs/skill-framework/shared/test-creation-principles.md) — this file
states only what's different for black-box Postman/Newman API testing.

## Contract

1. **Scope** — write or modify the Postman collection (and its environment file, when a new variable is
   needed) only. Never modify production/application code to make a failing assertion pass; a failure
   that traces to production code is a finding to report and hand off, not something to silently patch
   ([test-creation-principles.md §3](../../docs/skill-framework/shared/test-creation-principles.md#3-refactor-limits),
   [gate-policy.md §7](gate-policy.md#7-verification-surfaces-a-probable-production-bug)).
2. **Detect before writing** — always run [workflow/detect-conventions.md](../workflow/detect-conventions.md)
   first. Never create a second collection alongside one the repo already uses, and never invent one for a
   repo with none, without asking.
3. **Never fabricate a request/response shape** — every request and its expected response must trace to
   real, observed usage (the actual route-handler code, an OpenAPI/Swagger spec already in the repo, or
   `API_CATALOG.md` as corroborating evidence only). No observed usage means `NEEDS_OBSERVED_ENDPOINT`,
   never a guess ([test-creation-principles.md §1](../../docs/skill-framework/shared/test-creation-principles.md#1-test-first-evidence),
   [gate-policy.md §5](gate-policy.md#5-target-has-no-real-observed-endpoint-to-derive-its-shape-from)).
4. **Requires a reachable running API instance** — a meaningful assertion can only be written and run
   against a real, currently-reachable API (locally started, staging, or a preview deployment). Without
   one, gate the affected targets `NEEDS_API_ENV` rather than fabricating what a response would look like
   ([gate-policy.md §6](gate-policy.md#6-no-reachable-api-instance)).
5. **Real assertions only** — every request must satisfy
   [reference/test-quality-deltas.md](test-quality-deltas.md) on top of the shared
   [test-quality rules](../../docs/skill-framework/shared/test-creation-principles.md#2-test-quality-rules);
   status code alone is never sufficient.
6. **Gate, don't guess** — HARD STOP / ask per [reference/gate-policy.md](gate-policy.md) rather than
   guessing which collection is canonical, inventing a request/response shape, or defaulting to a
   greenfield collection layout.
7. **Verify before claiming** — never report a request as passing without having run it via `newman` in
   this session. When `run_tests: false` or no reachable API instance exists, mark every affected target
   `UNVERIFIED`/`NEEDS_API_ENV` explicitly.
8. **A verification failure is a finding, not a target to loosen** — never widen a schema check, drop a
   status-code assertion, or otherwise weaken a `pm.test()` to make a failing run pass; that hides a real
   break from every real caller of the endpoint ([gate-policy.md §7](gate-policy.md#7-verification-surfaces-a-probable-production-bug)).
9. **No silent caps** — `max_files_per_run` or `deadline` overflow is always listed in the report by name,
   never dropped quietly.
10. **Never hide a failure** — no skipped/disabled request, or deleted assertion, to force a collection run
    green without flagging it in `API_TEST_REPORT.md`.
11. **Deliverable** — emit [API_TEST_REPORT.md](report-format.md) every run, even for a single-endpoint
    backfill.
12. **Lazy-load** — only the reference file(s) named for the current phase in
    [lazy-load-index.md](lazy-load-index.md); do not bulk-read all of `reference/`.
13. **Escalate, don't absorb** — a caller wanting an in-process mocked test, a real-dependency-seam test, a
    consumer-driven contract agreement, or a full browser journey is out of scope here; route to
    **unit-test-creator**, **integration-test-creator**, **contract-test-creator**, or **e2e-test-creator**
    respectively ([SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation)).

Routing: [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md).
