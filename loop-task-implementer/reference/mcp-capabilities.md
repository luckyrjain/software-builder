# Capability matrix

This skill has **no Datadog/GitLab/Jira MCP dependency** — it is host-agent-agnostic by design so it
can run inside Cursor, Claude Code, ChatGPT/Codex, or Kiro. What it *does* require is repository and
isolation capability from whichever host agent is running it.

| Capability | Required / Optional | Source | Degraded path when absent |
|------------|----------------------|--------|----------------------------|
| Repository read/write (git) | Required | Host agent's native git access or a repo connector (GitHub/GitLab MCP, Cursor background agent, etc.) | Cannot implement — stop and report the missing access |
| Independent role isolation (subagents, fresh sessions, or worktrees) | Required | Host agent — see [platform-adapters.md](platform-adapters.md) for the per-platform primitive | Fall back to sequential role simulation with explicit context resets (§ Platform behavior in `SKILL.md`) — never skip isolation silently |
| CI status for the exact head commit | Required for merge gating | Host agent's CI integration (GitHub Actions, GitLab CI, etc.) | Stop at verified readiness; do not merge on Builder-reported checks alone |
| Pull-request creation/update | Required | Host agent's repo connector or local `git`/`gh`/`glab` CLI | Stop and report — a completed implementation with no PR is not a completed task |
| Issue/task tracker read (GitHub Issues, Jira, Linear, etc.) | Optional | Whatever the caller's task source is | Accept task text directly from the user instead of a tracker link |

**Phase 0 equivalent:** the Orchestrator's policy-discovery step (`workflow/orchestrator.md` §1)
serves the same purpose other skills give a Phase 0 MCP-profile announcement — it records which of
the above capabilities are actually available before selecting a task.

No `telemetry.intent` requirement applies — this skill makes no observability-platform calls.
