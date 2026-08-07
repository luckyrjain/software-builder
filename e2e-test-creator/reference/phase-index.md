# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `target`, `repo_root`, `run_tests`, `max_files_per_run`, `deadline`, `session_token_budget`, `output_dir` |
| **Detect conventions** | [workflow/detect-conventions.md](../workflow/detect-conventions.md) | `test_framework`, `test_layout`, `selector_convention`, `detection_confidence` |
| **Select targets** | [workflow/select-targets.md](../workflow/select-targets.md) | `target_list` — journeys, each tagged `NEW` / `SKIPPED_ALREADY_COVERED` / `SKIPPED_MAX_FILES` |
| **Generate tests** | [workflow/generate-tests.md](../workflow/generate-tests.md) | `test_files_written` |
| **Verify & iterate** | [workflow/verify-and-iterate.md](../workflow/verify-and-iterate.md) | `verify_result` (per-journey pass/fail/blocked/needs-human) |
| **Report** | [workflow/report.md](../workflow/report.md) | `E2E_TEST_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `target: {mode: diff, source: "MR !123"}` | Inputs → Detect → Select (journeys inferred from changed routes/pages) → Generate → Verify → Report |
| `target: {mode: backfill, journeys: [...]}` | Inputs → Detect → Select (caller's explicit journeys, capped) → Generate → Verify → Report |
| `target.mode: backfill` with an absent/empty `journeys` list | Inputs HARD STOP — ask, no further phase runs |
| Repo has 2+ comparably-confident browser tooling frameworks, no `test_framework_hint` | Inputs → Detect gate asks once — no journey selected yet |
| `target` or `repo_root` missing | Inputs HARD STOP — ask, no further phase runs |
| No reachable running instance of the app | Generate tests gates the affected journeys `NEEDS_BROWSER_ENV` — no fabricated assertions |
| A generated test fails against real app behavior | Verify & iterate reports the finding; does not proceed to "passing" for that journey |
