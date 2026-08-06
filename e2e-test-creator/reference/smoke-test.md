# Smoke test — expected minimal output

Run after install and after any edit to `SKILL.md`, `workflow/`, `reference/`, or `scripts/`.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Fixture

Any small repo with browser e2e tooling already configured and at least one route/page a journey can be
named against — or use the detection fixtures this skill ships:
`e2e-test-creator/tests/fixtures/e2e-detect/playwright-repo`.

## Invocation

> `target: {mode: backfill, journeys: [{name: "home page loads", start_route: "/"}]}`,
> `repo_root: <software-builder clone>`, `run_tests: false`

(`run_tests: false` here because the detection fixture isn't a real running app this session can reach —
for a real target repo with a reachable instance, omit `run_tests` and let it run for real; without a
reachable instance, expect `NEEDS_BROWSER_ENV` instead of `UNVERIFIED` per
[gate-policy.md §5](gate-policy.md#5-no-reachable-app-instance).)

## A correct minimal output contains

1. **Detected browser tooling announced first** — framework name + confidence (or the ambiguity/no-
   tooling gate question), before any journey is selected.
2. **Journey list** — the resolved journey(s), tagged `NEW` or a `SKIPPED_*` reason — never silently
   empty with no explanation.
3. **Written spec file(s)** — path(s), following the detected layout convention.
4. **Verification outcome per journey** — `WRITTEN_PASSING` / `WRITTEN_FAILING_PROD_BUG` / `NEEDS_HUMAN` /
   `NEEDS_BROWSER_ENV` / `UNVERIFIED`, never a bare "done."
5. **`E2E_TEST_REPORT.md`** produced, matching [report-format.md](report-format.md).
6. **Next-step line** at the end of the report.

## Script self-test

```bash
bash e2e-test-creator/scripts/detect-e2e-tooling.sh e2e-test-creator/tests/fixtures/e2e-detect/playwright-repo
python3 -m pytest e2e-test-creator/tests/test_detect_e2e_tooling.py -q
```

Also via `make lint-e2e-test-creator`.

## Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Detection returns `NONE_DETECTED` on a repo that clearly has Playwright/Cypress configured | Marker file check missed a nonstandard config file location | Check `scripts/detect-e2e-tooling.sh` against [framework-detection.md](framework-detection.md)'s table |
| Report shows `WRITTEN_PASSING` but the test wasn't actually run | Regression in verify-and-iterate — a test must never be marked passing without running | Re-check `run_tests` handling in [workflow/verify-and-iterate.md](../workflow/verify-and-iterate.md) §1 |
| Every journey comes back `NEEDS_BROWSER_ENV` even though an app instance was supplied | Generate tests didn't actually check the supplied instance before gating | Re-check [workflow/generate-tests.md §1](../workflow/generate-tests.md#1-no-reachable-app-instance-check-before-writing-a-single-assertion) |
| `max_files_per_run` overflow not listed in the report | Regression in report rendering | Check [workflow/report.md](../workflow/report.md) and [gate-policy.md §7](gate-policy.md#7-maxfilesperrun-reached) |
| Generated selectors don't match the repo's own convention | Detect-conventions didn't read existing specs before Generate tests ran | Re-check [workflow/detect-conventions.md §4](../workflow/detect-conventions.md#4-layout-and-selector-convention) |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
