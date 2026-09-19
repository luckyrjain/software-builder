# Run log

A structured, redacted, tamper-evident record of what the Orchestrator did, written by
`scripts/run_log.py`: an audit trail that does not depend on the model's own summary, and the measured
source for the token and time budgets in [state-schema.yaml](state-schema.yaml).

**Only the Orchestrator reads or writes it.** A Reviewer that saw it would see prior verdicts. It records
Builder and Reviewer activity on their behalf (`actor`). Only `run_id` and `chain_head` ever go into a
dispatch package, PR body, or report — never the directory or path.

## What it protects against

| Threat | Held by |
|--------|---------|
| Corruption, a stray edit, a deleted or reordered record, a forged or out-of-order record | the hash chain and strict parsing (`verify`; `append` refuses a bad tail) |
| A dropped tail, a wiped-and-restarted log, another process appending | `--expect-head`: the previous receipt's `chain_head`, kept in the Orchestrator's context, not in a file |
| Secrets in what is logged | redaction of values and keys, plus "identifiers and counts, not content" |
| A Builder running as the **same OS user** that rewrites the whole file | **not held here** — it can also run this script. Keep the Builder out of the log directory (another account, container, or sandbox) if that matters |

## Where it lives, and the run id

`--log-dir <absolute path>`, else `<your home>/.software-builder/runs/<run_id>.jsonl` (taken from the
account, not `$HOME`; directories `0700`, file `0600`, an existing looser one is tightened). The directory
must not be inside **any** git repository (a home that is itself a repo needs an explicit `--log-dir`
elsewhere), must be absolute, without `..`, owned by you, not a symlink. Keep it unchanged for the whole run.

