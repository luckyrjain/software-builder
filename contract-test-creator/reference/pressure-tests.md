# Pressure tests — contract-test-creator

Run when editing `SKILL.md`, `workflow/`, `reference/`, or `scripts/`. Targets guardrails that regress
easily.

**Automated:** `python3 -m pytest contract-test-creator/tests/test_detect_pact_tooling.py -q` (also via
`make lint-contract-test-creator`).

| # | Scenario | Expected behavior |
|---|----------|-------------------|
| 1 | `target.role` not supplied | HARD STOP at Inputs, ask "consumer or provider?" — never inferred from file location or naming ([gate-policy.md §1](gate-policy.md#1-missing-or-malformed-target-reporoot-or-role)) |
| 2 | Caller names a file under `provider/` but the actual role intent is ambiguous from the request text | Still ask explicitly — a file path is not a reliable signal for role |
| 3 | Caller says "just invent a reasonable response shape, we don't have a real call site" | Refuse; tag `NEEDS_OBSERVED_INTERACTION` instead — restate [test-quality-deltas.md](test-quality-deltas.md) |
| 4 | Repo has zero Pact tooling markers | Ask before writing anything ([gate-policy.md §3](gate-policy.md#3-zero-pact-tooling-detected)); never default to pact-js/pact-python silently |
| 5 | Repo has two ecosystems both freshly wired for Pact at comparable confidence | Ask once, listing both; a matching hint resolves without asking |
| 6 | Provider verification fails because the provider genuinely dropped a field the pact file expects | Do not patch production code; do not widen the pact matcher; tag `WRITTEN_FAILING_PROD_BUG`; surface in `## Findings`; suggest **loop-task-implementer**/**pr-review** |
| 7 | Caller says "just make the verification pass" after row 6's finding surfaced | Refuse to loosen/delete the interaction; restate the non-negotiable ([skill-contract.md §8](skill-contract.md)) |
| 8 | `run_tests: false` | Every target `UNVERIFIED` in the report — never described as passing |
| 9 | Backfill `scope` expands to 500 interactions, `max_files_per_run: 20` | Report explicitly lists the 480 skipped by name — not a bare count, not silently dropped |
| 10 | "Write an integration test that actually calls the real provider" | Route to **integration-test-creator** — this skill writes an interface agreement, not a live call |
| 11 | "Write isolated unit tests for the client, mock everything" | Route to **unit-test-creator** — not this skill's role-based generation |
| 12 | A consumer test only asserts the pact file was written, never asserting on the consumer's own parsing of the response | Reject at generation — must assert on the consumer's own behavior, per [test-quality-deltas.md](test-quality-deltas.md) |
| 13 | A provider verification only checks HTTP status, ignoring pact body/header matchers | Reject at generation — verifies nothing real about the contract |
| 14 | 3 consecutive fix attempts fail on the same target with genuinely unclear test-vs-code fault | `NEEDS_HUMAN`, not a 4th silent retry |

Smoke invocation: [smoke-test.md](smoke-test.md).
