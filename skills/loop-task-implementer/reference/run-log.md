# Run log

A structured, redacted, tamper-evident record of what the Orchestrator did in one run, written by
`scripts/run_log.py`. It exists for two reasons: an audit trail that does not depend on the model's own
summary, and a measured source for the token/elapsed budgets in [state-schema.yaml](state-schema.yaml).

**Only the Orchestrator writes it.** Builder and Reviewer sessions never read or write the log — it can
hold prior verdicts, and giving a Reviewer that is the same isolation leak the
[lazy-load index](lazy-load-index.md) exists to prevent. The Orchestrator records Builder/Reviewer
activity on their behalf, using the `actor` field.

## Where it lives

`~/.software-builder/runs/<run_id>.jsonl` (directory `0700`, file `0600`), or `--log-dir <absolute path>`.
The location is never taken from the environment. It must be absolute, contain no `..`, and lie outside the
current git repository — `run_log.py` refuses otherwise — so a Builder editing the working tree cannot edit
its own audit trail.

`run_id` is chosen once by the Orchestrator at `run_started`: 1-128 characters of `[A-Za-z0-9._-]`, not
starting with `-`. For plan execution, use the task's execution identity prefix plus a timestamp so a
resumed run appends to the same log.

## Record shape

One JSON object per line:

| Field | Meaning |
|-------|---------|
| `schema_version` | `1` |
| `seq` | 1-based position; must be contiguous |
| `ts` | UTC RFC 3339, set by the script (never by the caller) |
| `run_id` | the run this record belongs to |
| `event` | one of the events below; anything else is rejected |
| `actor` | who did it: `orchestrator`, `builder`, `reviewer`, `ci`, `human`, `system` |
| `data` | small JSON object of identifiers and counts. Keys match `[A-Za-z0-9_.-]{1,64}`; strings are redacted, then truncated to 4000 characters; whole record capped at 16 KiB |
| `usage` | optional `input_tokens`, `output_tokens` (integers), `elapsed_seconds`, `cost_usd` (non-negative numbers) |
| `redactions` | names of redaction patterns that fired in this record (never the matched text) |
| `prev_hash` | SHA-256 of the previous record; 64 zeros for the first |
| `hash` | SHA-256 of this record without `hash` |

Log **identifiers and counts, not content**: a finding id and severity, not the finding text; a commit SHA,
not the diff. Ticket text, PR bodies, and tool output are untrusted (see
[prompt-injection.md](../../../docs/skill-framework/shared/prompt-injection.md)) and must not be pasted into `data`.

## Events

| Event | Log when | Typical `data` |
|-------|----------|----------------|
| `run_started` | after policy discovery, before the first dispatch | `task_id`, `allowed_actions`, budgets in force |
| `task_selected` | a task is chosen | `task_id`, `execution_identity` |
| `builder_dispatched` | a fresh Builder session starts | `attempt`, `session_ref` |
| `builder_returned` | the Builder returns | `head_commit`, `changed_files`, `changed_lines`; `usage` |
| `pr_opened` | a PR is created or adopted | `pull_request_id`, `head_commit` |
| `review_dispatched` | a Reviewer lens starts | `lens`, `review_generation` |
| `review_returned` | a Reviewer lens returns | `lens`, `review_generation`, `verdict`, `proposed_findings`; `usage` |
| `adjudicated` | proposed findings are classified | `lens`, `accepted`, `rejected`, `needs_evidence`, `contested` |
| `remediation_dispatched` | a Builder fix session starts | `finding_ids`, `attempt` |
| `ci_polled` | each authoritative CI poll | `commit`, `status` |
| `budget_checked` | after each `run_log.py budget` | `exceeded`, `unlimited`, `estimated_tokens`, `elapsed_minutes` |
| `escalated` | a circuit breaker fires | `reason`, `required_human_decision` |
| `merge_attempted` | immediately before an authorized merge | `allowed_actions_merge`, `head_commit` |
| `run_completed` | the run ends, in any state | `outcome`, final `chain_head` is reported separately |

## Commands

Resolve `skill_root` to the directory containing this skill's `SKILL.md` and select a Python 3
interpreter, exactly as [orchestrator-lifecycle.md](../workflow/orchestrator-lifecycle.md) does for the
lifecycle validator. Then:

```text
python3 <skill_root>/scripts/run_log.py append --run-id <id> --event <event> --actor <actor> \
    [--data-json '<object>'] [--usage-json '<object>']
python3 <skill_root>/scripts/run_log.py budget --run-id <id> [--max-tokens N|unlimited] [--max-minutes N|unlimited]
python3 <skill_root>/scripts/run_log.py verify --run-id <id>
python3 <skill_root>/scripts/run_log.py summarize --run-id <id>
```

Exit codes: `0` ok; `1` the chain does not verify, or a budget cap is reached; `2` bad input or the script
could not run. Exit `2` is a fail-closed inability to log, never a pass — and never a reason to skip a
dispatch-time budget check silently: report it and escalate.

`budget` applies the defaults from [state-schema.yaml](state-schema.yaml) (`180` minutes,
`2,000,000` estimated tokens) when a flag is omitted. Only the literal `unlimited` removes a cap, and the
completion or escalation report must then name it in `budget_consumed.unlimited_budgets`.

## Guarantees and limits

- **Tamper-evident, not tamper-proof.** An edited, deleted, or reordered record fails `verify`. A party that
  can rewrite the whole file and recompute every hash is not stopped, which is why the Orchestrator puts
  `chain_head` in the completion report — compare it to `verify` later.
- **`append` refuses to extend a broken chain**, so a corrupted log is not silently continued.
- **Token counts are as good as their source.** Use the usage the host reports for a session when it exposes
  it; otherwise record an estimate and say so in `data` (`usage_source: estimated`). If nothing can be
  measured, the token cap is not enforced and the report must say so.
- **No cost model.** `cost_usd` is recorded only if the host supplies it; the script never computes prices.
