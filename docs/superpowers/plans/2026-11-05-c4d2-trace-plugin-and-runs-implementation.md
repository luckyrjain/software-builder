# C4d-2 trace plugin and per-side trace runs: implementation plan

**Goal:** add the harness-owned line-event trace to the benchmark gate (`TRACE_PLUGIN_SOURCE`, `trace_env`, `trace_paired`,
`TRACE_REFUSAL_CODES`) and the shared run chain (`_prepare_run`, `_execute`, `_check_timeout`, `_check_sides`, `_benchmark_file_of`) in
`skills/loop-task-implementer/scripts/benchmark_gate.py`. Library only; nothing is wired until C4f. `compare`, `run-once`, `HOST_BUSY_*`
are C4d-3 and are **not** in this plan.

**Architecture:** one module-level pytest plugin shipped as a raw-string constant inside `benchmark_gate.py`, written fresh per side into a
harness-owned directory, loaded with `-p`, counting `LINE`+`JUMP` events in the test body (and its `__wrapped__` chain) via
`sys.monitoring`, and reporting through a nonce-bearing marker file the harness reads from a separate `out_dir`. The per-run chain of
`measure_paired` is extracted so the trace run reuses it. Details are binding in the spec.

**Tech stack:** Python 3.12+ standard library for the harness; the plugin string must also import on CPython 3.8+ (static rule); pytest
for tests (`/opt/homebrew/bin/python3`).

**Spec (binding):** `docs/superpowers/specs/2026-11-05-c4d2-trace-plugin-and-runs-design.md` (rev 7; sections D1 to D9, 3 to 6). Where
this plan and the spec disagree, the spec wins; stop and report the disagreement.

**Branch / worktree:** `c4d2-trace` in `/Users/luckyjain/Projects/sb-c4d2`, base `77859929`.

## Global constraints

- All code tasks edit the **same file**, so tasks run strictly in order; never run two implementers at once, never edit
  `benchmark_gate.py` while a full suite runs (the harness-hash test reads the module hash at import).
- Test commands (no engineering profile exists): focused `/opt/homebrew/bin/python3 -m pytest <file> -q`; the benchmark-gate set
  `/opt/homebrew/bin/python3 -m pytest skills/loop-task-implementer/tests -q -k "benchmark_gate or packaged_runtime"` (about 8 to 10
  minutes: run in the background); lint `PATH=/tmp/pybin:$PATH make lint-static` (the `/tmp/pybin` directory holds a symlink to
  `/opt/homebrew/bin/python3`, which has `yaml`).
- TDD: write the failing test first, see it fail for the stated reason, then implement. A task's tests must be green at its own commit.
- Commits: one commit per task, message `C4d-2 <task>: <what>`, ending with the attribution line
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Do not push; the controller pushes.
- Snyk Code is not enabled for the org: do not try to run it or change org settings; note "Snyk Code scan not run" in the PR body.
- No new dependencies. No wiring into workflow files, lifecycle validators, other scripts or CLI subcommands.
- The plugin string is production code: ASCII only, no annotations, 3.8-safe syntax (spec D2), and it is never edited by a later task
  except T3c.
- Never use `print` debugging left in; keep comments to the *why* (house style: see neighbouring C4d-1 code).

## Review focus (for the final whole-branch rounds)

Fail-closed behaviour of every `trace_paired` path; no un-coded exception from the harness; the forged-result and FIFO rows; that
`measure_paired` behaviour is unchanged by T1/T2 (T0 characterization suite and the whole C4d-1 suite); the 3.12 fallback in
`_release_tool`; identity membership; honest wording of the disclosed limits.

## Tasks

### T0 `[CODE]` characterization tests (green on the base)

- **Files:** `skills/loop-task-implementer/tests/test_benchmark_gate_measure.py` (add only tests).
- **Tests to add** (spec section 4, "T0"): `test_characterize_error_details`; `test_oversize_beats_timeout` (child script writes 3 MiB
  swallowing the `OSError`, then sleeps); `test_oversize_beats_nonzero_exit`;
  `test_scratch_is_removed_after_spawn_failure_timeout_and_nonzero` (spy on `bg.shutil.rmtree` that calls through, filter basename
  `<side>-<n>`); `test_spawn_failure_cause_is_spawn_failed`; extend the existing environment test so no timed run sees `PYTHONPATH`,
  `BENCH_TRACE_FILE`, `BENCH_TRACE_OUT`, `BENCH_TRACE_NONCE`.
