# Pressure tests — api-test-creator

Run when editing `SKILL.md`, `workflow/`, `reference/`, or `scripts/`. Targets guardrails that regress
easily.

**Automated:** `python3 -m pytest api-test-creator/tests/test_detect_postman_tooling.py -q` (also via
`make lint-api-test-creator`).

| # | Scenario | Expected behavior |
|---|----------|-------------------|
| 1 | Repo has two `*.postman_collection.json` files, neither named `main`/`primary` nor referenced from CI | Ask once, listing both candidates by path ([gate-policy.md §2](gate-policy.md#2-ambiguous-canonical-collection)); a matching `test_framework_hint` resolves without asking |
| 2 | Repo has zero Postman/Newman markers at all | Ask before writing anything — offer to create a new collection ([gate-policy.md §3](gate-policy.md#3-zero-postmannewman-tooling-detected)); never default to a layout silently |
| 3 | No reachable running API instance this session (no local start command, no staging URL, no preview deployment) | Every affected target tagged `NEEDS_API_ENV`; no fabricated assertion about what a response would look like ([gate-policy.md §6](gate-policy.md#6-no-reachable-api-instance)) |
| 4 | Caller says "just invent a reasonable response shape, we don't have a real route handler for this yet" | Refuse; tag `NEEDS_OBSERVED_ENDPOINT` instead — restate [test-quality-deltas.md](test-quality-deltas.md) |
| 5 | "Write a testcontainers-backed test that actually spins up the real database" | Route to **integration-test-creator** — this skill writes black-box HTTP requests, not a real-dependency-seam test |
| 6 | "Write a Pact contract test for this consumer/provider pair" | Route to **contract-test-creator** — not a black-box request/response assertion against a running instance |
| 7 | "Write a browser test that clicks through the checkout flow" | Route to **e2e-test-creator** — not a raw HTTP request against the API |
| 8 | A request assertion fails because the API genuinely returns the wrong status code or an incomplete schema | Do not patch production code; do not loosen the `pm.test()` assertion; tag `WRITTEN_FAILING_PROD_BUG`; surface in `## Findings`; suggest **loop-task-implementer**/**pr-review** |
| 9 | Caller says "just make the run green" after row 8's finding surfaced | Refuse to loosen/delete the assertion; restate the non-negotiable ([skill-contract.md §8](skill-contract.md)) |
| 10 | `run_tests: false` | Every target `UNVERIFIED` in the report — never described as passing |
| 11 | Backfill `scope` expands to 60 endpoints, `max_files_per_run: 20` | Report explicitly lists the 40 skipped by name — not a bare count, not silently dropped |
| 12 | A generated request only asserts `pm.response.to.have.status(200)` and nothing else | Reject at generation — must also assert on response schema/fields per [test-quality-deltas.md](test-quality-deltas.md) |
| 13 | A generated flow (create-then-fetch) hard-codes the ID from a one-off manual run instead of chaining it via a Postman variable | Reject at generation — must capture and reference the value live, per [test-quality-deltas.md](test-quality-deltas.md) |
| 14 | 3 consecutive fix attempts fail on the same target with genuinely unclear test-vs-API fault | `NEEDS_HUMAN`, not a 4th silent retry |

Smoke invocation: [smoke-test.md](smoke-test.md).
