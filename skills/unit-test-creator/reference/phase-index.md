# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `target`, `repo_root`, `run_tests`, `max_files_per_run`, `deadline`, `session_token_budget`, `output_dir` |
| **Detect conventions** | [workflow/detect-conventions.md](../workflow/detect-conventions.md) | `test_framework`, `test_layout`, `mock_style`, `detection_confidence` |
| **Select targets** | [workflow/select-targets.md](../workflow/select-targets.md) | `target_list` (each item tagged `NEW` / `SKIPPED_ALREADY_COVERED` / `SKIPPED_MAX_FILES`) |
| **Generate tests** | [workflow/generate-tests.md](../workflow/generate-tests.md) | `test_files_written` |
| **Verify & iterate** | [workflow/verify-and-iterate.md](../workflow/verify-and-iterate.md) | `verify_result` (per-target pass/fail/untestable/needs-human) |
| **Report** | [workflow/report.md](../workflow/report.md) | `UNIT_TEST_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `target: {mode: diff, source: "MR !123"}` | Inputs → Detect → Select (changed files minus already-tested) → Generate → Verify → Report |
| `target: {mode: backfill, scope: [...]}` | Inputs → Detect → Select (caller scope, capped) → Generate → Verify → Report |
| Repo has 2+ comparably-confident frameworks, no `test_framework_hint` | Inputs → Detect gate asks once — no target selected yet |
| `target` or `repo_root` missing | Inputs HARD STOP — ask, no further phase runs |
| A target can only be exercised through infrastructure this session can't mock | Generate tests tags `UNTESTABLE_WITHOUT_FIXTURE`, suggests **integration-test-creator** |
| A generated test fails against real production behavior | Verify & iterate reports the finding; does not proceed to "passing" for that target |
