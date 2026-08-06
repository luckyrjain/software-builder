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
3. **Written test file(s)** — path(s), following the detected layout convention.
4. **Verification outcome per target** — `WRITTEN_PASSING` / `WRITTEN_FAILING_PROD_BUG` / `NEEDS_HUMAN` /
   `UNVERIFIED`, never a bare "done."
5. **`TEST_WRITER_REPORT.md`** produced, matching [report-format.md](report-format.md).
6. **Next-step line** at the end of the report.

## Script self-test

```bash
bash test-writer/scripts/detect-test-framework.sh test-writer/tests/fixtures/test-framework-detect/python-pytest
python3 -m pytest test-writer/tests/test_detect_test_framework.py -q
```

Also via `make lint-test-writer`.

## Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Detection returns `NONE_DETECTED` on a repo that clearly has pytest configured | Marker file check missed a valid pyproject.toml table name | Check `scripts/detect-test-framework.sh` against [framework-detection.md](framework-detection.md)'s table |
| Report shows `WRITTEN_PASSING` but the test wasn't actually run | Regression in verify-and-iterate — a test must never be marked passing without running | Re-check `run_tests` handling in [workflow/verify-and-iterate.md](../workflow/verify-and-iterate.md) §1 |
| `max_files_per_run` overflow not listed in the report | Regression in report rendering | Check [workflow/report.md](../workflow/report.md) and [gate-policy.md §7](gate-policy.md#7-maxfilesperrun-reached) |
| Skipped-already-covered count looks too high | Select-targets matching too loosely | Re-check [select-targets.md §1](../workflow/select-targets.md#1-diff-mode) confidence bar |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
