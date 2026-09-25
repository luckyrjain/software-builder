# loop-task-implementer changelog

For earlier history, see the `## loop-task-implementer` section in the repository root `CHANGELOG.md`.

## Unreleased — durable plan-state store and Builder checkpoint (2026-09-25)

Closes gap-backlog ticket A5: `plan_execution_state` had zero persistence code anywhere in the
repository (confirmed by direct grep — every reference was either the schema declaration, prose
stating non-durability, or in-memory-only validate/reconcile functions), and a Builder that died
before its single final report lost all unpushed work, detected only by a 30-minute timeout with no
partial-progress signal. See `docs/superpowers/specs/2026-09-25-a5-durable-state-checkpoint-*.md` for
the full architecture review, system design, and change-impact analysis.

- Added `scripts/plan_state_store.py`: a durable, locked, atomic file backing for one plan's
  `plan_execution_state`, keyed by `plan_id` (not `run_id`, since plan progress must survive a
  `run_resumed` event spanning multiple run identities). Mirrors `run_log.py`'s directory
  (`<home>/.software-builder/plan-state/`), permission (`0700`/`0600`, symlink/ownership refusal), and
  lock-timeout (`LOCK_TIMEOUT_SECONDS = 30.0`, a named `PlanStateLockTimeoutError` rather than an
  unbounded block) conventions, and refuses any directory inside a git repository the same way. Wraps
  — never reimplements — the already-tested in-memory CAS logic in `scripts/implementation_plan.py`
  (`advance_plan_execution_state`, `initial_plan_execution_state`); `cas_advance` is the one write
  entry point, merges `completed_evidence_refs` across calls (a union, never a silent replace or
  truncation) under a new `MAX_COMPLETED_EVIDENCE_REFS = 1000` safety-valve cap
  (`PlanStateStoreError` if exceeded), and fails closed with `PlanStateStoreError` on a
  malformed/corrupt existing file rather than treating it as "no state yet". `PlanStateCasError`
  surfaces a generation mismatch (a concurrent writer already advanced) as an exception at the
  durable-store boundary.
- Added `scripts/builder_resume.py`: pure resume-decision logic (no I/O) that turns a deterministic
  task branch's observed commits into `FROM_SCRATCH` / `CONTINUE_FROM(marker, head_sha)` / `ESCALATE`,
  by parsing each commit's `Checkpoint: <token>` trailer. `ESCALATE` fires when no commit carries a
  recognized marker (a third-party/unexpected push, routed into the existing §16 handling) or when a
  marker appears out of order (`tests-passing` with no earlier `implementation-complete`).
