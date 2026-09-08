# loop-task-implementer

**Autonomous multi-task implementation loop.** Takes one or more software tasks from requirements to
verified, PR-ready repository state — separating implementation (Builder), independent review
(Reviewer, two lenses), and orchestration into isolated contexts so the Builder can never grade its
own homework.

Platform-neutral by design: works the same way whether the active agent is Cursor, ChatGPT/Codex,
Claude Code, GitHub Copilot, Kiro, or another repository-capable agent. No Datadog/GitLab/Jira MCP
dependency.

Core principle: **claims are advisory; repository evidence is authoritative.** Review and completion
freshness are bound to the shared `change_identity` / `review_evidence` contracts rather than a head
SHA or ad-hoc diff fingerprint alone.

## What it does

1. **Discovers repository policy** — branch protection, required checks/approvals, whether
   autonomous merge is authorized (defaults to `false`).
2. **Selects one eligible task** and dispatches a fresh **Builder** session to implement it, add
   tests, and open/update a pull request.
3. **Rebuilds and validates the current change identity** from base/head/merge-base, normalized
   effective patch, generated paths, dependency changes, and config changes.
4. **Dispatches two fresh Reviewer sessions** — Lens A (Safety and State), Lens B (Contracts and
   Operations) — each blind to the other's verdict and to the Builder's narrative.
5. **Adjudicates** every proposed finding as `ACCEPTED` / `REJECTED` / `NEEDS_EVIDENCE` /
   `CONTESTED`, using repository evidence, not persuasion, then converts each adjudicated lens result
   into validated portable `review_evidence` for that exact current identity.
6. **Remediates** accepted findings via fresh Builder dispatch, then reruns any lens invalidated by
   content, conflict-resolution, requirements, or unresolved third-party branch changes.
7. **Verifies authoritative checks and lifecycle readiness** for the exact current head. READY,
   COMPLETE, or an authorized merge requires both lenses CLEAN with complete defect-free evidence,
   current requirements, all existing merge-policy gates satisfied, and a zero-error lifecycle
   validation immediately before the action.
8. **Moves to the next eligible task**, repeating until the queue is empty or a circuit breaker
   fires.

**Read-only boundary for Reviewers:** inspect, run checks, use disposable worktrees — never commit,
push, edit the PR, merge, or self-certify lifecycle readiness.

## When to use

| Use loop-task-implementer | Use instead |
|-----------------------------|--------------|
| "Implement issue 42, review it deeply, fix findings, open a PR" | Review someone else's existing MR → **pr-review** |
| "Work through these tasks one by one, stop when each is ready to merge" | Post-incident root cause → **incident-rca** |
| "Run only reviewer Lens A on this change" | Understand an unfamiliar codebase first → **domain-comprehension** |
| "Adjudicate the review findings instead of blindly fixing them" | MySQL→Postgres dialect scrub → **mysql-to-postgres-sql** |
| Interactive, human-driven task loop | Scheduled/unattended overnight sweep across many tickets → **backlog-runner** |

## Invocation examples

```
Use loop-task-implementer to complete the next task.
Implement issue 42, review it deeply, fix findings, and open a PR.
Work through these tasks one by one and stop when each is ready to merge.
Take this PR through independent review and remediation.
Resume the loop-task-implementer workflow for the current branch.
```

## What you get

A completion report per task — see [report-template.md](report-template.md):

> **Task:** `TASK-42` — `org/repo`
> **Branch / PR:** `task-42-rate-limit-fix` — `https://.../pull/128`
> **Head commit:** `a1b2c3d...` · **change identity:** validated
> **Lens A:** CLEAN · **Lens B:** CLEAN · **review evidence:** fresh for same identity
> **Authoritative checks:** `ci/build: PASS (a1b2c3d...)`
> **Lifecycle gate:** PASS
> **Completion state:** `HUMAN_ACTION_REQUIRED` — autonomous merge not authorized; approve and merge manually

## Install

```bash
cd software-builder
make install-loop-task-implementer
```

Restart Cursor / start a new Claude Code session. Full setup, including in-repo discovery for
Cursor/Kiro and the ChatGPT/Codex/GitHub-Copilot/generic-fallback paths: [SETUP.md](SETUP.md).

## Related skills

- **pr-review** — hand off when a Builder-opened MR needs review beyond this skill's own lenses
- **incident-rca** — hand off when a task's implementation causes or requires incident investigation
- **domain-comprehension** — hand off when a task needs unfamiliar-codebase context first
- **mysql-to-postgres-sql** — hand off when a task touches MySQL-dialect SQL during a PG migration
- **backlog-runner** — for scheduled/overnight batch runs across many tickets, wraps this skill on a
  cadence instead of one interactive task loop

Agent instructions: [SKILL.md](SKILL.md).
