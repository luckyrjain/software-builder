# Smoke test — expected minimal output

Run after install and after any edit to `SKILL.md`, `workflow/`, `reference/`, or `scripts/`.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Fixture

Any small repo with an established Postman collection and at least one request — or use the fixtures under
`tests/fixtures/postman-detect/` in this skill's own directory.

## Invocation

> `target: {mode: backfill, scope: ["POST /api/orders"]}`, `repo_root: <fixture repo clone>`,
> `run_tests: false`

(`run_tests: false` here because the fixture isn't wired to a real running API instance in this session —
for a real target repo with a reachable API, omit `run_tests` and let it run.)

## A correct minimal output contains

1. **Detection announced first** — resolved collection path + confidence, and `Newman: yes|no` (or the
   ambiguous-collection/no-tooling gate question), before any target is selected.
2. **Target list** — the resolved target(s), tagged `NEW` or a `SKIPPED_*` reason — never silently empty
   with no explanation.
3. **Written request(s)** — collection folder/request name(s), following the detected layout convention.
4. **Verification outcome per target** — `WRITTEN_PASSING` / `WRITTEN_FAILING_PROD_BUG` / `NEEDS_HUMAN` /
   `NEEDS_OBSERVED_ENDPOINT` / `NEEDS_API_ENV` / `UNVERIFIED`, never a bare "done."
5. **`API_TEST_REPORT.md`** produced, matching [report-format.md](report-format.md).
6. **Next-step line** at the end of the report.

## Script self-test

```bash
bash api-test-creator/scripts/detect-postman-tooling.sh api-test-creator/tests/fixtures/postman-detect/single-collection
python3 -m pytest api-test-creator/tests/test_detect_postman_tooling.py -q
```

Also via `make lint-api-test-creator`.

## Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Detection returns `NONE_DETECTED` on a repo that clearly has a collection file | Marker check missed a valid `*.postman_collection.json` path (nested or under an unusual directory) | Check `scripts/detect-postman-tooling.sh` against [framework-detection.md](framework-detection.md)'s marker table |
| Skill proceeds without asking on two collection files with no clear canonical one | Regression in the ambiguity gate | Re-check [workflow/detect-conventions.md §2](../workflow/detect-conventions.md#2-ambiguous-canonical-collection-ask-once-never-guess) |
| Generated request has an invented request/response body | Regression in the observed-usage gate | Re-check [workflow/generate-tests.md §1](../workflow/generate-tests.md#1-derive-the-requestresponse-shape-from-real-observed-usage-only) |
| A run against a genuinely broken endpoint was "fixed" by loosening the assertion | Regression in the never-loosen-an-assertion rule | Re-check [gate-policy.md §7](gate-policy.md#7-verification-surfaces-a-probable-production-bug) |
| `max_files_per_run` overflow not listed in the report | Regression in report rendering | Check [workflow/report.md](../workflow/report.md) and [gate-policy.md §8](gate-policy.md#8-maxfilesperrun-reached) |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
