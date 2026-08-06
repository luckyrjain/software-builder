# Smoke test — expected minimal output

Run after install and after any edit to `SKILL.md`, `workflow/`, `reference/`, or `scripts/`.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Fixture

Any small repo with an established test framework and at least one recently changed, untested function
— or use this repo itself: `mysql-to-postgres-sql/scripts/scan-report.sh` has no dedicated test file.

## Invocation

> `target: {mode: backfill, scope: ["mysql-to-postgres-sql/scripts/scan-report.sh"]}`,
> `repo_root: <software-builder clone>`, `run_tests: false`

(`run_tests: false` here because the fixture script isn't itself a unit under a test framework this repo
runs — for a real target repo with pytest/Jest/etc. already configured, omit `run_tests` and let it run.)

## A correct minimal output contains

1. **Detection announced first** — framework name + confidence (or the ambiguity/no-framework gate
   question), before any target is selected.
2. **Target list** — the resolved target(s), tagged `NEW` or a `SKIPPED_*` reason — never silently
   empty with no explanation.
3. **Written test file(s)** — path(s), following the detected layout convention, every external
   dependency mocked.
4. **Verification outcome per target** — `WRITTEN_PASSING` / `WRITTEN_FAILING_PROD_BUG` / `NEEDS_HUMAN` /
   `UNTESTABLE_WITHOUT_FIXTURE` / `UNVERIFIED`, never a bare "done."
5. **`UNIT_TEST_REPORT.md`** produced, matching [report-format.md](report-format.md).
6. **Next-step line** at the end of the report.

## Script self-test

```bash
bash unit-test-creator/scripts/detect-test-framework.sh unit-test-creator/tests/fixtures/test-framework-detect/python-pytest
python3 -m pytest unit-test-creator/tests/test_detect_test_framework.py -q
```

Also via `make lint-unit-test-creator`.

## Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Detection returns `NONE_DETECTED` on a repo that clearly has pytest configured | Marker file check missed a valid pyproject.toml table name | Check `scripts/detect-test-framework.sh` against [framework-detection.md](framework-detection.md)'s table |
| Report shows `WRITTEN_PASSING` but the test wasn't actually run | Regression in verify-and-iterate — a test must never be marked passing without running | Re-check `run_tests` handling in [workflow/verify-and-iterate.md](../workflow/verify-and-iterate.md) §1 |
| `max_files_per_run` overflow not listed in the report | Regression in report rendering | Check [workflow/report.md](../workflow/report.md) and [gate-policy.md §7](gate-policy.md#7-maxfilesperrun-reached) |
| A generated "unit" test reaches a real network/DB call | Regression in generate-tests mocking discipline | Re-check [test-quality-deltas.md](test-quality-deltas.md) and [workflow/generate-tests.md](../workflow/generate-tests.md) §1–2 |
| A target that needs a real dependency was force-mocked instead of tagged `UNTESTABLE_WITHOUT_FIXTURE` | Gate §5 skipped | Re-check [gate-policy.md §5](gate-policy.md#5-target-cant-be-isolated-from-a-real-dependency) |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