- **Step 1 (red/green):** these assert today's behaviour, so they pass immediately. Prove they are not vacuous: temporarily mutate
  `measure_paired` (swap the oversize/timeout checks; delete the `finally: shutil.rmtree`; change `from exc`; format the timeout with
  `float`) and confirm each named test fails, then revert the mutation (do not commit mutations).
- **Run:** `/opt/homebrew/bin/python3 -m pytest skills/loop-task-implementer/tests/test_benchmark_gate_measure.py -q` -> all pass.
- **Commit:** `C4d-2 T0: characterize measure_paired error details and cleanup`.

### T1 `[CODE]` extract `_prepare_run` and `_execute` (behaviour-preserving)

- **Files:** `benchmark_gate.py` (`measure_paired` region only).
- **Failing test first:** none new; the T0 suite plus the whole measure suite are the guard. Run them first to confirm green.
- **Implement (spec D5, exact):** module-level `_prepare_run(side, bin_dir, work, counter) -> (scratch, env)` (three `os.makedirs` per
  run; pycache override) and `_execute(side, argv, root, scratch, env, timeout_seconds, fail) -> (elapsed_ns, stdout)` with the
  try/except `_SpawnFailed`/finally-rmtree then oversize -> timeout -> nonzero order and the four detail strings. `fail(kind, detail)` is
  the caller's adapter (returns the error; `_execute` raises it; spawn keeps `from exc`). `measure_paired` keeps `nonlocal counter`,
  `phase_now[0] = phase` before `_prepare_run`, `argvs.setdefault`, the digest parse, and an adapter mapping kinds to
  `<SIDE>_NONZERO_EXIT` / `OUTPUT_TOO_LARGE` / `<SIDE>_TIMEOUT` with `side`, `phase`, `partial`.
- **Run:** `/opt/homebrew/bin/python3 -m pytest skills/loop-task-implementer/tests/test_benchmark_gate_measure.py -q` -> unchanged, all pass.
- **Commit:** `C4d-2 T1: extract _prepare_run/_execute from measure_paired`.

### T2 `[CODE]` shared argument validation

- **Files:** `benchmark_gate.py`; `test_benchmark_gate_measure.py`.
- **Failing tests first (spec section 4, T2 rows):** `test_benchmark_file_of_and_check_timeout_reject_the_bad_inputs` (also through
  `measure_paired`; includes: traversal, absolute, backslash, `.`/`..`/empty component, trailing slash, leading `-`, non-`.py`, non-`str`,
  NUL); `test_sides_checks_run_before_the_target_check`. Edit the six existing `"t"` targets (lines 421, 458, 615, 683, 693, 704) to
  `"bench.py::t"`. Confirm the new-rejection rows fail on the base.
- **Implement (spec D4):** `_benchmark_file_of`, `_check_timeout`, `_check_sides(...) -> (sides, benchmark_file)` where `sides` keeps the
  existing `{name: (realpath root, realpath bin)}` shape; `measure_paired` calls `_check_timeout` before the `min_base_ns` check and
  `_check_sides` after it, so error precedence is unchanged.
- **Run:** measure test file -> all pass (including the six edited tests).
- **Commit:** `C4d-2 T2: shared target/timeout/sides validation`.

### T3a `[CODE]` constants, `trace_env`, `pytest_argv(plugins=)`, tripwire tokens

- **Files:** `benchmark_gate.py` (after `pytest_argv`; `_TRIPWIRE_TOKENS` near `:2658`; `token_tripwire` docstring `:2868`);
  `test_benchmark_gate_measure.py` (argv rows) or the new trace file; `test_benchmark_gate_diff.py` (`:304` parametrization).
- **Failing tests first:** `test_trace_env_is_a_copy_with_four_keys`;
  `test_pytest_argv_plugins_keyword_only_validated_and_placed_before_the_target`; `test_token_tripwire_flags_the_new_tokens`
  (`(sample, expected_token)`; membership among hit tokens; samples include `BENCH_TRACE_OUT`, `bench_trace_plugin`, `sys.monitoring`,
  `from sys import monitoring`, `sys.orig_argv`, `/proc/self/cmdline`, `/proc/self/environ`).
