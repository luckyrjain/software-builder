# Run log

A structured, redacted, tamper-evident record of what the Orchestrator did in one run, written by
`scripts/run_log.py`. It exists for two reasons: an audit trail that does not depend on the model's own
summary, and a measured source for the token and time budgets in [state-schema.yaml](state-schema.yaml).

**Only the Orchestrator writes it.** Builder and Reviewer sessions never read or write the log — it can
hold prior verdicts, and giving a Reviewer that is the same isolation leak the
[lazy-load index](lazy-load-index.md) exists to prevent. The Orchestrator records Builder/Reviewer
activity on their behalf, using the `actor` field. The log's location and path never go into a dispatch
package, a PR body, or a report; only `run_id` and `chain_head` do.

## What it does and does not protect against

| Threat | Held by |
|--------|---------|
| Accidental corruption, a stray edit, a deleted or reordered record | the hash chain (`verify`, and `append` refuses a bad tail) |
| A dropped tail, a wiped-and-restarted log, or another process appending | `--expect-head`: the Orchestrator passes the `chain_head` from its **previous receipt**, which lives in its context, not in any file |
| Secrets, tokens and credentials in what is logged | redaction of values and keys, plus "identifiers and counts, not content" |
| A Builder that can run commands **as the same OS user** and rewrite the whole file | **not held by this script.** Such a process can also run `run_log.py`. Keep the Builder out of the log directory (separate account, container, or a sandbox that cannot read it) if that matters |

## Where it lives

`--log-dir <absolute path>`, else `<your home directory>/.software-builder/runs/<run_id>.jsonl` (every created
directory `0700`, file `0600`; an existing directory or file with looser modes is tightened). The default is
taken from the account database, not from `$HOME`. The script refuses a directory that is relative, contains
`..`, is not owned by you, is a symlink, or sits inside **any** git repository (so a home directory that is
itself a git repo, as with some dotfiles setups, needs an explicit `--log-dir` elsewhere). If the default is
unwritable, pick another absolute directory outside the repository and use it for the whole run.

Record the chosen directory in `run_log.log_dir` in state and pass the same `--log-dir` on every call — a
resumed run must find the same log.

## Run id and resuming

`run_id` is deterministic for a task so a resumed run finds its own log. Derive it, never invent or
timestamp it:

```text
python3 <skill_root>/scripts/run_log.py run-id <<'JSON'
["<repo>", "<base_branch>", "<task_id>"]
JSON
```

For plan execution, use the execution identity as the single seed. The output (`run-` plus 16 hex digits) is
safe to use as a filename. Ticket text is hashed, never used as a name.

- A **new** run starts with `run_started` (only ever the first record). Log `task_selected` straight after it.
- A run that was interrupted, escalated, or completed and is now being continued appends `run_resumed`.
  After `run_completed`, `run_resumed` is the only event the log accepts.
- One log can hold several tasks. Each `task_selected` starts a new **budget window** (below).

## Record shape

One canonical JSON object per line (sorted keys, no extra whitespace, duplicate keys and NaN/Infinity rejected):

| Field | Meaning |
|-------|---------|
| `schema_version` | `1` |
| `seq` | 1-based position; contiguous integers |
| `ts` | UTC RFC 3339, set by the script; never earlier than the previous record's |
| `run_id` | the run this record belongs to |
| `event` | one of the events below; anything else is rejected |
| `actor` | who did it: `orchestrator`, `builder`, `reviewer`, `ci`, `human`, `system` |
| `data` | small JSON object of identifiers and counts. Keys match `[A-Za-z0-9_.-]{1,64}` and must not look like secrets; a key whose name says credential (`password`, `token`, `api_key`, ...) has its value replaced; strings are redacted then cut to 4000 characters; the record is capped at 16 KiB |
| `usage` | optional `input_tokens`, `output_tokens` (integers up to 10^10), `elapsed_seconds`, `cost_usd` (non-negative numbers) |
| `redactions` | names of redaction patterns that fired (never the matched text) |
| `prev_hash`, `hash` | SHA-256 chain: `hash` covers the record without `hash`; the first `prev_hash` is 64 zeros |

Log **identifiers and counts, not content**: a finding id and severity, not the finding text; a commit SHA,
not the diff. Ticket text, PR bodies, and tool output are untrusted (see
[prompt-injection.md](../../../docs/skill-framework/shared/prompt-injection.md)) and must not be pasted into
`data`. `escalated` takes `reason` as an UPPER_SNAKE code (for example `DIRTY_REVIEW_LIMIT`,
`TOKEN_BUDGET`, `SIZE_HARD_STOP`) and `run_completed` takes `outcome` as one of `COMPLETE`, `ESCALATED`,
`HUMAN_ACTION_REQUIRED`, `ABANDONED`; free prose there is rejected.

## Events

| Event | Log when | Typical `data` |
|-------|----------|----------------|
| `run_started` | first record of a new run | `allowed_actions`, budgets in force |
| `run_resumed` | continuing an interrupted, escalated, or completed run | `reason_code` |
| `task_selected` | a task is chosen (starts a budget window) | `task_id`, `execution_identity` |
| `builder_dispatched` | a fresh Builder session starts | `attempt`, `session_ref` |
| `builder_returned` | the Builder returns | `head_commit`, `changed_files`, `changed_lines`; `usage` |
| `pr_opened` | a PR is created or adopted | `pull_request_id`, `head_commit` |
| `review_dispatched` | a Reviewer lens starts | `lens`, `review_generation` |
| `review_returned` | a Reviewer lens returns | `lens`, `review_generation`, `verdict`, `proposed_findings`; `usage` |
| `adjudicated` | proposed findings are classified | `lens`, `accepted`, `rejected`, `needs_evidence`, `contested` |
| `remediation_dispatched` | a Builder fix session starts | `finding_ids`, `attempt` |
| `remediation_returned` | a fix session returns | `head_commit`; `usage` |
| `orchestrator_usage` | the Orchestrator's own tokens, at least once per phase | `usage` |
| `ci_polled` | each authoritative CI poll | `commit`, `status` |
| `budget_checked` | only when a check reports a cap reached, `unmeasured`, or `unlimited` | `exceeded`, `unmeasured`, `unlimited` |
| `escalated` | a circuit breaker fires | `reason` (a code) |
| `merge_attempted` | immediately before an authorized merge | `head_commit` |
| `log_recovered` | written by the script itself when it drops a torn final line | `dropped_bytes`, `previous_head` |
| `run_completed` | the run ends, in any state | `outcome` (a code) |

