# C4d-2: the trace plugin and the per-side trace runs (rev 8, spec rounds 1 to 6 and branch review round 1 applied)

**Readiness: Approved for planning.** Six review rounds were used (the maximum); the round-6 multi-persona reviewer returned CLEAN and the attacker and test-author findings were applied in this revision without a seventh round. Gap-backlog ticket C4, part C4d-2 of C4d. Library only: nothing here is wired until C4f,
and `compare` (C4d-3) is the only caller. Parent design (binding except where section 1 lists a revision):
`docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md` (rows "Measurement harness" and "`compare`", review
history lines 94 to 111, tables at 250 to 259). Base: `77859929` (main, includes C4d-1, #366). All `file:line` are in
`skills/loop-task-implementer/scripts/benchmark_gate.py` at that commit unless stated; tests live in
`skills/loop-task-implementer/tests/`.

## Revision history

**Rev 1** (initial). **Round 1** (multi-persona, attacker, test author) found, rev 2 fixed: the caller-frame count rule fails on helpers
below callbacks (417 against 3) and on C-level library entries (`map`: 210 against 2); a decorated test counted 0 on both sides; a stdout
"last line wins" parser is forgeable with `atexit`; one plugin directory served both runs; a second test collided on the tool id; the
callback fired on every library line; callback exceptions skewed the count; the `_execute` extraction was not behaviour-preserving;
interpreters without `sys.monitoring` were blamed on the Builder.

**Round 2** (same three personas, all `NOT CLEAN`) found, rev 3 fixes:

- **Blocker**: the result file sat in the scratch directory that `_execute` removes before the harness reads it. **Fixed**: a separate
  `out_dir` sibling (D2, D3, D5).
- **High**: a result file pre-created by the code under test was accepted whenever the plugin wrote nothing (failed, zero count, early
  `_exit`). **Fixed**: the plugin always leaves exactly one marker (`out` or `out.failed`); a per-run **nonce** that the plugin pops from
  the environment at import is part of every result line (D2, D3).
- **High/Medium**: `__wrapped__` could point at a decoy and hide the real body; non-`wraps` decorators counted 1; one-line loops and
  inlined comprehensions are invisible to `LINE` alone; `TRACE_UNAVAILABLE` could be forced by a Builder-installed startup hook to
  downgrade a rejection; `BENCH_TRACE_*` names are not covered by the token tripwire; "asyncio.run bodies count 0" and "decorated tests
  fail closed" were false. **Fixed**: wrapper-chain rule with a name check, `LINE`+`JUMP` counting, both-sides rule for
  `TRACE_UNAVAILABLE`, tripwire extension, corrected disclosures (D2, D3, D6, D9).
- **Test-plan defects**: D4 broke three existing tests (`"t"` targets); the symlink test could not fail; the scratch-removal check was
  vacuous (the work directory is removed anyway); no seams for the callback, the claim and the hash check; async/directory/outside-root
  rows contradicted D4; the real-pytest library had no install path; the mtime rule was redundant and flaky; no test-to-task map.
  **Fixed** (sections 4 and 6).

**Round 3** (same personas, all `NOT CLEAN`) found, rev 4 fixes:

- **Defect in the spec's own plugin code**: a `JUMP` callback receives three arguments (`code, instruction_offset, destination_offset`), a
  `LINE` callback two, so the two-argument `on_event` made every real run exit 1. **Fixed**: `on_event(code, arg1, arg2=None)`, tested with
  both arities and in a real one-line-loop run.
- The `unavailable` path was unreachable (the hooks still verified and freed another tool's id); `pytest.exit` without `returncode` exits 0;
  the plugin has no import seam for tests and could fail to import on an old venv interpreter (then blamed on the Builder). **Fixed**
  (`_init`, guards, `returncode=3`, a Python 3.8 syntax rule with a test).
- The nonce claim was overstated: any same-user code can read it (`sys.modules`, `gc`, `ps`, `/proc`) and rewrite `out` after
  `sessionfinish`. **Fixed**: the wording now says what the nonce does and does not stop; no new machinery.
- Underspecified decision table for `UNAVAILABLE` plus hard failures, order of `_verify_plugin`, `MEASURE_FAILED` phase, `OSError` on the
  result read, the timeout arithmetic, ineffective `TMPDIR` monkeypatching, plugin MUSTs without tests, CI is CPython 3.12 while the evidence
  is 3.14. **Fixed** (D3, section 4).

**Round 4** (same personas, all `NOT CLEAN`) found, rev 5 fixes:

- **CI interpreter**: `sys.monitoring.clear_tool_id` does not exist on CPython 3.12 (added in 3.13), so the specified `sessionfinish` made every real run on the CI interpreter a `TRACE_MISMATCH`. **Fixed**: `_release_tool` (D2) with a 3.12 fallback, and real-launch rows.
- **Code objects compare by value**, so a library function with the test's name, first line and identical body counted as traced. **Fixed**: membership by identity (`id`), with the objects held alive.
- A FIFO at the result path hangs the harness's `open`. **Fixed**: `O_NONBLOCK` and friends, with FIFO and directory rows.
- D2 contradicted itself on `target_real`/cwd (computed at import vs at call time). **Fixed**: `STATE.target_real` and `STATE.root_real` are captured once; the hooks never call `os.getcwd()`.
- The Python 3.8 rule was not enforceable with `feature_version=(3, 8)` (it accepts `X | None`, `list[int]`, parenthesised `with`; walrus is valid 3.8). **Fixed**: an AST rule set, honestly labelled static.
- Test-plan defects: the token row could not be green as worded; T2 blinded three more existing tests (683, 693, 704); the tamper rows passed for the wrong reason (0o400 file); no `exec` contract; no helper for the traced set; MUSTs without rows; T3 and T4 too big. **Fixed** (sections 4 and 6).
- Disclosures added: a benchmark that delegates its whole workload to a helper gets no power from the trace; single-line branches are invisible; `setsid` escapes; `get_tool` by name is not an ownership proof; `from sys import monitoring` evades the token.

**Round 5** (same personas, all `NOT CLEAN`; the plugin was prototyped on CPython 3.12.13 and 3.14.7 and worked) found, rev 6 fixes:

- The AST rule "reject `BinOp(BitOr)`" rejects the plugin's own `os.O_CREAT | os.O_EXCL` and `LINE | JUMP`. **Fixed**: `BitOr` is rejected only on types, dicts and `isinstance` arguments (D2); parenthesised `with` is reviewed by hand.
- `_init` can skip the claim (`failed`) while the hooks and `sessionfinish` still drove or freed tool id 4 (`ValueError: tool 4 is not in use`, no marker, a foreign id freed). **Fixed**: `STATE.claimed`, hooks and release only when claimed, release in `try/finally`, a missing `BENCH_TRACE_OUT` is `pytest.exit` (D2).
- The marker bullets contradicted each other (an unavailable run has count 0). **Fixed**: explicit precedence (D2).
- `DISABLE` state survives a release and re-claim in one process, so in-process exec rows depend on test order. **Fixed**: unique code objects or `restart_events()` in the test's `finally` (section 4).
- **Honesty**: for the typical lint-permitted benchmark (one library call, then a digest) the count is a constant on both sides, so the trace discriminates only when the body loops or branches on library behaviour; and the trace run is observably different from timed runs (`sys.orig_argv`, `/proc/self`, the loaded plugin), so a trace-aware head passes the trace. **Fixed**: disclosed in full, `orig_argv` and `/proc/self` tokens, `body_has_control_flow` returned for `compare` to show, timeout-verdict rule recorded (D3, D9, disclosed limits).
- Test plan: a real launch tagged T3b before the hooks exist (moved to T3c smoke and T4c); T4c "test-only" while it can expose defects (now allowed to fix); FIFO "deadline" without a mechanism (thread plus `join`); `_release_tool` row asserted only "works" (now the exact call sequence); the early-return row used an uncaught exception; six more MUSTs got rows; `_check_sides` return value and the `work` prefixes were unstated. **Fixed** (D3, D4, sections 4 and 6).

**Round 6** (the last allowed; multi-persona `CLEAN`, attacker and test author `NOT CLEAN`) found, rev 7 fixes:

- **A base-side trace timeout let a Builder-authored benchmark (slow only under tracing) turn a blocking rejection into a non-blocking `INCONCLUSIVE`** and skip the head trace (the same downgrade round 2 closed for `TRACE_UNAVAILABLE`); the "2.5x median" guidance contradicted the 7x slowdown. **Fixed**: the recorded verdict rule now rejects a Builder-authored base timeout; guidance is 10x (D3).
- The `/proc/self` token is common in ordinary fd/memory code (a false positive costs a manual merge) and the D9 grep claim was false. **Fixed**: `/proc/self/cmdline` and `/proc/self/environ` only; claim corrected (D9).
- `_claim_tool` had no consistent contract; `pytest_sessionfinish` did not say what a raising release writes; D3 and D5 disagreed on the detail format; `dir=work` was a `TypeError` (a `TemporaryDirectory` object); the T3c smoke launch could not be built (no helper, no plugin file before T4a); `body_has_control_flow` was thin; `_check_sides` mixed value types; several MUSTs lacked rows. **Fixed** (D2 to D5, sections 4 and 6).

## 1. Premise check (read against `77859929`)

| Claim | Evidence |
|---|---|
| C4d-1 gives the timed-round harness and nothing about the trace | `measure_paired` at `:3286`; its docstring ends "A trace run is not part of this function (C4d-2)." |
| The per-run chain is a closure inside `measure_paired` | `def run(side, phase)` at `:3351`; `fail(code, detail, side, phase)` at `:3334` returns the error and callers `raise` it; `nonlocal counter`, `phase_now[0] = phase`, the pycache override and `argvs.setdefault` live in `run`; the `try:` at `:3362` and its `finally: shutil.rmtree(scratch)` at `:3366` to `:3367` run before the oversize, timeout and exit checks |
| Per-run `os.makedirs` count is three | scratch, and `home`, `tmp` inside `side_env` (`:3188`); a C4d-1 test fails on the 13th call |
| `_run_once` is reusable as is | `:3228`, `(argv, cwd, env, timeout) -> (code or None, ns, stdout, stderr_tail, oversize)`; spawn failure is `_SpawnFailed` (`:3271`) |
| `pytest_argv` has no hook for `-p <plugin>` | `:3209`: a fixed list ending `"-p", "no:cacheprovider", target` |
| `side_env` has nine keys and no `PYTHONPATH` | `:3188` to `:3207` |
| `-P` does not remove `PYTHONPATH` entries; `sys._getframe(1)` in a `LINE` callback is the monitored frame; `hookwrapper=True` works on pytest 9.1.1 / pluggy 1.6.0; tool id 4 is free by default | verified by four reviewers on CPython 3.14.7 |
| `harness_sha256` is over this file's own source plus the validator | `:2168` |
| `BenchmarkGateError` has `side`, `phase`, `partial` | `:908` to `:910` |
| The token tripwire lists `BENCH_TRACE_LINES` only | `_TRIPWIRE_TOKENS` at `:2658`; parametrized in `test_benchmark_gate_diff.py:304` |
| Existing tests that pass the target `"t"` and reach the run | `test_benchmark_gate_measure.py` lines 421, 458, 615 (`BASE_NONZERO_EXIT`, `DIGEST_MISSING`/ini, `WORKLOAD_TOO_SHORT`); lines 683, 693, 704 also pass `"t"` but expect `MEASURE_ARGS_INVALID` |

**Where this spec revises the parent design** (to be folded into the C4d-3 design update; the parent file is untracked in the main
checkout and is not edited here):

1. The plugin ships as a constant inside `benchmark_gate.py`; the own-file digest covers it; the `harness_sha256` domain string stays `-v1`.
2. **Count rule**: `LINE` plus `JUMP` events in the **traced code set** (the test body and its decorator chain), not "benchmark-file
   frames whose caller is a benchmark-file frame".
3. **Result channel**: a harness-owned file under an `out_dir`, with a per-run nonce, not a stdout line.
4. `TRACE_UNAVAILABLE`, returned only when **both** sides report the same unavailability.
5. `BENCH_TRACE_*`, `bench_trace_plugin`, `sys.monitoring`, `import monitoring`, `orig_argv`, `/proc/self/cmdline` and `/proc/self/environ` join the token
   tripwire (twelve tokens in all, not the parent's six).

**Further deviations found by the whole-branch review (implementation round 1) to be written back before C4d-3:**

6. `measure_paired` now rejects a target that is not an ASCII, relative `.py` path (no `..`, no empty/`.` component, no control character or
   backslash in the file part, no leading `-`); a C4d-1 tightening (D4).
7. A spawn failure and an oversize output of the trace run fold into `TRACE_MISMATCH` (the parent names only timed-out, failed and silent
   runs). Every error carries a structured `kind` (closed vocabulary `TRACE_FAILURE_KINDS`) so `compare` need not parse the detail;
   errors raised after both sides produced a result also carry `trace` (both sides' values, interpreters, argv,
   `body_has_control_flow`); `partial` stays `None`.
8. `TRACE_UNAVAILABLE` has no row in the parent outcome table; C4d-3 must define its result, finding and retry semantics (no timed run has
   happened, so it behaves like `HOST_BUSY_START`).
9. `trace_paired` runs before the timed runs and does not check the digest: a head with wrong output and different control flow reports
   `TRACE_MISMATCH` (non-blocking for a PRE_EXISTING benchmark) rather than the blocking `DIGEST_MISMATCH`; C4d-3 should order the checks
   or run the digest check first.
10. The trace budget: `validate_benchmark_gate`'s cap `(warmup + repeats + 3) * 2 * T <= 1800` hardcodes the factor 3 of
    `_TRACE_TIMEOUT_FACTOR`; there is no base median before the trace runs, so the "10x median" advice of rev 7 is replaced by: the gate's
    `per_run_timeout_seconds` must leave room for a traced run (about 7x the benchmark's time for a tight loop), and a
    `BUILDER_AUTHORED` benchmark that cannot be traced in `3 * T` is rejected with that text.
11. The shipped trace `argv` is not rerunnable by a human (the ini and plugin directory are temporary): `compare` must label it harness-only.

**Prototype numbers** (macOS, CPython 3.14.7, pytest 9.1.1; simulations of the D2 plugin, not the shipped one; real tests assert
relations and lower bounds, never literals, because event counts differ across CPython versions): a library calling a benchmark-file
callback 208 times against once with a batch, test-body counting: equal counts. A 300,000-iteration in-file loop: about 7 times slower
in the test body (0.01 s to 0.07 s). A 3,000,000-iteration pure-Python library loop: 0.94 s with a callback firing on every line, 0.18 s
when it returns `DISABLE` for every other code object. A one-line `for` over K items: `LINE` count 5 for K=10 and K=1000; with `JUMP`
counted it is 10 and 1000.

## 2. Design

**D1. The plugin is a raw-string constant, written fresh per side.** `TRACE_PLUGIN_SOURCE: str` (a raw `r"""` string, ASCII, about 210
lines) lives in `benchmark_gate.py`. For each side `trace_paired` runs inside `with tempfile.TemporaryDirectory(prefix="bench-run-") as work:` (`work` is the path string; the
`with` encloses the run and the result steps of D3, so the result is read before the directory goes, and each side's directory is gone
before the next side starts; the empty ini is `work/empty.ini`; `measure_paired` uses the same `bench-run-` prefix and the same per-run names, so a trace run is not recognisable from its `HOME`, `TMPDIR`, pycache or ini paths) and creates `plugin_dir = tempfile.mkdtemp(dir=work, prefix="plugin-")`
(mode `0o700` by construction), writes `bench_trace_plugin.py` into it with `O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW` mode `0o400` through
`_write_plugin(plugin_dir) -> str`, and, **after the argv and environment are built and immediately before `_execute`**, calls `_verify_plugin(path)`, which re-reads the file and compares
its SHA-256 with that of `TRACE_PLUGIN_SOURCE.encode("ascii")`; a mismatch is `MEASURE_FAILED`. A path containing `os.pathsep` is
`MEASURE_FAILED`. Rejected: a separate file under `scripts/` (needs `harness_sha256`, packaging and a domain bump); a directory under
the repository; one directory for both sides (the Builder-authored benchmark in the base run could rewrite the plugin the head run loads).
**Residual (disclosed)**: same-user code in the child can rewrite its own side's plugin file between the hash check and the import.

**D2. The plugin.** Module `bench_trace_plugin` (`_TRACE_MODULE`), loaded with `-p bench_trace_plugin`. **It must import on CPython 3.8
and later** (the side's venv may be older than this repo's 3.12; pytest 9 itself needs 3.10, so the floor only matters with an older
pytest): the module has **no annotations at all**, no `match`/`except*`, no `X | Y` on types or dicts, no parenthesised `with`, no
subscripted builtins (`list[int]`) and none of `str.removeprefix`/`removesuffix`, `functools.cache`, `zoneinfo`; anything that needs 3.12
sits behind the `sys.monitoring` guard. This is enforced **statically** (`ast.parse(source, feature_version=(3, 8))` plus an AST walk that
rejects annotations, subscripted builtins, those names, and a `BinOp(BitOr)` only where an operand is `None`, a builtin type name, a
`Subscript`, a `Dict`, or the second argument of an `isinstance`; flag arithmetic such as `os.O_CREAT | os.O_EXCL` and
`events.LINE | events.JUMP` is allowed); "no parenthesised `with`" cannot be seen by that walk and is **reviewed by hand**; the whole
rule set is not run on a real 3.8. A venv interpreter without
`sys.monitoring` must report `no_monitoring`, never fail to import. The module ends with one call, `_init(os.environ,
sys)`, which runs at import (before collection, so before any benchmark or library import) and:

1. pops each of `BENCH_TRACE_FILE`, `BENCH_TRACE_OUT` and `BENCH_TRACE_NONCE` **with a default** from the given environment into `STATE`
   (so a missing one cannot leave the others behind), then sets `failed` if any was absent; captures **once**, here, `root_real =
   os.path.realpath(os.getcwd())` and `target_real = os.path.realpath(os.path.join(root_real, BENCH_TRACE_FILE))` (so a benchmark that
   later `chdir`s, even to `/`, cannot move them) and sets `failed` unless `target_real` is a regular file inside `root_real`; removes its
   own directory (`os.path.dirname(__file__)`) from `sys.path` and from `PYTHONPATH` (deleting the key when it ends up empty). This is
   hygiene, not an integrity control (`sys.modules` still holds the module);
2. unless `failed` is already set, claims `sys.monitoring` tool id `4` through `_claim_tool(sys_module)`, which returns
   `None` on success (it calls `use_tool_id(4, _TRACE_MODULE)`, so the tool name is the module name) or one of three tokens and never
   raises: `no_monitoring` (no `sys.monitoring`, Python below 3.12), `tool_in_use` (`ValueError`), or `error` (any other exception, for
   example an `AttributeError` from `use_tool_id`). `_init` stores the first two in `STATE.unavailable`, sets `failed` for `error`, and sets
   `STATE.claimed = True` **only** when `_claim_tool` returned `None`.

`_release_tool(sys_module)` releases the id on CPython 3.12 and later alike: `clear_tool_id(4)` where it exists (3.13+), otherwise
`register_callback(4, LINE, None)` and `register_callback(4, JUMP, None)`; then `free_tool_id(4)`. (On 3.12 `clear_tool_id` is absent and a
callback survives `free_tool_id`; on 3.14 `free_tool_id` clears it.) `pytest_sessionfinish` and every test that really claims id 4 use it.

**Seams for tests.** The plugin source is `exec`'d by tests with the namespace `{"__file__": <tmp path>, "__name__": "bench_trace_plugin"}`
(the module needs `__file__`); because the module ends by calling `_init(os.environ, sys)` on the *real* process objects, every exec test
(a) sets the three `BENCH_TRACE_*` variables via `monkeypatch`, (b) patches `sys.monitoring` with a fake when it must not claim the real
id, and (c) releases a really-claimed id in a `finally` via `_release_tool`; rows that claim the real id carry
`skipif(not hasattr(sys, "monitoring"))`. `_init` and `_claim_tool` can also be called directly with fakes after one such exec.

State lives in a module-level object `STATE` with fields `traced_ids` (a set of `id(code)`; the code objects themselves are held in `keep`, so
an id is never reused; **membership is by identity, because code objects compare by value** and an equal-bodied function in another file
would otherwise count), `keep`, `thread`, `count`, `failed`, `unavailable`, `out`, `nonce`, `root_real`, `target_real`; the event function is the module-level **`on_event(code, arg1, arg2=None)`** (a `LINE` callback is called with
`(code, line_number)`, a `JUMP` callback with `(code, instruction_offset, destination_offset)`), so tests can drive it with both arities.
**`pytest_pyfunc_call` and `pytest_sessionfinish` do monitoring work (register, `set_events`, `get_tool`, release) only when
`STATE.claimed`**: with `failed` set before the claim, or `unavailable`, the id is not ours and is never driven or freed. Hooks:

- `pytest_collection_modifyitems`: not exactly **one** item collected -> `failed`.
- `pytest_pyfunc_call` (`hookwrapper=True`): unless not `claimed` (so also when `unavailable`; decided first, so a decoy cannot mask an unavailable report), resolve
  the **traced set** with the module function `_traced_set(obj, originalname) -> tuple | None` (`None` -> `failed`): walk the `__wrapped__`
  chain starting at `obj` (`obj` plus at most 8 `__wrapped__` hops; a cycle or a longer chain -> `None`); every link must have a
  `__code__`; keep the codes whose `os.path.realpath(co_filename)` equals `STATE.target_real` (the hook never calls `os.getcwd()`); the **innermost** link's `__code__.co_name` must equal
  `pyfuncitem.originalname` and be in the target file, else `failed` (this rejects a decoy named differently and a decorator that did not
  use `functools.wraps`). A link without `__code__` (a `functools.partial`) -> `failed`. Register `on_event` for `LINE` and `JUMP`, enable
  both events for the call, record `threading.get_ident()`, and disable them again right after the `yield` (so teardown is never traced).
- `on_event` is wrapped in `try/except BaseException` (any exception sets `failed`, never propagates into the monitored frame). A code
  object whose `id` is not in `traced_ids` -> `return sys.monitoring.DISABLE` (all of pytest and the library are switched off for good); otherwise count
  one event iff the thread matches. It never returns `DISABLE` for a traced code object and never calls `restart_events`. `BRANCH` is not
  used (deprecated in 3.14).
- `pytest_sessionfinish`: only when `claimed`: `set_events(4, 0)`, verify `sys.monitoring.get_tool(4)` equals `_TRACE_MODULE` (else
  `failed`; the name is a courtesy check, **not** an ownership proof: a re-claim under the same name passes), `_release_tool`, all inside
  `try/except BaseException: STATE.failed = True` followed by `finally`: the marker below is written on every path, and a raising release
  therefore yields the `.failed` marker (the exception is swallowed). If `STATE.out` is absent (the variable was
  missing) there is no path to write: `pytest.exit("trace out path missing", returncode=3)`. `restart_events` is never called. Note `DISABLE` switches off one code *location*, so the cost is one callback per distinct
  location of other code, not per execution.

**Count rule: `LINE` + `JUMP` events in the traced code set.** Not counted, and **disclosed as blind spots**: helper and callback bodies,
generator expressions, lambdas, `map`, `exec`/`eval` code, `async` bodies (an `async def` test fails in pytest, so it ends as a non-zero
exit; the body of `asyncio.run(main())` is simply invisible, the count is a small constant), and a decoy function that happens to carry the
test's own name inside the benchmark file. Because a C-level library entry and a Python one leave the test-body events unchanged, the
count does not depend on how the library is implemented. A one-line loop or an inlined comprehension in the body **is** seen (via `JUMP`).

**Terminal marker (the plugin writes exactly one marker).** In `pytest_sessionfinish` the plugin writes, with `O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW`,
mode `0o600`, looping on `os.write` until the whole content is written:

Decided in this order (first match wins):

1. `failed` (the collection hook has no `claimed` gate, so two collected tests set it in every state) -> `BENCH_TRACE_OUT + ".failed"` containing `failed\n`
   (same flags; if that also fails the plugin calls `pytest.exit("trace marker not writable", returncode=3)`, which makes the exit
   non-zero; either way step 2 of D3 finds no usable `out` and fails closed);
2. `unavailable` -> `BENCH_TRACE_OUT` containing
   `BENCH_TRACE_UNAVAILABLE: <no_monitoring|tool_in_use> <major.minor.micro> <impl> <nonce>\n`;
3. a count of `0` (only reachable when not unavailable) -> `.failed` as in 1;
4. success -> `BENCH_TRACE_OUT` containing `BENCH_TRACE_LINES: <n> <major.minor.micro> <sys.implementation.name> <nonce>\n`.

An `O_EXCL` failure on the primary write (rules 2 and 4) also writes `.failed`.

The `.failed` file is attacker-creatable: it can only **suppress** a result (fail closed); it is never an integrity signal. **What the
nonce does and does not stop**: it defeats code that never executes in the child at the right moment (a pre-created file, `os._exit`,
a wrong-nonce rewrite). It does **not** stop any code running in the child, which can read the nonce and the out path from `sys.modules`,
`gc`, `ps` or `/proc/self/environ`, set `STATE.count`, or unlink and rewrite `out` in an `atexit` handler after `sessionfinish`; such a forge
needs the base count (deterministic and one local run away) and no knowledge of `sys.monitoring`. That is in-process tampering, the
accepted limit of the parent threat model, and it is the cheap end of it; the D9 tokens catch only its textual forms. Tool id 4 is claimed at plugin import, before collection and so before any benchmark or library import; a startup hook
(`sitecustomize`, `.pth`) that claims it earlier is install-time code execution, outside every in-process control (parent threat model) and
caught as `PROTECTED_PATH_CHANGED` when it is in the diff.

**D3. `trace_paired`.**

```
trace_paired(base_root, head_root, base_bin, head_bin, target, *, timeout_seconds, argv_builder=None, ini_path=None) -> dict
```

Returns `{"base": int, "head": int, "interpreter": "<version> <impl>", "argv": {"base": [...], "head": [...]}, "body_has_control_flow": bool}`
(`body_has_control_flow` is **advisory, not an integrity signal**: computed **before the first child run** from the base root's benchmark file, opened
with `O_RDONLY|O_NOFOLLOW|O_NONBLOCK`, a regular-file `fstat` and a 16 KiB cap (as in step 2 below); it reports on the function named by
the target's `::name` (when the target has no `::name`, or names a method or something absent, the first module-level `test*` function;
none found is `False`); the walk does not descend into nested `Lambda`, `FunctionDef` or `GeneratorExp` (the trace cannot see them) and
looks for `For`, `AsyncFor`, `While`, `If`, `IfExp`, `Try`, `Match`, `BoolOp`, `ListComp`, `SetComp` or `DictComp`; every parse or read
exception (`SyntaxError`, `ValueError`, `RecursionError`, `MemoryError`, `OSError`) is `False`; function is `False`; it lets `compare` tell a human "the trace has no discriminating power for this benchmark"). Validation (exactly C4d-1's
messages, same order): `os.name == "posix"` (`UNSUPPORTED_PLATFORM`), `_check_timeout(timeout_seconds)`, `_check_sides(...)` (D4; it returns the tuple `(sides, benchmark_file)` where `sides` keeps `measure_paired`'s existing `{name: (realpath root, realpath bin)}`
shape, and `trace_paired` passes the full `target` to `pytest_argv` and `benchmark_file` to `trace_env`).
Per side, **base then head**, one untimed run in its own `work` directory (`TemporaryDirectory`) with an empty ini (or `ini_path`):
`_prepare_run` (with `work` as in D1), a fresh `plugin_dir` (D1), a fresh `out_dir = tempfile.mkdtemp(dir=work, prefix="out-")` (a **sibling** of the scratch
directory, not under scratch, `HOME` or `TMPDIR`), `out_path = out_dir/trace.out`, a fresh `nonce = os.urandom(16).hex()`, the sequence is: write the plugin, build argv from
`pytest_argv(..., plugins=(_TRACE_MODULE,))` or `argv_builder(side, bin_dir, root, target)` (the seam), build the environment with
`trace_env(env, plugin_dir, benchmark_file, out_path, nonce)`, `_verify_plugin`, then `_execute` with timeout `_TRACE_TIMEOUT_FACTOR *
timeout_seconds` (`3`; the traced slowdown is about 7x for a pure in-file loop and unmeasured for others, so an honest benchmark that runs
longer than about `3T/7`, roughly 43% of `timeout_seconds`, becomes a `TRACE_MISMATCH`: disclosed). **Verdict rule recorded for C4d-3**: a trace timeout's detail starts with `timeout:`. For `side="base"`: when `benchmark_origin` is
`BUILDER_AUTHORED`, `compare` MUST treat it as `TRACE_MISMATCH` (REJECTED, Builder-fixable: "your benchmark is too slow to trace"), because
the Builder authored the only thing that differs on the base side and the head trace was never run (otherwise a benchmark that is slow only
under tracing would turn a blocking rejection into an `INCONCLUSIVE`); when `PRE_EXISTING`, `INCONCLUSIVE`. For `side="head"` after a
completed base trace: REJECTED. No trace outcome other than a normal return may lead to `IMPROVED`, and a trace timeout never counts as the
per-task re-measure. Because the traced slowdown is at least 7x and unbounded for tight loops, the gate's `per_run_timeout_seconds` must leave room for a
traced run (there is no base median yet when the trace runs; see deviation 10); raising `_TRACE_TIMEOUT_FACTOR` would break the gate's
budget cap, which hardcodes the factor 3.
After `_execute` returns, in this order:

1. `os.path.lexists(out_path + ".failed")` -> `TRACE_MISMATCH` ("plugin reported failure").
2. Read `out_path`: `os.open(..., O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_NOCTTY|O_CLOEXEC)` (a FIFO with no writer would block a plain open
   forever and hang the verdict path; `O_NONBLOCK` makes it return so the regular-file check rejects it), then `fstat` **on the descriptor**: regular file, `st_nlink == 1`, `st_uid ==
   os.getuid()`, `st_size <= 256`, read at most 257 bytes; absent, any check failing, or an `OSError` from open, fstat or read (ELOOP for a
   symlink, EACCES) caught **locally** -> `TRACE_MISMATCH` ("no trace result"), never `MEASURE_FAILED`.
3. Full-match one of `\ABENCH_TRACE_LINES: ([0-9]{1,18}) ([0-9]+\.[0-9]+\.[0-9]+) ([a-z]+) ([0-9a-f]{32})\n\Z` or
   `\ABENCH_TRACE_UNAVAILABLE: (no_monitoring|tool_in_use) ([0-9]+\.[0-9]+\.[0-9]+) ([a-z]+) ([0-9a-f]{32})\n\Z`; no match, a count of `0`
   (defence in depth: the plugin never writes it), or a nonce different from the one generated for this run -> `TRACE_MISMATCH` ("no trace
   result"). A **fresh nonce per side**.

The *interpreter string* is the `<major.minor.micro> <impl>` fields of the result line. A hard failure (`_execute` kinds, steps 1 to 3) on
either side raises `TRACE_MISMATCH` at once with `side` set and the second side is not run; this also applies when the base side was
`UNAVAILABLE` and the head side hard-fails (`side="head"`). After both sides produced a result, this table is evaluated top to bottom:

| Base / head result | Outcome |
|---|---|
| exactly one side `UNAVAILABLE` | `TRACE_MISMATCH`, `side` = the unavailable side ("unavailable on one side only") |
| both `UNAVAILABLE`, different tokens | `TRACE_MISMATCH`, `side=None` |
| both `UNAVAILABLE`, same token, interpreter strings equal | `TRACE_UNAVAILABLE`, `side=None`, `detail` holds the token |
| both `UNAVAILABLE`, same token, interpreter strings differ | `TRACE_MISMATCH`, `side=None` |
| both counts, interpreter strings differ | `TRACE_MISMATCH`, `side=None`, both strings in `detail` |
| both counts, counts differ | `TRACE_MISMATCH`, `side=None`, both counts in `detail` |
| both counts equal | return |

**One rule for the two error codes**: a fault of the harness's own machinery (`mkdtemp`, `_write_plugin`, `_verify_plugin` mismatch, a path
containing `os.pathsep`, any `OSError`/`RuntimeError`/`SubprocessError` outside the child, creating the per-side `work`) is `MEASURE_FAILED`;
what the child did (every `_execute` kind including spawn failure, a missing/invalid result, `.failed`, a mismatch) is `TRACE_MISMATCH`
(or `TRACE_UNAVAILABLE`). `phase = "trace"` on every error raised after argument validation has passed (that includes creating the first
`work` directory); `UNSUPPORTED_PLATFORM` and `MEASURE_ARGS_INVALID` keep `phase = None`; `side` is `None` on `MEASURE_FAILED`; `partial =
None` throughout. The trace adapter formats every detail as `"<kind>: <detail>"` (`_execute`'s detail already names the side; `side` is also an
attribute) with `kind` in
`spawn`, `oversize`, `timeout`, `nonzero` (a death by signal is `nonzero`) (`_execute` prints the timeout it was given, `3T`, so the adapter appends " (3x the per-run
timeout)" for `timeout`). The digest is not checked and stdout is not parsed.
`TRACE_UNAVAILABLE` is meaningful only when `base_bin` and `head_bin` are distinct, independently built venvs (a shared `site-packages`
or startup file would let one Builder-controlled effect hit both sides): C4d-3 relies on `check_venv`'s distinct-roots result.

**D4. Shared validation.** `_benchmark_file_of(target) -> str`: `isinstance(target, str)` (kept), the part before the first `::`; non-empty, no NUL, no backslash, not
absolute, no `.`, `..` or empty component (a trailing slash is rejected), does not start with `-`, ends in `.py`; else
`MEASURE_ARGS_INVALID` (message "target must be a .py path under the root, without '..' or a leading '-'"). It is a second path grammar next to the gate's own (`_benchmark_path_ok`); it is deliberately lower level (it validates a pytest target
string for the harness, not a gate field) and is not shared with it. It rejects traversal by name; an in-tree symlink pointing outside the root is refused by the export step and by the
plugin's "regular file inside `realpath(cwd)`" check. `_check_timeout(t)`: a number (not `bool`, not NaN) in `(0, 3600]`, else
`MEASURE_ARGS_INVALID`. `_check_sides(base_root, head_root, base_bin, head_bin, target, ini_path) -> (sides, benchmark_file)`: the roots/bins checks, the
`samefile` and nested-root checks, `_benchmark_file_of`, and the `ini_path` check, moved unchanged out of `measure_paired` and called at the
same position (`_check_timeout` before the `min_base_ns` check, `_check_sides` after it), so error precedence is unchanged. `measure_paired` now applies `_benchmark_file_of` too; the six existing tests that pass
`"t"` (lines 421, 458, 615, which reach the run, and 683, 693, 704, which expect the sides errors and would be masked by the new target
error) change their target to `"bench.py::t"` in T2.

**D5. One classification chain.** Module level, exact:

```
_prepare_run(side, bin_dir, work, counter) -> tuple[str, dict]
    # os.makedirs(work/<side>-<counter>) -> scratch; env = side_env(bin_dir, scratch);
    # env["PYTHONPYCACHEPREFIX"] = work/pycache-<side>; three makedirs per run, as today
_execute(side, argv, root, scratch, env, timeout_seconds, fail) -> tuple[int, bytes]    # (elapsed_ns, stdout)
    # try: _run_once(argv, root, env, float(timeout_seconds))
    # except _SpawnFailed as exc: raise fail("spawn", f"could not start the run: {exc}") from exc
    # finally: shutil.rmtree(scratch, ignore_errors=True)
    # then, in this order: oversize -> raise fail("oversize", f"{side} run wrote {_RUN_FSIZE_LIMIT} bytes")
    #   timed out (code None) -> raise fail("timeout", f"run exceeded {timeout_seconds} s")   # the ORIGINAL value, int stays "1 s"
    #   code != 0 -> raise fail("nonzero", f"exit {code}: {_tail_detail(tail)}")
```

`_execute` builds all four detail strings; `fail(kind, detail) -> BenchmarkGateError` is the caller's adapter, which only maps kind to code,
`side`, `phase`, `partial` (`measure_paired`: `<SIDE>_NONZERO_EXIT` for spawn and nonzero, `OUTPUT_TOO_LARGE`, `<SIDE>_TIMEOUT`;
`trace_paired`: `TRACE_MISMATCH` with the detail prefixed `"<kind>: "`). `measure_paired` keeps `nonlocal counter`,
`phase_now[0] = phase` (before `_prepare_run`), `argvs.setdefault`, the digest parse. The per-side `work` directory (and so `out_dir`) is
removed by its `TemporaryDirectory`; `_execute` never gets a keep-scratch flag. **T0 characterization tests pass on the base first.**

**D6. Codes.** `TRACE_REFUSAL_CODES = ("TRACE_MISMATCH", "TRACE_UNAVAILABLE")`; `ERROR_CODES += TRACE_REFUSAL_CODES`; the pin in
`test_benchmark_gate_exports.py` is extended in the same commit. `compare` (C4d-3) maps `TRACE_MISMATCH` by `benchmark_origin` per parent
lines 250 and 252 and `TRACE_UNAVAILABLE` to `INCONCLUSIVE`/`NEEDS_EVIDENCE` (both sides agreeing that the interpreter cannot trace is
an environment fault, not the Builder's) -- recorded for the C4d-3 design.

**D7. `pytest_argv(bin_dir, root, target, ini, *, plugins=())`**: `plugins` must be a `tuple` or `list` whose every element equals
`_TRACE_MODULE` (else `ValueError`); each becomes `"-p", name` after `"-p", "no:cacheprovider"` and before the target. The no-plugin argv
is byte-identical to today's.

**D8. `trace_env(env, plugin_dir, benchmark_file, out_path, nonce) -> dict`**: a **copy** of `env` plus exactly `PYTHONPATH=plugin_dir`,
`BENCH_TRACE_FILE`, `BENCH_TRACE_OUT`, `BENCH_TRACE_NONCE`. The input is not mutated; timed runs never see these keys.

**D9. Token tripwire.** `_TRIPWIRE_TOKENS` (`:2658`) gains, **appended in this order** (existing hit-order tests depend on tuple order), `BENCH_TRACE_`, `bench_trace_plugin`, `sys.monitoring`,
`import monitoring` (it covers `from sys import monitoring [as m]`), `orig_argv`, `/proc/self/cmdline` and `/proc/self/environ` (the trace run's argv carries
`-p bench_trace_plugin`, a timed run's does not, and `sys.argv` is already a token but `sys.orig_argv` is not) -- a head diff adding any
of them outside the benchmark file is `BENCHMARK_AWARE_CODE`, a human-reviewed outcome; the existing `BENCH_TRACE_LINES` stays. The
parametrized test (`test_benchmark_gate_diff.py:304`; it asserts `token in error.detail`, so it stays green) gains the new samples
and the `token_tripwire` docstring (`:2868`) is updated. Because the detail names the **matched** token, a line with `BENCH_TRACE_OUT` is
reported as `BENCH_TRACE_ in <path>` (the prefix token); the parametrization is therefore `(sample, expected_token)` and asserts on the
hits, not on the sample text. A multi-name `from sys import path, monitoring` and a bare `monitoring` are not tokens (the word is common in observability code). The
tokens are **textual only** (evaded by `import sys as s`, `getattr`, string concatenation or `gc`), and
`sys.monitoring` will flag legitimate head code (profilers, coverage) for human review. Repo-wide grep: `orig_argv` occurs nowhere else; `/proc/self` occurs only as harness or test source (`benchmark_gate.py:1100-1114`,
`test_benchmark_gate_overlay.py:473`, `test_benchmark_gate_exports.py:1050-1051`), never as a tripwire sample or diff fixture. Bare
`/proc/self` is deliberately not a token (fd, memory and container code uses it routinely and a false positive here is a manual merge);
`/proc/%d/cmdline` with `os.getpid()`, `/proc/thread-self`, `psutil` and `ps` evade the tokens.

**Disclosed limits (carried into the module docstring).** The trace is a narrow tripwire, not a boundary, and its value is smaller than
"the trace" suggests. **For the typical benchmark** (one test function whose body makes a library call and prints a digest of the result,
which the lint permits and the Builder is told to write) **the count is a small constant on both sides and equality proves nothing**; the
trace discriminates only when the test body loops or branches on something the code under test returns or does (`while lib.more()`, an
early return on a library flag). Then it catches library behaviour that changes the body's control flow while the digest stays equal. For
every other shape (including a body that delegates the workload to a module-level helper, a loop whose bound does not depend on the
library, helpers, callbacks, generator expressions, lambdas, `map`, `exec`/`eval`, `asyncio.run(main())` bodies, a same-named decoy, and
branches inside a single line) the controls are the digest, the lint and human acceptance. `trace_paired` returns the counts and
`body_has_control_flow` so `compare` can show a human a suspiciously small count.

Two further classes sit outside the trace and are not detected by it: (1) code executing in the child can tamper with `sys.monitoring`
(`register_callback` returns the plugin's callback, so a library can wrap it and stop forwarding at a chosen count; only the textual
`sys.monitoring` token sees it), the plugin file, the result file, `STATE` or the nonce (reachable from `sys.modules`, `gc`, `ps` and
`/proc`; same user, in process), and a process that escapes the group kill (`setsid`) can rewrite `out` after the plugin; (2) **the trace run
is observably different from the timed runs** (`sys.orig_argv`, `/proc/self/cmdline`, `sys.modules`, `sys.monitoring.get_tool(4)`,
slowdown), so head code that branches on the difference passes the trace and shortcuts the timed runs: benchmark-aware code of the same
class as `PYTEST_CURRENT_TEST`, caught only by the textual tokens and human review. A suppressed or missing result is fail-closed and not a
bypass; only a forged matching result is. A structural fix (load the plugin, inert, in the timed runs too, removing the argv and
`sys.modules` differentiators at equal cost on both sides) is deferred to the C4d-3 design pass (section 8).

## 3. Acceptance

Numbers are relations; literals above are simulation only.

| Scenario | Expected |
|---|---|
| Library calls a benchmark callback N times (base) vs once with a batch (head); callback calls a benchmark helper | counts equal -> returns |
| The library entry written as Python `[f(i) ...]` vs `map` (comprehension lives in the library module) | counts equal |
| Head's library makes the test body loop a different number of times (`while lib.more():`; also as a one-line `for`) | counts differ -> `TRACE_MISMATCH`, `side=None`, both counts in `detail` |
| Body catches an exception inside the loop / returns early on head only | counts differ -> `TRACE_MISMATCH` |
| Straight-line body (no loop, no branch): any library change | counts equal; expected, the typical case; `body_has_control_flow` is `False` |
| `functools.wraps`-decorated test | traced; equal counts on equal bodies |
| Decorator without `wraps`, or `__wrapped__` pointing at a differently-named decoy; two tests; plugin `failed` | `TRACE_MISMATCH` ("plugin reported failure") |
| `async def` test | pytest exits non-zero -> `TRACE_MISMATCH` |
| Library prints `BENCH_TRACE_LINES: 999` at exit; creates `BENCH_TRACE_OUT` early (also when the plugin fails and writes only `.failed`, and via `os._exit`); a FIFO or a directory at the out path | count unchanged / `TRACE_MISMATCH`, never accepted (for code that does not read the nonce; a nonce-aware rewrite is the disclosed in-process tamper), never a hang |
| Benchmark `chdir`s at import (also to `/`); an `evil -> ../outside` symlink | still matches / rejected by the plugin |
| A code object with the test's name and body from another file | not counted |
| Both sides report tool id 4 taken (or both `no_monitoring`) | `TRACE_UNAVAILABLE` |
| Only one side unavailable; both unavailable with different tokens or interpreters | `TRACE_MISMATCH` |
| CPython 3.12 (no `clear_tool_id`) | claim, trace, release, re-claim all work |
| Library-heavy workload | `on_event` returns `DISABLE` for every non-traced code object (asserted on the function) |
| Timed-run environment | none of `PYTHONPATH`, `BENCH_TRACE_FILE`, `BENCH_TRACE_OUT`, `BENCH_TRACE_NONCE` |

## 4. Tests

"Base" is `77859929`. T3a/T3b/T3c/T4a/T4b/T4c rows fail there by `AttributeError` or assertion; the T0 rows and the T2 characterization guards (the
six edited `"t"` tests, `test_sides_checks_run_before_the_target_check`) **pass on the base** and exist to catch a slipped extraction;
only the new-rejection rows of T2 fail on the base. The mutant column is what each test is for. Real-pytest rows carry
`skipif(not hasattr(sys, "monitoring"))`; CI runs CPython 3.12 while this spec's evidence came from 3.12 and 3.14 (counts differ by
version), so they assert relations and lower bounds only, and the async row asserts the code, not the detail text. The new file
`test_benchmark_gate_trace.py` is **created in T3b**, which copies `fake_sides`, `builder` and `pytest_venv` (extended to write the
per-side library module into the venv's `site-packages`, because `-P` needs the code under test installed) from the measure file;
T4c defines the claiming `.pth` helper (a `.pth` line that calls `sys.monitoring.use_tool_id(4, "x")`).

**Exec-test contract (T3b and later).** Tests `exec` the plugin source with `{"__file__": <tmp path>, "__name__": "bench_trace_plugin"}`. Because the
module ends with `_init(os.environ, sys)` on the *real* process objects, each such test: sets the three `BENCH_TRACE_*` variables with
`monkeypatch.setenv`; `monkeypatch.chdir`s into a directory holding a real regular `BENCH_TRACE_FILE` (otherwise `_init` sets `failed`
and never claims); patches `sys.monitoring` with a fake (`monkeypatch.setattr(sys, "monitoring", fake, raising=False)`, the fake having
`events`, `DISABLE`, `use_tool_id`, `get_tool`, `set_events`, `register_callback`, `free_tool_id`, optionally `clear_tool_id`) unless the
row deliberately claims the real id; releases a really-claimed id in a `finally` through `_release_tool`; and, because `DISABLE` state
survives a release and re-claim in the same process, uses code objects unique to the row (built with `compile(..., filename, "exec")`
and given `co_filename = target_real` where the row needs a matching file) or calls `sys.monitoring.restart_events()` in the `finally`
(the "no `restart_events`" rule is about the plugin source only). Forged-result rows read `out` and the nonce from
`sys.modules["bench_trace_plugin"].STATE` inside the child.

**T0 (pass on the base), in `test_benchmark_gate_measure.py`:** `test_characterize_error_details` (the four detail strings; int timeout ->
`"run exceeded 1 s"`); `test_oversize_beats_timeout` (child script: write 3 MiB swallowing the `OSError`, then sleep) and
`test_oversize_beats_nonzero_exit` ("timeout beats non-zero" is not separately observable: a timed-out child has `code is None`);
`test_scratch_is_removed_after_spawn_failure_timeout_and_nonzero` (a spy on `bg.shutil.rmtree` that **calls through to the real one**,
filtering by the `<side>-<n>` basename, one call per failing run); `test_spawn_failure_cause_is_spawn_failed`; the existing
>12-makedirs test stays; the existing environment test gains the assertion that none of `PYTHONPATH`, `BENCH_TRACE_FILE`,
`BENCH_TRACE_OUT`, `BENCH_TRACE_NONCE` is in any timed run's environment (a guard, non-vacuous only against a `side_env` change).

| Test | Task | Kills |
|---|---|---|
| `test_benchmark_file_of_and_check_timeout_reject_the_bad_inputs` (also through `measure_paired`) | T2 | D4 gaps |
| `test_sides_checks_run_before_the_target_check` (bad sides plus bad target -> the sides message) | T2 | changed error precedence |
| the six existing `"t"` tests edited to `"bench.py::t"` | T2 | the sides checks being masked by the new target check |
| `test_trace_env_is_a_copy_with_four_keys` | T3a | mutating the input; extra keys |
| `test_pytest_argv_plugins_keyword_only_validated_and_placed_before_the_target` (tuple and list of the module name accepted; `"abc"`, `("os",)`, `["x;y"]` rejected) | T3a | string iteration; misplacement |
| `test_token_tripwire_flags_the_new_tokens` (`(sample, expected_token)`; assert `expected_token` is **among** the hit tokens, not equal to them; new tokens appended; samples include `BENCH_TRACE_OUT`, `bench_trace_plugin`, `sys.monitoring`, `from sys import monitoring`, `sys.orig_argv`, `/proc/self/cmdline`) | T3a | missing token; reordering |
| `test_plugin_source_is_ascii_has_no_annotations_and_passes_the_static_3_8_rules` (the real plugin accepted; samples with `dict \| dict`, `x: int \| None`, `list[int]`, `removeprefix`, `match` rejected; the `r"""` prefix read with `tokenize` from the file) | T3b | new syntax or APIs; a non-raw literal |
| `test_the_plugin_constant_lives_in_the_digested_file_and_the_literals_agree` (`TRACE_PLUGIN_SOURCE` occurs verbatim in `Path(bg.__file__).read_bytes()`; `_TRACE_MODULE`, the file name `_write_plugin` will use, the `use_tool_id` name and the `get_tool` check in the source all agree) | T3b | constant moved out of the file; drifting literals |
| `test_init_pops_with_defaults_captures_root_and_target_once_and_removes_only_its_dir_from_sys_path_and_pythonpath` (other `PYTHONPATH` entries kept; key deleted when empty; dir absent from `sys.path` tolerated; `chdir("/")` after import; absent variable -> `failed`, none left behind; outside-root target -> `failed`) | T3b | leaving the nonce; live `getcwd` |
| `test_claim_tool_reports_tool_in_use_no_monitoring_and_error_and_never_raises` (real id 4 occupied; `_claim_tool(fake_sys)` for no `monitoring`; an `AttributeError`/`RuntimeError` fake -> `"error"`, and `_init` maps it to `failed`) | T3b | raising; wrong token |
| `test_release_tool_without_clear_tool_id_registers_none_callbacks_then_frees` (fake records the exact sequence `register_callback(4,LINE,None)`, `register_callback(4,JUMP,None)`, `free_tool_id(4)`, no `clear_tool_id`; and the `clear_tool_id` path when the fake has it) | T3b | the round-4 3.12 failure; `free_tool_id` alone |
| `test_on_event_accepts_line_and_jump_arities_disables_other_code_counts_traced_code_once_per_thread_and_marks_failed_on_exception` | T3b | the round-3 `TypeError`; per-line cost; wrong `DISABLE`; propagating exceptions |
| `test_membership_is_by_identity_an_equal_code_object_from_another_file_is_not_counted` | T3b | value-equality membership |
| `test_traced_set_rules` (`_traced_set`: obj plus 8 hops accepted, 9 rejected, cycle, link without `__code__`, name mismatch, wrong file; `wraps` accepted; code objects compiled with `co_filename = target_real`) | T3c | decoy and wrapper holes |
| `test_collection_of_other_than_one_item_marks_failed` | T3c | silent multi-test |
| `test_hooks_enable_line_and_jump_record_the_thread_disable_after_the_yield` and `test_hooks_and_sessionfinish_make_no_monitoring_calls_when_not_claimed` (failed before the claim; unavailable; a fake foreign tool on id 4 untouched afterwards) | T3c | traced teardown; driving or freeing a foreign id |
| `test_sessionfinish_writes_exactly_one_marker_with_the_documented_content_and_precedence` (T3c) (success; unavailable; failed; zero count when not unavailable; two tests after a successful claim -> `.failed`; both markers pre-created -> `pytest.exit` with `returncode=3`; `out` absent -> `pytest.exit` 3; a fake `os.write` that writes one byte at a time still yields the whole content (it delegates to the real `os.write` for every other fd); the marker file mode is `0o600`; a `get_tool` fake naming another tool -> `.failed`; release raising writes the `.failed` marker; `restart_events` absent from the AST outside comments) | T3c | marker protocol; precedence; exit status |
| `test_a_real_smoke_launch_writes_a_success_marker` (writes the plugin with a plain `write_text` into a temp dir, builds argv and env with the T3a functions, runs through `bg._run_once` in a `pytest_venv` from T3b) | T3c | hooks that only work with fakes |
| `test_write_plugin_makes_one_read_only_file_and_verify_plugin_rejects_a_tampered_one` (tamper = `chmod 0o600` then write, or unlink and recreate; assert the detail "plugin file hash mismatch", not only the code) | T4a | shared/writable file; no hash check; passing on `PermissionError` |
| vocabulary pin `TRACE_MISMATCH TRACE_UNAVAILABLE` appended; `TRACE_REFUSAL_CODES` added to the uniqueness loop at `test_benchmark_gate_exports.py:473` | T4a | an unpinned code |
| `test_result_file_is_read_from_out_dir_after_scratch_is_removed` (fake `_run_once` writes a valid file; also asserts the return dict: `base`, `head`, `interpreter`, `argv` per side, `body_has_control_flow` for a straight-line and a looping benchmark, `ini_path` passthrough, base runs before head, a fresh nonce per side) | T4b | the blocker; reused nonce |
| `test_the_result_validation_matrix` (symlink, hardlink, wrong uid via monkeypatched `os.getuid` (delegating to the real one elsewhere), 257-byte file, trailing text, `12ab`, `5.5`, 19 digits, count `0`, wrong nonce, empty file, `.failed` present, dangling `.failed` symlink, a FIFO and a directory at `out`; the FIFO and directory rows run `trace_paired` in a daemon thread, `join(5)`, assert it finished, and unblock a FIFO in a `finally` by opening its write end with `O_NONBLOCK`) | T4b | each check; trusting existence; the FIFO hang |
| `test_the_unavailable_decision_table` (every D3 row, plus base-`UNAVAILABLE` with a head hard failure -> `TRACE_MISMATCH`, `side="head"`) | T4b | one-sided downgrade; precedence |
| `test_a_hard_failure_stops_before_the_second_side_and_names_the_side`; `test_each_trace_failure_kind_is_trace_mismatch_with_the_kind_prefix` (timeout, non-zero including death by signal, oversize, spawn; detail starts with `timeout:` etc., also for the head; the timeout detail ends " (3x the per-run timeout)") | T4b | running on; C4d-1 codes leaking |
| `test_trace_timeout_argument_is_three_times_timeout_seconds` (monkeypatch `bg._run_once`) | T4b | 1x; a measured median |
| `test_validation_precedence_platform_then_timeout_then_sides_and_phase_none_for_them`; `test_every_error_after_validation_carries_phase_trace` (`TRACE_MISMATCH`, `TRACE_UNAVAILABLE`, `MEASURE_FAILED`) | T4b | attribute defaults |
| `test_the_digest_is_not_checked_and_stdout_is_not_parsed` (a fake run printing a malformed digest and a forged `BENCH_TRACE_LINES` on stdout) | T4b | parsing stdout |
| `test_body_has_control_flow` (straight-line, `for`, `while`, `if`, `try`, `BoolOp`, comprehension, nested lambda only, no test function, two test functions with `::name`, parse failure, NUL bytes, a FIFO at the benchmark path) | T4b | wrong function; hang; exceptions |
| `test_harness_faults_are_measure_failed_with_phase_trace_no_side_and_no_partial` (a failing `mkdtemp(out)`, `_write_plugin` `OSError`, the tamper via an `argv_builder` that globs `bench-trace-*/plugin-*/bench_trace_plugin.py` under a `tempfile.tempdir` set by `monkeypatch.setattr` and rewrites the file, a `:` in that directory, a failing per-side `work` creation) | T4b | wrong code or phase; silent `PYTHONPATH` split; `_verify_plugin` placed too early |
| `test_interpreters_must_match_across_sides` | T4b | missing check |
| Real pytest, venvs (each ~2 launches), in `test_benchmark_gate_trace.py`: `test_batching_with_a_helper_below_the_callback_has_equal_counts`; `test_python_and_c_level_entries_count_the_same`; `test_a_different_loop_count_differs_including_one_line_loops`; `test_early_return_and_a_caught_exception_abandoning_the_loop_differ` (the exception is caught inside the body); `test_an_honest_fixed_count_benchmark_matches_itself` (only meaningful beside the loop-count rows); `test_wraps_traced_plain_wrapper_and_decoy_fail_closed`; `test_two_tests_async_and_plugin_failure_are_trace_mismatch`; `test_forged_results_are_not_accepted` (library prints the token; precreates the out path in an honest run, in a failing run via a two-test file, and via `getattr(os, "_e"+"xit")(0)`; a FIFO at the out path with `os._exit`; an `atexit` rewrite with a wrong or missing nonce; asserts the exact outcome and that `999` never appears; it deliberately does **not** assert that a nonce-aware rewrite is rejected); `test_a_real_launch_with_tool_id_4_taken_by_a_venv_pth_reports_tool_in_use` (both sides; one side only); `test_release_and_reclaim_work_on_the_ci_interpreter`; `test_an_outside_pointing_symlink_is_rejected_by_the_plugin` (`evil/bench.py` where `evil` links to `../outside`; the init-`failed` path is distinguishable from the exit-code path); a benchmark that `chdir`s at import, also to `/`, still matches | T4c | the trace's purpose and each forged path |

Runtime: about 25 real pytest launches plus a few waits: expect 20 to 40 s for the new file; no assertion depends on a duration; real-pytest
tests use 120 s child timeouts.

## 5. Docs

- Module docstring lines 11 to 17 ("Calling order for `compare`"): add `trace_paired` after the pairing set-up; the line-17 sentence ("C4d is
  delivered in parts: C4d-1 ..., then the trace and `compare` with `run-once`") names C4d-2 (`TRACE_PLUGIN_SOURCE`, `trace_env`,
  `trace_paired`, `_execute`); add the disclosed limits.
- Section header comment (`:3135` to `:3140`), the `MEASURE_FAILED` comment (`:3157`: also raised by the trace with `phase="trace"`), the
  `ERROR_CODES += MEASURE_REFUSAL_CODES ...` block (`:3157` to `:3158`: `TRACE_REFUSAL_CODES`), `BenchmarkGateError` attribute comments
  (`:908` `side`, `:909` `phase` also `"trace"`, `:910`), `measure_paired` docstring (remove "A trace run is not part of this function";
  phase vocabulary), `pytest_argv` docstring (`plugins`), `side_env` docstring (point to `trace_env`), `harness_sha256` docstring (`:2173`,
  which says C4d "bumps the domain string": rewrite to "the trace plugin is a constant inside this file; the domain string stays `-v1`"),
  `token_tripwire` docstring (`:2868`) and `_TRIPWIRE_TOKENS`.
- Module docstrings of `test_benchmark_gate_trace.py`, `test_benchmark_gate_exports.py` (it describes C4c-1 only) and
  `test_benchmark_gate_measure.py` (after T0), and the parametrization docstring in `test_benchmark_gate_diff.py`.
- Unchanged and fine: `:347` ("+3 is the untimed trace run"), `:827`, `:2643`.
- No changelog fragment (library only, unwired); the gap tracker is updated when C4 completes (C4f).

## 6. Suggested task order and dependency audit

| Task | Edits | Tests | Depends on |
|---|---|---|---|
| T0 characterization tests | `test_benchmark_gate_measure.py` | pass on base | none |
| T1 `_prepare_run`, `_execute`, adapter | `measure_paired` region | T0 + whole measure suite | T0 |
| T2 `_check_timeout`, `_check_sides`, `_benchmark_file_of`; edit the six `"t"` tests | same region | the T2 rows | T1 (same lines) |
| T3a constants (`_TRACE_MODULE`, `_TRACE_TIMEOUT_FACTOR`), `trace_env`, `pytest_argv(plugins=)`, tripwire tokens | after `pytest_argv`; `_TRIPWIRE_TOKENS` | the T3a rows | T2 (listed literally; the plugin and token edits are independent of T1/T2 but share the file) |
| T3b creates `test_benchmark_gate_trace.py` (helpers copied); `TRACE_PLUGIN_SOURCE` skeleton: `_claim_tool`, `_release_tool`, `_init`, `STATE`, `on_event` | the constant | the T3b rows (fakes, in-process) | T3a |
| T3c plugin hooks: collection check, `_traced_set`, `pytest_pyfunc_call`, `pytest_sessionfinish`, markers | the constant | the T3c rows incl. one real smoke launch | T3b |
| T4a `_write_plugin`, `_verify_plugin`, `TRACE_REFUSAL_CODES`, vocabulary pin | new functions; exports test | the T4a rows | T3c |
| T4b `trace_paired`, `body_has_control_flow` (fake-seam rows) | new function | the T4b rows | T1, T2, T4a |
| T4c real-pytest rows; **may carry code fixes** the real launches expose | new test file (+ fixes) | the T4c rows | T4b |
| T5 docs/comments | docstrings | lint | T4c |
| T6 `[CONTROLLER]` full gate suite, `make lint-static`, `graphify update .`, review rounds, PR | | | T0 to T5 |

All code tasks edit one file: sequential. Each task's tests run green at its own commit (T4c is the first place every hook runs under
real pluggy against `trace_paired`; a defect it finds is fixed in that commit). The plugin constant is about 210 lines.

## 7. Rollout and rollback

Library only; nothing calls it until C4f. Rollback is `git revert` of the squash commit. No settings, migrations or deploy order.

## 8. Open questions

None blocking. For C4d-3's design pass: the order of the trace pair against `HOST_BUSY_START`; the `TRACE_UNAVAILABLE` mapping and the
trace-timeout verdict rule (D3); folding the revisions and deviations of section 1 into the parent design file; the deferred structural option of
loading the plugin, inert, in the timed runs too (removes the argv and `sys.modules` differentiators).