- **Implement (spec D7, D8, D9):** `_TRACE_MODULE = "bench_trace_plugin"`, `_TRACE_TIMEOUT_FACTOR = 3`; `trace_env(env, plugin_dir,
  benchmark_file, out_path, nonce)` returning a copy with exactly `PYTHONPATH`, `BENCH_TRACE_FILE`, `BENCH_TRACE_OUT`,
  `BENCH_TRACE_NONCE`; `pytest_argv(..., *, plugins=())` (tuple/list whose every element equals `_TRACE_MODULE`, else `ValueError`;
  `"-p", name` after `"-p", "no:cacheprovider"`, before the target); append to `_TRIPWIRE_TOKENS` in this order `BENCH_TRACE_`,
  `bench_trace_plugin`, `sys.monitoring`, `import monitoring`, `orig_argv`, `/proc/self/cmdline`, `/proc/self/environ` (keep existing
  order and `BENCH_TRACE_LINES`).
- **Run:** measure file, `test_benchmark_gate_diff.py` -> all pass; existing `test_pytest_argv_is_the_designed_argv` unchanged.
- **Commit:** `C4d-2 T3a: trace_env, pytest_argv plugins, tripwire tokens`.

### T3b `[CODE]` plugin skeleton (`TRACE_PLUGIN_SOURCE`)

- **Files:** `benchmark_gate.py` (new constant); **create** `skills/loop-task-implementer/tests/test_benchmark_gate_trace.py` copying
  `fake_sides`, `builder`, `pytest_venv` from the measure file (extend `pytest_venv` to install a per-side library module).
- **Failing tests first (spec section 4, T3b rows):** static rules (`ast.parse(feature_version=(3, 8))` + AST walk: no annotations, no
  subscripted builtins, banned names, `BitOr` only where allowed; the real plugin accepted, samples rejected; `r"""` prefix via
  `tokenize`); constant-in-file and literals-agree; `_init` (defaults-pop, captures `root_real`/`target_real` once, removes only its own
  dir from `sys.path`/`PYTHONPATH`, absent variable -> `failed`); `_claim_tool` (`tool_in_use`, `no_monitoring`, `error`); `_release_tool`
  exact call sequence on 3.12 and the `clear_tool_id` path; `on_event` (2 and 3 arguments, `DISABLE` for other code, once per thread,
  exception marks `failed`); identity membership. Follow the exec-test contract in spec section 4.
- **Implement (spec D1, D2):** `TRACE_PLUGIN_SOURCE` with the module-level `_claim_tool`, `_release_tool`, `_init`, `STATE`
  (`traced_ids`, `keep`, `thread`, `count`, `failed`, `unavailable`, `claimed`, `out`, `nonce`, `root_real`, `target_real`) and
  `on_event(code, arg1, arg2=None)`; the module ends with `_init(os.environ, sys)`. Hooks are added in T3c.
- **Run:** trace test file -> pass. (Real tool-id claims are released in `finally` via `_release_tool`; `restart_events()` where code
  objects are shared.)
- **Commit:** `C4d-2 T3b: trace plugin skeleton (init, claim/release, on_event)`.

### T3c `[CODE]` plugin hooks and markers

- **Files:** `benchmark_gate.py` (the constant); `test_benchmark_gate_trace.py`.
- **Failing tests first (spec section 4, T3c rows):** `_traced_set` rules; collection not exactly one item; hooks enable `LINE`+`JUMP`,
  record the thread, disable after the `yield`; no monitoring calls when not claimed; marker content and precedence (success,
  unavailable, failed, zero count, pre-created markers -> `pytest.exit(returncode=3)`, absent `out` -> `pytest.exit` 3, one-byte
  `os.write`, mismatching `get_tool` -> `.failed`, raising release -> `.failed`, mode `0o600`, no `restart_events` outside comments);
  one real smoke launch (plugin written with plain `write_text`, argv/env from the T3a functions, run through `bg._run_once` in a
  `pytest_venv`).
