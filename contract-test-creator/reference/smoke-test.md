# Smoke test — expected minimal output

Run after install and after any edit to `SKILL.md`, `workflow/`, `reference/`, or `scripts/`.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Fixture

Any small repo with an established Pact library and at least one consumer/provider interaction — or use
the fixtures under `tests/fixtures/pact-detect/` in this skill's own directory.

## Invocation

> `target: {mode: backfill, scope: ["services/orders-consumer/src/clients/ordersClient.ts"], role: consumer}`,
> `repo_root: <fixture repo clone>`, `run_tests: false`

(`run_tests: false` here because the fixture isn't wired to a real Pact Broker in this session — for a
real target repo with Pact tooling already configured, omit `run_tests` and let it run.)

## A correct minimal output contains

1. **Detection announced first** — Pact library name + confidence, and `BROKER: yes|no` (or the
   ambiguity/no-tooling gate question), before any target is selected.
2. **Role confirmed** — `consumer` or `provider`, never inferred silently.
3. **Target list** — the resolved target(s), tagged `NEW` or a `SKIPPED_*` reason — never silently empty
   with no explanation.
4. **Written test file(s)** — path(s), following the detected layout convention, plus a written/updated
   pact file for a consumer target.
5. **Verification outcome per target** — `WRITTEN_PASSING` / `WRITTEN_FAILING_PROD_BUG` / `NEEDS_HUMAN` /
   `NEEDS_OBSERVED_INTERACTION` / `UNVERIFIED`, never a bare "done."
6. **`CONTRACT_TEST_REPORT.md`** produced, matching [report-format.md](report-format.md).
7. **Next-step line** at the end of the report.

## Script self-test

```bash
bash contract-test-creator/scripts/detect-pact-tooling.sh contract-test-creator/tests/fixtures/pact-detect/python-provider-local
python3 -m pytest contract-test-creator/tests/test_detect_pact_tooling.py -q
```

Also via `make lint-contract-test-creator`.

## Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Detection returns `NONE_DETECTED` on a repo that clearly has pact-python configured | Marker check missed a valid `requirements*.txt` entry or `pyproject.toml` table | Check `scripts/detect-pact-tooling.sh` against [framework-detection.md](framework-detection.md)'s table |
| Skill proceeds without ever asking for `role` | Regression in Inputs — `role` must HARD STOP if absent | Re-check [workflow/inputs.md](../workflow/inputs.md) §"Required" |
| Generated consumer test has an invented request/response body | Regression in the observed-usage gate | Re-check [workflow/generate-tests.md §3](../workflow/generate-tests.md#3-derive-the-interaction-shape-from-real-observed-usage-only) |
| Provider verification failure was "fixed" by widening a pact matcher | Regression in the never-loosen-a-contract rule | Re-check [gate-policy.md §6](gate-policy.md#6-verification-surfaces-a-probable-production-bug) |
| `max_files_per_run` overflow not listed in the report | Regression in report rendering | Check [workflow/report.md](../workflow/report.md) and [gate-policy.md §7](gate-policy.md#7-maxfilesperrun-reached) |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
