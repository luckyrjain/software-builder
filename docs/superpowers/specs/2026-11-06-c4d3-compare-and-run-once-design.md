# C4d-3: `compare`, `run-once` and the verdict mapping (rev 7: design review rounds D1 to D6; implementation review rounds I1 to I8 follow it)

Ticket C4 (performance-review to loop-task-implementer benchmark gate), sub-ticket C4d-3. Base `2dc72667` (C4d-2, #367, merged).
Parent design (untracked in the main checkout, read there): `docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md`,
rows "Measurement harness", "`compare(...)`", "Outcome mapping", "Capacity", tests rows 2 and 2b. Sibling spec:
`2026-11-05-c4d2-trace-plugin-and-runs-design.md` (its section 1 lists eleven deviations from the parent; this spec resolves 8, 9 and 11; the
rest, and section 9 below, go to the C4e docs write-back).

## Revision history

Two sequences, never to be confused: the **design rounds D1 to D6** (revisions 1 to 7, before any code) and the **implementation review rounds
I1 to I8** (after the code existed). Commit names use "round N" for implementation round I<N> (`C4d-3 round N: fix review findings`); a design round D<N> is never a commit.

### Design rounds D1 to D6 (revisions 1 to 7)

- rev 1 to 4: design rounds D1 to D3. Result-or-raise split, one precedence list, ctime fingerprint, snapshot pin, per-run scratch/ini (the shared work
  directory was a writable channel), `untrusted_text`, crash contract, head-first provisioning, `verify_export`, stage table.
- rev 5 (D4: 1 blocker, 10 majors): overlay allowance (every PR adding its benchmark was rejected), `pyvenv.cfg` pin, dependency parity, tracked
  symlinks, errno classification, salt semantics, re-derived test fallout.
- rev 6 (D5: 2 blockers, 7 majors): **dependency parity** compared a RECORD hash that differs between any two honest venvs (console scripts
  embed the venv path) and verified no file: now it excludes `../` rows, verifies every hashed row against disk, and requires every top-level
  site-packages entry to be owned by a verified RECORD; the **`home` check** failed on Homebrew, uv and Xcode CLT venvs: now it resolves
  `home/<name>`; `version_info` accepted; the interpreter pin now includes `__pycache__`, the files directly under `<prefix>` and `<prefix>/lib` (the
  framework dylib, `libpython`, `python3XY.zip`) and a **writable interpreter needs `--allow-writable-interpreter`** (shown in the `RESULT:` line);
  `_SpawnFailed` errno plumbing specified; test tags, fixtures and the task graph re-cut (no circular edge); stale citations fixed.
  **Scope statement**: `compare` is a mechanical filter that raises the cost of forging a result; the control the parent relies on is the human
  acceptance of every `IMPROVED`. The spec pins what can be pinned before the install, checks what can be checked cheaply, requires a provisioning
  contract of C4e, and records the rest as residuals.
- rev 7 (D6, the last allowed; applied without a further round): `dependency_parity` became a full site-packages **inventory** (every file hash-verified
  or allowlisted, no symlinks, no bytecode, one exempt editable dist limited to its own names with its finder mapping parsed and confined to the export);
  the interpreter pin gained a **start-up probe** (`python -I -S`) because CPython finds the stdlib from `pyvenv.cfg` `home`; error codes of the
  interpreter helper named; `pyvenv.cfg` in the baseline fingerprint; `interpreter_writable=n/a`; the editable-finder, bytecode and `.egg-link`
  residuals settled; minors from the Software Architect (CLEAN) applied. Open risk accepted knowingly: no seventh review round.

### Implementation review rounds I1 to I8

- I1 (implementation round 1): the `compare` CLI no longer re-reads the result file (the `RESULT:` line, the exit code and `interpreter_writable` come
  from the in-memory result and the sha256 `_write_result` returned; `_compare_impl` returns a `dict` subclass carrying `written_sha256`); the signal
  table is built lazily (imports without `SIGHUP`); `_run_once` kills the process group in its own `finally`; one `COMPARE_REASONS` table with the
  derived vocabularies; invariant asserts became `BenchmarkGateError(MEASURE_FAILED)`; wait-floor wording with the per-git-invocation caveat;
  `dependency_parity` keeps `NOT_PROVISIONED` outside the capped findings; step 12 maps `TREE_TOO_LARGE` from `check_venv` to `VENV_CHANGED`.
- I2 (implementation round 2, wording only): the retry rule is keyed on `(reason, stage, detail)` (2.3); the provisioning contract no longer orders
  bytecode removal before the pin (the pins precede the install, the removal follows it; 2.5 step 5b); step 12's `EXPORT_REJECTED` also beats everything
  (2.4, 2.7 item 1); security round 2: the dispatch root, both exports, both bin directories and both venv roots are bound by `(st_dev, st_ino)` at
  the step-9 baseline and re-checked before EVERY spawn (2.5, "Directory identity"); the dispatch root's ctime joins the dispatch state; the runs get
  the step-9 resolved roots and bins; `_result_dict` allowlists `kind`, `trace_fault`, `side`, `phase`, `host_check`, `benchmark_origin`; the result
  file is linked with `follow_symlinks=False`.
- I3 (implementation round 3, wording only): the retry column of 2.3 means "the same-exports retry can change the outcome" and the rule is the
  machine-readable constant (split in I5 into `COMPARE_RETRYABLE_AUTOMATIC` and `COMPARE_RETRYABLE_WITH_HUMAN_FLAG`); the spawn guard also takes the root it spawns in, keeps the sealed roots' ctime, runs again when an
  argument check fails after a child ran, and its exception is not a `BenchmarkGateError`; a `.pth`/finder path through a link the user owns is refused;
  the dispatch listing is bounded.
- I4 (implementation round 4): the residuals numbered 1 to 9 the same in the module docstring, the `compare` docstring and 2.5 (pinned by a test), the
  provisioning contract and section 9 gain "pin the expected `harness_sha256`" and "project venv CPython >= 3.12"; a `.pth`/editable-finder target is
  judged on its RAW text (non-normal targets refused) and no alias is trusted when the euid is 0; the codecs are looked up at import; old-git skips
  fail under `CI`; the `EXPORT_CHANGED` result carries `side`, `phase`, `partial`.
- I5 (implementation round 5): `harness-sha256` subcommand and the rule that the expected digest comes from a TRUSTED copy (2.5 item 6); the retry rule
  split into two constants (2.3); `allow_abbrev=False` and the exit-0-needs-a-RESULT-line reading (2.9); the residuals carry stable labels `[R1]` to
  `[R9]` (nine then; twelve since I6) (2.5); a link is trusted only in a directory only root can change, with one name ("Directory identity"); the euid 0 consequence (2.5, 9); the
  probe wording (2.4, 2.2); `busy_end` is probed on every measured path except `INVALID_INPUT`, which is never replaced and so never probed (2.6); one snapshot size limit.
- I6 (implementation round 6): a link is trusted only in a ROOT-OWNED directory whose every ancestor is closed too (2.5 "Directory identity"); `snapshot-venv`
  removes an oversize snapshot it just wrote; the euid-0 consequence (`INTERPRETER_WRITABLE` on every compare) is documented (2.5 item 9, 9.8); residuals
  `[R10]` to `[R12]` join the list (2.5); the provisioning contract, 9.8 and the module docstring carry the same item set (pinned by a test); the 9.12 wait
  floor names the probe term; `parse_compare_outcome` is the public reference reader (2.9); the crash contract is stated per subcommand (2.9).
- I7 (implementation round 7, commit `C4d-3 round 7: ...`): `format_result_line` is the one builder of the `RESULT:` line and `parse_compare_outcome` also checks `interpreter_writable=` against the file
  (`n/a` is the file's `null`), survives deeply nested JSON and requires an int exit code; the retry budget and `attempt` semantics are stated (2.3, 9); a trusted link's ancestors must be OWNED by the trusted uid
  and a root-owned sticky ancestor is accepted whatever the euid can write (2.5 "Directory identity"); `_write_json_atomic` creates its final name with `link` (never overwrites); the known
  environment refusals of the alias rule are listed (2.5 item 9).
- I8 (implementation round 8, commit `C4d-3 round 8: ...`): the allowed re-measure list is restored to the parent design's `NOISY`, `INCONSISTENT`, `BORDERLINE` (I7 had derived it from the stage column of `COMPARE_REASONS`, an undeclared widening); the allowance and the busy-start retry scope are stated; the list test now parses the list and requires an exact match.

## 1. Premise check (read against `2dc72667`)

| Claim | Evidence |
|---|---|
| Every building block `compare` needs exists and is library-only | `benchmark_gate.py`: `validate_benchmark_gate` `:337`, `is_ancestor`, `diff_checks`, `export_commit`, `repo_top_levels`, `overlay_benchmark_file`, `seal_export`, `hash_export`, `read_benchmark`, `validate_benchmark_content`, `check_venv`, `trace_paired`, `measure_paired`, `evaluate_paired_samples`, `harness_sha256`, `gate_sha256` |
| The CLI has no `compare`/`run-once`; a crash has no exit-code contract | `main()` registers six subcommands; docstring "C4d owns the exit-code contract for a crash"; `return args.func(args)` has no catch-all |
| `_evaluate` computes ratios, median and MAD inline | `:424-453`; `_ratio_stats` extracted from it (T0a) |
| `validate_benchmark_gate` accepts `warmup_runs` 0..2; the cap is `(warmup+repeats+3)*2*T <= 1800` | bound `:385`, cap `:392`; `measure_paired` needs `1 <= warmup <= 3` at `:3669`; a bare clamp breaks the cap: `(1+8+3)*2*81 = 1944` |
| `run_order` allows `attempt` 1 or 2; its seed is `"\0".join(...)` of public inputs; tests assert `result["order"] == run_order(BASE, HEAD, BENCH, 1, 4)` | `:3457-3464`; `test_benchmark_gate_measure.py:168, :536, :618` (unchanged: the unsalted default keeps today's bytes) |
| The overlay copies a Builder-authored benchmark into the base export as a NEW untracked `.py` and refuses a sealed base | `:2589-2600`, `:2631` |
| `measure_paired` errors carry `side`, `phase`, `partial`, no `kind`; a spawn failure keeps the code `<SIDE>_NONZERO_EXIT`; `trace_paired` errors carry `kind` (13 values incl. `harness`) | `:900-919`; `adapt` `:3704-3710`; `TRACE_FAILURE_KINDS` `:3180` |
| `_run_once` turns every `OSError`/`SubprocessError` into `_SpawnFailed(str(exc))` and `_execute` maps it to the `spawn` kind; the harness handlers convert a plain `OSError`/`RuntimeError` into `MEASURE_FAILED` with `phase`/`partial` | `:3536`; `_execute` `:3586`; the `except (OSError, RuntimeError, ...)` branches of `measure_paired`/`trace_paired` |
| `measure_paired` shares ONE work directory across runs: writable `empty.ini`, a per-side warm `pycache-<side>`, predictable `side-<counter>` scratch from `os.makedirs` | `_prepare_run(side, bin_dir, work, counter)` `:3577-3583`; two callers (`:3702`, `:3887`), no test calls it directly |
| `side_env` already sets `PYTHONPYCACHEPREFIX` (`:3481`) and `_prepare_run` overrides it (`:3583`) | both lines go in T0b2a |
| Layer 2 allows `-q`/`--no-header` in any position | `:231-240` |
| `hash_tree` excludes timestamps; `check_venv` re-reads the snapshot by path and covers only `.pth`/startup files; `_venv_layout` reads `include-system-site-packages` but not `home` | `:2008-2010`, `:3044-3058`, `:3004-3024`, `:2960-3001` |
| `_parse_listing` yields `(kind, size, exec)` with kinds `F`, `L`, `G`, unpacked at `:1830`, `:1857` and by the exports tests with a fake id `abc` | `:1787-1818`; `test_benchmark_gate_exports.py:215-232, :701-795, :832-847` |
| `_PrivateGit` supports sha1 and sha256 repositories | `:1703-1730` |
| `_write_json_atomic`: O_EXCL on a predictable pid-named temp, then `os.replace` | `:971-985` |
| `diff_checks` can raise `GIT_OUTPUT_TOO_LARGE`, `TREE_TOO_LARGE`, `GIT_TIMEOUT` on PR content | `:894`, `:2721`, `:2741` |
| Real venv layouts (macOS, observed in D5): Homebrew `home = /opt/homebrew/opt/python@3.14/bin` (a symlink path), Xcode CLT `home = /Library/Developer/CommandLineTools/usr/bin` (a shim directory), uv `home` under a symlinked minor-version directory and `version_info` instead of `version`; a pip-installed RECORD row for `../../../bin/pip` hashes differently in two venvs | the reason `home` is resolved by file and parity excludes `../` rows |
| `_cmd_cleanup` holds the signal-handler pattern; `_run_once` has only a comment "single-threaded here" (`:3534`) | `:4103` |
| The argv already has `-P`, `--noconftest`, `-p no:cacheprovider` | `:3504-3505` |
| Reviewer/Orchestrator/Builder workflow files do not exist yet | C4e/C4f |

## 2. Design

### 2.1 Result or raise
`compare` returns a **result dict** for every outcome that PR content, the child processes or the host's measured state can cause, and **raises
`BenchmarkGateError`** only for a caller error or a fault of the harness's own machinery (CLI exit 2, no JSON). Exit 2, a signal death and a missing
file mean "no pass, escalate"; never a pass, never a free retry. Disclosed: a hostile install can remove the work directory or make the dispatch
root unusable, so a PR can always turn its verdict into exit 2 (a denial, not a pass).

| Raises (exit 2) | Returns a result |
|---|---|
| A bad argument (`MEASURE_ARGS_INVALID` for a bad `Side`, `attempt` outside 1..2, a bad `order_salt`, a bad `out_path`; `COMMIT_INVALID`, `COMMIT_NOT_FOUND`), a root that is not one of our exports or two roots that are not siblings (`DEST_REJECTED`, compare's own check), `OVERLAY_COMMIT_MISMATCH`, `OVERLAY_BASE_SEALED`, `VENV_SNAPSHOT_INVALID` (a snapshot that is invalid from the start; one that changed after minting is `SNAPSHOT_CHANGED`), `MARKER_MISSING`, `MARKER_INVALID` (a root that is not ours), `BASE_NOT_ANCESTOR` (new, appended to `ERROR_CODES`), `REPO_UNREADABLE`, `GIT_FAILED`, `GIT_TOO_OLD`, `GIT_TIMEOUT` (a host fault, at any step including 12), `HARNESS_UNREADABLE`, `OVERLAY_FAILED`, `MEASURE_FAILED`, an I/O error of the harness (including the result write) | every `reason` in `COMPARE_RESULT_OF_REASON` (2.3) |

`diff_checks` size limits (`GIT_OUTPUT_TOO_LARGE`, `TREE_TOO_LARGE`) become `DIFF_UNCHECKABLE`; a hostile export (`SEAL_FAILED`, `TREE_*`, `EXPORT_*`)
becomes `EXPORT_REJECTED` at steps 4 to 9; a `TREE_UNREADABLE` or `DEST_REJECTED` raised **by `check_venv`** becomes `ISOLATION_REJECTED`/
`VENV_NOT_ISOLATED`; the interpreter helper's `VENV_NOT_ISOLATED`/`TREE_TOO_LARGE` become `ISOLATION_REJECTED` (`INTERPRETER_DIFFERS`/`NOT_PROVISIONED`);
at step 12 every **integrity** error (hash, fingerprint, snapshot, interpreter, verification, `check_venv`, parity) is `ISOLATION_REJECTED`, but a git or
host fault (`GIT_TIMEOUT`, `GIT_FAILED`, `REPO_UNREADABLE`) still raises; `DEST_REJECTED`/`OVERLAY_FAILED` raised by `hash_export` or the fingerprints there are integrity errors (`HASH_UNREADABLE`/`FINGERPRINT_FAILED`). `GIT_OUTPUT_TOO_LARGE` from `verify_export_against_commit` is `EXPORT_REJECTED`. `UNSUPPORTED_PLATFORM` is a result of step 1, after the arguments and
`out_path` were validated.

### 2.2 Signature and structure
```
class Side(NamedTuple): root: str; commit: str; bin_dir: str; snapshot: str; snapshot_sha256: str; interpreter_sha256: str
compare(gate, repo, base: Side, head: Side, *, attempt=1, out_path, allow_writable_interpreter=False) -> dict   # thin: _compare_impl with default seams
_compare_impl(gate, repo, base, head, *, attempt, out_path, allow_writable_interpreter=False, argv_builder=None, load_probe=None,
              min_base_ns=_MIN_BASE_NS, order_salt=None, interpreter_of=None) -> dict
```
`_compare_impl` runs the pipeline, catches the internal `_Verdict`, adds the common fields and writes the file. `snapshot_sha256` and
`interpreter_sha256` are minted by the Orchestrator when it runs `snapshot-venv` (which now also prints `snapshot_sha256: <hex>` and
`interpreter_sha256: <hex>`) **before any install**. `out_path` is required and **new for every call**. `argv_builder` is the C4d-1/2 seam; on trace
runs it must emit the trace-plugin result protocol (shared fixtures provide `fake_trace_builder`, new in T2c: it emits the digest on measure runs and the trace result only when `BENCH_TRACE_*` is in the environment; today's trace tests monkeypatch
`_run_once`). `load_probe() -> (load1, cpu_count)` (default `os.getloadavg()[0]` and `len(os.sched_getaffinity(0))` where present, else
`os.cpu_count() or 1`). `min_base_ns` is the `WORKLOAD_TOO_SHORT` floor (the 2 s default makes every fast fake child `WORKLOAD_TOO_SHORT`).
`interpreter_of(bin_dir) -> InterpreterPin(sha256, writable, real_python)` is the interpreter-pin seam (default `interpreter_pin`); tests use a small fake prefix so a test
can edit the "interpreter" safely and quickly. **Salt**: in `measure_paired` and `run_order`, `salt=None`/`order_salt=None` means **unsalted** (today's
seed bytes unchanged; a given salt is appended as a fifth `\0`-joined field); in `_compare_impl`, `order_salt=None` means **generate**
`os.urandom(8).hex()`, and the result records the salt used. Salt validation (lowercase hex, 1 to 64 chars, else `MEASURE_ARGS_INVALID`) happens at
step 1. Helpers: `_compare_checks` (steps 1 to 6), `_compare_prepare` (7 to 9; frozen `_Prepared`), `_compare_runs` (10 to 13). `_Verdict` subclasses
`Exception` only. All in `benchmark_gate.py`, so `harness_sha256` covers it. The 1800 s gate cap budgets child time only; `is_ancestor` and
`diff_checks` (up to 300 s each) and the hashing sit outside it, so the Orchestrator's wait is at least `cap + hashing + 300 s x (the git invocations `compare` opens, at least nine contexts)` plus up to ~20 s per interpreter probe (`python -I -S`, `_startup_probe`, a child that runs before the sealed runs at steps 4, 9 and 12): `is_ancestor`, `diff_checks`, the benchmark-origin read at step 7 and `verify_export_against_commit` per side at steps 4, 9 and 12, several invocations each (the module docstring says the same). The floor is a lower bound, not a deadline.

### 2.3 Vocabularies (module constants, each pinned by an exact-contents test)
- `COMPARE_RESULT_OF_REASON: dict[str, str]`, one entry per reason: REJECTED: `GATE_REJECTED`, `ISOLATION_REJECTED`, `PROTECTED_PATH_CHANGED`,
  `BENCHMARK_AWARE_CODE`, `DIFF_UNCHECKABLE`, `EXPORT_REJECTED`, `OVERLAY_REJECTED`, `BENCHMARK_MODIFIED`, `LINT_REJECTED`, `TRACE_MISMATCH`,
  `BASE_NONZERO_EXIT`, `DIGEST_MISSING`, `DIGEST_UNSTABLE`, `WORKLOAD_TOO_SHORT`; NOT_IMPROVED: `HEAD_NONZERO_EXIT`, `HEAD_TIMEOUT`,
  `HEAD_OUTPUT_TOO_LARGE`, `DIGEST_MISMATCH`, `BELOW_HALF_THRESHOLD`; INCONCLUSIVE: `UNSUPPORTED_PLATFORM`, `HOST_BUSY_START`, `HOST_BUSY_END`,
  `TRACE_UNAVAILABLE`, `BASE_TIMEOUT`, `BASE_OUTPUT_TOO_LARGE`, `NOISY`, `INCONSISTENT`, `BORDERLINE`, `INVALID_INPUT` (unreachable after gate
  validation; its test monkeypatches `evaluate_paired_samples`); IMPROVED: `IMPROVED_CLEAR`. `HEAD_/BASE_OUTPUT_TOO_LARGE` are result reasons (the
  parent's single `OUTPUT_TOO_LARGE` is INCONCLUSIVE); the error code stays `OUTPUT_TOO_LARGE`. Domain exactly `{IMPROVED, NOT_IMPROVED, INCONCLUSIVE,
  REJECTED}`. A coverage test proves every `MEASURE_REFUSAL_CODES`, `TRACE_REFUSAL_CODES`, `TRACE_FAILURE_KINDS` (incl. `harness`) and
  `evaluate_paired_samples` reason is mapped or deliberately raised.
- `ISOLATION_DETAILS`: `ROOT_HAS_GIT`, `BIN_NOT_ISOLATED`, `NOT_PROVISIONED`, `INTERPRETER_DIFFERS`, `INTERPRETER_WRITABLE`, `HARNESS_FILE_UNDER_ROOT`,
  `TRACKED_FILE_DIFFERS`, `UNTRACKED_PYTHON_FILE`, `DEPENDENCY_PARITY`, `BENCHMARK_BYTES_DIFFER`, `VENV_NOT_ISOLATED`, `VENV_HOOK_REJECTED`,
  `SNAPSHOT_CHANGED`, `INTERPRETER_CHANGED`, `EXPORT_CHANGED`, `VENV_CHANGED`, `HASH_UNREADABLE`, `FINGERPRINT_FAILED`. The spawn guard (2.5, "Directory
  identity") also emits `ISOLATION_REJECTED`/`EXPORT_CHANGED` at stage `ran` with no measured field; C4e routes it as tamper, to a human.
- `COMPARE_REASONS`: THE table, `reason -> (result, stages, details)`; `COMPARE_RESULT_OF_REASON` and `COMPARE_DETAIL_TOKENS` are derived from it (the
  union of the details of every row: the gate codes, `ISOLATION_DETAILS`, `VIOLATION_CODES`,
  `OVERLAY_REFUSAL_CODES`, `DIFF_REFUSAL_CODES`, the git/tree/seal codes, `TRACE_FAILURE_KINDS`, the measure kinds), not an independent literal. `detail` is exactly one
  token from the reason's own closed set in `COMPARE_REASONS` (D2: no integer tail; `_result_dict` rejects anything else). For `LINT_REJECTED` it is the **first** violation code in `VIOLATION_CODES` order and the full list goes to `untrusted_text`.
  `kind` (a result key) is the `_execute`/trace kind that produced the result, else null.
- **Step to stage table** (`stage` in `pre_overlay`, `overlaid`, `ran`; pinned by a test that asserts the stage of every step-ending):

"Retry on the same exports" means: a second `compare` on the SAME exports, always with a new `out_path`, **can give another outcome**. The rule is the
two module constants of `(reason, stage, detail)` triples, validated against `COMPARE_REASONS` by a test: `COMPARE_RETRYABLE_AUTOMATIC` (the `HOST_BUSY_START` triple
only: the Orchestrator waits and retries by itself) and `COMPARE_RETRYABLE_WITH_HUMAN_FLAG` (the `INTERPRETER_WRITABLE` triple: retried ONLY after a human sets
`--allow-writable-interpreter`, never automatically); every row below is "no" unless it names a triple of one of them. Step-7 refusals are content-determined (the same files refuse again), so they are "no".

| Step | Stage | Retry on the same exports |
|---|---|---|
| 1, 2, 4, 5, 6 | `pre_overlay` | by `(reason, stage, detail)`: **retryable on the same exports** are `HOST_BUSY_START` (waited out) and `INTERPRETER_WRITABLE` only when a human sets `--allow-writable-interpreter`; every other `ISOLATION_REJECTED` at `pre_overlay` (`INTERPRETER_CHANGED`, `INTERPRETER_DIFFERS`, `SNAPSHOT_CHANGED`, `DEPENDENCY_PARITY`, `TRACKED_FILE_DIFFERS`, ...) is **not**: the pins are minted before the install and never re-minted after one, so it needs fresh provisioning. `INTERPRETER_CHANGED` is what a stray `.pyc` in the interpreter prefix gives; `INTERPRETER_DIFFERS` comes from two different interpreters, an interpreter inside a venv or export, or a failed start-up probe |
| 3 | raises | n/a |
| 7 refusals (the overlay leaves nothing it created) | `pre_overlay` | no: content-determined, so the same exports refuse again (they are left unsealed and unmodified, but nothing about a retry changes the outcome) |
| 7 success, 8, 9 | `overlaid` | no: fresh exports, new install, snapshot and origin |
| 10, 11, 12, 13 (incl. `HOST_BUSY_END`, `TRACE_UNAVAILABLE`, step-12 `ISOLATION_REJECTED`, the spawn guard's `ISOLATION_REJECTED`/`EXPORT_CHANGED` with no measured fields; also a T3 spawn even if no child ran) | `ran` | no: fresh exports |

A step-12 `_check_parity` that is over budget is `ISOLATION_REJECTED`/`NOT_PROVISIONED` at stage `ran` (the same word as at step 4, a later stage); `INTERPRETER_CHANGED` can likewise end at `overlaid` (step 9) or `ran` (step 12), not only at `pre_overlay`, and neither is retryable on the same exports.

**Retry budget and `attempt`.** (a) `HOST_BUSY_START` is retried automatically on the SAME exports with `attempt` unchanged: at most 3 retries per dispatch, with a wait of at least 60 s between them; then the Orchestrator stops and reports `INCONCLUSIVE`/`HOST_BUSY_START` to the human (C4e owns the exact numbers but must cap them). (b) `attempt=2` is the one allowed re-measure per task (the parent design's rule, unchanged): a new Lens B dispatch on FRESH exports (a fresh head-first provisioning), allowed only after a measured result with one of these re-measure reasons: `NOISY`, `INCONSISTENT`, `BORDERLINE`. No other reason allows it (`COMPARE_REMEASURABLE_REASONS` is that list). `HOST_BUSY_END` is not retried either; it follows a full run, so it counts as the one re-measure. Only `attempt=2` measurements use up the allowance: the busy-start retries of (a) and a dispatch for a new head or merge-base do not. A second `attempt=2` measurement for the same task is out of contract. (c) `compare` validates `attempt` as 1 or 2 and nothing more: the CAP on the number of calls is enforced by C4e, not by `compare` (listed in section 9). (d) The acceptance screen shows the count of `compare` results.

C4e keys the retry on the two constants (`COMPARE_RETRYABLE_AUTOMATIC` may be retried by C4e itself; `COMPARE_RETRYABLE_WITH_HUMAN_FLAG` only by a human decision), by `(reason, stage, detail)`, and records every `compare` result of a dispatch, showing the COUNT of `compare` results at the acceptance screen (fresh-export
retries give a bimodal head repeated draws). Fresh exports means a fresh head-first provisioning (2.5).

### 2.4 Pipeline
No BENCHMARK child runs before step 10, but the interpreter probe (`python -I -S`, `_startup_probe`, up to ~20 s each, at steps 4, 9 and 12) IS a child that runs before the sealed runs; the wait floor (2.2) counts it.

| # | Step | Ends with |
|---|---|---|
| 1 | arguments (incl. salt, `attempt`, `out_path`, `Side` shapes) validated before anything is touched; then POSIX else a result | `UNSUPPORTED_PLATFORM`; bad arguments raise |
| 2 | `validate_benchmark_gate(gate)`; `target = benchmark_target(normalized)`; `harness_sha256()` computed now | `GATE_REJECTED`, detail = the gate code |
| 3 | `is_ancestor(repo, base, head)` | raises `BASE_NOT_ANCESTOR` |
| 4 | isolation, no child yet, in this order: roots distinct siblings (`DEST_REJECTED`); `export_commit(root) == Side.commit` (`OVERLAY_COMMIT_MISMATCH`); no `.git` in either root (`ROOT_HAS_GIT`); `*_bin` distinct and outside both roots (`BIN_NOT_ISOLATED`); **interpreter** (2.5): derivation, pin, writable flag (`NOT_PROVISIONED`/`INTERPRETER_DIFFERS`/`INTERPRETER_CHANGED`/`INTERPRETER_WRITABLE`); this file's `__file__` not under a root (`HARNESS_FILE_UNDER_ROOT`); each snapshot's sha256 equals its pin (`SNAPSHOT_CHANGED`); `check_venv` per side, venv roots distinct; **`dependency_parity`** (`DEPENDENCY_PARITY`); **`verify_export_against_commit`** per side with an empty allowance (`TRACKED_FILE_DIFFERS`, `UNTRACKED_PYTHON_FILE`) | `ISOLATION_REJECTED` (or `EXPORT_REJECTED` for hostile-tree errors); offending paths and hooks under `untrusted_text` |
| 5 | `diff_checks(...)` | `PROTECTED_PATH_CHANGED`, `BENCHMARK_AWARE_CODE`, `DIFF_UNCHECKABLE` |
| 6 | `HOST_BUSY_START` (2.6), before the overlay | `INCONCLUSIVE`/`HOST_BUSY_START` |
| 7 | `top = repo_top_levels(base_root)` (after the install, against its docstring; `build/`, `dist/` join the lint allowlist, harmless; disclosed); `overlay_benchmark_file` | `BENCHMARK_MODIFIED`; `OVERLAY_REJECTED`; `EXPORT_REJECTED`; sets `benchmark_origin`. Stage `overlaid` from here |
| 8 | in this order: `seal_export` both; `read_benchmark` both; unequal bytes are `BENCHMARK_BYTES_DIFFER`; `benchmark_sha256`; `validate_benchmark_content`; `hash_export` both (`h0`); re-read and require the same sha256 | `BENCHMARK_BYTES_DIFFER`; `LINT_REJECTED`; `EXPORT_REJECTED` |
| 9 | **immediately before the first child**: rerun the snapshot pin, `check_venv`, interpreter pin, `dependency_parity` and `verify_export_against_commit` (base with `allow = {benchmark_rel: benchmark_sha256}` only when the origin is `BUILDER_AUTHORED`, which also allows the directories the overlay created; head with an empty allowance); then the baseline fingerprints (2.5) | `ISOLATION_REJECTED` |
| 10 | `trace_paired(..., timeout_seconds=per_run_timeout_seconds)` | 2.7 |
| 11 | `measure_paired(...)`, `warmup = warmup_runs`, `repeats`, seed `(base, head, benchmark_sha256, attempt)` + salt, `min_base_ns` | 2.7 |
| 12 | **post-run check** (2.5), after every path that started a child (also if a T3 spawn means none did) | `ISOLATION_REJECTED` (or `EXPORT_REJECTED`, stage `ran`, from the step-12 export check); beats everything below |
| 13 | the precedence list (2.7): the single merge point of steps 10 to 12 | the verdict |

Gate change (T0a): `validate_benchmark_gate` accepts `warmup_runs` 1..2 (default already 1); `BOUNDS_REJECTED` for 0.

### 2.5 Integrity checks
**Provisioning contract for C4e (required; the checks depend on it):** (1) mint each side's snapshot, `snapshot_sha256` and `interpreter_sha256` (one
`snapshot-venv` call) **before that side's install**; (2) **provision head first, then create the base export and venv after the head install has
finished**; (3) install with `PYTHONDONTWRITEBYTECODE=1`, a fresh `HOME` and `TMPDIR`, `PIP_CONFIG_FILE=/dev/null`, `PIP_NO_CACHE_DIR=1`, from the
repository's pinned requirements (or a wheelhouse), the project **editable only**, ideally with no network; (4) prefer an interpreter not writable
by the build user; a writable one needs `--allow-writable-interpreter` and shows in the `RESULT:` line; (5) a stray-process census around the
installs is recommended and not enforced here; (5b) `--no-compile` at install, and every `__pycache__` and `.pyc` under the venv's site-packages removed
after the install and before `compare` (`dependency_parity` rejects bytecode there). The pins of (1) are minted before the install and are never
re-minted after one: the removal touches only site-packages, which the interpreter pin does not cover; (6) the Orchestrator pins the EXPECTED `harness_sha256` (the harness file is writable by the same user, [R2]) and compares it with the result's. `harness_sha256` is a domain-separated, length-prefixed digest of the module's import-time source and the loaded `validate_task_target.py`: `sha256sum` cannot reproduce it, and the `harness-sha256` subcommand prints it (`harness_sha256: <hex>`, exit 0). The expected value must be taken from a TRUSTED copy of the harness (the pinned release, or `harness-sha256` run in a clean checkout), NEVER from a previous `compare` result (that is circular: a tampered harness would vouch for itself); (7) each project venv must be CPython >= 3.12 (no `sys.monitoring` before it: the trace is `TRACE_UNAVAILABLE` and the run can never reach `IMPROVED`, [R3]); (8) the Orchestrator reads the result file once into bytes, hashes those bytes, compares to `sha256=`, parses the SAME bytes and reads `stage` and `detail` only from them (the `RESULT:` line carries neither; `INTERPRETER_WRITABLE` needs the detail from the file) and checks the line's result, reason and `interpreter_writable=` against them (`parse_compare_outcome` does it); (9) when the harness's euid is 0 (a root Orchestrator, e.g. in Docker) every symlink alias is refused (see "Directory identity"): the paths handed to `compare` must have no symlink hop, and a refusal that comes from an alias (a `.pth` or finder path, the venv hook check) is an ENVIRONMENT fault that C4e routes as such, not a Builder fault. The same refusal (fail closed, alias paths only) also comes from a user-namespace remapped or rootless Docker where root appears as nobody, from ancestors on a bind mount owned by a CI user, from overlayfs with `st_nlink` above 1, and from a euid-0 harness: route as an environment fault, not a Builder fault. A euid-0 Orchestrator also gets `ISOLATION_REJECTED`/`INTERPRETER_WRITABLE` on EVERY compare: `writable` is `st_uid == euid or os.access(W_OK)`, true for every root-owned interpreter file and for root's `os.access`, so item (4)'s "non-writable interpreter" cannot be met as root. Root is therefore effectively unsupported unless a human passes `--allow-writable-interpreter` AND the paths have no symlink hop; C4e must run the Orchestrator non-root (behaviour unchanged; a test patches the `geteuid`/stat seams to show the outcome).

**Interpreter (T2b1b), `interpreter_pin(bin_dir) -> InterpreterPin(sha256, writable, real_python)`.** Per side, `pyvenv.cfg` is parsed as `key = value`
lines (UTF-8, non-ASCII allowed: a user home may contain it; the `command` key and every key other than the four below are ignored); a duplicate of
`home`, `version`/`version_info`, `include-system-site-packages` or `executable` is refused; `include-system-site-packages` must be `false`; the
version is `version` or `version_info` (first two components), cross-checked with the `python3.X` basename of the realpath binary when it has one.
`home` is checked **by file**: `realpath(join(home, name)) == realpath(<bin>/python)` where `name` is the basename of the venv python's first
symlink hop (else `python`), which holds for Homebrew, uv and Xcode CLT layouts. **A start-up probe then confirms what CPython actually loads**: per
side, `<bin>/python -I -S -c 'import os,sys;print(os.path.realpath(sys.base_prefix), os.path.realpath(os.__file__),
os.path.realpath(sys.base_exec_prefix))'` with the side's clean environment (`-I -S`: no `.pth`, no `sitecustomize`, no user site, so no head code
runs; only the pinned interpreter binary does). `base_prefix` must equal the pinned `prefix` and `os.__file__` must lie under the pinned stdlib, else
the venv's `home` was redirected (`INTERPRETER_DIFFERS`). The `pyvenv.cfg` sha256 also goes into the baseline fingerprint (step 9). Both sides must
resolve to the same real interpreter (compared by `compare` from the two `real_python` values, outside the `interpreter_of` seam), outside both venvs
and both exports (`--copies` venvs are unsupported: `INTERPRETER_DIFFERS`). `prefix = dirname(dirname(realpath(python)))`; the stdlib is the first
existing of `<prefix>/lib/python<X.Y>`, `<prefix>/lib64/python<X.Y>`. `sha256` is a content hash (no timestamps) of: the realpath binary's bytes; the
stdlib tree **excluding `site-packages` and including `__pycache__` and `lib-dynload`**; and the regular files directly under `<prefix>` and
`<prefix>/lib`, non-recursive (the framework `Python` dylib, `libpython*`, a `python3XY.zip`). Bounded by `_INTERPRETER_LIMIT = 20_000` entries.
Errors, named so the mapping tests can be written: `VENV_NOT_ISOLATED` (cfg, layout, symlink or probe mismatch; `compare` reports
`INTERPRETER_DIFFERS`), `TREE_TOO_LARGE` (entries or hashed bytes over the limit), `DEST_REJECTED` (no stdlib directory), `TREE_UNREADABLE` (I/O); the
last three are `NOT_PROVISIONED`. `writable` is true if any pinned file, any directory containing a pinned entry, `<prefix>` or `<prefix>/lib` is
writable by the euid (`os.access(W_OK)` or owned by the euid), computed while hashing. At step 4, `writable` without `allow_writable_interpreter` is
`ISOLATION_REJECTED`/`INTERPRETER_WRITABLE` (stage `pre_overlay`); with the flag the result and the `RESULT:` line carry `interpreter_writable=1`, which
C4e shows beside the accept action. **C4e must never auto-retry `INTERPRETER_WRITABLE` with the flag: the flag is a human signal.** The pin is recomputed
(with the probe) at steps 4, 9 and 12 (`INTERPRETER_CHANGED`); because `__pycache__` is hashed, another process legitimately writing bytecode into a
writable interpreter can fail an honest run: that is a host-or-tamper signal and C4e sends it to a human, not to the Builder. The harness never takes
the stdlib path from `home`. The trace result's `interpreter` string is child-derived and is not an identity check. `snapshot-venv` prints the pin; a
missing or oversized stdlib exits 2 with the code on stderr. Residual [R10]: the ancestors of `<prefix>` are not checked for writability, and shared
libraries outside `<prefix>` (`libssl`, `libffi` linked by `_ssl`, `_hashlib` under a user-owned Homebrew) are not pinned.

**`verify_export_against_commit(repo, commit, export_root, *, allow=None) -> list[(detail, relpath)]`** (T2b2; returns findings, raises only for
`EXPORT_*`, size and git/I/O errors). It reads the commit's listing with `_PrivateGit` through a new `_parse_listing_oids(raw)` returning
`path -> object id` (`_parse_listing`'s tuple shape and tests stay untouched; the id is validated here), and walks the export with no symlink followed:
- tracked `F`: a regular file whose git blob id (`blob <n>\0` framing, sha1 or sha256 by commit length, **no filters**) equals the listing, same
  executable bit (the seal removes write bits, so only the exec bit is compared); tracked `L`: a symlink whose `readlink` bytes hash to the listing's
  blob id and whose target stays inside the export; tracked `G` (gitlink): an empty directory. Mismatch is `TRACKED_FILE_DIFFERS`. A test pins that
  the export applies no filters (`ident`, `eol`, `working-tree-encoding`) so the two agree;
- untracked entries: a regular file or a directory only (any untracked symlink, socket, device or fifo is `UNTRACKED_PYTHON_FILE`); no untracked file
  with a module/startup suffix (`.py`, `.pyc`, `.pyd`, `.so`, `.pth`, `.zip`, `.egg`, `.whl`, or a `sitecustomize*`/`usercustomize*` name via
  `_MODULE_FILE_RE`/`_STARTUP_MODULES`) and no `__pycache__` directory, **except** under the root-level `build/`, `dist/`, `.eggs/` and
  `<root>/*.egg-info` (a `src/pkg.egg-info` holds no module-suffix files and passes anyway; a test pins the src layout), and except the `allow`
  entries (exact relative path, regular file, sha256; nothing else new in the directories the overlay created);
- `conftest.py` is a `.py` file and is rejected as untracked; the pytest/packaging files are not part of this predicate (the child runs
  `--noconftest -c <ini>`); non-code untracked inputs (`.env`, `*.json`, `*.cfg`) are not covered; disclosed as [R12].
**Honest-install limits (disclosed here and repeated by C4e):** a build that rewrites tracked files, writes an untracked `_version.py`
(setuptools_scm, hatch-vcs: exports have no `.git`, so these need a committed version file or a pretend-version variable), or builds extension
modules in place fails closed. The workaround is committed generated files or out-of-tree builds. A test names each of these file types.

**`dependency_parity(base_bin, head_bin, base_root, head_root)`** (T2b1c): an **inventory** of each venv's site-packages, not a RECORD comparison.
- Walk every entry with `lstat` and no link followed. Any symlink, device, socket or fifo is `DEPENDENCY_PARITY`; so is any `.pyc` and any
  `__pycache__` directory (the provisioning contract installs with `--no-compile` and removes bytecode after the install; the cost is that the
  dependencies compile on every run on both sides, calibrated in T6; verifying a `.pyc` against its source is not possible without running the
  venv's interpreter and marshal output is not reproducible). `inventory = {relpath: sha256 of the bytes on disk}` for every regular file; bounded by
  `_VENV_HASH_BYTES = 1 << 30` (else `NOT_PROVISIONED`).
- Each `*.dist-info` RECORD is parsed: a row's path must be relative, contain no `..` component except a leading `../` run (such rows, the venv's
  console scripts, are dropped) and never be joined when absolute (`os.path.join` would let an absolute path replace the base); each remaining row
  with a hash must equal the file's on-disk hash. **Every regular file** of the inventory must be a verified RECORD row of some dist, a file inside a
  `*.dist-info` named `INSTALLER`, `REQUESTED`, `RECORD` or `direct_url.json`, or `distutils-precedence.pth` / `_virtualenv.*`; anything else, including
  an unlisted `.py`, `.so`, `.pyd`, `.pth` or an `.egg-link`, is `DEPENDENCY_PARITY`. This covers a file added inside an owned directory.
- The two inventories must be equal over every file except the exempt dist's. At most **one exempt dist per side**: its `direct_url.json` has
  `dir_info.editable == true` and a `file://` url resolving inside that side's export; it may own only `*.pth`, `__editable__*`, `_editable_impl_*` and
  its dist-info. Its `__editable___*_finder.py` is parsed with `ast.literal_eval` for `MAPPING` and `NAMESPACES` (anything that does not parse as
  literals fails) and every target must resolve inside that side's export. A non-editable project install and a dist without RECORD fail closed. A
  test covers a head with an extra dist forged "editable" and a finder that points outside the export.
`untrusted_text` names the differences. Stance: a PR that changes pins is already `PROTECTED_PATH_CHANGED`; this check catches drift between the two
resolves and content edits. Residual [R11]: the editable finder's own code is trusted by name once its mapping is checked; the venv `bin/` directory
(`PATH` puts it first) is not verified (the benchmark lint allows no subprocess module; only the library under test could spawn a tool).

**Fingerprint** `fingerprint_tree(root, *, limit) -> str`: sha256 over sorted `(relative path, dev, ino, mode, nlink, size, mtime_ns, ctime_ns)` of
every entry without following links, bounded by `limit` entries and `_MAX_HASH_DEPTH` (exceeding either is an error, never a skip), plus the root's
`(dev, ino, ctime_ns)`. `ctime` cannot be set by the user, so tamper-and-restore moves it. Taken at step 9, compared at step 12, over: both exports
(`_MAX_TREE_ENTRIES`); both venvs (`_VENV_FINGERPRINT_LIMIT = 200_000`); both snapshot files; the dispatch root (its name list and every non-export
entry as `(dev, ino, size, ctime_ns)`, so a swapped sidecar or marker shows). The interpreter is covered by its content pin, not by this
fingerprint. Step 12 runs, in this order: snapshot pins (`SNAPSHOT_CHANGED`), interpreter pin (`INTERPRETER_CHANGED`), `hash_export` and the export
fingerprints (`EXPORT_CHANGED`/`HASH_UNREADABLE`), `check_venv` and the venv fingerprints (`VENV_CHANGED`/`VENV_HOOK_REJECTED`),
`dependency_parity`, `verify_export_against_commit` (with the step-9 allowance); the first failure names the detail. A venv over its limit is
`FINGERPRINT_FAILED`, which the Builder cannot fix.

**Directory identity (security, I2).** Children are spawned by path (`cwd=<root>`, `<bin>/python`), so a path swap between runs could run a planted
tree and restore the original afterwards with every inode inside unchanged. A `.pth` line or editable-finder target whose lexical string goes through a
symlink is accepted only when every link on the way is trusted (macOS `/var` -> `/private/var`): owned by root, with `st_nlink == 1`, held by a root-owned directory that is either sticky or one the harness's euid cannot write
(`os.access(W_OK, effective_ids=True)` where supported) and group and other cannot write (`st_mode & 0o022 == 0`), and whose every ancestor is OWNED by root (a user-owned 0555 ancestor can be chmodded by its owner) and likewise closed to the euid and to group and other, except that a STICKY root-owned directory such as `/tmp` is acceptable whatever the euid can write (the entries the checks look at are root-owned, and a same-user child can rename only entries it owns): a directory only root can change, ancestors too. The owner alone is not enough, because whoever can rename or
unlink a link in its directory replaces it. A link the user owns, or one in a directory the user can write, could be repointed or replaced by a head child between runs, and
the guard only re-checks resolved paths. When the harness's euid is 0 the head child is root too, so NO alias is trusted (a root Orchestrator must use paths without symlink hops, and every compare as root also ends at `ISOLATION_REJECTED`/`INTERPRETER_WRITABLE`, 2.5 item 9: root is effectively unsupported unless a human passes `--allow-writable-interpreter` and the paths have no symlink hop; C4e runs the Orchestrator non-root). The step-9 baseline therefore records `(resolved path, st_dev, st_ino, label, ctime_ns or None)` of the
dispatch root, both exports, both resolved bin directories and both venv roots (the ctime only for the dispatch root and the two sealed export roots, which the
harness never modifies after sealing; the bins and venv roots are not sealed, so they stay `(dev, ino)`), and `_dispatch_state` adds the dispatch root's own
`(dev, ino, ctime_ns)` and is bounded by `_MAX_TREE_ENTRIES` (over it: `FINGERPRINT_FAILED`, a verdict). A rename-and-restore moves the ctime, which the guard
sees at the next spawn and step 12 sees at the end. `trace_paired` and `measure_paired` receive the step-9 resolved roots and bins (not resolved
again after a child ran) and a `spawn_guard(side, root)` that `_execute` calls before every spawn (also once before `trace_paired` and once before `measure_paired`): the root must be the
recorded one, and each recorded path must still be its own `realpath`, the same inode (and ctime where recorded), else `_IdentityChanged`, whose text starts with
the label. `_IdentityChanged` derives from `Exception`, not from `BenchmarkGateError` (decision: no generic `except BenchmarkGateError` can swallow it or remap
it to `MEASURE_FAILED`; `compare`'s `except _IdentityChanged` comes first); it carries `code` `MEASURE_FAILED`, `side`, `phase` (`trace`, `warmup` or `timed`), `kind`
`harness`, `partial` (the completed timed rounds once `phase` is `timed`) and `trace` `None`, the same semantics out of `measure_paired` and `trace_paired`. A
`MEASURE_ARGS_INVALID` out of either function (a child that renamed its export root, or symlinked one side to the other, makes the argument checks fail before
any spawn) runs the guard again: if it objects, the outcome is the guard's, otherwise the error stands (exit 2). `compare` maps it, conservatively, to **`ISOLATION_REJECTED`/`EXPORT_CHANGED`,
stage `ran`** with no further run and no measured field, and step 12 still runs and wins with its own finding (precedence item 1). It never becomes a
measured verdict. Test rows: the planted-dispatch swap during the head trace, the head warmup, the head timed runs and the base trace (left in place), each with step 12 live
(`HASH_UNREADABLE`: the head root is then a symlink, refused by `hash_export`) and stubbed out (`EXPORT_CHANGED`); a swap-and-restore inside ONE run (the guard's ctime
at the next spawn, step 12 through the dispatch state) and inside the LAST head run (step 12 alone).

**2.5b Work directory (closes the D2 blocker).** No mutable harness state crosses a child boundary. `_prepare_run(side, bin_dir, work,
ini_path=None) -> (scratch, env, ini)` (the `counter` argument goes) makes the scratch with `tempfile.mkdtemp(dir=work)`, writes that run's
`empty.ini` into it when `ini_path` is `None` (otherwise `ini` is `ini_path`), and returns the ini path for the caller's argv; `_execute` removes the
scratch afterwards. `trace_paired` takes the same call (its per-side `work` stays). **`measure_paired`** records `(st_dev, st_ino)` of `work` and
requires `lstat(work)` to match before every `_prepare_run`, else `MEASURE_FAILED` (a denial); the check is vacuous in `trace_paired` (one run per
`work`). **No `PYTHONPYCACHEPREFIX`**: the line in `side_env` (`:3481`) and the override in `_prepare_run` (`:3583`) both go; `side_env` sets
`PYTHONDONTWRITEBYTECODE=1` instead (still nine keys). Reason: CPython would otherwise ignore every existing `__pycache__`, recompiling the
interpreter, pytest and the benchmark's imports on every run on both sides, pushing ratios toward 1 and letting compile time satisfy the 2 s floor.
Existing bytecode in the venvs and stdlib is read and nothing is written; the sealed exports hold no bytecode, so the project's own modules compile
on every run on both sides (a constant that biases toward ratio 1, conservative; calibrated in T6). `ini_path` stays a test-only parameter that
`compare` never passes.

**Spawn failures (T0b1).** `_SpawnFailed(msg, errno=errno.ENOENT)`; `_run_once` passes `exc.errno` for an `OSError` and `None` for a
`SubprocessError` (for example a failing `preexec_fn`). `_execute` maps `errno` in {`ENOENT`, `EACCES`, `ENOEXEC`, `ENOTDIR`} to `fail("spawn")`
(a missing `cwd` is `ENOENT` too); any other errno, `None` included, raises a `RuntimeError("host spawn fault")` chained, which the existing handlers
of `measure_paired` (with `phase` and `partial`) and `trace_paired` (kind `harness`) turn into `MEASURE_FAILED`. The default errno keeps the
existing stubs `raise bg._SpawnFailed("no python")` (`test_benchmark_gate_trace.py:1081`) working unchanged.

**Signals (T5a).** The CLI commands (main thread) install the SIGTERM/SIGHUP handler (raises `KeyboardInterrupt`; the first signal sets `SIG_IGN` for
the rest, as `_cmd_cleanup`) and restore the previous handlers in a `finally`; a library caller on another thread gets no handlers and must not use
the CLI path. `_run_once` masks SIGTERM, SIGHUP and SIGINT with `pthread_sigmask` around `Popen` (a `preexec_fn` in the child restores `SIG_DFL` and
an empty mask), enters `try`, then unmasks; `signal` and `pthread_sigmask` are imported in the parent before the fork. The mask is per thread: the
window is safe only while the process is single-threaded, which `_run_once`'s comment states by contract (not asserted).

**Disclosed residuals (claim no more).** The module docstring of `benchmark_gate.py` ("Known residuals of `compare`") is the single source of the wording; this list keeps the same
stable labels `[R1]` to `[R12]` (a test compares the numbers and the short labels, not the prose, so re-wrapping cannot break it).
1. [R1:setsid] An escaped `setsid` daemon: a head child can leave the process-group kill behind with fork + `setsid`; a stray same-user daemon survives the run
   and nothing detects it (no process census; page-cache effects included).
2. [R2:harness-file] The harness file is writable by the same user: C4e must pin the EXPECTED `harness_sha256` and compare it with the result's; it should also prefer a
   non-writable interpreter (a stray `.pyc` in a writable prefix between the pin and `compare` gives `INTERPRETER_CHANGED`; `INTERPRETER_DIFFERS` is a
   different fault).
3. [R3:py312] A project venv older than CPython 3.12 has no `sys.monitoring`: its trace is `TRACE_UNAVAILABLE` and it can never reach `IMPROVED`.
4. [R4:path-chain] The interpreter's own path chain (the `home` of `pyvenv.cfg`, symlink hops to the real prefix, the parent of the prefix) is pinned by content and
   not guarded by directory identity, so a user-writable hop in front of a prefix that is not user-owned (a layout `INTERPRETER_WRITABLE` does not
   refuse) could be repointed by a head child between runs.
5. [R5:outside-state] State outside the fingerprints: they detect changes to the exports, venvs and dispatch root between the baseline and the end, not writes elsewhere
   (absolute `/tmp` or `/dev/shm` state a head run leaves for a later run).
6. [R6:ctime-tick] A coarse ctime tick: a change undone inside one ctime tick on a coarse filesystem is not seen.
7. [R7:writable-interpreter] A writable interpreter: the interpreter pin covers the files listed and is exact only for a non-writable interpreter; a bytecode or file planted
   into a writable interpreter by a *child during a run* is caught only by the end-of-run pin, not if restored.
8. [R8:sigkill] A SIGKILLed `compare` leaves a running child until its own timeout.
9. [R9:third-party] Third-party content that is identical and RECORD-consistent on both sides is not judged.
10. [R10:prefix-ancestors-libs] The ancestors of `<prefix>` (the interpreter's real prefix) are not checked for writability, and shared libraries outside `<prefix>`
   (`libssl`, `libffi` linked by `_ssl`, `_hashlib` under a user-owned Homebrew) are not pinned.
11. [R11:finder-and-bin] The editable finder's own code is trusted by name once its mapping is checked, and the venv `bin/` directory (`PATH` puts it first) is not verified
   (the benchmark lint allows no subprocess module; only the library under test could spawn a tool).
12. [R12:non-code-inputs] Non-code untracked inputs (`.env`, `*.json`, `*.cfg`) are not covered by `verify_export_against_commit`.

**The human acceptance of every `IMPROVED` is the control that remains.** The run order is public but salted (`order_salt`; the recorded `order`
reproduces a run).

### 2.6 Host checks
Exact arithmetic on `Fraction(str(load1))`: `busy_start = load1 * 10 > 7 * cpu_count` (always probed); `busy_end = (load1 - 1) * 10 > 7 * cpu_count`,
probed at the end when the start probe worked and the run reached precedence item 6 (it records `loadavg.end` and `cpu_count.end` whenever it probed: on every such path except `INVALID_INPUT`, which is never replaced and so never probed), and CHECKED only when `cpu_count >= 3` (`_HOST_BUSY_MIN_CPUS`; below it only the CHECK is skipped, `host_check: "end_skipped_few_cpus"`). A probe that raises or returns a non-finite, negative, `bool` or
non-real load, or a non-positive `cpu_count`, records `host_check: "skipped_probe_failed"` and skips both checks. `host_check` is `"checked"`,
`"end_skipped_few_cpus"`, `"start_only"` (the end probe did not run on this path) or `"skipped_probe_failed"`; `loadavg` and `cpu_count` are
`{"start": ..., "end": ...}` objects (`end` is recorded whenever the end probe ran, also when its CHECK was skipped for few CPUs; null only when the end probe did not run on this path or failed).

### 2.7 Trace and measure outcomes, and the precedence list
`measure_paired` errors carry `kind` (`spawn`, `oversize`, `timeout`, `nonzero`) from `_execute` through `_run_error_code(side, kind)` (keeps the
`unknown _execute failure kind` `AssertionError`); a spawn failure keeps its code `<SIDE>_NONZERO_EXIT`. **Dispatch: `error.code` first for the
raising rows T1 and M4 (`MEASURE_FAILED`, `MEASURE_ARGS_INVALID`: `kind` is `harness` or null), then `kind == "spawn"` for `trace_paired` and for the
`*_NONZERO_EXIT` codes of `measure_paired`, then `error.code`, then `side`.**

| # | Source | Becomes |
|---|---|---|
| T1 | `trace_paired` raising `MEASURE_FAILED` / `MEASURE_ARGS_INVALID` | **raises** |
| T2 | `trace_paired` `TRACE_UNAVAILABLE` (both sides, same token) | `INCONCLUSIVE`/`TRACE_UNAVAILABLE` (stage `ran`; retry needs fresh exports and a venv with CPython >= 3.12 and a free tool id; C4e reads the token from `trace` and never degrades it to "measure without trace") |
| T3 | `kind == "spawn"` from `trace_paired` or `measure_paired` | `ISOLATION_REJECTED`/`NOT_PROVISIONED` (stage `ran` even when no child ran) |
| T4 | `trace_paired` kinds `nonzero`, `timeout`, `oversize` | **by `error.side`, with the measure rows below** (head: `HEAD_NONZERO_EXIT`/`HEAD_TIMEOUT`/`HEAD_OUTPUT_TOO_LARGE`; base: `BASE_NONZERO_EXIT`, `BASE_TIMEOUT`, `BASE_OUTPUT_TOO_LARGE`); a head fault sets `trace_fault: "head"` (a base fault `"base"`) and `detail` names the kind |
| T5 | `trace_paired` kind `counts_differ` | **pending** `TRACE_MISMATCH`; continue to step 11 |
| T6 | `trace_paired` kinds `plugin_failed`, `no_result`, `unavailable_one_side`, `unavailable_tokens_differ`, `unavailable_interpreters_differ`, `interpreters_differ` | `REJECTED`/`TRACE_MISMATCH` at once |
| M1 | `measure_paired` `BASE_NONZERO_EXIT`, `DIGEST_MISSING`, `DIGEST_UNSTABLE`, `WORKLOAD_TOO_SHORT` | REJECTED |
| M2 | `HEAD_NONZERO_EXIT`, `HEAD_TIMEOUT`, `DIGEST_MISMATCH`, head `OUTPUT_TOO_LARGE` | NOT_IMPROVED |
| M3 | `BASE_TIMEOUT`, base `OUTPUT_TOO_LARGE` | INCONCLUSIVE |
| M4 | `MEASURE_ARGS_INVALID`, `MEASURE_FAILED` | raises |

**The one precedence list** (highest first):
0. A raise (T1, M4, or any 2.1 raise): exit 2. Step 12 does not run; each child's process group was already killed by `_run_once`'s `finally`.
1. `ISOLATION_REJECTED` or `EXPORT_REJECTED` from step 12 beats everything below (when it and a T3 both apply, step 12's detail wins).
2. An at-once trace result: T2, T3, T4, T6. `HOST_BUSY_END` is not probed; step 11 does not run.
3. A measure-raised REJECTED or NOT_IMPROVED (M1, M2, and a T3 spawn from measure). If a `counts_differ` was pending: `trace_mismatch_seen: true`.
   C4e escalates `trace_mismatch_seen` and `trace_fault` as human-review signals (a head that crashes only in the trace run is evidence of detection).
4. The pending `TRACE_MISMATCH` (T5; measure succeeded, or raised an INCONCLUSIVE). Measured data stays in the result; `HOST_BUSY_END` is not probed.
5. A measure-raised INCONCLUSIVE (M3) with no pending trace error. Not probed.
6. Measure succeeded: `evaluate_paired_samples` and `_ratio_stats` (`improvement = 1 - median(ratios)`); then `HOST_BUSY_END` replaces an `IMPROVED`,
   `NOT_IMPROVED` or INCONCLUSIVE from the evaluate, never `INVALID_INPUT`.
`ratios`, `improvement`, `mad_over_median` are filled only after a successful measure (also under item 4). The wasted measurement after
`counts_differ` stays inside the cap, which budgets trace plus the full measurement.

### 2.8 Result JSON
`schema` is a key: `"software-builder-bench-compare-v1"`. Keys, all ASCII (`ensure_ascii`): `schema`, `result`, `reason`, `detail`, `kind`, `stage`,
`trace_mismatch_seen`, `trace_fault`, `untrusted_text` (a list capped at 20 entries of escaped, length-capped strings: stderr tail, diff hits and
paths, venv hook entries, offending export paths, parity differences, the lint violation list; the consumer treats it as data), `benchmark_origin`,
`improvement`, `ratios`, `mad_over_median`, `n`, `repeats`, `min_improvement`, `max_noise`, `base_median_ns`, `head_median_ns`, `base_ns`, `head_ns`,
`order`, `order_salt`, `digest` (child-printed), `base_commit`, `head_commit`, `benchmark_sha256`, `gate_sha256` (equals
`gate_sha256(normalized_gate)`), `harness_sha256`, `argv`, `trace`, `python` and `interpreter_home` (escaped with `escape_diagnostic(.., 200)`),
`interpreter_writable` (a boolean computed by `interpreter_pin`, not escaped; null, printed `n/a`, for a result that ends before step 4), `loadavg`, `cpu_count`, `host_check`, `attempt`, `side`, `phase`,
`partial`. `trace` is `null` when it failed during a side's run, else `{"base": {"kind": "lines"|"unavailable", "value", "interpreter"}, "head":
{...}, "body_has_control_flow", "argv", "argv_note": "harness-only: temporary ini and plugin directory"}` (interpreters and tokens are child-derived,
regex-bounded). Not applicable is `null`. Fractions are floats; raw `base_ns`/`head_ns` allow exact recomputation. Every string is escaped; paths in
the file are data, none is trusted.

### 2.9 `out_path`, writing, CLI and crash contract
- Step 1 validates `out_path`: its directory `realpath` exists, is owned by the user and not group/other writable; the result path is not under (by
  `realpath`) either root, either bin, either venv, either snapshot or the dispatch root; `lexists(out_path)` is false; the directory's
  `(st_dev, st_ino)` is recorded.
- The write happens **after step 12**: open the directory with `O_DIRECTORY|O_NOFOLLOW` and require the recorded `(dev, ino)`; create a random-named
  temp through `dir_fd`, write, `os.link(tmp, name, src_dir_fd=, dst_dir_fd=)` (fails if the name exists), `unlink` the temp in a `finally`, then
  `os.stat(out_path, follow_symlinks=False)` must match the written `(dev, ino)`. A failure is exit 2. The directory being owner-only does not stop
  the head child (it is the owner): it can plant `out_path` or rename the directory; those only turn a verdict into exit 2 or are caught by the
  identity checks.
- `compare --gate FILE --repo DIR --base-root DIR --head-root DIR --base-commit SHA --head-commit SHA --base-bin DIR --head-bin DIR --base-snapshot FILE
  --base-snapshot-sha256 HEX --base-interpreter-sha256 HEX --head-snapshot FILE --head-snapshot-sha256 HEX --head-interpreter-sha256 HEX --out FILE
  [--attempt N] [--allow-writable-interpreter]`. `--gate` holds the raw `benchmark_gate` JSON (bounded read). Prints `RESULT: <result> <reason>
  interpreter_writable=<0|1|n/a> sha256=<hex of the written bytes>` (closed sets) after the file exists. **Exit** 0 only for `IMPROVED`, and an exit 0 counts as an `IMPROVED` ONLY together with a valid `RESULT: IMPROVED ...` line whose `sha256=` matches the bytes of the
  file: a bare exit 0 (for example `compare --help`, which argparse ends with exit 0 and no `RESULT:` line) is NOT an `IMPROVED`; 1 any other
  result; 2 usage, a raised error or a crash. Every parser (the main one and each subparser) has `allow_abbrev=False`: an abbreviation such as `--allow-writable-i` is a usage
  error (exit 2) and never sets the human flag. An exit 1 **without** a valid RESULT line and a matching file sha256 is treated as exit 2 (Python's
  uncaught-exception exit is also 1). The Orchestrator reads the file once into bytes, hashes those bytes, checks the RESULT sha, parses the same bytes
  and checks the RESULT line's result, reason and `interpreter_writable` against them (`parse_compare_outcome` does all of it; the line is built by the one `format_result_line`). Exit 2 with a file present means "ignore the file".
- `harness-sha256` prints `harness_sha256: <hex>` (exit 0; 2 with the code on stderr if the harness cannot be digested). It is how C4e obtains the EXPECTED digest from a TRUSTED
  copy of the harness (2.5 item 6). `snapshot-venv` fails (exit 2, `VENV_SNAPSHOT_INVALID`) for a snapshot over `_VENV_MAX_SNAPSHOT_BYTES`, the one limit every reader uses, and unlinks the oversize file it just wrote (best effort) so a retry on the same `--out` is possible.
- **Reference reader.** `parse_compare_outcome(returncode, stdout, file_bytes) -> (exit_code, parsed)` in `benchmark_gate.py` (stdlib only) is the reference reader for C4e: it returns the exit code the Orchestrator may act on (0 only for a valid `RESULT: IMPROVED` line whose sha256 matches `file_bytes` and whose result, reason and `interpreter_writable=` (`n/a` is the file's `null`) agree with the parsed file; 1 for any other valid result; anything else 2) and the parsed file (`None` when the code is 2). The tests import it from the module.
- Crash contract: only `compare` and `run-once` own it. An unexpected crash in `harness-sha256`, `snapshot-venv`, `fixed-parent` and the other non-compare subcommands is Python's uncaught exception and exits 1, so C4e must treat ANY non-zero exit of those as a failure. `_cmd_compare` and `_cmd_run_once` catch `BenchmarkGateError`, `OSError`, `ValueError`, `RecursionError`, `Exception` and
  `KeyboardInterrupt`, print `usage error: <CODE or INTERNAL>: <type>` (never attacker text), return 2 and write nothing. Sealed exports stay sealed;
  `cleanup` restores them.
- `run-once --gate FILE --root DIR --bin DIR [--side base|head]` (default `head`; no ini option). Exit 0 prints `digest: <64 hex>` (child-printed,
  **not evidence**); 1 prints the reason (`<SIDE>_NONZERO_EXIT`, `<SIDE>_TIMEOUT`, `OUTPUT_TOO_LARGE`, `DIGEST_MISSING`, `REJECT:<gate code>`) with
  the escaped detail on stderr (child text: untrusted); 2 usage/crash.
- `run_benchmark_once(root, bin_dir, target, *, timeout_seconds, side="head", argv_builder=None, ini_path=None) -> {"digest", "argv"}` (named apart
  from the private `_run_once`): one untimed run through `_prepare_run`/`_execute`. `_check_one_side(root, bin_dir, target, ini_path)`: absolute
  existing directories; `bin_dir` passes `_venv_layout`; `_benchmark_file_of(target)`; the target is a regular non-symlink file under `root`
  (resolved containment); `_check_timeout`. `root` need not be an export; nothing is sealed, hashed or written.

### 2.10 `benchmark_target(normalized_gate) -> str`
The single non-dash token after the `pytest` or `python3 -m pytest` prefix of the normalized command, wherever the options sit.

### 2.11 Not changed, and why
`evaluate_paired_samples` (numbers shared through `_ratio_stats`, a no-behaviour-change extraction; it also computes median and MAD on the clear-win
path, harmlessly), the plugin, the `harness_sha256` domain string, `_parse_listing`. Provisioning and root lifetimes stay with the caller. No retry
loop inside `compare`. Rejected: a third run to probe the digest before the trace; best-effort sealing of the venvs; `PR_SET_CHILD_SUBREAPER`;
excluding `__pycache__` from the interpreter pin (it opened a forging channel); refusing every user-writable interpreter outright (replaced by the
explicit flag); a per-dispatch private interpreter copy and a sandboxed head install (C4e provisioning options, not `compare` features).

## 3. Acceptance
Produced with the `_compare_impl` seams (fake children, small `min_base_ns`, `interpreter_of` with a fake prefix) and two real-pytest rows; figures
recorded in T6 (unverified until then). One test row exists per vocabulary entry of 2.3 not listed here.

| Scenario | Expected |
|---|---|
| fix halves the work, honest benchmark, quiet host, **benchmark is new in head (overlay-origin)** | `IMPROVED`/`IMPROVED_CLEAR`, exit 0, JSON with every key; steps 9 and 12 pass with the overlaid file; an honest child leaves every fingerprint unchanged |
| the two sides' benchmark bytes differ at step 8 | `ISOLATION_REJECTED`/`BENCHMARK_BYTES_DIFFER` |
| after the overlay a second untracked `.py`, or the overlaid file changed, appears (step 9 or 12) | `ISOLATION_REJECTED`/`UNTRACKED_PYTHON_FILE` |
| head slower or equal | `NOT_IMPROVED`/`BELOW_HALF_THRESHOLD`, exit 1 |
| noisy samples | `INCONCLUSIVE`/`NOISY` |
| digest differs | `NOT_IMPROVED`/`DIGEST_MISMATCH` |
| trace counts differ, digests match | `REJECTED`/`TRACE_MISMATCH` |
| trace counts differ and digests differ | `NOT_IMPROVED`/`DIGEST_MISMATCH`, `trace_mismatch_seen: true` |
| trace counts differ and base times out | `REJECTED`/`TRACE_MISMATCH` |
| head exits non-zero in the trace run | `NOT_IMPROVED`/`HEAD_NONZERO_EXIT`, `trace_fault: "head"` |
| trace `harness` kind; a spawn errno `EAGAIN` or `None` | exit 2 |
| spawn failure with `ENOENT` | `ISOLATION_REJECTED`/`NOT_PROVISIONED` |
| both sides report the trace unavailable | `INCONCLUSIVE`/`TRACE_UNAVAILABLE`, stage `ran` |
| busy host before the overlay | `INCONCLUSIVE`/`HOST_BUSY_START`, stage `pre_overlay`, nothing sealed; a second call on the same exports with a new `out_path` succeeds |
| busy host after the runs, would be `IMPROVED` | `INCONCLUSIVE`/`HOST_BUSY_END`; with a pending trace mismatch the mismatch stands |
| a child edits or restores an export file; adds a venv hook and rewrites the snapshot; edits the (fake) interpreter | `ISOLATION_REJECTED` (`EXPORT_CHANGED`/`VENV_CHANGED`/`SNAPSHOT_CHANGED`/`INTERPRETER_CHANGED`) beating every other result |
| venvs made like Homebrew, uv and Xcode CLT (`home` a symlink path or shim directory, `version_info` only) | accepted; a `home` that does not resolve to the venv's python, a `--copies` venv, or different interpreters on the two sides: `INTERPRETER_DIFFERS` |
| writable interpreter, no flag; with the flag | `ISOLATION_REJECTED`/`INTERPRETER_WRITABLE` at `pre_overlay`; with the flag it runs and `interpreter_writable=1` is in the RESULT line |
| interpreter differs from the Orchestrator's pin (incl. a `python3XY.zip`, a dylib, a `__pycache__` file) | `ISOLATION_REJECTED`/`INTERPRETER_CHANGED` |
| two honest venvs with pip-installed console-script dists at different paths | `dependency_parity` passes |
| a dependency file edited with its RECORD intact; a bare module or `.so` in site-packages; a non-editable project install | `ISOLATION_REJECTED`/`DEPENDENCY_PARITY` |
| a child rewrites its `empty.ini` or plants a file in the harness work directory | no effect on the next run (fresh scratch and ini per run) |
| a child renames the dispatch root, plants a copy, and restores the original later | `ISOLATION_REJECTED`/`EXPORT_CHANGED` at the next spawn (stage `ran`), never a measurement |
| tracked file edited after the install; untracked `hashlib.py`; untracked symlink; `__pycache__`; `_version.py`; an in-place `.so` | `ISOLATION_REJECTED`/`TRACKED_FILE_DIFFERS` / `UNTRACKED_PYTHON_FILE`, stage `pre_overlay` |
| honest tree with `*.egg-info`, `src/pkg.egg-info`, `build/lib`, `dist/`, a tracked symlink and a gitlink | passes `verify_export_against_commit` |
| `warmup_runs: 0` | `GATE_REJECTED`/`BOUNDS_REJECTED` |
| `run-once` on an honest benchmark | exit 0, `digest: <hex>` |

## 4. Tests
New module `skills/loop-task-implementer/tests/test_benchmark_gate_compare.py`. Fixtures: **T2b0** a minimal real git repo with two commits (incl. a
tracked symlink and a gitlink), two exports, two fresh venvs whose `python` is a **symlink** (Homebrew-, uv- and CLT-shaped `pyvenv.cfg` variants) with a
pytest-bearing `.pth` created before `snapshot-venv` (the pattern at `test_benchmark_gate_trace.py:55-64`), and a small fake interpreter prefix; **T2c**
adds `fake_trace_builder` and the `snapshot-venv` pins. Rows name the mutant they kill; each row is tagged with the task that can first run it.
1. [T2a] Pure: vocabulary contents; result assembly from a synthetic `_Verdict` (exact key set, ASCII, attacker text only in `untrusted_text`, capped
at 20); the dir-fd writer (every `out_path` rejection, identity checks, planted target and temp). 2. [T3a/T3b/T4a2] Raise vs return, one row per
entry of 2.1 at the step that produces it; the step-order spy table; `HOST_BUSY_START` leaves nothing sealed. 3. [T4b] The coverage test over all
codes; the stage of every step-ending; `gate_sha256` equals `validate`'s; `INVALID_INPUT` via a monkeypatch; one row per vocabulary entry. 4. [T4a2]
The 2.7 rows T1..M4 one by one; dispatch order (`code` for T1/M4, then `kind == "spawn"`); the spawn errno split. 5. [T4b] The precedence list:
every adjacent pair of 0 to 6. 6. [T4a1] The step-12 helper called directly with a mutation hook: edit, tamper-and-restore, dispatch-root sibling
swap, sidecar edit, venv hook plus rewritten snapshot, (fake) interpreter edit, `TREE_UNREADABLE`, `GIT_TIMEOUT` raising, the check order of 2.5;
[T4a2/T6] the same through real children. 7. [T0b2a] **Work-directory isolation (blocker test, at `measure_paired`/`trace_paired` level)**: the argv ini
path is distinct per run and inside a scratch removed after the run; a child that rewrites its ini or plants a file under `work` does not change the
next run; a pre-created scratch name does not fail the run; a replaced `work` raises `MEASURE_FAILED` (measure only); no `PYTHONPYCACHEPREFIX`,
`PYTHONDONTWRITEBYTECODE=1`, nine keys. 8. [T4b] Host checks: 0.70 vs 0.71 exact, own-load subtraction, `cpu_count` 2, bad probe values,
`host_check` values. 9. [T5b] The `RESULT:` line with sha256 and `interpreter_writable`, exit-code contract (exit 1 without RESULT treated as 2).
10. [T0a] `_ratio_stats` equals `_evaluate`; gate `warmup_runs`; `benchmark_target`; [T3a] `attempt` 0 and 3 and a bad salt raise before any child.
11. [T2b1a] `fingerprint_tree`. 12. [T2b1b] `interpreter_pin`: every layout variant, duplicate keys, `version`/`version_info`, `lib64`, the framework
and `python3XY.zip` files, `__pycache__` in the pin, writable flag, over-limit. 13. [T2b1c] `dependency_parity`: console scripts at different paths
pass; edited file, bare module, `.so`, non-editable project, RECORD-less dist, `direct_url.json` exemption limited to one editable dist per side.
14. [T2b2] `verify_export_against_commit`: every row of 2.5 incl. the overlay allowance, tracked `L`/`G`, no-filters pin for sha1 and sha256
repositories, honest pass, error mappings; `_parse_listing_oids` keeps the id for both hash widths and leaves `_parse_listing` unchanged.
15. [T5a/T5b] CLI: exit codes, injected `RuntimeError`, SIGTERM kills the child's group, a child reports `signal.getsignal` TERM/HUP/INT = default and
an empty mask while the parent has them ignored and masked, handlers restored in `finally`, no JSON on exit 2. 16. [T1] `run_benchmark_once`/`run-once`.
17. [T6] Two real-pytest rows through `_compare_impl` with a lowered `min_base_ns` (one overlay-origin). 18. [T2a/T7] Pins: `ERROR_CODES` gains
exactly `BASE_NOT_ANCESTOR`, appended; subparsers exist; the CLI path uses default seams; the generated salt is random.

Existing tests changed (exact, from reading the files): **T0b1** `test_benchmark_gate_measure.py:243` (`_run_error_code` keeps the `AssertionError`);
the stubs `raise bg._SpawnFailed("no python")` at `test_benchmark_gate_trace.py:1081` and the `__cause__` assertion at
`test_benchmark_gate_measure.py:384-389` stay valid through the default errno. **T0b2a** `test_benchmark_gate_measure.py:79-86` (`side_env` keys),
`:360-380` (the `shutil.rmtree` spy and its `(base|head)-\d+` / `["base-1"]` assertion: rewrite to "the scratch's parent is `work`"), `:599-613` (the
`os.makedirs` counter: calls per run drop from three to two, so `> 12` and its "second timed round" comment are re-derived), `:661` and `:665` (the
pycache-prefix test), `:678` (patches `os.makedirs`; still passes because `side_env` keeps using it), `test_benchmark_gate_trace.py:1822` (scratch
regex); `:894` and `:900` need no change. `:168, :536, :618` stay valid. **T0a** `test_benchmark_gate_core.py:474-475, :499, :548-551`. **T2a**
the `ERROR_CODES` pin in `test_benchmark_gate_exports.py` (about `:461-467`). **T2c** `test_benchmark_gate_venv.py:366-370` (the `world` fixture has
no `bin/python`, so the new interpreter pin needs a fixture update). **T2b2** adds tests for `_parse_listing_oids` and leaves `:215-232, :701-795,
:832-847` alone.

## 5. Docs
`main()` docstring; the module docstring (a section index; the "still to come (C4d-3)" sentence and the calling-order paragraph rewritten); the
`ERROR_CODES` comment (`HOST_BUSY_*` and the rest are reasons, not exceptions); the `validate_benchmark_gate` docstring (`:346-348`); the docstrings
of `run_order`, `measure_paired`, `trace_paired`, `_prepare_run`, `_execute`, `_run_once`, `side_env`; the `BenchmarkGateError.kind` comment (`:911`,
"trace_paired only"); the `snapshot-venv` help text and docstring. `workflow/*` is not touched (C4e).

## 6. Suggested task order and dependency audit
| Task | Content | Depends on |
|---|---|---|
| T0a | gate `warmup_runs` 1..2 (+ docstring and the core tests); `_ratio_stats`; `benchmark_target` | none |
| T0b1 | `kind` on measure errors, `_run_error_code`, `_SpawnFailed` errno plumbing, `run_order(..., *, salt=None)`, `measure_paired(..., order_salt=None)` | none |
| T0b2a | per-run scratch/ini (`_prepare_run` signature, `trace_paired` adaptation), `PYTHONDONTWRITEBYTECODE`, `measure_paired` work identity check, the blocker test and the listed test edits | T0b1 |
| T1 | `_check_one_side`, `run_benchmark_once` | T0b2a |
| T2a | vocabularies, `Side`, `_Verdict`, result assembly, dir-fd writer, `BASE_NOT_ANCESTOR` + pin | T0a |
| T2b0 | minimal shared fixtures (repo, exports, venv variants, fake interpreter prefix) | T2a |
| T2b1a | `fingerprint_tree` | T2b0 |
| T2b1b | `interpreter_pin` and the `pyvenv.cfg` parser | T2b0 |
| T2b1c | `dependency_parity` inventory (builds its own dist-info/RECORD/console-script fixture trees) | T2b0 |
| T2b2 | `_parse_listing_oids`, `verify_export_against_commit` (builds its own sha256-repository fixture) | T2b0 |
| T2c | `snapshot-venv` prints both sha256s (+ the venv test fixture), `fake_trace_builder` | T2b1b, T0b2a |
| T3a | `_compare_checks` (steps 1 to 6) | T2b1a-c, T2b2, T2c |
| T3b | `_compare_prepare` (steps 7 to 9) | T3a |
| T4a1 | step 12 post-run check and the step-9 baseline (`_Prepared` gains its baseline field here; the baseline also holds the directory identities and resolved bins) | T3b |
| T4a2 | steps 10, 11 and the 2.7 rows | T4a1, T0b2a |
| T4b | step 13: precedence, `HOST_BUSY_END`, statistics, the coverage and stage tests | T4a2 |
| T5a | `_run_once` signal masking and child restore, CLI handler helper, with their library-level tests | T4b |
| T5b | CLI `compare`, `run-once`, crash contract, `RESULT:` line | T1, T5a |
| T6 | two real-pytest rows (they use `allow_writable_interpreter=True` or the `interpreter_of` seam, since CI interpreters are runner-writable), acceptance figures, the project and dependency recompile calibration | T5b |
| T7 | docs, pins | T6 |
Everything edits `benchmark_gate.py`, so commits are sequential; T0a/T0b1 and T1/T2a are independent of each other.

## 7. Rollout and rollback
Library and CLI only; nothing calls them until C4f. Rollback is a revert. The `warmup_runs` change makes a gate with 0 invalid: no stored gate exists
yet.

## 8. Open questions
None that block.

## 9. Deviations from the parent design (to write back in C4e)
1. Gate `warmup_runs` 1..2. 2. `HOST_BUSY_START` runs before the overlay. 3. `HOST_BUSY_END` replaces only the evaluate output. 4. Gate validation
precedes the ancestry check, which raises. 5. A pending `TRACE_MISMATCH` after `counts_differ`, measure first; trace faults map by side (the parent
makes every trace fault `TRACE_MISMATCH`; both are non-pass; `trace_fault` carries the escalation signal; C4e to confirm). 6. New reasons
`DIFF_UNCHECKABLE`, `EXPORT_REJECTED`, `BASE_/HEAD_OUTPUT_TOO_LARGE`; the `TRACE_UNAVAILABLE` row; `NOT_PROVISIONED` and the other
`ISOLATION_DETAILS`. 7. Result fields `stage`, `untrusted_text`, `trace_mismatch_seen`, `trace_fault`, `order_salt`, `interpreter_*`; retry keyed on
`(reason, stage, detail)` (the constants `COMPARE_RETRYABLE_AUTOMATIC` and `COMPARE_RETRYABLE_WITH_HUMAN_FLAG`: C4e retries the first by itself and the second only on a human's `--allow-writable-interpreter`); the spawn guard's `ISOLATION_REJECTED`/`EXPORT_CHANGED` at stage `ran` with no
measured fields (C4e routes it as tamper, to a human); `detail` is a closed vocabulary (parent: free-form escaped). 8. **Head provisioned first, base created after** (head first; each side's snapshot and interpreter pins are minted before that side's install), the provisioning
contract of 2.5, snapshot and interpreter pins minted pre-install, `--allow-writable-interpreter`, `verify_export_against_commit`,
`dependency_parity`, the ctime fingerprint, per-run scratch and ini, no pycache prefix; the C4e write-back list also carries: install with `PYTHONDONTWRITEBYTECODE=1`, a fresh `HOME` and `TMPDIR`, `PIP_CONFIG_FILE=/dev/null` and `PIP_NO_CACHE_DIR=1`, from pinned requirements or a wheelhouse, ideally with no network (2.5 item 3); prefer an interpreter not writable by the build user (2.5 item 4); a stray-process census around the installs, the Orchestrator-side check for the accepted `setsid` residual [R1] (2.5 item 5); run the Orchestrator with a non-zero euid: as root every compare ends at `INTERPRETER_WRITABLE` and every symlink alias is refused (2.5 item 9); pin the expected `harness_sha256`, taken from a TRUSTED copy of the harness with `harness-sha256` (never from a previous `compare` result), and the project venv must be CPython >= 3.12; remove every `__pycache__` and `.pyc` under the venv's site-packages after the install and before `compare` (2.5 step 5b); install editable only and with `--no-compile`; read the result file ONCE into bytes and hash, parse and read `stage`/`detail` from those same bytes (2.5 item 8); an exit 0 is an `IMPROVED` only with a valid `RESULT: IMPROVED` line whose `sha256=` matches the file (2.9); never degrade `TRACE_UNAVAILABLE` to "measure without the trace" (2.7 T2); show the count of `compare` results of a dispatch at the acceptance screen (2.3); enforce the retry budget and the `attempt` cap (2.3: at most 3 automatic `HOST_BUSY_START` retries per dispatch at least 60 s apart on the same exports with `attempt` unchanged; `attempt=2` once per task, only after `NOISY`, `INCONSISTENT` or `BORDERLINE`, on fresh exports; `compare` itself only validates 1 or 2); with a root Orchestrator (euid 0) every symlink alias is refused, so route an alias or venv-hook refusal as an environment fault, not a Builder fault (2.5 item 9). 9. `out_path` written by dir-fd link after step 12 with the
file's sha256 in the `RESULT:` line (parent: temp file then rename). 10. `repo_top_levels` taken after the install. 11. Seeded order gains a random
salt. 12. The Orchestrator's wait is at least the gate cap plus hashing plus 300 s x the git invocations `compare` opens (at least nine contexts) plus up to ~20 s per interpreter probe (at least 6: steps 4, 9 and 12, per side). 13. `compare`'s signature: `Side` tuples with the two pins and
`allow_writable_interpreter` replace the parent's positional `(gate, base_root, head_root, repo, base_commit, head_commit, base_bin, head_bin, ...)`.