- `builder.md` §6 now pushes the deterministic task branch at two checkpoints in addition to the final
  commit, when `allowed_actions.commit`/`.push` are both `true`: after §3 Implement is functionally
  complete (`Checkpoint: implementation-complete`) and after §4 Test's full run succeeds (`Checkpoint:
  tests-passing`). Unchanged when either flag is `false` (existing diff-only path stands).
- `orchestrator.md` §5 now calls `builder_resume.decide` before dispatching a Builder onto a task
  whose branch already exists, and Core responsibilities now documents that `plan_execution_state` is
  durably backed by `plan_state_store` at the Orchestrator's existing initialization
  (item 3)/reconciliation (item 12) points. In both cases the new signal is explicitly a hint, never a
  substitute for this skill's existing independent-verification and "Builder prose is never sole
  source of merge-gate truth" doctrine (§13) — a fresh Builder given a `CONTINUE_FROM` still re-runs
  tests and re-inspects the diff before proceeding.
- This change is behaviorally dormant: nothing in the existing skill flow calls either new module yet
  (confirmed by the change-impact report) — the `builder.md`/`orchestrator.md` edits describe how a
  future `loop-task-implementer` run should use them, and take effect only on the next real run.
  Pressure tests: `scripts/tests/test_plan_state_store.py` (CAS success/rejection, lock-timeout via a
  live held lock, directory-refusal inside a git repository, malformed-file fail-closed,
  evidence-ref-cap enforcement) and `scripts/tests/test_builder_resume.py` (`FROM_SCRATCH`,
  `CONTINUE_FROM` with one and with both markers, `ESCALATE` for no recognized marker and for
  out-of-order markers).

## Unreleased — default task budgets and run log (2026-09-19)

- `budgets.max_task_elapsed_minutes` now defaults to `180` and `budgets.max_task_tokens` to `2000000`
  (estimated) instead of `null`. An unset or `null` budget applies the default and is never unbounded;
  the only way to run without a ceiling is the explicit value `unlimited`, which the report echoes in
  `budget_consumed.unlimited_budgets`.
- Orchestrator §3 now checks both budgets before every dispatch and states how token usage is measured
  or, when unmeasurable, that the token cap is not enforced. Pressure tests 23-25 and
  `tests/test_budget_defaults.py` cover the defaults.
- Added an append-only, redacted, SHA-256 hash-chained run log (`scripts/run_log.py`, `reference/run-log.md`,
  orchestrator section 20), written only by the Orchestrator and never shown to a Builder or Reviewer. Repeated
  adversarial review (pentester, SRE, prompt engineer, code reviewer, architect) shaped the contract:
  - **Exit codes** `0` ok, `1` integrity failure, `2` bad input or cannot run, `3` budget cap reached.
  - **Tamper evidence**: strict canonical parsing; the first record is `run_started`; timestamps never go backwards;
    only `run_resumed` continues a completed run. `--expect-head` (the previous receipt's hash, held in the
    Orchestrator's state) is required on every append after the first and catches a dropped tail, a wiped log
    (including one left as a stray byte) and foreign appends; `verify` reports the number of records beyond a held
    head as `ahead_by`, but that is a diagnostic: a mismatch stops the run, and only a person who has inspected the log
    may continue with `run_resumed --unanchored` (counted in `verify` as `unanchored_resumes`). A process running as
    the same OS user can still rewrite the whole file; the docs say so.
  - **Durability**: writes are all-or-nothing, appends read only the tail, locks time out, and a torn final write
    (a fragment under 48 KiB, including a torn first record) is repaired by the next append, which records
    `recovered_bytes` and `recovered_sha256` on that record. A repeated append whose receipt was lost is idempotent, and the Orchestrator saves each call with the head it is
    sent with in `run_log.pending`, so a crash before the receipt is replayed (before `verify`) whether or not it landed.
  - **Budgets measure the current task** (`task_selected` requires a `task_id`). Time is active time: each gap between
    records counts at most 30 minutes (a crash loop cannot hide), only the wait before a `run_resumed` that follows a
    `run_completed` counts nothing, a budget read after a finished run adds no tail, and a session's own return record
    counts the interval its host-reported `elapsed_seconds` says it ran (unioned, so parallel sessions are not
    charged twice and an inserted record cannot shrink it). A `COMPLETE` task that is resumed starts a fresh window.
    `unmeasured` is judged per returned session, an all-zero usage record is not a measurement, and the caps are
    passed on every call.
  - **Safety**: `data` goes on stdin so untrusted text never enters a shell string; receipts replace echoed records;
    `escalated.reason` and `run_completed.outcome` take codes, not prose; caller-supplied text is never echoed back
    (errors show a length and digest); the script-written keys `recovered_bytes`, `recovered_sha256` and
    `unanchored` are refused from callers; the log directory is outside every git repository, private, not the
    home directory itself, and never chmodded if it already existed; readers never change the file's mode.
  - **Redaction** (shared patterns plus local extras, bounded against ReDoS): keys are judged by their words, values by
    shape (a punctuated value, a UUID, a random-looking segment or anything under a key that names a credential is
    masked; kebab-case, ALL_CAPS and path identifiers under a merely credential-flavoured key are kept), and text
    under a credential-worded key is always replaced, so log such facts as codes under another name. Many token
    families, `Authorization: <scheme>`, URL userinfo, CLI password flags (digits and prefixes allowed), cookies, session
    ids, JSON quoted for a shell, Kubernetes and CloudFormation name/value pairs, XML elements, GitHub Actions workflow
    commands, and `aws`/`npm`/netrc/`gh secret set`/`cargo login` layouts are covered. `::` scopes (pytest, Rust, C++ ids)
    and `PWD=/path` are hidden from the shared patterns while they run and restored afterwards, so those ordinary values
    survive; a maintainer changing a pattern must keep that shield in mind. Not done, by
    design: replacing the stack with a per-event allowlist, and a queue-start log-writability preflight.
  - New `run-id` subcommand derives a deterministic id from task seeds; the UTC start time is a seed, so a task started again
    later is a new run.
  - Docs: section 20 step 1 covers every `verify` outcome (a new run only when there is no log and no held head; an
    existing log with no matching head is an integrity finding, apart from a lone `run_started`), a failing log appends nothing, the completion report carries
    `Budgets:` and `Run log:` lines in `key=value` form that backlog-runner reads, and pressure tests 26-49,
    `tests/test_run_log.py` and `tests/test_packaged_run_log.py` cover it.

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