`run_id` is derived, never invented, so a resumed run finds its own log:
`run_log.py run-id` reads a JSON array of seed strings on stdin (`["<repo>","<base_branch>","<task_id>"]`, or
a plan's execution identity as the single seed) and prints `run-` plus 16 hex digits.

## Record and events

One canonical JSON line per record (sorted keys; duplicate keys, NaN, non-canonical form rejected):
`schema_version` (1), `seq`, `ts` (set by the script, never earlier than the previous record), `run_id`,
`event`, `actor` (`orchestrator`, `builder`, `reviewer`, `ci`, `human`, or `system`), `data`, `usage`,
`redactions` (pattern names only), `prev_hash`, `hash` (SHA-256 chain).

`data` is a small object of **identifiers and counts**. Keys are `[A-Za-z0-9_.-]{1,64}`, must not look like
secrets, and a key whose *words* say credential (`password`, `apiKey`, `DB_SECRET`, `token_hint`) has its value
replaced — so do not use such names for real fields (`max_tokens`, `token_count`, `tests_passed`, `session_ref`
are fine). Strings are redacted then cut to 4000 characters; a string over 8000 characters or a record over
16 KiB is refused. Ticket text, PR bodies and tool output are untrusted ([prompt-injection.md](../../../docs/skill-framework/shared/prompt-injection.md))
and never go in `data`. Use `changed_file_count`, not a file list.

`usage` takes `input_tokens`, `output_tokens`, `total_tokens` (use it when the host gives only a total),
`elapsed_seconds`, `cost_usd`; tokens are integers up to 10^10.

| Event | Log when | Typical `data` |
|-------|----------|----------------|
| `run_started` | first record of a new run (only ever the first) | `allowed_actions`, budgets in force (`max_tokens`: `unlimited` allowed) |
| `run_resumed` | continuing an interrupted, escalated, or completed run (the only event a completed run accepts) | — |
| `task_selected` | a **new** task is chosen; starts its budget window | `task_id`, `execution_identity` |
| `builder_dispatched` / `remediation_dispatched` / `review_dispatched` | a session starts | `attempt`, `session_ref`, `lens`, `review_generation` |
| `builder_returned` / `remediation_returned` / `review_returned` | a session returns; **carries its `usage`** | `head_commit`, `changed_file_count`, `verdict`, `proposed_findings` |
| `orchestrator_usage` | your own tokens, at least once per phase | — (`usage`) |
| `pr_opened`, `adjudicated`, `ci_polled`, `merge_attempted` | the action happens | ids and counts |
| `budget_checked` | only when a check reports a cap reached, `unmeasured`, or `unlimited` | those lists |
| `escalated` | a circuit breaker fires | `reason`, one of the codes below |
| `run_completed` | the run ends in any state | `outcome`, one of the codes below |
| `log_recovered` | written **by the script** when it drops a torn final line | `dropped_bytes`, `previous_head` |

`escalated.reason` is one of `DIRTY_REVIEW_LIMIT`, `FIX_ATTEMPT_LIMIT`, `CONTESTED_TWICE`, `SIZE_HARD_STOP`,
`FINGERPRINT_ALTERNATION`, `SCOPE_EXCEEDED`, `MISSING_DECISION`, `THIRD_PARTY_CHANGE`, `CI_UNDIAGNOSABLE`,
`SESSION_TIMEOUT`, `TOKEN_BUDGET`, `TIME_BUDGET`, `INTEGRITY_FAILURE`, `LOG_UNAVAILABLE`, `OTHER` (anything else
is rejected with exit `2`: correct it and retry once). `run_completed.outcome` is `COMPLETE`, `ESCALATED`,
`HUMAN_ACTION_REQUIRED` or `ABANDONED`.

## Commands

Resolve `skill_root` to the directory containing this skill's `SKILL.md` and a Python 3.10+ interpreter, as
[orchestrator-lifecycle.md](../workflow/orchestrator-lifecycle.md) does for the lifecycle validator.

```text
python3 "<skill_root>/scripts/run_log.py" append --run-id <id> --log-dir <dir> --event <event> --actor <actor> \
    --expect-head <previous chain_head> --data-json - [--usage-json '<numbers only>'] <<'JSON'
{"task_id": "T-1", "attempt": 1}
JSON
python3 "<skill_root>/scripts/run_log.py" budget --run-id <id> --log-dir <dir> --expect-head <head> \
    --max-tokens <N|unlimited> --max-minutes <N|unlimited>
python3 "<skill_root>/scripts/run_log.py" verify --run-id <id> --log-dir <dir> [--expect-head <head>]
python3 "<skill_root>/scripts/run_log.py" summarize --run-id <id> --log-dir <dir>
```

**Never put a value into a quoted shell string** — branch names, task ids and reviewer prose can hold `'`,
`$(...)`, backticks and newlines. Send `data` on stdin with `--data-json -` and a heredoc with a **quoted**
delimiter. Make **one call per tool step, never in parallel**: each needs the head from the previous receipt.

`append` prints a **receipt**: `seq`, `event`, `chain_head`, and `usage_missing: true` on a session or usage
event that carried no token usage. Pass `chain_head` (or its first 16+ characters) as `--expect-head` next
time. Every append after the first needs it. `--unanchored` (only with `run_resumed`) is the one way to
continue without it, and the record says so.

An append whose outcome you do not know (crash, timeout, closed pipe) is safe to **repeat exactly**, with the
same `--expect-head`: if it was already committed, the script returns that record and writes nothing.

### Exit codes

| Code | Meaning | What to do |
|------|---------|------------|
| `0` | ok | continue |
| `1` | **integrity failure**: chain does not verify, `--expect-head` mismatch, a head with no log, a forged or future-dated record | stop and report it as a finding; do not rewrite or delete the log. One exception: `verify` printing `"recoverable": true` (a torn final write) — repeat your append, which repairs it |
| `2` | bad input, a wrong call (event out of sequence, missing `--expect-head`), no log, unwritable directory, lock timeout, unsupported Python, or the script could not run | fail closed: say so and escalate; never continue an unlogged run silently. A wrong call: fix it and retry once |
| `3` | `budget` only: a cap is reached | stop dispatching; escalate (`TOKEN_BUDGET` or `TIME_BUDGET`) |

## Budgets

`budget` measures the **current task**: from the first `task_selected` of the latest run of records for the same
`task_id` (the whole log if there is none), so re-selecting a task after a resume does not reset it.

- **Tokens**: each record counts `total_tokens` if given, else `input_tokens + output_tokens`; reaching the
  cap counts as exceeding it.
- **Time** is *active* time. A gap that follows a dispatch (a session is running) counts in full, so a hung
  session shows up; any other gap counts at most 30 minutes, so a human decision or an overnight pause does not
  spend the budget. Host-reported `elapsed_seconds` sets a floor. `wall_clock_minutes` is for information.
- **Caps**: always pass the resolved `--max-tokens` and `--max-minutes` (defaults `2,000,000` and `180`; omitting
  a flag applies the default, so a caller's lower cap would be silently ignored). A cap is a positive number
  (`2,000,000`, `2_000_000`, `500000`; not `1e6` or `1,5`) or exactly `unlimited`.
- **`unmeasured: ["tokens"]`** means a session returned with no usage recorded: the token cap is **not
  enforced** for it, whatever the exit code says. Say so in the report. Usage comes from what the host reports
  for a session, never from a figure a Builder or Reviewer states in prose; if the host reports none, record an
  estimate and put `usage_source: estimated` in `data`.

## Recovery and limits

- A **torn final line** (killed mid-write, disk full) is repaired by the next append: the fragment is saved
  to `<run_id>.jsonl.torn-<seq>`, cut off, and a `log_recovered` record notes the loss. A complete record missing
  only its newline is kept. A fragment over 16 KiB, or any other damage, is not repaired: report it.
- `append` chains from the file's tail only (constant time in the run's length); `verify`, `summarize` and
  `budget` read the whole log. Locks time out after 30 seconds (exit `2`). POSIX only.
- A log is written and read in the version of its first record; new optional events are compatible, anything else
  needs a new `schema_version` with the old reader kept. `cost_usd` is recorded only if the host supplies it.
- `backlog-runner` sums each task's `budget_consumed` from the completion or escalation report (see its
  `run-queue.md`); it does not read this log.
