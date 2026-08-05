# Claude Code setup

**Normative.** How to install and configure any skill in this repo for **Claude Code**. Every skill
installs for Claude Code by default alongside Cursor — this doc also covers installing for one editor
only. `SKILL.md` frontmatter (`name` + `description` + optional `skill_version`) is
already Claude Code-compatible — both editors discover skills the same way, by `description` for
auto-invocation and `/<skill-name>` for explicit invocation. This doc covers the two things that
differ: **where skills install to** and **where MCP servers are configured**.

## 1. Install paths

| Scope | Cursor | Claude Code |
|-------|--------|-------------|
| User (all projects) | `~/.cursor/skills/<name>/` | `~/.claude/skills/<name>/` |
| Project (one repo) | `.cursor/skills/<name>/` | `.claude/skills/<name>/` |

Install with `scripts/install.sh --agent <agent>`:

| Command | Installs to |
|---------|-------------|
| `bash scripts/install.sh` | both `~/.cursor/skills/` and `~/.claude/skills/` (default) |
| `bash scripts/install.sh --agent all` | both, explicitly (same as default) |
| `bash scripts/install.sh --agent cursor` | `~/.cursor/skills/` only |
| `bash scripts/install.sh --agent claude-user` | `~/.claude/skills/` only |
| `bash scripts/install.sh --agent claude-project --target-dir <repo>` | `<repo>/.claude/skills/` only |

`make install` and `make install-<skill>` already install for both editors by default — no separate
step is needed to also get Claude Code. `make install-claude` and `make install-claude-<skill>` wrap
`--agent claude-user` for when you want Claude Code **only** (e.g. a machine without Cursor). See the
root [README.md](../../../README.md#install) and [docs/REPOSITORY.md](../../REPOSITORY.md#install).

No editor restart is required for Claude Code — a new session picks up installed skills.

## 2. MCP server config location

| | Cursor | Claude Code |
|---|--------|--------------|
| Config file | `~/.cursor/mcp.json` (one file, all scopes) | `.mcp.json` at a project root (project scope, commit or gitignore per team convention), or `~/.claude.json` under `mcpServers` (user scope) |
| CLI helper | none — edit `mcp.json` directly, or use Settings → MCP GUI | `claude mcp add <name> <command> [args...] [-s local\|project\|user]` (writes to the matching scope) or `claude mcp add-json <name> '<json>'` for a raw server block |
| Scopes | implicitly global | `local` (private, per-project), `project` (`.mcp.json`, shared with the team via git), `user` (all projects) |

The `mcpServers` JSON entries documented in each skill's `SETUP.md` (GitLab, Jira/Atlassian, Datadog,
GitHub, Jenkins) use the same schema Claude Code expects — only the file/command differs:

```bash
# Cursor: paste the JSON block into ~/.cursor/mcp.json under "mcpServers"

# Claude Code equivalent, same JSON block, project-shared scope:
claude mcp add-json gitlab '<paste the "mcpServers" entry JSON from pr-review/SETUP.md § 3 here>' -s project
```

Reuse the exact `command`/`args`/`env` values from the skill's `SETUP.md` — that content is
editor-agnostic and is not duplicated here.

## 3. No Cursor-GUI-plugin equivalent

A few MCP integrations are wired in Cursor via a one-click Settings → MCP plugin instead of a raw
JSON block. Those plugins don't exist in Claude Code; use the documented non-GUI alternative instead
— every skill that references a GUI plugin also documents the npx/JSON alternative it's built on:

| Cursor GUI plugin | Skill / section with the alternative | Claude Code path |
|--------------------|----------------------------------------|-------------------|
| GitLab plugin / official Duo MCP | [pr-review/SETUP.md § GitLab — full inline posting](../../../pr-review/SETUP.md#3-configure-mcp-servers-cursormcpjson) (`@zereight/mcp-gitlab`) | `claude mcp add-json gitlab '<json>' -s project` using that same server |
| GitHub MCP plugin | [k8s-overprovisioning-datadog/SETUP.md § Git provider MCP](../../../k8s-overprovisioning-datadog/SETUP.md#5-git-provider-mcp-gitlab-or-github-optional) | Configure the official GitHub MCP server (`command`/`args` per its docs) via `claude mcp add-json github '<json>'` instead of the Cursor plugin installer |
| Datadog plugin | [k8s-overprovisioning-datadog/SETUP.md § Enable Datadog MCP](../../../k8s-overprovisioning-datadog/SETUP.md#2-enable-datadog-mcp) | Install the `datadog` Claude Code plugin (marketplace) and run its `ddsetup` skill — same `ddsetup`/`ddconfig`/`ddtoolsets` skill names this repo's docs already reference work unchanged in Claude Code |

## 4. User input gates (`ask-question` equivalent)

Skills that pause for user confirmation (e.g. pr-review Phase 3 posting confirm, an ambiguous MR pick)
reference an `ask-question` tool by Cursor's name for it. Claude Code's equivalent is the
**`AskUserQuestion`** tool — same contract: presents numbered options, blocks until the user's next
message contains an explicit choice, never a simulated UI chip that continues the workflow without real
input. Where a skill's workflow file says "if `ask-question` is available, use it," read that as
"use `AskUserQuestion` on Claude Code" — the pause-and-wait rules that follow (no silence-as-consent,
no auto-generated chips) apply identically to both.

## 5. Verify

```bash
bash scripts/install.sh --agent claude-user <skill-name>
claude mcp list   # confirms configured servers are reachable
```

Then start a Claude Code session and confirm `/<skill-name>` appears, or ask a natural-language
question that should auto-invoke it (per that skill's `SETUP.md` § Use it / Smoke test).
