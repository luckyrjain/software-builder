# contract-test-creator

**Writes real, running consumer-driven contract tests** (Pact-style) — detects the repo's own Pact
library and broker configuration first, then generates either a **consumer** test (records the
consumer's expectations, produces/updates a pact file) or a **provider verification** test (replays
existing pact files against the real running provider), runs it, and iterates on failures. Two entry
modes: **diff** (test what just changed) and **backfill** (test an existing coverage gap you point it
at).

No MCP, no other skill required to run standalone — pure repository read/write plus the ability to
execute the target repo's own test command (optional; see `run_tests` below).

## What it does

1. **Detects conventions** — scans for a Pact library (pact-js, pact-python, Pact JVM, pact-go, Ruby
   pact) and whether a Pact Broker is configured (env var/CI reference) vs. local-file-only usage. Asks
   once if detection is genuinely ambiguous; asks before writing anything if the repo has no Pact tooling
   at all — it never invents one.
2. **Selects targets** — diff mode: changed consumer call sites or provider routes without matching pact
   test changes already in the diff. Backfill mode: the files/directories you scope it to. Either way,
   capped by `max_files_per_run` with every skipped target listed by name, never silently dropped.
3. **Generates tests** — consumer and provider generation are different code paths (see
   [SKILL.md](SKILL.md)). Every interaction's request/response shape traces to real, observed usage — an
   actual call site, an existing client method, or a schema file already in the repo — never a guess.
4. **Verifies and iterates** — runs the new tests, fixes genuine test bugs, and — critically — **never
   patches production code or loosens a pact file to force a failing verification green**. A provider
   verification failure against a real pact file is reported as a finding, not silently resolved.
5. **Reports** — `CONTRACT_TEST_REPORT.md`: per-target status, any production-bug findings with the exact
   interaction and expected/actual, and a one-line next step.

## `target.role` is required

Every invocation must say `role: consumer` or `role: provider` — the generation logic is completely
different per role, so this skill never infers it from file location or naming. See
[reference/gate-policy.md §1](reference/gate-policy.md#1-missing-or-malformed-target-reporoot-or-role).

## When to use

"Write a Pact contract test for `orders-consumer` calling `orders-provider`", "verify the provider still
satisfies its consumer pacts", "backfill a contract test for `<consumer/provider pair>`." Not for a real
running integration test against a live dependency (**integration-test-creator**) or isolated mocked unit
tests (**unit-test-creator**). Full routing table:
[SKILL.md](SKILL.md#when-to-use-not-to-use).

## Invocation examples

```
target: {mode: diff, source: "MR !123", role: consumer}, repo_root: ./services/orders-consumer
target: {mode: backfill, scope: ["services/orders-provider/"], role: provider}, repo_root: .
```

More scenarios, including a provider-side production-bug finding and a degraded (`run_tests: false`) run:
[examples.md](examples.md).

## What you get

New/modified contract test files (plus a written/updated pact file for a consumer target) matching the
repo's own conventions, plus `CONTRACT_TEST_REPORT.md` — format spec:
[reference/report-format.md](reference/report-format.md).

## Install

```bash
cd software-builder
make install-contract-test-creator
```

## Related skills

- **integration-test-creator** — a real running integration test against a live adjacent dependency;
  contract-test-creator only writes an interface agreement, never a live end-to-end call
- **unit-test-creator** — isolated, fully-mocked unit tests; contract-test-creator's mock-provider setup
  in a consumer test is scoped to the interaction only, never a substitute for a real unit test
- **test-writer** — the thin router that dispatches a level-unspecified test-writing request to this
  skill (or one of its three siblings) when the caller names "contract"/"Pact" explicitly
- **loop-task-implementer** — implements production features/fixes; contract-test-creator hands
  production-bug findings to it rather than fixing them itself

Agent instructions: [SKILL.md](SKILL.md).
