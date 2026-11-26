# C4d-3 `compare`, `run-once` and the verdict mapping: implementation plan

> **Note (I5): the spec wins over this plan** wherever they differ, and the spec is annotated by round (design D1 to D6, implementation I1 to I8). Known
> differences: the spawn guard (`spawn_guard`, called before every spawn, with the recorded directory identities); `_IdentityChanged` (derives from
> `Exception`, not from `BenchmarkGateError`); `_WrittenResult` and `written_sha256` (the CLI prints the line from the in-memory result and the hash of the
> bytes written); the retry rule (two constants, `COMPARE_RETRYABLE_AUTOMATIC` and `COMPARE_RETRYABLE_WITH_HUMAN_FLAG`, not one); `harness-sha256`; `allow_abbrev=False`; `format_result_line` (the one builder of the `RESULT:` line) and `parse_compare_outcome` (the reference reader, which also checks `interpreter_writable=`).
> "Spec question 4" and the `NotImplementedError` scaffold between T3a and T4b are HISTORICAL: the scaffold was removed, `_compare_impl` has none. Commands and
> commands below that run Python say `python3`; use any Python 3.12+ with PyYAML (no machine-specific interpreter path is part of the plan).

**Goal:** add `compare` (the 13-step pipeline, the result vocabularies, the integrity checks, the result file) and `run-once` to the
benchmark gate in `skills/loop-task-implementer/scripts/benchmark_gate.py`, plus the CLI crash contract. Library and CLI only; nothing is
wired until C4f. The provisioning, the `IMPROVED` acceptance screen, the retry policy and the write-back of the parent-design deviations are
C4e/C4f and are **not** in this plan.

**Architecture:** `compare(gate, repo, base: Side, head: Side, *, attempt, out_path, allow_writable_interpreter)` is a thin wrapper over
`_compare_impl(..., seams)`, which runs `_compare_checks` (steps 1 to 6), `_compare_prepare` (7 to 9) and `_compare_runs` (10 to 13) and turns
an internal `_Verdict` into a result dict (or raises `BenchmarkGateError` for a caller or harness fault). The integrity checks
(`fingerprint_tree`, `interpreter_pin`, `dependency_parity`, `verify_export_against_commit`) are separate module-level functions. The C4d-1/2
run chain is hardened first (per-run scratch and ini, no pycache prefix, errno-aware spawn failures, `kind` on measure errors, salted order).

**Tech stack:** Python standard library only (the skill ships `scripts/` wholesale); pytest for tests (any Python 3.12+ with PyYAML for `make lint-static`).

**Spec (binding):** `docs/superpowers/specs/2026-11-06-c4d3-compare-and-run-once-design.md` (rev 7; sections 2.1 to 2.11, 3 acceptance, 4 tests
and "Existing tests changed", 6 task table). Where this plan and the spec disagree, the spec wins; stop and report the disagreement. The
"Spec questions" section at the end records what reading the real file turned up; none changes the design.

