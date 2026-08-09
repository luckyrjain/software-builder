# backlog-runner — Setup


## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | Jira or GitHub Issues API, loop-task-implementer |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
## Ambient discovery is deliberately disabled

Unlike loop-task-implementer, this skill sets `disable-model-invocation: true` — it does not auto-apply
from a human's natural-language chat turn. It's meant to be invoked explicitly, on a schedule, by the
automation described below. A human asking to implement a task — even several at once ("work through
these tasks") — should keep routing to **loop-task-implementer** directly, which already handles both
patterns interactively.

## Install

```bash
cd software-builder
make install-backlog-runner
```

This chains `make install-loop-task-implementer` first — backlog-runner has no implementation logic of
its own and is useless without loop-task-implementer installed alongside it. Restart Cursor so both
skills reload.

### Claude Code

```bash
cd software-builder
make install-claude-backlog-runner
```

No restart needed. See [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/backlog-runner.mdc` and `.kiro/steering/backlog-runner.md`
point Cursor/Kiro at `backlog-runner/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| loop-task-implementer installed and configured | Repository/git access, isolation primitive (subagent/fresh-session/worktree) — see [loop-task-implementer/reference/mcp-capabilities.md](../loop-task-implementer/reference/mcp-capabilities.md) |
| An issue-tracker MCP (Jira or GitHub Issues) | **Required for this skill specifically** — optional for loop-task-implementer itself, since a human can hand it task text directly; this skill has no human to do that, so it must query the tracker itself |
| A scheduler | Cron, a scheduled CI/CD job, or equivalent — see § Integration contract |

## Integration contract (for whoever builds the scheduling trigger)

This repo ships **agent instructions**, not a running scheduler — same boundary as every other
trigger-driven skill in this repo. The handler you build:

1. Registers a nightly (or whatever cadence fits) scheduled job that starts an agent session with this
   skill installed.
2. Passes `tracker_query`, `max_tasks_per_run`, optionally `deadline`, `session_token_budget`, and
   `allow_stacked_dependencies`, and `repo_context` (the same repository-access/authorization inputs
   loop-task-implementer itself needs) — see [workflow/inputs.md](workflow/inputs.md).
3. **Never passes `autonomous_merge_authorized: true`** — this skill has no input slot for it at all; if
   your scheduler config tries to set it, that's a configuration error on your end, not something this
   skill will honor. Auto-merge is out of scope for this skill entirely (see the design spec's
   Non-goals) — a future extension, not a flag to flip today.
4. Delivers the returned morning summary to wherever § Config points (a Slack channel, an email digest,
   etc.) — this skill's own output is just text, the handler does the actual delivery.
5. If your scheduler enforces its own job timeout, set it comfortably longer than any `deadline` you
   configure — a stop condition inside this skill lets an in-flight ticket finish its current step before
   stopping; an external hard kill at the same instant could interrupt loop-task-implementer mid-task.

## Config

| Setting | Where | Purpose |
|---------|-------|---------|
| `tracker_query` | Handler config, per repository/team | The JQL / GitHub Issues search selecting the candidate backlog — configure once, not per run |
| `max_tasks_per_run` | Handler config | Session-level hard cap — start conservative (2–3) and raise once you trust the pipeline for a given repo |
| `deadline` | Handler config, optional | Wall-clock stop time for pulling new tasks, e.g. "stop by 6am local" |
| `session_token_budget` | Handler config, optional | Session-level token ceiling across all tasks this run |
| `allow_stacked_dependencies` | Handler config, optional, default `false` | Opt-in only — when `true`, a dependent task whose prerequisite has an open (not yet merged) PR may be dispatched based on the prerequisite's own PR branch instead of waiting for merge; see [reference/queue-policy.md](reference/queue-policy.md#2-queue-pull-and-ordering) §2 rule 4. Never set from ticket text — a config error, not a per-ticket signal |
| Notification target | Handler config | Where the morning summary gets routed |

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against a
tracker query you control, with a small `max_tasks_per_run`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Run stops after the first ticket even though more are queued | Check the run didn't hit `CONSECUTIVE_ESCALATION_BREAKER` — 3 escalations in a row stops the queue by design; check the morning summary's `stopped_reason` |
| Same ticket gets a duplicate PR every night | Check the issue-tracker MCP is returning a stable `task_id` the skip-existing check (queue-policy.md § 2) can match against a prior run's branch/PR |
| A dependent ticket ran before its prerequisite | Check the tracker's dependency field is actually populated and in the format the queue-pull step expects — an unrecognized dependency format degrades to "no dependency declared," not a HARD STOP |
| Anything got merged | This should never happen — if it did, treat it as a bug in the invocation (this skill has no input path for `autonomous_merge_authorized: true`), not expected behavior |