## Commands

Resolve `skill_root` to the directory containing this skill's `SKILL.md` and select a Python 3 interpreter,
exactly as [orchestrator-lifecycle.md](../workflow/orchestrator-lifecycle.md) does for the lifecycle
validator. Then:

```text
python3 <skill_root>/scripts/run_log.py append --run-id <id> --log-dir <dir> --event <event> --actor <actor> \
    --expect-head <previous chain_head> --data-json - [--usage-json '<object>'] <<'JSON'
{"task_id": "...", "attempt": 1}
JSON
python3 <skill_root>/scripts/run_log.py budget --run-id <id> --log-dir <dir> --expect-head <head> \
    --max-tokens <N|unlimited> --max-minutes <N|unlimited>
python3 <skill_root>/scripts/run_log.py verify --run-id <id> --log-dir <dir> --expect-head <head>
python3 <skill_root>/scripts/run_log.py summarize --run-id <id> --log-dir <dir>
```

**Never put a value into a quoted shell string.** Branch names, task ids, and reviewer prose can contain
`'`, `$(...)`, backticks and newlines. Send `data` on stdin with `--data-json -` and a heredoc whose
delimiter is quoted (`<<'JSON'`), which the shell does not expand. `--usage-json` takes only numbers you
computed yourself; if it ever carries anything else, use stdin for it too (only one of the two may read stdin).

`append` prints a **receipt** (`seq`, `event`, `chain_head`), not the record. Keep the latest `chain_head` in
state and pass it as `--expect-head` on the next call. If a call fails, do not guess a head: run `verify` and
report.

### Exit codes

| Code | Meaning | What to do |
|------|---------|------------|
| `0` | ok | continue |
| `1` | **integrity failure**: chain does not verify, `--expect-head` mismatch, out-of-order or future-dated record | stop; report it as a finding; do not rewrite or delete the log |
| `2` | bad input, no log, unwritable directory, lock timeout, or the script could not run | fail closed: say so in the report and escalate; never continue an unlogged run silently |
| `3` | `budget` only: a cap is reached | stop dispatching and escalate per [orchestrator.md §3](../workflow/orchestrator.md) |

A missing or empty log is exit `2` for every command, including `verify`. There is no code that means both
"cap reached" and "log damaged".

## Budgets

`budget` measures the **current task**: everything since the latest `task_selected` (the whole log if there is
none), because the caps are per task and one log may hold several.

- **Tokens** are the sum of `usage.input_tokens + output_tokens` in the window. Reaching the cap counts.
- **Time** is *active* time: each gap between consecutive records counts at most 30 minutes, including the gap
  from the last record to now, so a human decision or an overnight pause does not spend the task's budget.
  `wall_clock_minutes` is reported for information only.
- **Caps**: always pass the resolved `--max-tokens` and `--max-minutes` (the caller's values, or the defaults
  `2,000,000` and `180`). Omitting a flag applies the default, so a caller's lower cap would be silently ignored.
  A cap is a positive number (`2,000,000` and `2_000_000` are fine; `1e6` is not) or exactly `unlimited`.
- **`unmeasured`**: the verdict lists `tokens` when the window holds no usage at all. That means the token cap
  is **not enforced**, whatever the exit code says. Say so in the report.
- **Where usage comes from**: the usage the host reports for a session (API metadata or the subagent
  result's usage field), never a figure a Builder or Reviewer states in prose. If the host reports none,
  record an estimate and put `usage_source: estimated` in `data`. Record the Orchestrator's own tokens with
  `orchestrator_usage`, and a fix session's with `remediation_returned`.

## Recovery

- **Torn final line** (the process was killed mid-write, or the disk filled): the next `append` truncates the
  unparseable fragment under the lock and writes a `log_recovered` record (`dropped_bytes`,
  `previous_head`) before your event, so the loss is on the record. A final line that is a complete, valid
  record missing only its newline is kept. `verify` reports a torn tail as a failure until then.
- **Anything else wrong** (`verify` exit `1`): do not repair it. Report the errors and the `chain_head` you last
  held, and continue the run's work only if the caller's policy allows an unlogged continuation — otherwise
  escalate.

## Limits

- `append` chains from the tail of the file only, so it stays fast however long the run is; `verify`,
  `summarize` and `budget` read the whole log.
- Locks time out after 30 seconds (exit `2`). Windows locking is best-effort and untested.
- **No cost model**: `cost_usd` is recorded only if the host supplies it.
- **Schema versions**: a log is written and read in the version of its first record. New optional events are
  compatible; a change that is not needs a new `schema_version` with the old reader kept, so archived and
  in-flight logs stay verifiable.
- **Not a session-budget source**: `backlog-runner` tracks its own session totals from each task's
  `budget_consumed` in the completion or escalation report (see its `queue-policy.md`); it does not read this log.
