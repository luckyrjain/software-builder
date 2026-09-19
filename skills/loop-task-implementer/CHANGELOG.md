# loop-task-implementer changelog

For earlier history, see the `## loop-task-implementer` section in the repository root `CHANGELOG.md`.

## Unreleased — default task budgets and run log (2026-09-19)

- `budgets.max_task_elapsed_minutes` now defaults to `180` and `budgets.max_task_tokens` to `2000000`
  (estimated) instead of `null`. An unset or `null` budget applies the default and is never unbounded;
  the only way to run without a ceiling is the explicit value `unlimited`, which the report echoes in
  `budget_consumed.unlimited_budgets`.
- Orchestrator §3 now checks both budgets before every dispatch and states how token usage is measured
  or, when unmeasurable, that the token cap is not enforced. Pressure tests 23-25 and
  `tests/test_budget_defaults.py` cover the defaults.
- Added an append-only, redacted, SHA-256 hash-chained run log (`scripts/run_log.py`, `reference/run-log.md`,
  orchestrator section 20), written only by the Orchestrator and never shown to a Builder or Reviewer. After an
  adversarial review (five personas: pentester, SRE, prompt engineer, hostile code reviewer, architect) the
  contract is:
  - **Exit codes** `0` ok, `1` integrity failure, `2` bad input or cannot run, `3` budget cap reached
    (previously `1` meant both "chain broken" and "cap reached").
  - **Tamper evidence**: `--expect-head` (the previous receipt's hash, held by the Orchestrator) catches a
    dropped tail, a wiped log, and foreign appends; strict parsing rejects duplicate keys, NaN, non-canonical
    lines and wrong-typed fields; the first record must be `run_started`, timestamps may not go backwards or
    into the future, and only `run_resumed` continues a completed run. The docs state plainly that a process
    running as the same OS user can still rewrite the whole file.
  - **Budgets measure the current task**: `run_log.py budget` covers everything since the latest
    `task_selected`, counts *active* time (each gap capped at 30 minutes, so a pause or resume does not spend the
    budget), reports `unmeasured` when no usage was recorded, and the Orchestrator passes the resolved caps
    every call.
  - **Durability**: writes are all-or-nothing (a failed or short write is rolled back), a torn final line is
    repaired by the next append (see round 3 below), appends read only the tail (constant time in run length), and
    locks time out instead of hanging.
  - **Safety**: `data` is sent on stdin (`--data-json -`) so untrusted text never enters a shell string;
    receipts replace echoed records; keys are redacted and secret-named keys masked; more token families are
    covered; redaction input is bounded; `escalated.reason` and `run_completed.outcome` take codes, not prose;
    the log directory must be outside every git repository and private, and is not read from `$HOME`/the environment.
  - New `run-id` subcommand derives a deterministic, resumable id from task seeds (hashed from a JSON encoding,
    so NUL-joined seeds cannot collide).
  - **Round 2 review** (five fresh personas against the fixed code) added: `--expect-head` is required on every
    append after the first (a 16+ character prefix is enough), with `run_resumed --unanchored` as the one recorded
    way to continue without it, and a repeated append whose receipt was lost is idempotent; a head with no log
    is an integrity failure on every command; sequencing mistakes exit `2` (a wrong call), not `1`; the budget
    window is the current `task_id`, so re-selecting a task after a resume no longer resets it; `total_tokens`
    is accepted; `unmeasured` is judged per returned session and receipts flag `usage_missing`; `escalated.reason`
    is a closed set of codes; redaction covers generic `key=value` / `"key":"value"` / `--flag value` credentials,
    more token families, unterminated PEM blocks and integer values under secret keys, and a key is judged by its
    words (`token_count`, `max_tokens`, `compass` are not secrets); strings over 8000 characters are refused
    instead of half-redacted; errors describe file-derived text by length and digest instead of quoting it (an
    injection channel); repository detection is structural (bare repos, `GIT_DIR`, gitfiles; a stub `.git` no
    longer locks the directory out); FIFOs, deep-nesting lines and broken pipes are handled; macOS uses
    `F_FULLFSYNC`; Python 3.10+ and POSIX are checked with a clear message.
  - **Round 3 review** simplified rather than patched again. A torn final write is repaired by the next append,
    which records `recovered_bytes` and `recovered_sha256` **on the record it writes** — there is no separate
    `log_recovered` event, no saved fragment file and no unlink cleanup, so a retry with the caller's head still
    finds that record's predecessor (a separate recovery record had broken idempotence), and the file-accumulation,
    unlink-race and directory-fsync problems disappear with them. Time is wall time with each gap capped at 30
    minutes, or at the host-reported `elapsed_seconds` when the gap ends at a session's return: no in-flight
    charging (a crash then a resume no longer trips the cap) and no summed floor (parallel lenses are not charged
    twice). A `COMPLETE` task that is run again gets a new budget window. `escalated.reason` and
    `run_completed.outcome` are required; an all-zero usage record is not a measurement; `verify` flags only a
    far-future record (consistent with `append`), says `"recoverable": true` for anything the next append can
    repair (up to 64 KiB), and prints `"no_log": true` for a missing or empty log so a caller can tell "new run"
    from "unusable"; a pre-existing loose directory is refused instead of `chmod`ed, and the home directory is
    never the log directory. Redaction: the generic `key=value` pattern was cubic (5.6K characters took 21 s) and
    is bounded, values are masked unless they are clearly identifiers (`enabled-by-default`,
    `cl100k_base_tokenizer_v2`, `E_AUTH_TOKEN_EXPIRED_0042`, absolute paths), plural and more credential key
    names are covered (`passwords`, `api_keys`, `creds`, `dsn`, `signing_key`), any non-number under a weak key
    is masked whole, a `*_count` number is a count, more token shapes (`hf_`, `dop_v1_`, `sntrys_`,
    `Authorization: Token`, `redis://:pw@`, `sessionid=`), and caller-supplied text (data keys, duplicate keys,
    argparse errors) is no longer echoed. Docs: `run-log.md` and section 20 keep the same procedure in fewer
    words, with explicit branches for a held head, a lost head, a wiped log, a crash mid-resume, and a JSON-escaped
    heredoc with an unpredictable delimiter; the completion report now carries `Budgets` and `Run log` lines
    (backlog-runner sums them); backlog-runner's SETUP states the Python/POSIX/log-directory prerequisite.
    Pressure tests 26-46, `tests/test_run_log.py` (about 300 tests, mutation-tested three times) and
    `tests/test_packaged_run_log.py` cover it.

## v1.4 — implementation-plan execution bridge (2026-08-26)

- Added validated `implementation_plan` input while preserving legacy `implementation_task` behavior.
- Added deterministic earliest-wave task selection and plan-task normalization; a plan field can
  never grant merge or any authority beyond the legacy task schema.
- Added collision-safe (not exactly-once) remote dispatch: execution identity is the SHA-256 of
  `plan_digest + task_id + task_contract_digest + target_repo + base_revision`, never `plan_id`
  alone, since a plan revision can change a task's contract while the plan's own identity stays
  stable. Remote writes use expected-head/fast-forward preconditions, never force-push, and never
  fall back to a random-suffix branch.
- Added generation-checked, SCM-reconciled host/runtime `plan_execution_state`; it is not a durable
  composition artifact and caller-supplied status cannot promote a task to complete.
- Kept the existing Builder, Reviewer, CI, merge, and lifecycle gates unchanged.

## v1.2 — post-merge Batch 5.2C lifecycle hardening (2026-08-21)

- Made `scripts/validate_loop_lifecycle.py` an actual fail-closed CLI. The documented Python 3 lifecycle gate now reads official JSON state and exits `0` only on a valid state, `1` on lifecycle errors, and `2` whenever argument/input/runtime validation cannot complete. This closes the original function-only direct-execution no-op, unexpected runtime exceptions, imported-runtime `SystemExit(0)`, argparse success exits such as `--help`, ambiguous duplicate JSON object keys, non-finite JSON constants, and standards-valid numeric syntax such as `1e999` that would overflow Python floats to infinity, none of which may count as lifecycle proof.
- Bound third-party branch-change evidence to the exact current head with `workspace.third_party_change_checked_head`, and changed the default detection state from `false` to `null` so unrefreshed state cannot masquerade as a clean branch check.
- Bound degraded-isolation human exceptions to both the exact `reviewed_change_identity` and a positive integer per-lens `review_generation`. A reviewer rerun increments that generation even when the code identity is unchanged, so an old human waiver cannot silently carry forward; an `ISOLATED` review must also have all exception fields cleared.
- Made review-generation mutation single-owner: the Orchestrator increments and clears prior exception fields before adjudication; the post-adjudication reviewer-evidence adapter consumes/validates that already-current generation and never increments it again.
- Added `review_evidence_generation` as an explicit crash/resume freshness binding. When a reviewer result advances `review_generation`, prior CLEAN evidence remains intentionally stale until new adjudicated evidence validates and is persisted with the same generation. The lifecycle validator rejects any CLEAN lens where `review_evidence_generation != review_generation`, preventing old evidence from being paired with a newer same-head reviewer result after interruption/resume.
- Aligned `reference/phase-index.md` with the canonical review/remediation order, including generation increments before adjudication/evidence, and made the mandatory lifecycle overlay explicitly authoritative wherever legacy readiness/completion text conflicts with it.
- Made the shared lifecycle contract portable in both source and installed packages. Shared contract paths resolve from the repository/package root; shared Markdown links are rewritten to vendored package-local copies; lifecycle execution resolves the validator from the actual skill root and invokes it with a Python 3 interpreter (`python3` on the supported Unix/macOS setup, host equivalent elsewhere) instead of assuming either a bare `python` command or source-checkout working directory.
- Corrected completion-report safe output: human-entered isolation-exception provenance is escaped/redacted free text, the report projects only validated scalar fields from `isolation_exception_change_identity`, the review/evidence generation mismatch is rendered explicitly, and the escalation machine-state block uses a dynamically sized outer backtick fence rather than a fixed triple-backtick YAML fence.
- Aligned setup metadata with the platform-neutral contract: the skill has repo-specific Git-provider/API and CI-provider dependencies, not a fixed GitLab MCP dependency; `scripts/registry/setup_freshness.yaml` and `SETUP.md` agree.
- Contract generations are `1.6` for `reference/state-schema.yaml` and `1.7` for all three Batch 5.2C lifecycle workflows (`orchestrator-lifecycle`, `reviewer-evidence`, `lifecycle-gate`); skill version is `1.2`.
- Expanded regression coverage for CLI exit semantics, strict/ambiguous JSON parsing including exponent overflow, stale/missing third-party check heads, isolation-exception identity/provenance/generation hygiene including same-head reviewer reruns, single-owner generation timing, stale evidence-generation crash/resume states, canonical review ordering, source/install shared-contract and validator-path portability, Python 3 invocation, workflow-version alignment, and safe report rendering.
