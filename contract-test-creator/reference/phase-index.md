# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `target` (incl. `role`), `repo_root`, `run_tests`, `max_files_per_run`, `deadline`, `session_token_budget`, `output_dir` |
| **Detect conventions** | [workflow/detect-conventions.md](../workflow/detect-conventions.md) | `pact_library`, `broker_configured`, `test_layout`, `detection_confidence` |
| **Select targets** | [workflow/select-targets.md](../workflow/select-targets.md) | `target_list` (each item tagged `NEW` / `SKIPPED_ALREADY_COVERED` / `SKIPPED_MAX_FILES`) |
| **Generate tests** | [workflow/generate-tests.md](../workflow/generate-tests.md) | `test_files_written` (consumer test + pact file, or provider verification test) |
| **Verify & iterate** | [workflow/verify-and-iterate.md](../workflow/verify-and-iterate.md) | `verify_result` (per-target pass/fail/needs-observed-interaction/needs-human) |
| **Report** | [workflow/report.md](../workflow/report.md) | `CONTRACT_TEST_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `target: {mode: diff, source: "MR !123", role: consumer}` | Inputs → Detect → Select → Generate (consumer) → Verify → Report |
| `target: {mode: backfill, scope: [...], role: provider}` | Inputs → Detect → Select (caller scope, capped) → Generate (provider verification) → Verify → Report |
| `target.role` missing | Inputs HARD STOP — ask which role, no further phase runs |
| Repo has 2+ comparably-confident Pact libraries, no hint | Inputs → Detect gate asks once — no target selected yet |
| A target has no real observed interaction to derive its shape from | Generate tests tags `NEEDS_OBSERVED_INTERACTION`; never fabricates one |
| A provider verification fails against a real pact file | Verify & iterate reports the finding; does not proceed to "passing" for that target, never loosens the pact |
