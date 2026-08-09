# loop-task-implementer — Setup


## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | GitLab MCP, CI provider (repo-specific) |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
Platform-neutral autonomous task-implementation skill: isolated build → evidence-based review →
remediation → validation → pull-request → completion. No Datadog/GitLab/Jira MCP required — see
[reference/mcp-capabilities.md](reference/mcp-capabilities.md) for what it does need from the host
agent.

## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` in its frontmatter, so the agent
can auto-apply it when you ask to implement a task, work through a queue, or take something to PR in
natural language — no slash command exists for this skill. Leave it unset unless you want invocation
to require an explicit ask.

## Quickstart

1. `git clone` this repo (see root [README.md § Install](../README.md#install)), then
   `make install-loop-task-implementer` (or `bash scripts/install.sh loop-task-implementer`).
2. Restart your agent (Cursor) or start a new session (Claude Code) so the skill loads.
3. Confirm your host agent can isolate roles — native subagents, fresh sessions, or worktrees (see
   [reference/platform-adapters.md](reference/platform-adapters.md)). Without this, role isolation
   falls back to sequential context resets, which is weaker but still usable.
4. Confirm repository write access and CI visibility for the target repo — see
   [reference/mcp-capabilities.md](reference/mcp-capabilities.md).
5. Say: "Use loop-task-implementer to implement `<task>` and open a PR."

## What's in here

```
loop-task-implementer/
├── SKILL.md                        # thin orchestrator — roles, workflow, guardrails
├── SETUP.md                        # this file
├── README.md                       # human-facing one-pager
├── examples.md                     # invocation table + scenario walkthroughs
├── report-template.md              # canonical completion-report skeleton
├── workflow/
│   ├── orchestrator.md             # Orchestrator role prompt
│   ├── builder.md                  # Builder role prompt
│   └── reviewer.md                 # Reviewer role prompt (both lenses)
└── reference/
    ├── phase-index.md              # ordered role list → workflow file links
    ├── lazy-load-index.md          # which file loads per role, and what never to load
    ├── mcp-capabilities.md         # host-capability matrix (no Datadog/GitLab/Jira MCP)
    ├── smoke-test.md               # post-install / post-edit verification checklist
    ├── pressure-tests.md           # maintainer scenario → expected-behavior table
    ├── platform-adapters.md        # Cursor / Codex / Claude Code / Kiro / generic fallback
    └── state-schema.yaml           # per-task shared state (Orchestrator-owned)
```

## 1. Requirements

- A host agent capable of running this skill's SKILL.md — Cursor, Claude Code, ChatGPT/Codex, Kiro,
  or a generic repository-capable agent via the fallback path in
  [reference/platform-adapters.md](reference/platform-adapters.md).
- Repository write access (git) for the Builder role, and repository read access for the Reviewer
  role.
- Some CI/check visibility for the exact head commit — required for merge gating (§ Evidence
  priority in `SKILL.md`). Without it, the skill can still implement and open a PR but must stop
  before any authorized merge.
- Explicit authorization (user instruction, repository policy, or approved workflow config) before
  autonomous merge is ever attempted — it defaults to `false`.

## 2. Install the skill

From the repo root: `make install-loop-task-implementer` (or `bash scripts/install.sh
loop-task-implementer`). See the root [README.md § Install](../README.md#install) for the full
clone/install steps and `--agent` targeting (`cursor` / `claude-user` / `claude-project` / `all`),
which apply the same way here.

## 3. In-repo discovery (no install step)

When you're working directly inside this repo (not via an installed copy), two discovery files let
Cursor and Kiro find the skill without an explicit install:

- `.cursor/rules/loop-task-implementer.mdc`
- `.kiro/steering/loop-task-implementer.md`

Both simply point at `loop-task-implementer/SKILL.md`. See
[reference/platform-adapters.md](reference/platform-adapters.md) for Codex and generic fallback.

## 4. Use it

Invoke with natural language — there is no slash command. A few common forms:

- "Use loop-task-implementer to complete the next task."
- "Implement issue 42, review it deeply, fix findings, and open a PR."
- "Resume the loop-task-implementer workflow for the current branch."

Full invocation table and scenarios: [examples.md](examples.md).

## 5. Tuning

Budgets (dirty review cycles, contested rounds, review size thresholds, CI polling) are set by the
Orchestrator per task — see `workflow/orchestrator.md` §3. Override by stating them explicitly in
the task instruction (e.g. "cap dirty reviews at 5" or "hard-stop review at 60 files").

## Framework

This skill follows the same shared-framework conventions as the other skills in this repository:
[docs/skill-framework/README.md](../docs/skill-framework/README.md) ·
[cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md) ·
[smoke-test-conventions](../docs/skill-framework/shared/smoke-test-conventions.md) ·
[examples-conventions](../docs/skill-framework/shared/examples-conventions.md) ·
[post-action-templates](../docs/skill-framework/shared/post-action-templates.md) ·
[claude-code-setup](../docs/skill-framework/shared/claude-code-setup.md).

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against a small
repo with at least one open, well-scoped task and repository write access. A correct minimal run states
the policy-discovery result, dispatches a fresh Builder, runs two isolated Reviewer lenses, and stops at
verified readiness rather than merging without explicit authorization. Deeper edge cases:
[reference/pressure-tests.md](reference/pressure-tests.md).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Reviewer lens sees the Builder's PR description or commit messages | Orchestrator failed to withhold them when building the neutral review package — see `workflow/orchestrator.md` §6 |
| Same finding keeps getting "fixed" without resolving | Two failed Builder fix attempts on the same accepted finding should escalate, not trigger a third silent remediation attempt (pressure test #3) |
| Run merges without you explicitly authorizing it | Should never happen — `autonomous_merge_authorized` defaults to `false` and is never inferred from silence (pressure test #8); treat as a bug in the invocation |
| Both Reviewer lenses report `CLEAN` from a stale run after a manual rebase | Both lens approvals must be invalidated and rerun after a base-branch conflict-resolution rebase, not reused (pressure test #6) |
| No subagent/worktree/fresh-session primitive available | Falls back to sequential role simulation with explicit context resets — see [reference/platform-adapters.md](reference/platform-adapters.md) § Sequential role simulation; the smoke test still requires evidence the reset actually happened, not just narration |
| CI never resolves and the run seems stuck | Orchestrator should stop polling once the configured active-polling budget is hit and report the pending state, not poll indefinitely (pressure test #12) |
