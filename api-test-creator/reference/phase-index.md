# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `target`, `repo_root`, `run_tests`, `max_files_per_run`, `deadline`, `session_token_budget`, `output_dir` |
| **Detect conventions** | [workflow/detect-conventions.md](../workflow/detect-conventions.md) | `collection_path`, `newman_present`, `environment_files`, `detection_confidence` |
| **Select targets** | [workflow/select-targets.md](../workflow/select-targets.md) | `target_list` (each item tagged `NEW` / `SKIPPED_ALREADY_COVERED` / `SKIPPED_MAX_FILES`) |
| **Generate tests** | [workflow/generate-tests.md](../workflow/generate-tests.md) | `test_files_written` (requests + `pm.test()` assertions added to the collection) |
| **Verify & iterate** | [workflow/verify-and-iterate.md](../workflow/verify-and-iterate.md) | `verify_result` (per-target pass/fail/needs-observed-endpoint/needs-api-env/needs-human) |
| **Report** | [workflow/report.md](../workflow/report.md) | `API_TEST_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `target: {mode: diff, source: "MR !123"}` | Inputs → Detect → Select → Generate → Verify → Report |
| `target: {mode: backfill, scope: ["POST /api/orders", ...]}` | Inputs → Detect → Select (caller scope, capped) → Generate → Verify → Report |
| Repo has 2+ `*.postman_collection.json` with no canonical one, no hint | Detect gate asks once — no target selected yet |
| A target has no real observed endpoint to derive its shape from | Generate tests tags `NEEDS_OBSERVED_ENDPOINT`; never fabricates one |
| No reachable running API instance this session | Verify & iterate tags every target `NEEDS_API_ENV`; never runs a guessed assertion |
| A run surfaces the wrong status code/schema/header | Verify & iterate reports the finding; does not proceed to "passing" for that target, never loosens the assertion |