**Branch / worktree:** `c4d3-compare` in `/Users/luckyjain/Projects/sb-c4d3`, base `2dc72667` (C4d-2, #367; the spec commit `d83c6bee` sits on top).

## Global constraints

- All code tasks edit the **same file**, so tasks run strictly in order; never run two implementers at once, never edit `benchmark_gate.py`
  while a full suite runs (the harness-hash test reads the module hash at import).
- Test commands (no engineering profile exists): focused `python3 -m pytest <file> -q`; the benchmark-gate set
  `python3 -m pytest skills/loop-task-implementer/tests -q -k "benchmark_gate or packaged_runtime"` (8 to 10 minutes: run in
  the background); lint `make lint-static` (run it with a Python 3.12+ first on `PATH` that has PyYAML).
- TDD: write the failing test first, see it fail for the stated reason (on the base, or on the previous task's commit), then implement. A task's
  tests must be green at its own commit. A "green on arrival" pin (T7) is proven non-vacuous by a temporary mutation that is reverted, not committed.
- Commits: one commit per task, message `C4d-3 <task>: <what>`, ending with the line
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Do not push; the controller pushes.
- Snyk Code is not enabled for the org: do not run it or change org settings; the PR body says "Snyk Code scan not run".
- No new dependencies. No wiring into `workflow/*` files, lifecycle validators, other scripts. New CLI subcommands are `compare` and `run-once` only.
- Fakes, not real children, except the two T6 rows and the single-purpose real-child rows named in T4a1, T4a2 and T5a. Use the seams of 2.2
  (`argv_builder`, `load_probe`, `min_base_ns`, `order_salt`, `interpreter_of`); a fast fake child is `WORKLOAD_TOO_SHORT` unless `min_base_ns=0`.
- House style: comments say *why*; no leftover `print`; every attacker-influenced string goes through `escape_diagnostic` once, where the result or error is built.
- Line anchors in this plan are against base `2dc72667` and move as tasks land; find the function by name.

## Review focus (for the final whole-branch rounds)

Result-or-raise split (2.1) and the single precedence list (2.7); that step 12 runs after every path that started a child and beats everything
but a raise; the `ctime` fingerprint inputs and the check order of 2.5; `dependency_parity` and `verify_export_against_commit` fail-closed
behaviour and the honest-install pass rows; that `measure_paired`/`trace_paired` behaviour is unchanged by T0b1/T0b2a except where the spec
says so (the whole C4d-1/2 suite); no un-coded exception out of the CLI; honest wording of the disclosed residuals.

## Tasks

### T0a `[CODE]` gate `warmup_runs` 1..2, `_ratio_stats`, `benchmark_target`

- **Files:** `benchmark_gate.py` (`validate_benchmark_gate` bound `:385` and docstring `:337-348`; `_evaluate` `:424-453`; new `benchmark_target`
  after `validate_benchmark_gate`, `:409`); `test_benchmark_gate_core.py`.
- **Existing tests to edit (spec "Existing tests changed", T0a):** `test_benchmark_gate_core.py:474-475` (the `BOUNDS_REJECTED` parametrization:
  add `{"warmup_runs": 0}` next to `-1` and `3`); `:499` (the accepted row `{"warmup_runs": 0, "repeats": 4, "per_run_timeout_seconds": 10}`
  becomes `warmup_runs: 1`; it stays valid, `(1+4+3)*2*10 = 160`); `:548-551` (`test_gate_budget_largest_timeout_at_repeats_8_per_warmup`: drop the
  `(0, 81)` row, keep `(1, 75)`, `(2, 69)`; fix its "figures in the docstring" comment).
- **Failing tests first (spec section 4 row 10, T0a):**
  - `test_gate_warmup_zero_is_bounds_rejected` (`validate_benchmark_gate(_gate(warmup_runs=0)) == (None, "BOUNDS_REJECTED")`; kills "bound left at 0"; base returns OK).
  - `test_ratio_stats_matches_evaluate_on_every_branch` (parametrize the samples of the existing evaluate tests; `bg._ratio_stats(base, head)` returns
    `(ratios, median, mad)` as Fractions, and re-deriving the verdict from it equals `evaluate_paired_samples`; kills a `_ratio_stats` that rounds,
    sorts `ratios` or uses mean; fails on base: `AttributeError`). Also pins that `_ratio_stats` does not validate (the validation stays in `_evaluate`).
  - `test_benchmark_target_is_the_single_non_dash_token` (`"pytest -q --no-header bench/b.py::t"`, `"python3 -m pytest bench/b.py::t -q"`, options on
    either side, with and without `::symbol`; returns the token exactly; kills "first token after pytest" and "last token"; fails on base: `AttributeError`).
- **Implement:** change `0 <= values["warmup_runs"] <= 2` to `1 <= ... <= 2` and the docstring figures ("at most 75 with 1 and 69 with 2"; the
  `warmup_runs` 0 statement goes). `_ratio_stats(base, head) -> (ratios, median, mad)` extracted from `_evaluate`'s inline computation (`ratios = [Fraction(h, b)
  ...]`, `_median`, `_median([abs(r - median) ...])`) with no behaviour change: `_evaluate` keeps its validation, its clear-win early return (it may
  call `_ratio_stats` before it; spec 2.11 allows the harmless extra median) and its branch order. `benchmark_target(normalized_gate) -> str`: split
  `normalized_gate["command"]` on a space, drop the `pytest` or `python3 -m pytest` prefix, return the one token that does not start with `-`
  (the gate was validated, so exactly one exists; a missing one raises `ValueError`, unreachable).
- **Run:** `python3 -m pytest skills/loop-task-implementer/tests/test_benchmark_gate_core.py -q` -> all pass.
- **Commit:** `C4d-3 T0a: gate warmup 1..2, _ratio_stats, benchmark_target`.

### T0b1 `[CODE]` `kind` on measure errors, errno-aware spawn failures, salted order

- **Files:** `benchmark_gate.py` (`run_order` `:3446-3464`; `_run_once` `:3519-3559` the `except` at `:3535-3536`; `_SpawnFailed` `:3562`;
  `measure_paired` `:3648` and its `adapt` `:3704-3710`; `_execute` `:3586-3602`; new `_run_error_code`); `test_benchmark_gate_measure.py`.
- **Existing tests (spec "Existing tests changed", T0b1):** `test_benchmark_gate_measure.py:243` (the `_execute`-patching test that expects
  `AssertionError: unknown _execute failure kind`) must still pass unchanged: `_run_error_code(side, kind)` keeps that `AssertionError`. The stubs
  `raise bg._SpawnFailed("no python")` (`test_benchmark_gate_trace.py:1081`) and the `__cause__` assertion at `test_benchmark_gate_measure.py:384-389` stay
  valid because the errno argument defaults to `errno.ENOENT`. Re-run both after the change; edit nothing.
- **Failing tests first (this task owns no row of spec section 4 by tag; these are the spec 2.4/2.5b/2.7 contracts T4a2 depends on):**
  - `test_measure_errors_carry_kind` (one parametrized row per `_execute` kind: `spawn`, `oversize`, `timeout`, `nonzero`; `error.kind` equals it, and
    `error.code` is unchanged: `<SIDE>_NONZERO_EXIT` for a spawn failure; kills a `kind` set only on trace errors; fails on base: `kind is None`).
  - `test_run_error_code_maps_every_kind_and_asserts_on_unknown` (pure; kills a silent default).
  - `test_spawn_failed_errno_split` (stub `bg._run_once` to raise `_SpawnFailed(msg, errno.X)`: ENOENT, EACCES, ENOEXEC, ENOTDIR -> `kind == "spawn"`;
    EAGAIN, ENOMEM and `None` -> `MEASURE_FAILED` with `phase`/`partial` for `measure_paired`, and `kind == "harness"` for `trace_paired`; kills "every
    errno is a spawn"; fails on base: `_SpawnFailed` takes no errno).
  - `test_run_once_passes_the_errno_of_an_oserror_and_none_for_a_subprocess_error` (monkeypatch `subprocess.Popen` to raise `OSError(errno.EACCES, ..)`
    and then `subprocess.SubprocessError`; kills a missing `exc.errno`).
  - `test_run_order_unsalted_is_todays_bytes_and_salt_changes_it` (`run_order(B, H, S, 1, 4)` equals a frozen list computed on the base; a salt appends
    a fifth `\0`-joined field: two salts differ for some input, the same salt repeats; `salt=""`, `"G"`, 65 chars, non-str -> `MEASURE_ARGS_INVALID`;
    kills "salt=None means random" and a salt joined into the existing fields; fails on base: `TypeError`).
  - `test_measure_paired_order_salt_reaches_run_order` (`result["order"] == run_order(.., salt=s)`; the existing `:168, :536, :618` assertions stay valid unsalted).
- **Implement:** `_SpawnFailed(msg, errno=errno.ENOENT)` (the default is bound at definition; do not use the `errno` module inside `__init__`, the parameter
  shadows it); `_run_once` raises `_SpawnFailed(str(exc), exc.errno)` for an `OSError` and `_SpawnFailed(str(exc), None)` for a `SubprocessError`.
  `_execute`'s `except _SpawnFailed` maps `errno in {ENOENT, EACCES, ENOEXEC, ENOTDIR}` to `raise fail("spawn", ...) from exc`; any other errno or `None`
  raises `RuntimeError("host spawn fault")` chained `from exc` (the existing `except (OSError, RuntimeError, ...)` branches of `measure_paired` and
  `trace_paired` already turn it into `MEASURE_FAILED`). `_run_error_code(side, kind) -> str` takes the dict now inline in `adapt`
  (`oversize -> OUTPUT_TOO_LARGE`, `timeout -> <SIDE>_TIMEOUT`, `nonzero`/`spawn -> <SIDE>_NONZERO_EXIT`) with the `AssertionError`; `adapt` sets
  `error.kind = kind` (the `kind` attribute exists, `BenchmarkGateError.kind`, `:911`). `run_order(..., *, salt=None)`: validate (`None` or lowercase hex of 1 to 64
  chars, else `MEASURE_ARGS_INVALID`) after the existing checks; with a salt the seed string gains `"\0" + salt`. `measure_paired(..., order_salt=None)` passes it through.
- **Run:** `python3 -m pytest skills/loop-task-implementer/tests/test_benchmark_gate_measure.py skills/loop-task-implementer/tests/test_benchmark_gate_trace.py -q` -> all pass.
- **Commit:** `C4d-3 T0b1: error kind, spawn errno split, salted run order`.

### T0b2a `[CODE]` per-run scratch and ini, no pycache prefix, work identity check (the blocker test)

- **Files:** `benchmark_gate.py` (`side_env` `:3467-3487` incl. the docstring and `:3481`; `_prepare_run` `:3577-3583`; `measure_paired`
  `:3648-3745` incl. the `ini` block `:3687-3691`, the `counter` and call `:3702`; `trace_paired` `run_side` `:3879-3922` incl. call `:3887`; `_execute`
  `:3586`); `test_benchmark_gate_measure.py`; `test_benchmark_gate_trace.py`.
- **Existing tests to edit (spec "Existing tests changed", T0b2a), exactly:**
  - `test_benchmark_gate_measure.py:79-86`: the `side_env` key set loses `PYTHONPYCACHEPREFIX` and gains `PYTHONDONTWRITEBYTECODE` (still nine keys; assert its value `"1"`).
  - `:360-380` (`test_scratch_is_removed_after_spawn_failure_timeout_and_nonzero`): the spy filters `(base|head)-\d+`, which no longer exists. Rewrite to "an
    `rmtree` call whose parent is `work` (a `bench-run-*` directory) and whose basename is the run's scratch happens once per run", and replace `["base-1"]` by a count of 1.
  - `:599-613` (the `os.makedirs` counter): `_prepare_run` now makes the scratch with `tempfile.mkdtemp`, so `os.makedirs` is called twice per run (`side_env`'s home and
    tmp, `:3473-3475`). Re-derive: the threshold becomes `> 8` (4 runs of warmup+first round x 2), and the comment "a few runs in: the second timed round" is re-checked
    (run 5 is the first of timed round 2; the assertion `len(err.partial["base_ns"]) >= 1` still holds).
  - `:661` and `:665` (`test_the_pycache_prefix_is_per_side_and_shared_across_that_sides_runs`): replace by the new no-prefix test below (delete the old one).
  - `:678` (patches `os.makedirs` to raise): unchanged and still passes because `side_env` keeps `os.makedirs`; run it to confirm.
  - `test_benchmark_gate_trace.py:1822`: the `(base|head)-\d+` regex over the home directories' names becomes "the home's parent is a directory directly under the side's work directory".
  - `test_benchmark_gate_trace.py:894` and `:900` need no change (the default ini is still named `empty.ini`); `test_benchmark_gate_measure.py:168, :536, :618` stay valid.
- **Failing tests first (spec section 4 row 7, the blocker test, at `measure_paired`/`trace_paired` level, with real tiny children where noted):**
  - `test_each_run_gets_its_own_ini_inside_a_scratch_removed_after_the_run` (record the `-c` argv value per run through `argv_builder`/the default
    builder; all distinct, each under a directory that does not exist after the run; kills "ini written once into `work`"; fails on base: one shared `empty.ini`).
  - `test_a_child_that_rewrites_its_ini_or_plants_a_file_under_work_changes_nothing_for_the_next_run` (real child; first run overwrites its ini with
    `[pytest]\naddopts=-x` and writes `work/planted`; the next run's ini bytes are `_EMPTY_INI` and `planted` is absent from its view; kills the shared work channel).
  - `test_a_precreated_scratch_name_does_not_fail_the_run` (pre-create `work/base-1` via a patched `mkdtemp` wrapper or `argv_builder` side effect; the run
    succeeds; kills a predictable `os.makedirs(scratch)` that raises `FileExistsError`; fails on base).
  - `test_measure_paired_raises_measure_failed_when_work_is_replaced` (a child, or a `_prepare_run` spy, renames `work` and recreates it: the next `lstat(work)`
    `(st_dev, st_ino)` differs -> `MEASURE_FAILED` with `phase`; measure only; kills a missing identity check). A twin `test_trace_paired_has_no_work_identity_check`
    documents that one run per `work` makes the check vacuous (no failure).
  - `test_no_pycache_prefix_and_bytecode_is_not_written` (`side_env` has no `PYTHONPYCACHEPREFIX`, has `PYTHONDONTWRITEBYTECODE == "1"`, nine keys; a real child
    that imports a small module from `-P` root leaves no `__pycache__` under the root or the scratch; kills the old override at `_prepare_run` `:3582`).
- **Implement (spec 2.5b):** `_prepare_run(side, bin_dir, work, ini_path=None) -> (scratch, env, ini)`: `scratch = tempfile.mkdtemp(dir=work)` (no `counter`),
  `env = side_env(bin_dir, scratch)`, `ini = ini_path` or a new `empty.ini` written inside `scratch` (`_EMPTY_INI`, ASCII), nothing else in `env`; delete the
  `PYTHONPYCACHEPREFIX` override. `side_env`: drop the `PYTHONPYCACHEPREFIX` key, add `"PYTHONDONTWRITEBYTECODE": "1"`, update its docstring (the reason: a
  prefix would make CPython ignore every existing `__pycache__` and recompile the interpreter, pytest and the benchmark's imports on every run). `_execute`
  keeps removing the scratch. `measure_paired`: drop the `ini` block and `counter`; before every `_prepare_run` compare `os.lstat(work)`'s `(st_dev, st_ino)`
  with the value taken right after the `TemporaryDirectory` opens, else `raise BenchmarkGateError("MEASURE_FAILED", ...)` with
  `phase` and `partial` set as the existing `except (OSError, RuntimeError, ...)` handler does (`:3741-3745`); build the default argv with the `ini` that `_prepare_run` returned. `trace_paired.run_side`: same call, its
  `ini` now comes from `_prepare_run`; `ini_path` stays a test-only parameter that `compare` never passes.
- **Run:** measure and trace test files -> all pass; then the whole benchmark-gate set once, in the background, because this task changes the run chain every later task builds on.
- **Commit:** `C4d-3 T0b2a: per-run scratch and ini, no pycache prefix, work identity check`.

### T1 `[CODE]` `_check_one_side`, `run_benchmark_once`

- **Files:** `benchmark_gate.py` (`_check_sides` `:3628-3645` split; new `run_benchmark_once` after `trace_paired`/before `gate_sha256`, `:3946`);
  `test_benchmark_gate_measure.py` (or the compare file; the compare file exists only from T2b0, so use the measure file here).
- **Failing tests first (spec section 4 row 16, T1):**
  - `test_run_benchmark_once_returns_digest_and_argv` (real tiny child printing `BENCH_RESULT_DIGEST`; result keys exactly `{"digest", "argv"}`; digest is the child's, argv is the default builder's;
    kills returning a boolean or the stdout; fails on base: `AttributeError`).
  - `test_run_benchmark_once_error_codes` (one row each: nonzero exit, timeout, oversize, no digest -> `DIGEST_MISSING`, spawn -> `<SIDE>_NONZERO_EXIT`; `side="base"`/`"head"`
    names the side; kills a hard-coded head).
  - `test_check_one_side_rejects` (relative or missing root, `bin_dir` that fails `_venv_layout`, target not a regular file under root, target a symlink, target
    resolving outside the root, bad timeout; each `MEASURE_ARGS_INVALID`; kills a missing containment check). `root` need not be an export: a plain `tmp_path` passes.
  - `test_run_benchmark_once_touches_nothing_in_the_root` (no seal, no hash, no write: the root's tree is byte-identical and writable afterwards).
  - `test_run_benchmark_once_scratch_is_per_run_and_removed` (uses T0b2a's `_prepare_run`).
- **Implement:** `_check_one_side(root, bin_dir, target, ini_path)` as 2.9: absolute existing directories, `bin_dir` through `_venv_layout`, `_benchmark_file_of(target)`,
  the target a regular non-symlink file under `root` by `realpath` containment (`_inside`), `_check_timeout` stays with the caller; `_check_sides` keeps its contract
  and calls it per side where it can (its own two-side checks stay). `run_benchmark_once(root, bin_dir, target, *, timeout_seconds, side="head", argv_builder=None,
  ini_path=None) -> {"digest", "argv"}`: `UNSUPPORTED_PLATFORM` as `measure_paired`, validate, `TemporaryDirectory(prefix="bench-run-")`, `_prepare_run`, `_execute` with a `fail`
  adapter built on `_run_error_code`, digest through `_digest_of` (`DIGEST_MISSING` when absent), the same `OSError/RuntimeError` -> `MEASURE_FAILED` handler.
- **Run:** measure test file -> all pass.
- **Commit:** `C4d-3 T1: run_benchmark_once and _check_one_side`.

### T2a `[CODE]` vocabularies, `Side`, `_Verdict`, result assembly, dir-fd writer, `BASE_NOT_ANCESTOR`

- **Files:** `benchmark_gate.py` (new section "C4d-3 compare" after `trace_paired`, `:3946`; `ERROR_CODES +=` after `:3175`); **create**
  `skills/loop-task-implementer/tests/test_benchmark_gate_compare.py` (module header and `bg` loading copied from the trace file's header, `posix_only`);
  `test_benchmark_gate_exports.py` (the pin, about `:457-467`).
- **Existing tests to edit (spec "Existing tests changed", T2a):** the `ERROR_CODES` pin in `test_code_vocabularies_are_pinned` gains `BASE_NOT_ANCESTOR` appended
  after `TRACE_UNAVAILABLE`; the uniqueness loop is unchanged.
- **Failing tests first (spec section 4 row 1, T2a; row 18 first half):**
  - `test_vocabularies_are_pinned_exactly` (exact-contents asserts of `COMPARE_RESULT_OF_REASON` including every reason-to-result pair of 2.3, the domain
    `{IMPROVED, NOT_IMPROVED, INCONCLUSIVE, REJECTED}`, `ISOLATION_DETAILS` as a tuple, `COMPARE_DETAIL_TOKENS` as the explicit union; kills a dropped or moved reason;
    fails on base: `AttributeError`). `test_every_detail_token_is_ascii_and_unique`.
  - `test_error_codes_gain_exactly_base_not_ancestor_appended` (the pin above plus `BASE_NOT_ANCESTOR` not in `CLEANUP_CODES`).
  - `test_result_assembly_from_a_synthetic_verdict` (build a `_Verdict`, assemble: exact key set of 2.8 (every key present, absent ones `null`), `schema ==
    "software-builder-bench-compare-v1"`, `json.dumps(..., ensure_ascii=True)` is ASCII, floats not Fractions; kills a missing key and a non-ASCII leak).
  - `test_attacker_text_appears_only_in_untrusted_text_and_is_capped` (a verdict with 30 hostile strings, backticks, newlines, a NUL: the list has 20 entries, each escaped and
    length-capped; `detail` stays exactly one closed token of its reason's row in `COMPARE_REASONS` (no integers); `python` and `interpreter_home` go through `escape_diagnostic(.., 200)`).
  - `test_out_path_rejections` (step-1 `_validate_out_path`: relative, directory missing, directory not owned or group/other-writable, under either root, bin, venv, snapshot or
    the dispatch root by `realpath` (a symlinked directory too), `lexists` true; each `MEASURE_ARGS_INVALID`; kills each missing predicate).
  - `test_dirfd_writer_creates_exclusively_and_checks_identities` (writer links a random temp into the name, unlinks the temp in a `finally`, checks `os.stat(out_path,
    follow_symlinks=False)` identity; a planted target between validation and write -> error; a renamed or swapped directory (different `(dev, ino)`) -> error; a planted
    temp name is irrelevant (random); a failing `os.link` leaves no temp; kills `os.replace` use and path-based writes).
- **Implement:** `Side(NamedTuple)` with the six fields of 2.2; `COMPARE_RESULT_OF_REASON`, `ISOLATION_DETAILS`, `COMPARE_DETAIL_TOKENS` (explicit tuple, literal gate codes);
  `_Verdict(Exception)` carrying `result, reason, detail, kind, stage, extra` (subclasses `Exception` only, never `BaseException`); `_result_dict(verdict, common)` building the
  2.8 key set with `None` for not applicable and `untrusted_text` capped at 20; `_validate_out_path(out_path, forbidden) -> (dir_ident, name)`; `_write_result(...)` per 2.9
  (`O_DIRECTORY|O_NOFOLLOW` open of the recorded directory, random temp via `dir_fd`, `os.link(src_dir_fd=, dst_dir_fd=)`, `unlink` in `finally`, final identity `stat`, returns the sha256 of
  the bytes written); `ERROR_CODES += ("BASE_NOT_ANCESTOR",)` directly after `ERROR_CODES += TRACE_REFUSAL_CODES`.
- **Run:** `python3 -m pytest skills/loop-task-implementer/tests/test_benchmark_gate_compare.py skills/loop-task-implementer/tests/test_benchmark_gate_exports.py -q` -> all pass.
- **Commit:** `C4d-3 T2a: compare vocabularies, Side, result assembly, dir-fd writer`.

### T2b0 `[CODE]` shared fixtures (no production code)

- **Files:** `test_benchmark_gate_compare.py` only (fixtures and a smoke test).
- **Do (spec section 4 fixtures, T2b0):** a minimal real git repo with two commits (including a tracked symlink and a gitlink; built with the system `git`, 2.43+, as the
  exports tests do); two exports through `bg.export_tree` into a dispatch root under `bg.fixed_parent()` (or the exports tests' patched parent) with a matching marker; two fresh
  venvs whose `python` is a **symlink**, in three `pyvenv.cfg` shapes (Homebrew-like `home` as a symlink path, uv-like `version_info` only with a minor-version symlink directory,
  Xcode-CLT-like `home` a shim directory) and a pytest-bearing `.pth` created before `snapshot-venv` (the pattern in `pytest_venv`, `test_benchmark_gate_trace.py:55-64`); a small fake
  interpreter prefix (`<prefix>/bin/python3.X`, `<prefix>/lib/python3.X/os.py`, `lib-dynload`, one `__pycache__`, a `python3XY.zip`, a dylib-named file) for the `interpreter_of` seam; a helper to
  rebuild the world per test.
- **Tests:** `test_fixture_world_is_consistent` (exports verify against their commits, venvs pass `check_venv` with their snapshots, both venv pythons resolve to the fake or real interpreter).
  This is the only new test and it passes on arrival by construction; the fixtures are exercised by T2b1a to T2b2.
- **Run:** compare test file -> pass.
- **Commit:** `C4d-3 T2b0: shared fixtures for the compare tests`.

### T2b1a `[CODE]` `fingerprint_tree`

- **Files:** `benchmark_gate.py` (new section; `_MAX_HASH_DEPTH` `:1982`, `_MAX_TREE_ENTRIES` `:891` are reused; new `_VENV_FINGERPRINT_LIMIT = 200_000`); `test_benchmark_gate_compare.py`.
- **Failing tests first (spec section 4 row 11):**
  - `test_fingerprint_changes_for_each_input` (one row per field: content edit with restored mtime (ctime moves), chmod, size, a new/removed/renamed entry, a hard-link count change, root `(dev, ino, ctime)` via
    replacing the root; each changes the digest; an untouched tree gives the same digest twice; kills dropping `ctime_ns`, `nlink`, `mode` or the root triple).
  - `test_fingerprint_follows_no_links` (a symlink to a directory outside is one entry, its target's changes do not move the digest).
  - `test_fingerprint_limits_are_errors_not_skips` (limit exceeded -> `BenchmarkGateError` `TREE_TOO_LARGE`; depth beyond `_MAX_HASH_DEPTH` -> same; an unreadable subdirectory -> `TREE_UNREADABLE`; kills a silent skip).
- **Implement:** `fingerprint_tree(root, *, limit) -> str`: iterative `lstat` walk without following links, entries sorted by relative path, sha256 over `(relpath, dev, ino, mode, nlink, size, mtime_ns,
  ctime_ns)` records plus the root's `(dev, ino, ctime_ns)`; raises `TREE_TOO_LARGE` over `limit` entries or `_MAX_HASH_DEPTH`, `TREE_UNREADABLE` on `OSError`.
- **Run:** compare test file -> pass.
- **Commit:** `C4d-3 T2b1a: fingerprint_tree`.

### T2b1b `[CODE]` `interpreter_pin` and the `pyvenv.cfg` parser

- **Files:** `benchmark_gate.py` (new section near `_venv_layout` `:2960-3001`; reuse `_venv_layout`, `hash_tree`-style no-timestamp hashing; new `_INTERPRETER_LIMIT = 20_000`, `InterpreterPin(NamedTuple)`);
  `test_benchmark_gate_compare.py`.
- **Failing tests first (spec section 4 row 12, T2b1b):**
  - `test_pin_accepts_homebrew_uv_and_clt_layouts` (the three T2b0 variants return a pin; `home` is resolved by file `realpath(join(home, name)) == realpath(<bin>/python)` with `name` the first
    symlink hop's basename; kills a `home == dirname(realpath)` comparison; fails on base: `AttributeError`).
  - `test_pin_rejects_cfg_faults` (duplicate `home`/`version`/`version_info`/`include-system-site-packages`/`executable`; `include-system-site-packages = true`; version mismatch with the `python3.X` basename;
    `home` that does not resolve to the venv's python; non-UTF-8 cfg; each `VENV_NOT_ISOLATED`; the `command` key and unknown keys ignored; a non-ASCII user home accepted; kills each missing branch).
  - `test_pin_rejects_copies_venv_and_interpreters_inside_the_venv_or_export` (`VENV_NOT_ISOLATED`).
  - `test_startup_probe_catches_a_redirected_home` (a venv whose cfg `home` is redirected to a decoy prefix with its own `os.py`: the `python -I -S` probe's `base_prefix`/`os.__file__` do not match the
    pinned `prefix`/stdlib -> `VENV_NOT_ISOLATED`; kills a pin without the probe; this row uses the real venv python, so it is marked `posix_only`).
  - `test_pin_hash_covers_binary_stdlib_pycache_lib_dynload_prefix_and_lib_files` (editing each of: the binary, a stdlib file, a `__pycache__` file, a `lib-dynload` file, a file directly under `<prefix>`
    (the framework dylib), a `libpython*` under `<prefix>/lib`, a `python3XY.zip` changes `sha256`; editing a `site-packages` file or a file in `<prefix>/lib/x/` deep dir not in the stdlib does not; timestamps do
    not matter; kills each omitted input and the old "exclude `__pycache__`").
  - `test_stdlib_lookup_prefers_lib_then_lib64` and `test_missing_stdlib_is_dest_rejected_and_maps_to_not_provisioned`; `test_over_limit_is_tree_too_large` (entries and hashed bytes).
  - `test_writable_flag` (computed while hashing: a writable pinned file, a writable containing directory, writable `<prefix>` or `<prefix>/lib`, a file owned by the euid; a read-only copy gives `False`).
  - `test_pin_error_mapping_names` (the four codes of 2.5 as raised: `VENV_NOT_ISOLATED`, `TREE_TOO_LARGE`, `DEST_REJECTED`, `TREE_UNREADABLE`).
- **Implement (spec 2.5 "Interpreter"):** `interpreter_pin(bin_dir) -> InterpreterPin(sha256, writable, real_python)` plus the cfg parser (`key = value`, first-two-components of `version`/`version_info`,
  duplicates refused) and the probe (`subprocess.run([bin/python, "-I", "-S", "-c", ...], env=clean env of the side, no shell, bounded output, short timeout)`; the clean environment is `side_env`'s
  allowlist without a scratch dependency: use a dedicated tiny helper). `prefix = dirname(dirname(realpath(python)))`; stdlib = first existing `<prefix>/lib/python<X.Y>`, `<prefix>/lib64/python<X.Y>`.
  The cross-side check (same real interpreter, outside both venvs and both exports) is `compare`'s (T3a), not this function's.
- **Run:** compare test file -> pass.
- **Commit:** `C4d-3 T2b1b: interpreter_pin and pyvenv.cfg parser`.

### T2b1c `[CODE]` `dependency_parity`

- **Files:** `benchmark_gate.py` (new section; reuses `_inside`, `_PTH_MAX_BYTES`; new `_VENV_HASH_BYTES = 1 << 30`); `test_benchmark_gate_compare.py` (this task builds its own `*.dist-info`/RECORD/console-script
  fixture trees under `tmp_path`, not the T2b0 venvs).
- **Failing tests first (spec section 4 row 13, T2b1c):**
  - `test_console_scripts_at_different_paths_pass` (two honest venvs with pip-style dists whose RECORD has `../../../bin/pip` rows hashing differently; passes; kills a raw RECORD comparison).
  - `test_edited_dependency_file_with_intact_record_fails` (`DEPENDENCY_PARITY`; kills a missing on-disk hash verification).
  - `test_bare_module_so_pth_egg_link_and_unlisted_py_fail` (each unowned file in site-packages; a file added inside an owned directory too; kills "top-level entry owned" shortcut).
  - `test_symlink_device_fifo_pyc_and_pycache_fail` (every non-regular entry and any bytecode; kills accepting `__pycache__`).
  - `test_record_row_path_rules` (absolute row never joined, `..` component not leading refused, a leading `../` run dropped; a row with a hash that differs from disk fails; a RECORD-less dist fails).
  - `test_allowed_dist_info_files` (`INSTALLER`, `REQUESTED`, `RECORD`, `direct_url.json`, `distutils-precedence.pth`, `_virtualenv.*` pass; others not).
  - `test_one_exempt_editable_dist_per_side` (`direct_url.json` with `dir_info.editable` and a `file://` url inside that side's export; owns only `*.pth`, `__editable__*`, `_editable_impl_*` and its dist-info; two exempt
    dists, a non-editable project install, a forged-editable extra dist in the head, and an exempt dist owning another file all fail).
  - `test_editable_finder_mapping_is_parsed_with_literal_eval_and_confined` (`MAPPING`/`NAMESPACES` as literals pointing inside the export pass; a computed value, a target outside the export, a symlink escape fail).
  - `test_over_the_hash_budget_is_not_provisioned` and `test_untrusted_text_names_the_differences` (the return value or raised findings carry the differing relative paths, escaped).
