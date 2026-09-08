# Smoke test — expected minimal output

Run after install and after any edit to `SKILL.md`, `workflow/`, `reference/`, or `scripts/`.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Fixture

Any small repo with an established base test runner, a real-dependency orchestration mechanism
(testcontainers or docker-compose), and at least one recently changed, untested seam — or use the bundled
fixture: `tests/fixtures/integration-detect/testcontainers-python/`.

## Invocation

> `target: {mode: backfill, scope: ["src/db/repository.py"]}`,
> `repo_root: <a repo with pytest + testcontainers>`, `run_tests: false`

(`run_tests: false` here for a quick smoke pass without actually spinning up a container; for a real
target repo with Docker reachable, omit `run_tests` and let it run against the real dependency.)

## A correct minimal output contains

1. **Detection announced first, both dimensions** — base runner name + confidence, orchestration
   mechanism + confidence (or the ambiguity/no-base-runner gate question), before any target is selected.
2. **Target list** — the resolved seam(s), tagged `NEW` or a `SKIPPED_*` reason — never silently empty
   with no explanation.
3. **Written test file(s)** — path(s), following the detected layout convention, asserting against the
   real dependency, never a mock of it.
4. **Verification outcome per target** — `WRITTEN_PASSING` / `WRITTEN_FAILING_PROD_BUG` / `NEEDS_HUMAN` /
   `NEEDS_INTEGRATION_ENV` / `UNVERIFIED`, never a bare "done."
5. **`INTEGRATION_TEST_REPORT.md`** produced, matching [report-format.md](report-format.md).
6. **Next-step line** at the end of the report.

## Script self-test

```bash
bash integration-test-creator/scripts/detect-integration-setup.sh integration-test-creator/tests/fixtures/integration-detect/testcontainers-python
python3 -m pytest integration-test-creator/tests/test_detect_integration_setup.py -q
```

Also via `make lint-integration-test-creator`.

## Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Detection returns `NONE_DETECTED` on a repo that clearly has pytest configured | Marker file check missed a valid pyproject.toml table name | Check `scripts/detect-integration-setup.sh` against [framework-detection.md](framework-detection.md)'s table |
| `ORCHESTRATION: none` on a repo that clearly uses testcontainers/docker-compose | Marker check missed a nonstandard manifest location or compose filename | Check [framework-detection.md §2](framework-detection.md#2-real-dependency-orchestration-mechanism) |
| Report shows `WRITTEN_PASSING` but the test wasn't actually run | Regression in verify-and-iterate — a test must never be marked passing without running against the real dependency | Re-check `run_tests`/orchestration handling in [workflow/verify-and-iterate.md](../workflow/verify-and-iterate.md) §§1–3 |
| A generated test mocks the dependency under test | Regression in generate-tests — never allowed regardless of orchestration availability | Re-check [workflow/generate-tests.md §3](../workflow/generate-tests.md#3-never-mock-the-dependency-under-test) and [test-quality-deltas.md](test-quality-deltas.md) |
| `max_files_per_run` overflow not listed in the report | Regression in report rendering | Check [workflow/report.md](../workflow/report.md) and [gate-policy.md §7](gate-policy.md#7-maxfilesperrun-reached) |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
