# backlog-runner: design

**Date:** 2026-08-05
**Status:** Approved design
**Source:** Item #7 of [team-facing-agents-roadmap.md](../plans/2026-08-05-team-facing-agents-roadmap.md) —
P1, "loop-task-implementer pointed at a ticket queue (Jira/GitHub Issues), works overnight, opens PRs by
morning. Mostly already what loop-task-implementer does per-task; the new part is queue management (pull
N tickets, respect dependencies across tickets, stop conditions for an unattended overnight run) — needs
its own budget/circuit-breaker profile tighter than an interactive session's." The roadmap's own suggested
build order notes #7 "can proceed independently of the aggregation-layer work" (Phase 4) — no dependency
on that phase.

## Problem

loop-task-implementer already implements a safe, isolated Builder → Reviewer → remediation → PR loop per
task — but a human still has to hand it one task at a time and stay around to say "next." Nobody wants to
do that at 11pm for a backlog of 15 tickets.

## What's already there vs. genuinely new — researched, not assumed

Unlike every skill wrapped so far in this repo (squad-map, pr-review, incident-rca), **loop-task-implementer
was already designed for unattended operation** — confirmed by an exhaustive grep of its own workflow and
reference files for ask/wait/confirm/pause patterns: every "stop" resolves to a **terminal report state**
per task (`HUMAN_ACTION_REQUIRED` or `ESCALATED`), never a live synchronous chat prompt the way pr-review's
Phase 3 or incident-rca's Phase 2 checkpoint do. There is **no `pr-gatekeeper`-style "answer every gate"
policy needed here** — the base skill has no gate of that kind to answer.