- **Implement (spec 2.5 "dependency_parity"):** `dependency_parity(base_bin, head_bin, base_root, head_root) -> list[(detail, text)]` (findings; empty means pass; `NOT_PROVISIONED` is signalled by the
  `_VENV_HASH_BYTES` overrun through a typed finding, mapped by `compare`): `lstat` walk of each venv's site-packages (`_venv_layout` gives the directories) without following links; inventory
  `{relpath: sha256}`; each `*.dist-info/RECORD` parsed with `csv`; ownership check; the two inventories equal over every file except the exempt dist's.
- **Run:** compare test file -> pass.
- **Commit:** `C4d-3 T2b1c: dependency_parity inventory`.

### T2b2 `[CODE]` `_parse_listing_oids`, `verify_export_against_commit`

- **Files:** `benchmark_gate.py` (`_parse_listing` `:1787-1818` stays untouched; new `_parse_listing_oids` beside it; new function in the C4d-3 section; reuses `_PrivateGit` `:1703`, `_MODULE_FILE_RE` `:2667`,
  `_STARTUP_MODULES` `:2662`); `test_benchmark_gate_compare.py` (this task builds its own **sha256-object-format** repository fixture; the sha1 one comes from T2b0).
- **Existing tests:** none edited; `test_benchmark_gate_exports.py:215-232, :701-795, :832-847` (the `_parse_listing` tuple shape and the fake id `abc`) must stay green: run that file.
- **Failing tests first (spec section 4 row 14):**
  - `test_parse_listing_oids_keeps_the_id_for_both_hash_widths_and_listing_is_unchanged` (40 and 64 hex ids validated; a malformed id raises; `_parse_listing`'s output on the same bytes is byte-identical to the base).
  - `test_honest_exports_pass` (the T2b0 export: tracked files, executable bit, a tracked symlink, a gitlink as an empty directory; plus an honest tree with `*.egg-info`, `src/pkg.egg-info`, `build/lib`, `dist/`, `.eggs/`; no findings).
  - `test_tracked_file_differences` (content edit, chmod +x, replaced by a symlink, missing, extra executable bit; each `TRACKED_FILE_DIFFERS`; a tracked symlink whose target changes or escapes the export; a gitlink that is non-empty).
  - `test_untracked_entries` (untracked `hashlib.py`, `.pyc`, `.so`, `.pth`, `.zip`, `.egg`, `.whl`, `sitecustomize.py`, a `__pycache__` directory, a symlink, a fifo, a socket; each `UNTRACKED_PYTHON_FILE`; the same names under root `build/`, `dist/`, `.eggs/`, `<root>/*.egg-info` pass;
    `conftest.py` untracked is rejected; `.env`/`*.json` untracked are not findings (disclosed)).
  - `test_overlay_allowance` (`allow={rel: sha256}`: that exact regular file passes, a changed byte or a symlink does not, nothing else new in the directories the overlay created passes, no allowance for the head).
  - `test_export_applies_no_filters` (a repo with `.gitattributes` `ident`, `eol=crlf`, `working-tree-encoding`: export bytes equal the blob bytes, so the check agrees; for a sha1 and a sha256 repository).
  - `test_honest_install_limits_fail_closed` (one row naming each: a build rewriting a tracked file, an untracked `_version.py`, an in-place `.so`; each fails; the docstring workaround is committed generated files).
  - `test_error_mappings` (raises only for `EXPORT_*`, size (`GIT_OUTPUT_TOO_LARGE`, `TREE_TOO_LARGE`), git and I/O errors; findings are returned, not raised).
- **Implement (spec 2.5 "verify_export_against_commit"):** `verify_export_against_commit(repo, commit, export_root, *, allow=None) -> list[(detail, relpath)]`: listing via `_PrivateGit` (`ls-tree -r -z --full-tree` as `_parse_listing`
  does) into `path -> (kind, oid)`; blob id by `blob <n>\0` framing with sha1 or sha256 chosen by `len(commit)`; exec-bit-only mode compare; walk without following links; allowlists exactly as spec.
- **Run:** compare and exports test files -> pass.
- **Commit:** `C4d-3 T2b2: verify_export_against_commit and _parse_listing_oids`.

### T2c `[CODE]` `snapshot-venv` prints both sha256s; `fake_trace_builder`

- **Files:** `benchmark_gate.py` (`_cmd_snapshot_venv` `:4088-4094`, the `snapshot-venv` subparser help `main()` `:4155-4158`); `test_benchmark_gate_venv.py`; `test_benchmark_gate_compare.py` (`fake_trace_builder`).
- **Existing tests to edit (spec "Existing tests changed", T2c):** `test_benchmark_gate_venv.py:366-370` (`test_cli_snapshot_venv_writes_the_file`): the `world` fixture (`:35-45`) has no `<bin>/python`, so the
  new interpreter pin cannot be computed; give the CLI tests a fixture whose bin has a `python` symlink to a fake prefix (reuse the T2b0 helper) and assert the two new printed lines. The failure test at `:372` keeps
  its expectation (exit 2, code on stderr).
- **Failing tests first (spec section 4: T2c fixtures; the pins the Orchestrator mints):**
  - `test_snapshot_venv_prints_both_pins` (stdout lines `snapshot_sha256: <64 hex>` and `interpreter_sha256: <64 hex>`; the first equals the sha256 of the written file's bytes, the second equals `interpreter_pin(..).sha256`;
    exit 0; kills printing only one, or hashing before the write; fails on base: nothing is printed).
  - `test_snapshot_venv_missing_or_oversized_stdlib_exits_2_with_the_code_on_stderr` (`DEST_REJECTED`/`TREE_TOO_LARGE` text, no snapshot file left, nothing on stdout; see Spec questions, item 5).
  - `test_fake_trace_builder_emits_digest_always_and_trace_result_only_with_trace_env` (the shared fixture: it prints `BENCH_RESULT_DIGEST` on a measure run and writes the nonce-bearing result only when `BENCH_TRACE_*` is in
    the environment; used by T4a2; exercised here against `trace_paired` and `measure_paired` with a real tiny child).
- **Implement:** `_cmd_snapshot_venv` computes `interpreter_pin(args.bin)` **first**, then `snapshot_venv(...)`, then reads the written file once (`_read_bounded`, nofollow), prints `snapshot_sha256: <hex>` and
  `interpreter_sha256: <hex>`; any `BenchmarkGateError` is `_fail`. Update the subparser help and `_cmd_snapshot_venv` docstring. `fake_trace_builder` is a test helper.
- **Run:** `python3 -m pytest skills/loop-task-implementer/tests/test_benchmark_gate_venv.py skills/loop-task-implementer/tests/test_benchmark_gate_compare.py -q` -> all pass.
- **Commit:** `C4d-3 T2c: snapshot-venv prints the snapshot and interpreter pins`.

### T3a `[CODE]` `_compare_checks` (steps 1 to 6) and the signature layer

- **Files:** `benchmark_gate.py` (C4d-3 section: `compare`, `_compare_impl`, `_compare_checks`, `_default_load_probe`; reuses `validate_benchmark_gate` `:337`, `is_ancestor` `:2903`, `export_commit` `:2234`,
  `diff_checks` `:2892`, `check_venv` `:3096`, `_COMMIT_RE`); `test_benchmark_gate_compare.py`.
- **Failing tests first (spec section 4 row 2 for steps 1 to 6; row 10 second half; step-order spy table; row 8 start check):**
  - `test_bad_arguments_raise_before_any_child_or_touch` (one row each: bad `Side` shape or field, `attempt` 0 and 3 (and bool), bad `order_salt` (`""`, uppercase, 65 chars, non-str), bad `out_path` -> `MEASURE_ARGS_INVALID`; bad commit
    -> `COMMIT_INVALID`; unknown commit -> `COMMIT_NOT_FOUND`; the spy proves `_run_once`, `seal_export` and `export_commit` were never called; kills validation after step 1).
  - `test_unsupported_platform_is_a_result_after_arguments_are_validated` (`os.name` patched: result `INCONCLUSIVE/UNSUPPORTED_PLATFORM`, stage `pre_overlay`; bad arguments still raise first).
  - `test_gate_rejected_maps_the_gate_code` (a gate with `warmup_runs: 0`, a bad path, a bad command; `REJECTED/GATE_REJECTED`, detail = gate code; `target = benchmark_target(normalized)`; `harness_sha256` taken).
  - `test_base_not_ancestor_raises` (a head that does not descend from the base -> `BASE_NOT_ANCESTOR`, exit-2 class, after gate validation, before step 4).
  - `test_step4_isolation_rows` (one per `ISOLATION_DETAILS` token of step 4: roots equal or nested -> raises `DEST_REJECTED`; `export_commit != Side.commit` -> raises `OVERLAY_COMMIT_MISMATCH`; `.git` in a root `ROOT_HAS_GIT`; bins shared or inside a root
    `BIN_NOT_ISOLATED`; `NOT_PROVISIONED` (no python / no stdlib); `INTERPRETER_DIFFERS` (different real interpreters on the sides, a `--copies` venv, a probe mismatch); `INTERPRETER_CHANGED` (pin differs from `Side.interpreter_sha256`);
    `INTERPRETER_WRITABLE` without and passing with `allow_writable_interpreter`; `HARNESS_FILE_UNDER_ROOT`; `SNAPSHOT_CHANGED`; `VENV_NOT_ISOLATED`/`VENV_HOOK_REJECTED` from `check_venv`; `DEPENDENCY_PARITY`; `TRACKED_FILE_DIFFERS`;
    `UNTRACKED_PYTHON_FILE`; each `ISOLATION_REJECTED`, stage `pre_overlay`, offending text in `untrusted_text`; hostile-tree errors `EXPORT_REJECTED`; `check_venv`'s `TREE_UNREADABLE`/`DEST_REJECTED` become `ISOLATION_REJECTED/VENV_NOT_ISOLATED`;
    kills a reordered or missing check; the order is asserted with a spy list).
  - `test_diff_checks_results` (`PROTECTED_PATH_CHANGED`, `BENCHMARK_AWARE_CODE`; `GIT_OUTPUT_TOO_LARGE`/`TREE_TOO_LARGE` -> `DIFF_UNCHECKABLE`; `GIT_TIMEOUT`, `GIT_FAILED`, `REPO_UNREADABLE` raise).
  - `test_host_busy_start_leaves_nothing_sealed_and_a_retry_succeeds_on_the_same_exports` (`load_probe` returns `(0.71, 1)`: result `INCONCLUSIVE/HOST_BUSY_START`, stage `pre_overlay`, the exports are still writable and unmodified; then a second call with a quiet probe
    and a new `out_path` gets past step 6; kills a late check; the `0.70` / `0.71` exactness of row 8 is asserted in T4b).
- **Implement:** `compare(...)` forwards to `_compare_impl` with default seams. `_compare_impl` and `_compare_checks` implement 2.4 steps 1 to 6 and the stage rules of the 2.3 table; `_compare_impl` catches `_Verdict`, adds the common fields, writes the
  file (T2a) and returns the dict. **Scaffold, stated here so nobody guesses:** until T3b the code after step 6 is `raise NotImplementedError("steps 7 to 13: T3b/T4")`; T3a tests drive `_compare_checks` directly for passing paths and `_compare_impl` for
  ending paths. The cross-side interpreter equality (same `real_python`, outside both venvs and exports) is checked here from the two `interpreter_of` results.
- **Run:** compare test file -> pass.
- **Commit:** `C4d-3 T3a: _compare_checks, steps 1 to 6`.

### T3b `[CODE]` `_compare_prepare` (steps 7 to 9)

- **Files:** `benchmark_gate.py` (C4d-3 section; reuses `repo_top_levels` `:2427`, `overlay_benchmark_file` `:2589`, `seal_export` `:2403`, `read_benchmark` `:2372`, `validate_benchmark_content` `:783`, `hash_export` `:2416`,
  `gate_sha256` `:3952`); `test_benchmark_gate_compare.py`.
- **Failing tests first (spec section 4 row 2 for steps 7 to 9; section 3 acceptance rows 1 to 3 and the honest-tree row):**
  - `test_overlay_origin_pass_through` (benchmark new in head: `benchmark_origin == "BUILDER_AUTHORED"`; steps 8 and 9 pass with the overlaid file; origin derived by the pipeline, not trusted from the overlay's return value).
  - `test_step7_refusals` (`BENCHMARK_MODIFIED` and `OVERLAY_REJECTED` for the overlay's refusals, `EXPORT_REJECTED` for hostile-tree errors; `OVERLAY_COMMIT_MISMATCH`/`OVERLAY_BASE_SEALED`/`OVERLAY_FAILED` raise; stage `pre_overlay` for a refusal that leaves nothing created,
    `overlaid` after success; `repo_top_levels` is taken at step 7, after the install).
  - `test_step8_unequal_benchmark_bytes` (`ISOLATION_REJECTED/BENCHMARK_BYTES_DIFFER`) and `test_step8_lint_rejected` (`LINT_REJECTED`; `detail` is the first violation in `VIOLATION_CODES` order, the full list in `untrusted_text`).
  - `test_step8_order_is_seal_read_hash_reread` (spy order; the re-read must give the same sha256 else `EXPORT_CHANGED`; `h0` recorded).
  - `test_step9_reruns_the_checks_and_allows_only_the_overlaid_file` (a second untracked `.py` appearing after the overlay, or the overlaid file changed, is `ISOLATION_REJECTED/UNTRACKED_PYTHON_FILE`, stage `overlaid`; a changed snapshot, hook, interpreter, parity
    or tracked file in between each fails with its own detail; the head allowance is empty; `PRE_EXISTING` origin has no allowance at all).
- **Implement:** `_Prepared` (frozen dataclass or NamedTuple: normalized gate, target, benchmark path, origin, `benchmark_sha256`, `h0`, `harness_sha256`, `gate_sha256`; the baseline fields arrive in T4a1) and `_compare_prepare(...)` for steps 7 to 9 exactly as the
  2.4 table. The `NotImplementedError` scaffold moves to after step 9.
- **Run:** compare test file -> pass.
- **Commit:** `C4d-3 T3b: _compare_prepare, steps 7 to 9`.

### T4a1 `[CODE]` step 12 post-run check and the step-9 baseline

- **Files:** `benchmark_gate.py` (`_Prepared` gains `baseline`; new `_baseline_fingerprints`, `_post_run_check`); `test_benchmark_gate_compare.py`.
- **Failing tests first (spec section 4 row 6, T4a1; calling the step-12 helper directly with a mutation hook):**
  - `test_honest_run_leaves_every_fingerprint_unchanged` (baseline, then no mutation: no finding).
  - `test_step12_detects_each_tamper` (one row each, all `ISOLATION_REJECTED`: edit an export file (`EXPORT_CHANGED`); tamper and restore the content and mtime (ctime moves: `EXPORT_CHANGED`); swap a sibling of the dispatch root, edit a sidecar or the marker
    (`EXPORT_CHANGED`/dispatch-root entry rows); add a venv hook and rewrite the snapshot (`SNAPSHOT_CHANGED` first by check order); edit a venv file (`VENV_CHANGED`); edit the (fake) interpreter, including its `__pycache__` (`INTERPRETER_CHANGED`);
    kills each fingerprint input and the check order).
  - `test_step12_check_order` (the first failure names the detail: snapshot pins, interpreter pin, `hash_export` and export fingerprints, `check_venv` and venv fingerprints, `dependency_parity`, `verify_export_against_commit` with the step-9 allowance).
  - `test_step12_error_classification` (`TREE_UNREADABLE` and `HASH_UNREADABLE`, `FINGERPRINT_FAILED` for a venv over `_VENV_FINGERPRINT_LIMIT`, are `ISOLATION_REJECTED`; `GIT_TIMEOUT`, `GIT_FAILED`, `REPO_UNREADABLE` **raise**; `GIT_OUTPUT_TOO_LARGE` from `verify_export_against_commit` is `EXPORT_REJECTED`).
  - `test_baseline_includes_pyvenv_cfg_and_the_snapshot_files` (editing `pyvenv.cfg` after step 9 -> `VENV_CHANGED`).
- **Implement:** `_baseline_fingerprints(...)` (both exports with `_MAX_TREE_ENTRIES`, both venvs with `_VENV_FINGERPRINT_LIMIT`, both snapshot files, the dispatch root: its name list and each non-export entry as `(dev, ino, size, ctime_ns)`, `pyvenv.cfg` sha256 per side)
  stored in `_Prepared`; `_post_run_check(prepared, ...)` recomputes in the order of 2.5 and returns the first `_Verdict`-ready finding or `None`.
- **Run:** compare test file -> pass.
- **Commit:** `C4d-3 T4a1: step 12 post-run check and the step-9 baseline`.

### T4a2 `[CODE]` steps 10 and 11 and the 2.7 mapping rows

- **Files:** `benchmark_gate.py` (`_compare_runs`: `trace_paired` call with `timeout_seconds=per_run_timeout_seconds`; `measure_paired` call with `warmup=warmup_runs`, `repeats`, `order_salt`, `min_base_ns`, and `argv_builder`; a `_map_trace_error` and `_map_measure_error`
  pair); `test_benchmark_gate_compare.py`.
- **Failing tests first (spec section 4 rows 2 (steps 10, 11), 4 and 6 second half):**
  - `test_row_T1_and_M4_raise` (`trace_paired` raising `MEASURE_FAILED`/`MEASURE_ARGS_INVALID`; `measure_paired` the same; exit-2 class; step 12 does not run; kills mapping them to a result).
  - `test_row_T2_trace_unavailable` (both sides the same token: `INCONCLUSIVE/TRACE_UNAVAILABLE`, stage `ran`, `trace` in the result, step 11 not run, `HOST_BUSY_END` not probed).
  - `test_row_T3_spawn` (`kind == "spawn"` from `trace_paired` and from `measure_paired`: `ISOLATION_REJECTED/NOT_PROVISIONED`, stage `ran` even though no child ran; the test uses an `argv_builder` that names a nonexistent executable, because a missing `<bin>/python` is already caught at step 4 and the
    acceptance row "spawn failure with `ENOENT`" needs a spawn that fails after it) and `test_spawn_errno_split` (`EAGAIN` and `None` -> exit 2; `ENOENT` -> result).
  - `test_row_T4_by_side_and_trace_fault` (trace kinds `nonzero`, `timeout`, `oversize` for the head give `NOT_IMPROVED/HEAD_NONZERO_EXIT`, `HEAD_TIMEOUT`, `HEAD_OUTPUT_TOO_LARGE` with `trace_fault: "head"`; for the base `REJECTED/BASE_NONZERO_EXIT`, `INCONCLUSIVE/BASE_TIMEOUT`,
    `BASE_OUTPUT_TOO_LARGE` with `trace_fault: "base"`; `detail` names the kind).
  - `test_row_T5_counts_differ_is_pending` (measure still runs; `trace_mismatch_seen`; the pending state is recorded for T4b's list).
  - `test_row_T6_at_once` (each of `plugin_failed`, `no_result`, `unavailable_one_side`, `unavailable_tokens_differ`, `unavailable_interpreters_differ`, `interpreters_differ`: `REJECTED/TRACE_MISMATCH`, step 11 not run).
  - `test_rows_M1_M2_M3` (`BASE_NONZERO_EXIT`, `DIGEST_MISSING`, `DIGEST_UNSTABLE`, `WORKLOAD_TOO_SHORT` -> REJECTED; `HEAD_NONZERO_EXIT`, `HEAD_TIMEOUT`, `DIGEST_MISMATCH`, head `OUTPUT_TOO_LARGE` -> `NOT_IMPROVED` (`HEAD_OUTPUT_TOO_LARGE`);
    `BASE_TIMEOUT`, base `OUTPUT_TOO_LARGE` -> INCONCLUSIVE).
  - `test_dispatch_order` (`error.code` first for T1/M4 (`kind` `harness` or null), then `kind == "spawn"` for `trace_paired` and the `*_NONZERO_EXIT` codes of `measure_paired`, then `error.code`, then `side`; a `HEAD_NONZERO_EXIT` that carries `kind == "spawn"` is T3, not M2; kills a code-first dispatch).
  - `test_step12_through_a_real_child` (spec row 6 "the same through real children", T4a2 half): a real tiny pytest child run through `_compare_runs` that edits an export file; result `ISOLATION_REJECTED/EXPORT_CHANGED`. (A second real-child row of the same kind, venv hook plus rewritten snapshot, lands in T6.)
  - `test_step12_runs_after_every_path_that_started_a_child` (each ending above also gets its step-12 check; a mutation hook in a fake child proves it).
- **Implement:** `_compare_runs` steps 10 and 11 and the mapping of 2.7 up to (not including) the precedence merge: it returns a small `_RunOutcome` (trace outcome, measure outcome or error, pending trace error) that step 13 (T4b) merges; until T4b, `_compare_runs` maps outcomes with the
  precedence list's items 2 and 3 only and `raise NotImplementedError` for items 4 to 6 (statistics path). Honour: the argv builder is passed to both calls; `order_salt=None` in `_compare_impl` generates `os.urandom(8).hex()` and records it.
- **Run:** compare test file -> pass; also measure and trace files (the call sites changed).
- **Commit:** `C4d-3 T4a2: steps 10 and 11 and the trace/measure mapping rows`.

### T4b `[CODE]` step 13: precedence, `HOST_BUSY_END`, statistics, coverage

- **Files:** `benchmark_gate.py` (`_compare_runs` step 13; `_host_state`/probe helpers; `_improvement` from `_ratio_stats`); `test_benchmark_gate_compare.py`.
- **Failing tests first (spec section 4 rows 3, 5, 8; section 3 acceptance rows):**
  - `test_precedence_every_adjacent_pair` (items 0 to 6 of 2.7: a raise beats a step-12 `ISOLATION_REJECTED`; step 12 beats a T2/T3/T4/T6 result (and its detail wins over a T3); T2/T3/T4/T6 beat a measure REJECTED/NOT_IMPROVED; a measure REJECTED/NOT_IMPROVED beats a pending
    `TRACE_MISMATCH` and sets `trace_mismatch_seen: true`; a pending `TRACE_MISMATCH` beats a measure INCONCLUSIVE (measured data stays, `HOST_BUSY_END` not probed); a measure INCONCLUSIVE beats the statistics; one test row per adjacent pair, built from fakes).
  - `test_acceptance_trace_rows` (counts differ with matching digests -> `REJECTED/TRACE_MISMATCH`; counts differ and digests differ -> `NOT_IMPROVED/DIGEST_MISMATCH`, `trace_mismatch_seen`; counts differ and the base times out -> `REJECTED/TRACE_MISMATCH`; head exits non-zero in the trace run ->
    `NOT_IMPROVED/HEAD_NONZERO_EXIT`, `trace_fault: "head"`; both sides unavailable -> `INCONCLUSIVE/TRACE_UNAVAILABLE`).
  - `test_statistics_and_verdict_rows` (fix halves the work: `IMPROVED/IMPROVED_CLEAR`, `improvement = 1 - median(ratios)`, `ratios`, `mad_over_median`, raw `base_ns`/`head_ns`; head slower -> `NOT_IMPROVED/BELOW_HALF_THRESHOLD`; noisy -> `NOISY`; also `INCONSISTENT`, `BORDERLINE`).
  - `test_invalid_input_via_monkeypatched_evaluate` (`evaluate_paired_samples` patched to return `INVALID_INPUT`: `INCONCLUSIVE/INVALID_INPUT`, never replaced by `HOST_BUSY_END`).
  - `test_host_busy_end` (an `IMPROVED`, a `NOT_IMPROVED` and an INCONCLUSIVE from evaluate become `INCONCLUSIVE/HOST_BUSY_END` when busy; with a pending trace mismatch the mismatch stands; not probed on at-once results).
  - `test_host_busy_arithmetic` (spec row 8: load `0.70` vs `0.71` at `cpu_count` 1 with `Fraction(str(load1))`; `cpu_count` 2 skips the end check (`end_skipped_few_cpus`); own-load subtraction `(load1 - 1) * 10 > 7 * cpu_count` at 3 or more CPUs;
    probe raising, `nan`, `inf`, negative, `bool`, non-real load and non-positive `cpu_count` -> `host_check: "skipped_probe_failed"` with both checks skipped; `host_check` values `checked`, `end_skipped_few_cpus`, `start_only`, `skipped_probe_failed`; `loadavg` and `cpu_count` objects with `end: null` when not probed).
  - `test_coverage_every_code_is_mapped_or_deliberately_raised` (all of `MEASURE_REFUSAL_CODES`, `TRACE_REFUSAL_CODES`, `TRACE_FAILURE_KINDS` including `harness`, and every `evaluate_paired_samples` reason appears in `COMPARE_RESULT_OF_REASON` or in an explicit raises list; kills a forgotten code).
  - `test_stage_of_every_step_ending` (the 2.3 table asserted for each ending, one parametrized row per step-ending; T3a/T3b rows assert their own, this one asserts the table whole).
  - `test_one_row_per_reason` (every reason of 2.3 not listed in section 3 is produced at least once through `_compare_impl`; kills an unreachable reason) and `test_gate_sha256_equals_validate_s` (the result's `gate_sha256 == gate_sha256(normalized)`).
- **Implement:** step 13 exactly as the 2.7 list; replaces the T4a2 `NotImplementedError`s; `_compare_impl` no longer has any scaffold. Host checks per 2.6 with `Fraction(str(load1))`, `_HOST_BUSY_MIN_CPUS = 3`, the default `load_probe` (`os.getloadavg()[0]` and `len(os.sched_getaffinity(0))` where present, else `os.cpu_count() or 1`).
- **Run:** compare test file -> pass; measure, trace files -> pass.
- **Commit:** `C4d-3 T4b: precedence list, host checks, statistics, coverage`.

### T5a `[CODE]` `_run_once` signal masking and child restore, CLI handler helper

- **Files:** `benchmark_gate.py` (`_run_once` `:3519-3559`: the comment at `:3534`; new `_with_signal_handlers` context helper modelled on `_cmd_cleanup` `:4103-4130`); `test_benchmark_gate_measure.py` (library-level tests; a real child).
- **Failing tests first (spec section 4 row 15, T5a half):**
  - `test_child_signals_are_default_and_mask_is_empty` (a real child prints `signal.getsignal` for TERM, HUP, INT and `signal.pthread_sigmask(SIG_BLOCK, [])`: all `SIG_DFL`/empty, while the parent has them ignored and masked at `Popen` time (a `preexec_fn`-observing stub or a wrapper
    around `subprocess.Popen` records the parent's mask during the call); kills "child inherits ignored signals").
  - `test_signal_during_a_run_kills_the_childs_process_group` (send SIGTERM to a CLI-helper-wrapped call while a child with a grandchild sleeps; the group is gone; `KeyboardInterrupt` is raised once, the second signal is ignored; kills a masked window that never unmasks).
  - `test_handlers_are_restored_in_finally` (previous handlers back after normal return, an exception, and `KeyboardInterrupt`).
  - `test_library_caller_on_another_thread_gets_no_handlers` (the helper is not installed by `compare`/`_run_once` themselves; installing from a non-main thread is not attempted).
- **Implement (spec "Signals (T5a)"):** `_run_once` masks SIGTERM, SIGHUP, SIGINT with `signal.pthread_sigmask(SIG_BLOCK, ...)` around `Popen`, a `preexec_fn` that restores `SIG_DFL` and an empty mask (it keeps the `RLIMIT_FSIZE` work), enters the `try`, then unmasks; `signal` and `pthread_sigmask` are imported in the parent before the fork; the
  comment at `:3534` states "single-threaded" as a contract (not asserted). `_with_signal_handlers()` (main thread only, used by CLI commands): SIGTERM/SIGHUP/SIGINT handler raises `KeyboardInterrupt`, sets `SIG_IGN` for the rest on the first signal, restores in `finally`.
- **Run:** measure test file -> pass (all existing run-once tests still pass).
- **Commit:** `C4d-3 T5a: signal masking around Popen, child restore, CLI handler helper`.

### T5b `[CODE]` CLI `compare` and `run-once`, crash contract, `RESULT:` line

- **Files:** `benchmark_gate.py` (`main()` `:4133-4174` new subparsers and docstring; new `_cmd_compare`, `_cmd_run_once`; `_read_bounded` `:3958` for `--gate`); `test_benchmark_gate_compare.py`.
- **Failing tests first (spec section 4 rows 9 and 15 (T5b half)):**
  - `test_cli_result_line_and_exit_codes` (the `RESULT: <result> <reason> interpreter_writable=<0|1|n/a> sha256=<hex of the written bytes>` line printed after the file exists, closed sets only; exit 0 iff `IMPROVED`, 1 for any other result, 2 for usage, a raise or a crash; a reader that hashes the file bytes
    matches the RESULT sha256; `interpreter_writable=1` with `--allow-writable-interpreter`, `n/a` for a step-1 ending).
  - `test_exit_1_without_a_valid_result_line_is_not_a_result` (documents the contract by a helper `parse_compare_outcome(returncode, stdout, file_bytes)`, which treats exit 1 without RESULT line and matching sha as exit 2; kills the Python-uncaught-exception-is-1 hole).
  - `test_injected_runtime_error_is_exit_2_with_no_json` (a `RuntimeError`, `OSError`, `ValueError`, `RecursionError`, a generic `Exception` and a `KeyboardInterrupt` raised inside `compare`: prints `usage error: <CODE or INTERNAL>: <type>`, never attacker text, returns 2, writes nothing, the sealed exports stay sealed and `cleanup` restores them).
  - `test_sigterm_kills_the_childs_group_and_exits_2` (real CLI subprocess, as 15 says: SIGTERM mid-run; no JSON; the child's group is gone).
  - `test_run_once_cli` (spec 2.9: `--side` default `head`, no ini option; exit 0 prints `digest: <64 hex>`; exit 1 prints the reason (`<SIDE>_NONZERO_EXIT`, `<SIDE>_TIMEOUT`, `OUTPUT_TOO_LARGE`, `DIGEST_MISSING`, `REJECT:<gate code>`) and the escaped detail on stderr; exit 2 for usage or crash; a gate with `warmup_runs: 0` prints `REJECT:BOUNDS_REJECTED`).
  - `test_cli_arguments_are_the_spec_ones` (every flag of the 2.9 synopsis exists and is required where the spec requires it; `--attempt` default 1; `--allow-writable-interpreter` a flag).
- **Implement:** `_cmd_compare` builds `Side` tuples, reads `--gate` bounded (`_read_bounded`, raw JSON, not the whole specialist inputs), calls `compare` under `_with_signal_handlers`, prints the RESULT line from the written file's bytes; `_cmd_run_once` calls `validate_benchmark_gate` and
  `benchmark_target`, then `run_benchmark_once` under the same helper; both catch `BenchmarkGateError`, `OSError`, `ValueError`, `RecursionError`, `Exception` and `KeyboardInterrupt` as in 2.9. Update the `main()` docstring and the parser description; remove the "no catch-all on purpose" sentence (the commands own it now).
- **Run:** compare and measure test files -> pass; `bg.main` smoke for the existing six subcommands (core/exports/venv files).
- **Commit:** `C4d-3 T5b: CLI compare and run-once, crash contract, RESULT line`.

### T6 `[CODE]` real-pytest rows, acceptance figures, recompile calibration

- **Files:** `test_benchmark_gate_compare.py`; `benchmark_gate.py` only if a real run exposes a defect (fix it here and say so in the commit body).
- **Tests (spec section 4 rows 6 (real children) and 17; section 3 acceptance):** two real-pytest rows through `_compare_impl` with a lowered `min_base_ns`, using `allow_writable_interpreter=True` or the `interpreter_of` seam (CI interpreters are runner-writable):
  - `test_real_improved_overlay_origin` (a fix that halves the work with the benchmark new in head: `IMPROVED/IMPROVED_CLEAR`, exit-0 class, JSON with every 2.8 key, steps 9 and 12 pass with the overlaid file, every fingerprint unchanged; a lower-bound assertion on `improvement`, not equality);
  - `test_real_not_improved_pre_existing_benchmark` (benchmark present at base: `NOT_IMPROVED` for an unchanged head).
  - Real-child tamper rows (spec row 6 "the same through real children"): a head child that adds a venv hook and rewrites the snapshot (`SNAPSHOT_CHANGED`), edits the (fake) interpreter (`INTERPRETER_CHANGED`), edits then restores an export file (`EXPORT_CHANGED`), and a child that rewrites its `empty.ini` or plants a file under `work` (no effect, section 3).
- **Calibration (recorded, not asserted):** run the two real rows ten times; record `improvement`, the base median, the recompile constant (project plus dependency bytecode compiled on every run on both sides, `PYTHONDONTWRITEBYTECODE`) and the runtime of the rows, in the commit body and the
  PR body. Spec section 3 says the figures are "unverified until then": if a figure cannot be produced, say so; do not loosen a threshold.
- **Run:** compare test file -> pass (the real rows take seconds to a minute each).
- **Commit:** `C4d-3 T6: real-pytest compare rows and calibration figures`.

### T7 `[DOCS-ONLY]` docs and pins

- **Files:** `benchmark_gate.py` (docstrings and comments only); test module docstrings; `test_benchmark_gate_compare.py` (the pins).
- **Do (spec section 5, plus the one addition in Spec questions, item 1):** `main()` docstring; the module docstring (a section index; rewrite the "still to come (C4d-3)" sentence and the calling-order paragraph, `:6-26`, so it matches 2.4 and the head-first provisioning of 2.5); the `ERROR_CODES` comment (`HOST_BUSY_*` and the rest are reasons, not exceptions); the
  `validate_benchmark_gate` docstring (`:346-348`, done in T0a: only re-read); the docstrings of `run_order`, `measure_paired`, `trace_paired`, `_prepare_run`, `_execute`, `_run_once`, `side_env`; the `BenchmarkGateError.kind` comment (`:911`, no longer "trace_paired only"); the `snapshot-venv`
  help text and docstring; the `repo_top_levels` docstring (`:2427-2433`) and the `overlay_benchmark_file` docstring (`:2589-2600`) so they state that `compare` takes `repo_top_levels` after the install (and that `build/` and `dist/` joining the allowlist is harmless and disclosed). `workflow/*` is not touched (C4e). Test-file docstrings (compare, measure, trace, venv, exports).
- **Pins (green on arrival; prove each non-vacuous by a temporary mutation, then revert; spec section 4 row 18):** `test_main_registers_compare_and_run_once` (subparsers exist), `test_cli_path_uses_default_seams` (the CLI calls `compare`, whose default seams are used: `argv_builder`, `load_probe`, `order_salt`, `interpreter_of` all unset), `test_generated_salt_is_random_and_recorded`
  (two `_compare_impl` calls without a salt record different `order_salt` values; the recorded salt reproduces the `order`).
- **Run:** `make lint-static` -> exit 0; compare, measure, trace, venv, exports files pass.
- **Commit:** `C4d-3 T7: docs and pins for compare and run-once`.

### T8 `[CONTROLLER]` gates, reviews, PR

Not for an implementer. The controller runs the full benchmark-gate set (background), `make lint-static`, `graphify update .`, the whole-branch adversarial review rounds until clean, commits any fixes, pushes, opens the PR (body: scope, "Snyk Code scan not run: not enabled for
the org", the disclosed residuals of 2.5 and 2.5b, the honest-install limits, the T6 figures, the parent-design deviations of spec section 9 to be written back in C4e, what is not in scope), and checks CI.

## Dependency audit

| Task | Reads a prior task's output / edits the same file or section? | Depends on |
|---|---|---|
| T0a | `validate_benchmark_gate`, `_evaluate`; edits three core tests | none |
| T0b1 | `run_order`, `_run_once`, `_SpawnFailed`, `_execute`, `measure_paired` `adapt`; keeps two tests valid by the errno default | none |
| T0b2a | `_prepare_run`, `side_env`, `measure_paired`, `trace_paired`; edits eight existing tests | T0b1 |
| T1 | `_check_sides`, `_prepare_run` (new signature), `_run_error_code` | T0b2a |
| T2a | new section; creates the compare test file; edits the exports pin | T0a |
| T2b0 | compare test file (fixtures); real exports and venv helpers | T2a |
| T2b1a | new section (`fingerprint_tree`) | T2b0 |
| T2b1b | new section (`interpreter_pin`); `_venv_layout` | T2b0 |
| T2b1c | new section (`dependency_parity`); `_venv_layout` | T2b0 |
| T2b2 | `_parse_listing` neighbourhood and new section | T2b0 |
| T2c | `_cmd_snapshot_venv`; uses `interpreter_pin`; edits venv tests; adds `fake_trace_builder` used by T4a2 | T2b1b, T0b2a |
| T3a | `compare`, `_compare_impl`, `_compare_checks`; uses T2a, T2b1a-c, T2b2, T2c | T2b1a, T2b1b, T2b1c, T2b2, T2c |
| T3b | `_compare_prepare`, `_Prepared`; moves the `NotImplementedError` scaffold | T3a |
| T4a1 | `_Prepared.baseline`, `_post_run_check`; uses `fingerprint_tree` | T3b |
| T4a2 | `_compare_runs`; uses T0b1 `kind`, T0b2a, `fake_trace_builder`, T4a1 | T4a1, T0b2a |
| T4b | step 13; removes the T4a2 scaffold; uses `_ratio_stats` (T0a) | T4a2 |
| T5a | `_run_once` (same function as T0b1 edited); CLI helper | T4b |
| T5b | CLI; uses T1 `run_benchmark_once`, T5a helper, T2a writer | T1, T5a |
| T6 | everything; may edit `benchmark_gate.py` | T5b |
| T7 | docstrings in the file edited by all prior tasks | T6 |
| T8 | everything | T0a to T7 |

Hidden edges checked: the `ERROR_CODES` pin lands with the new code (T2a); the five `side_env`/scratch/pycache test edits land with the behaviour change (T0b2a); the `warmup_runs` test edits land with the bound (T0a); `kind` is added before anything reads it (T0b1 before T4a2); `_prepare_run`'s signature
changes before `run_benchmark_once` is written (T0b2a before T1); the `snapshot-venv` fixture update lands with the printing (T2c); the `NotImplementedError` scaffold is introduced in T3a and removed by T4b, never committed past it; the docs follow the code they quote (T7 last).
**Waves:** none can run in parallel (one source file): W0 T0a, W1 T0b1, W2 T0b2a, W3 T1, W4 T2a, W5 T2b0, W6 T2b1a, W7 T2b1b, W8 T2b1c, W9 T2b2, W10 T2c, W11 T3a, W12 T3b, W13 T4a1, W14 T4a2, W15 T4b, W16 T5a, W17 T5b, W18 T6, W19 T7, W20 T8. (The spec notes T0a/T0b1 and T1/T2a are independent; they are
serialized anyway.)

## Self-review

- **Spec coverage:** 2.1 and 2.3 -> T2a, T3a, T3b, T4a2, T4b; 2.2 -> T2a, T3a; 2.4 steps 1 to 6 -> T3a, 7 to 9 -> T3b, 10 and 11 -> T4a2, 12 -> T4a1, 13 -> T4b; 2.5 interpreter -> T2b1b, parity -> T2b1c, `verify_export_against_commit` -> T2b2, fingerprint -> T2b1a, baseline and step 12 -> T4a1;
  2.5b and "Spawn failures" -> T0b2a, T0b1; "Signals" -> T5a; 2.6 -> T4b; 2.7 -> T4a2, T4b; 2.8 -> T2a; 2.9 -> T2a (writer), T5b (CLI), T1 (`run_benchmark_once`); 2.10 -> T0a; section 3 acceptance rows -> T3a, T3b, T4a1, T4a2, T4b, T6; section 4 rows 1 to 18 -> T2a, T3a/T3b/T4a2, T4b,
  T4a2, T4b, T4a1 and T4a2/T6, T0b2a, T4b, T5b, T0a and T3a, T2b1a, T2b1b, T2b1c, T2b2, T5a/T5b, T1, T6, T2a/T7; "Existing tests changed" -> T0b1, T0b2a, T0a, T2a, T2c, T2b2 as the spec lists; section 5 -> T7.
- **Placeholders:** none; every task names files, the failing tests with the mutant they kill, the implementation rule and a command. (Historical: the one scaffold, `NotImplementedError` between T3a and T4b, was declared with an owner and has since been removed; see the note at the top.)
- **Name consistency:** `Side`, `_Verdict`, `COMPARE_RESULT_OF_REASON`, `ISOLATION_DETAILS`, `COMPARE_DETAIL_TOKENS`, `compare`, `_compare_impl`, `_compare_checks`, `_compare_prepare`, `_compare_runs`, `_Prepared`, `interpreter_pin`, `InterpreterPin`, `dependency_parity`, `fingerprint_tree`,
  `verify_export_against_commit`, `_parse_listing_oids`, `run_benchmark_once`, `_check_one_side`, `benchmark_target`, `_ratio_stats`, `_run_error_code`, `_prepare_run`, `_SpawnFailed`, `_INTERPRETER_LIMIT`, `_VENV_FINGERPRINT_LIMIT`, `_VENV_HASH_BYTES` are used identically in the spec and here.

## Spec questions

None changes the design; each is recorded for the controller to confirm.

1. **A docstring the spec's section 5 does not list contradicts step 7.** `repo_top_levels` says "Compute it from the BASE export BEFORE `overlay_benchmark_file` and before any build step that could create `build/`, `dist/` or `venv/`" (`benchmark_gate.py:2430-2432`), and the module docstring's calling order puts `repo_top_levels(base)` before the install (`:15-16`); spec 2.4 step 7
   takes it after the install on purpose. The module docstring is in section 5; the `repo_top_levels` docstring is not. T7 adds it. No design change.
2. **Spec 2.1 cites `GIT_OUTPUT_TOO_LARGE` at `diff_checks` `:894`.** Line 894 is the constant `_GIT_OUTPUT_CAP`; the raise comes from `_PrivateGit.run` with that cap (`:1759`, used by `_diff_findings` `:2738-2741`), and `TREE_TOO_LARGE` is at `:2720-2721`. The mapping is feasible as written; tests use the real codes.
3. **Test-row tags versus the producing task.** Spec section 4 tags row 3 ("one row per vocabulary entry", the stage of every step-ending) to T4b, but reasons that end at steps 1 to 9 first become runnable in T3a/T3b (row 2 tags them there). The plan writes the ending's own test with the producing task (T3a, T3b, T4a1, T4a2) and puts the whole-table checks
   (`test_one_row_per_reason`, `test_stage_of_every_step_ending`, the coverage test) in T4b, as the spec tags them. Nothing is dropped; no row is duplicated by name.
4. **A scaffold is needed between T3a and T4b.** The task table has `compare` incomplete until step 13 (T4b), yet T3a-T4a2 must be green and committed. The plan uses a declared `raise NotImplementedError` after the last implemented step, moved forward by each task and removed by T4b; tests before T4b drive the step functions and `_compare_impl` only for
   ending paths. The CLI does not exist until T5b, so nothing can reach the scaffold.
5. **`snapshot-venv` ordering.** Spec 2.9/2.5 say `snapshot-venv` prints both pins and that a missing or oversized stdlib "exits 2 with the code on stderr", but not the order. T2c computes `interpreter_pin` before writing the snapshot, so a failure leaves no snapshot file behind (`snapshot_venv` refuses an existing `out_path`, `benchmark_gate.py:3032-3035`, so a leftover
   file would block the Orchestrator's retry). Confirm.
6. **`BenchmarkGateError.kind` comment and `trace_paired` docstring.** `kind` is documented "trace_paired only" (`:911`) and `trace_paired` says "Every error carries `kind`" (`:3860`); after T0b1 measure errors carry it too. Covered by section 5's `:911` item and the `trace_paired`/`measure_paired` docstring items; noted so T7 does not miss the `trace_paired` sentence "(None for every other error)".
7. **Line anchors in spec section 4 are approximate where it says "about".** `test_benchmark_gate_exports.py:461-467` (the `ERROR_CODES` pin) is at `:461-466` on the base; `test_benchmark_gate_core.py:474-475` are the `warmup_runs: -1/3` rows (`warmup_runs: 0` is not in the rejected list yet, which T0a adds). All other cited test lines (`measure.py:79-86, :243, :360-380, :384-389, :599-613, :661-665, :678`;
   `trace.py:1081, :1822, :894, :900`; `venv.py:366-370`) were opened and match.
