# Capability matrix

This skill has **no Datadog/GitLab/Jira MCP dependency** — it is host-agent-agnostic by design so it
can run inside Cursor, Claude Code, ChatGPT/Codex, GitHub Copilot, or Kiro. What it *does* require is repository and
isolation capability from whichever host agent is running it.

| Capability | Required / Optional | Source | Degraded path when absent |
|------------|----------------------|--------|----------------------------|
| Repository read/write (git) | Required | Host agent's native git access or a repo connector (GitHub/GitLab MCP, Cursor background agent, etc.) | Cannot implement — stop and report the missing access |
| Independent role isolation (subagents, fresh sessions, or worktrees) | Required | Host agent — see [platform-adapters.md](platform-adapters.md) for the per-platform primitive | Fall back to sequential role simulation with explicit context resets (§ Platform behavior in `SKILL.md`) — never skip isolation silently |
| CI status for the exact head commit | Required for merge gating | Host agent's CI integration (GitHub Actions, GitLab CI, etc.) | Stop at verified readiness; do not merge on Builder-reported checks alone |
| CI job/run structured metadata (`conclusion` field) for the exact head | Optional | Host agent's CI integration (structured API/CLI fields only, e.g. GitHub Actions' job/run `conclusion`; never log or annotation text) | Eligibility gate never runs; falls through to the existing, unchanged ambiguous-failure judgment call |
| Pull-request creation/update | Required | Host agent's repo connector or local `git`/`gh`/`glab` CLI | Stop and report — a completed implementation with no PR is not a completed task |
| Issue/task tracker read (GitHub Issues, Jira, Linear, etc.) | Optional | Whatever the caller's task source is | Accept task text directly from the user instead of a tracker link |
| `host.scm.comment.read` | Optional | Host agent's repo connector or local `gh`/`glab` CLI | Skip the comment-check step entirely; proceed exactly as this skill did before this capability existed |
| `host.scm.actor.permission` | Optional | Same source | Narrow actor-scoping to CODEOWNERS-membership only, and explicitly disclose this narrowing in the completion report — never silently default to trusting every commenter |
| `host.scm.comment.reply` | Optional | Same source | Skip reply-and-verify; findings are still adjudicated and remediated, just not announced back to the originating thread |
| `host.scm.review.request` | Optional | Same source | Skip re-request-review; the human reviewer is not automatically re-pinged |
| PR review-comment read for cross-run convention-capture (`fetch_and_score`) | Optional | Host agent's repo connector or local `gh`/`glab` CLI (same class as this skill's existing PR-comment-read capability) | Convention-scan/Reviewer-side similarity check cannot run; the scan skips affected candidates (scanner side) or the finding becomes `NEEDS_EVIDENCE` (Reviewer side) — never silently treated as passed |
| Local process start + port/readiness probe + process-group teardown for app-run/UI verification | Optional | Host agent's subprocess/process-group primitives (POSIX `setsid`/`killpg` — this whole row is gated as ONE capability because the teardown sub-mechanism is POSIX-only and the state machine's own invariant requires every started process to reach guaranteed teardown, so there is no safe degraded mode for "start without guaranteed teardown") | Skip this tier entirely; never fabricate a result; a host without POSIX process-group semantics gets this same degraded path |
| Screenshot capture for app-run/UI verification | Optional | Host agent's browser-automation/screenshot tooling (e.g. Claude Code's `Claude_Browser` `preview_start`/screenshot tools) | Skip just the screenshot sub-step; everything else in the tier (process start, readiness, smoke test) still runs |

**Phase 0 equivalent:** the Orchestrator's policy-discovery step (`workflow/orchestrator.md` §1)
serves the same purpose other skills give a Phase 0 MCP-profile announcement — it records which of
the above capabilities are actually available before selecting a task.

No `telemetry.intent` requirement applies — this skill makes no observability-platform calls.