What genuinely doesn't exist yet, confirmed directly against `state-schema.yaml` (explicitly a
*"per-task"* schema, no session/queue wrapper) and `reference/mcp-capabilities.md` (issue-tracker MCP is
**optional** — the base skill expects task text handed to it, it doesn't query a tracker itself):

| Capability | Exists in loop-task-implementer today? |
|-------------|--------------------------------------------|
| Per-task Builder→Reviewer→PR loop, isolation, circuit breakers | **Yes**, unchanged, fully reused |
| Per-task dependency check at selection time ("only pick a task whose dependencies are complete") | **Yes** (`orchestrator.md` §2) |
| Pulling N tickets from Jira/GitHub Issues autonomously | **No** — tracker MCP is optional and, when present, only resolves a link a human already gave it |
| Session-level queue state (multiple tasks in one run) | **No** — `state-schema.yaml` is per-task only |
| Session-level stop conditions (deadline, task count, token budget) | **No** — only per-task budgets (`max_task_elapsed_minutes`, `max_task_tokens`) exist |
| Continuing to the next task after `HUMAN_ACTION_REQUIRED` (not just after a merge) | **Ambiguous in the source** — `orchestrator.md` §18 only explicitly says "select next eligible task" *after an authorized merge*; the higher-level workflow diagram reads more generously but doesn't disambiguate. backlog-runner must resolve this explicitly, not inherit the ambiguity |

## Approach

`backlog-runner` is a **queue-management wrapper around loop-task-implementer** — no new Builder/Reviewer/
review-isolation logic, no relaxation of any existing circuit breaker. It:

1. Is triggered on a schedule (cron / scheduled CI job), not ambient chat or a live webhook.
2. Pulls up to `max_tasks_per_run` tickets from a configured issue-tracker query (Jira JQL or GitHub
   Issues search — a **new, required** dependency for this skill specifically, optional for the base
   skill), skipping tickets that already have an in-progress task/branch/PR from a prior run (reusing
   loop-task-implementer's own existing branch/PR-detection in `orchestrator.md` §2 — no second tracking
   mechanism invented).
3. Topologically orders the pulled tickets by declared dependencies (a queue-level concern
   loop-task-implementer's own per-task dependency check doesn't do — it only checks one task's
   dependencies at selection time, never orders a whole pulled batch).
4. Invokes loop-task-implementer once per ticket, in dependency order, exactly as if a human had pasted
   that ticket's text and said "implement this."
5. **Resolves the continuation ambiguity explicitly:** `HUMAN_ACTION_REQUIRED` (task verified-ready, PR
   opened, `autonomous_merge_authorized` false as always in this skill — see Non-goals) is the **expected,
   normal outcome for every task, every night** — continue to the next queue item. Only a **session-level
   circuit breaker** (see below) stops the run early; a single task's `ESCALATED` outcome defers/skips
   that one task and its dependents, but does not halt the queue.
6. Enforces its own **session-level** stop conditions — `max_tasks_per_run`, a wall-clock deadline
   ("stop pulling new tasks by HH:MM"), a session token/cost budget, and a consecutive-escalation circuit
   breaker (systemic-failure signal, distinct from one task's own per-task circuit breakers, which are
   loop-task-implementer's own and stay unchanged) — none of which exist in the base skill today.
7. Produces one **morning summary** — what shipped (PRs opened), what's blocked (escalated, with why),
   what's deferred (dependency not yet satisfied), routed to the configured notification target.

## Non-goals (explicitly out of scope for this item)

- **No auto-merge.** `autonomous_merge_authorized` is always `false` for every task this skill runs — not
  configurable in this version. The roadmap's own deliverable is "opens PRs by morning," not "merges PRs
  by morning"; auto-merge is a materially different trust decision left for a future extension, exactly
  the same way pr-gatekeeper explicitly deferred its own "auto-fix hand-off" extension.
- **No relaxation of loop-task-implementer's own isolation guarantees, circuit breakers, or review
  lenses** for speed — an overnight run gets no less scrutiny than an interactive one.
- **No new Builder/Reviewer logic, no new PR/review mechanics** — 100% loop-task-implementer's own.
- **No live scheduling infrastructure in this repo** — same "agent instructions, not infrastructure"
  boundary as every other item; `SETUP.md` documents the integration contract for whoever wires up cron.
- **No cross-ticket work splitting or merging** — each pulled ticket maps to exactly one
  loop-task-implementer task, never combined or split by this skill.

## Interface contract

**Input** (from the scheduler):

| Field | Required | Notes |
|-------|----------|-------|
| `tracker_query` | Yes | JQL / GitHub Issues search string selecting the candidate backlog — configured once, not per-run (see SETUP.md) |
| `max_tasks_per_run` | Yes | Session-level stop condition — hard cap regardless of how many the query returns |
| `deadline` | No | Wall-clock ISO-8601 — stop *pulling new tasks* at/after this time; an in-flight task is allowed to finish its current step, never aborted mid-Builder-dispatch |
| `session_token_budget` | No | Session-level token ceiling across all tasks this run |
| `repo_context` | Yes | Same repository-access/authorization-policy inputs loop-task-implementer itself requires — passed through unchanged |

**Output:** a morning summary — see [reference/morning-summary-format.md](../../../backlog-runner/reference/morning-summary-format.md).

## Acceptance criteria

- `backlog-runner/SKILL.md` exists, ≤ 180 lines, `disable-model-invocation: true` (scheduled-trigger entry
  point, same reasoning as the other three wrappers — a human typing "implement issue 42" still routes to
  loop-task-implementer directly).
- Given a `tracker_query` returning more tickets than `max_tasks_per_run`, only up to the cap is pulled,
  in dependency order.
- Given ticket B declares a dependency on ticket A, and both are in the same run's pulled batch, A is
  attempted before B; if A doesn't complete this run (escalated/deferred), B is deferred too, not
  attempted out of order.
- Given a task reaches `HUMAN_ACTION_REQUIRED` → the run continues to the next queue item (this is the
  expected default, not a stop condition).
- Given a task reaches `ESCALATED` → that task (and any queued dependent) is deferred/skipped, logged in
  the morning summary, and the run continues — unless the consecutive-escalation circuit breaker fires,
  in which case the run stops pulling new tasks and reports.
- Given `max_tasks_per_run`, the `deadline`, the `session_token_budget`, or the consecutive-escalation
  circuit breaker is reached → the run stops pulling new tasks; an in-flight task finishes its current
  step (never aborted mid-Builder-dispatch); the morning summary is produced regardless of how the run
  ended.
- `autonomous_merge_authorized` is never set to `true` by this skill, for any task, under any
  configuration — verified as a hardcoded, non-configurable constraint, not a default that could be
  overridden.
- A ticket that already has an in-progress branch/PR from a prior run is skipped at the queue-pull step,
  not re-attempted from scratch.
- `make lint-backlog-runner` and `make lint-framework` pass; skill wired into root README.md,
  docs/README.md, docs/REPOSITORY.md, `skill-routing.md`, `cross-skill-escalation.md`,
  `prompt-injection.md`, `CHANGELOG.md`. **Not** `phase-glossary.md` — see § Implementation plan step 7:
  loop-task-implementer itself is exempt, and this wrapper inherits that exemption.

## Implementation plan

1. `backlog-runner/SKILL.md`, `README.md`, `SETUP.md`, `CHANGELOG.md`, `examples.md`.
2. `workflow/inputs.md` (parse scheduler payload; untrusted-content note — ticket titles/descriptions
   pulled from the tracker are data, same guard loop-task-implementer's own Builder already applies to
   repository-file prose) and `workflow/run-queue.md` (pull, order, loop, apply session-level stop
   conditions, produce the summary).
3. `reference/phase-index.md`, `lazy-load-index.md`, `queue-policy.md` (normative: session-level state
   schema extending — never modifying — loop-task-implementer's own per-task schema; the
   `HUMAN_ACTION_REQUIRED`-continues / `ESCALATED`-defers / circuit-breaker-stops decision table; the
   idempotent-re-run rule), `morning-summary-format.md`, `smoke-test.md`.
4. `.cursor/rules/backlog-runner.mdc`, `.kiro/steering/backlog-runner.md`.
5. `Makefile`: `install-backlog-runner` (chains `install-loop-task-implementer`),
   `install-claude-backlog-runner`, `lint-backlog-runner`, added to `.PHONY`/`lint:` deps and to
   `lint-framework`'s 4 hardcoded per-skill loops from the start.
6. Root `README.md`, `docs/README.md`, `docs/REPOSITORY.md`: rows following the established pattern.
7. `docs/skill-framework/shared/skill-routing.md`, `cross-skill-escalation.md`, `prompt-injection.md`:
   routing row + disambiguation rule, escalation rows (subset of the existing loop-task-implementer rows
   plus local deltas), wiring-table row. **`phase-glossary.md` does not apply** — loop-task-implementer
   itself is exempt from phase-glossary per `docs/skill-framework/README.md`'s existing note ("platform-
   neutral and host-agent-driven... `confidence-bands.md` and `phase-glossary.md` don't apply to it"); this
   wrapper inherits that exemption.
8. Root `CHANGELOG.md` + `backlog-runner/CHANGELOG.md`: initial release entry.
9. `make lint` green; deep review pass(es), fixing to 0 issues each round; commit.