- **Implement (spec D2):** `collection_modifyitems`, `_traced_set(obj, originalname)` (chain of `obj` plus at most 8 hops; cycle;
  `__code__` required; name check on the innermost; file check against `STATE.target_real`), the `hookwrapper` `pytest_pyfunc_call`
  (only when `claimed`), `pytest_sessionfinish` (only-when-claimed monitoring work in `try/except BaseException`/`finally`; marker
  precedence failed > unavailable > zero count > success; `O_EXCL` failure writes `.failed`; `pytest.exit(..., returncode=3)` fallbacks).
- **Run:** trace test file -> pass.
- **Commit:** `C4d-2 T3c: trace plugin hooks and terminal markers`.

### T4a `[CODE]` plugin file helpers and codes

- **Files:** `benchmark_gate.py`; `test_benchmark_gate_trace.py`; `test_benchmark_gate_exports.py` (pin at `:457` and uniqueness loop at
  `:473`).
- **Failing tests first:** `test_write_plugin_makes_one_read_only_file_and_verify_plugin_rejects_a_tampered_one` (tamper with `chmod
  0o600` then write, or unlink/recreate; assert the detail "plugin file hash mismatch"); vocabulary pin extended with `TRACE_MISMATCH
  TRACE_UNAVAILABLE` after `MEASURE_FAILED`; `TRACE_REFUSAL_CODES` in the uniqueness loop.
- **Implement (spec D1, D6):** `_write_plugin(plugin_dir) -> path` (`O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW`, `0o400`), `_verify_plugin(path)`
  (SHA-256 against `TRACE_PLUGIN_SOURCE`; mismatch -> `MEASURE_FAILED` "plugin file hash mismatch"), `TRACE_REFUSAL_CODES`,
  `ERROR_CODES += TRACE_REFUSAL_CODES`.
- **Run:** trace file + exports file -> pass.
- **Commit:** `C4d-2 T4a: plugin file helpers and trace codes`.

### T4b `[CODE]` `trace_paired`

- **Files:** `benchmark_gate.py`; `test_benchmark_gate_trace.py`.
- **Failing tests first (spec section 4, T4b rows), using a fake `bg._run_once`/`argv_builder`:** result read from `out_dir` after
  scratch removal (and the return dict incl. `interpreter`, `argv`, `body_has_control_flow`, `ini_path`, base-before-head, fresh nonce
  per side); the validation matrix (symlink, hardlink, uid, size, trailing text, `12ab`, `5.5`, 19 digits, count 0, wrong nonce, empty,
  `.failed`, dangling `.failed`, FIFO and directory with the thread-`join(5)` deadline); the unavailable decision table; hard failure
  stops before the second side; failure kinds with the `<kind>:` prefix and the timeout suffix; the `3 *` timeout argument;
  validation precedence and `phase`; `MEASURE_FAILED` rows (failing `mkdtemp`, `_write_plugin` `OSError`, tamper via `argv_builder`
  glob under a `tempfile.tempdir` patch, `:` in the directory, failing `work` creation); interpreters must match; digest/stdout not
  parsed; `test_body_has_control_flow`.
- **Implement (spec D3, D4, D5):** `trace_paired(...)` with the per-side `with TemporaryDirectory(prefix="bench-run-")`, `_prepare_run`,
  `plugin-`/`out-` directories, nonce, write plugin -> build argv -> `trace_env` -> `_verify_plugin` -> `_execute` (3x timeout) -> steps 1
  to 3 (lexists `.failed`, `O_NONBLOCK` read + `fstat` checks, anchored regex, count >= 1, nonce), the decision table, `phase="trace"`
  after validation, `MEASURE_FAILED` for harness faults, and `body_has_control_flow` (advisory; computed before the first run; spec D3).
- **Run:** trace test file -> pass.
- **Commit:** `C4d-2 T4b: trace_paired with result protocol and decision table`.

### T4c `[CODE]` real-pytest rows (may carry fixes)

- **Files:** `test_benchmark_gate_trace.py`; `benchmark_gate.py` only if a real launch exposes a defect (fix it here and say so).
- **Tests (spec section 4, T4c row):** batching with a helper; Python vs `map` library entries; different loop counts incl. one-line
  loops; early return / caught exception; honest fixed count; `wraps` vs plain wrapper vs decoy; two tests / async / plugin failure;
  forged results (print the token, pre-create `out`, `os._exit` via `getattr`, FIFO + `os._exit`, `atexit` rewrite with wrong nonce, reads
  `STATE` via `sys.modules`); tool id 4 taken by a venv `.pth` (both sides, one side); release and re-claim on the CI interpreter;
  outside-pointing symlink; `chdir` at import (also to `/`). `skipif(not hasattr(sys, "monitoring"))`; 120 s child timeouts; relations
  and lower bounds only.
- **Run:** trace test file -> pass; then the whole benchmark-gate set in the background.
- **Commit:** `C4d-2 T4c: real-pytest trace rows`.

### T5 `[DOCS-ONLY]` docs and comments

- **Files:** `benchmark_gate.py` (docstrings/comments only); test module docstrings.
- **Do (spec section 5):** module docstring lines 11 to 17 and the C4d sentence, section header comment, the `MEASURE_FAILED` and
  `ERROR_CODES` comments, `BenchmarkGateError` attribute comments (`phase` also `"trace"`), `measure_paired`, `pytest_argv`, `side_env`,
  `harness_sha256` (`:2173`), `token_tripwire` docstrings, the disclosed limits; test-file docstrings (trace, exports, measure, diff).
- **Run:** `PATH=/tmp/pybin:$PATH make lint-static` -> exit 0; trace + measure + exports files pass.
- **Commit:** `C4d-2 T5: docs for the trace plugin and runs`.

### T6 `[CONTROLLER]` gates, reviews, PR

Not for an implementer. The controller runs the full benchmark-gate set (background), `make lint-static`, `graphify update .`, the
whole-branch adversarial review rounds until clean, then commits any fixes, pushes, opens the PR (body: scope, "Snyk Code scan not run: not
enabled for the org", the disclosed limits, what is not in scope), and checks CI.

## Dependency audit

| Task | Reads a prior task's output / edits the same file or section? | Depends on |
|---|---|---|
| T0 | edits the measure test file | none |
| T1 | edits `measure_paired` region; guarded by T0 | T0 |
| T2 | same region as T1; edits the six existing tests | T1 |
| T3a | same file; new constants after `pytest_argv`, `_TRIPWIRE_TOKENS`; edits the measure/diff tests | T2 |
| T3b | same file (new constant); creates the trace test file; copies helpers from the measure file | T3a |
| T3c | edits the constant T3b created; same test file | T3b |
| T4a | uses `TRACE_PLUGIN_SOURCE`; same files; edits the exports pin | T3c |
| T4b | uses T1 `_prepare_run`/`_execute`, T2 `_check_*`, T3a `trace_env`/argv, T4a helpers | T1, T2, T3a, T4a |
| T4c | uses everything; may edit `benchmark_gate.py` | T4b |
| T5 | docstrings in the file edited by all prior code tasks | T4c |
| T6 | everything | T0 to T5 |

Hidden edges checked: the vocabulary pin must land in the same commit as the new codes (T4a); docs follow the code they quote (T5 last);
the six `"t"` test edits land in T2 with the rejection they depend on; the trace test file is created in T3b before T3c/T4 rows use it.
**Waves:** none can run in parallel (one source file): W0 T0, W1 T1, W2 T2, W3 T3a, W4 T3b, W5 T3c, W6 T4a, W7 T4b, W8 T4c, W9 T5, W10 T6.

## Self-review

- **Spec coverage:** D1 -> T3b/T4a/T4b; D2 -> T3b/T3c; D3 -> T4b; D4 -> T2; D5 -> T1; D6 -> T4a; D7/D8/D9 -> T3a; section 3 acceptance ->
  T4b/T4c rows; section 5 docs -> T5; section 6 order -> this plan. The disclosed limits are carried by T5.
- **Placeholders:** none; every task names files, tests, the implementation points and a command.
- **Name consistency:** `_prepare_run`, `_execute`, `_check_timeout`, `_check_sides`, `_benchmark_file_of`, `TRACE_PLUGIN_SOURCE`,
  `_TRACE_MODULE`, `_TRACE_TIMEOUT_FACTOR`, `trace_env`, `trace_paired`, `_write_plugin`, `_verify_plugin`, `TRACE_REFUSAL_CODES`,
  `STATE`, `on_event`, `_traced_set`, `_claim_tool`, `_release_tool`, `_init` are used identically in the spec and here.
