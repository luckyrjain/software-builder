# Claude Code compatibility — design

## Problem

All six skills in this repo (`pr-review`, `k8s-overprovisioning-datadog`, `incident-rca`,
`domain-comprehension`, `squad-map`, `mysql-to-postgres-sql`) are documented, installed, and
distributed as **Cursor Agent Skills** only: `scripts/install.sh` copies each skill directory to
`~/.cursor/skills/`, and every `SETUP.md` gives Cursor-specific install paths, GUI steps ("Cursor
Settings → MCP → Add"), and `~/.cursor/mcp.json` instructions.

The `SKILL.md` files themselves (`name` + `description` + optional `skill_version` frontmatter,
Markdown body) are already directly compatible with Claude Code's skill format — Claude Code
discovers skills the same way (frontmatter `description` for auto-invocation, `/<skill-name>` for
explicit invocation). Confirmed by grep: no skill sets `disable-model-invocation` (a Cursor-only
frontmatter field), so there's no active frontmatter incompatibility to reconcile.

The gap is **distribution and setup docs**, not skill content:

1. No install path for Claude Code (`~/.claude/skills/` user-level, `.claude/skills/` project-level).
2. `SETUP.md` MCP-server instructions assume Cursor's config file (`~/.cursor/mcp.json`) and GUI
   plugins that don't exist in Claude Code.
3. Top-level docs (`README.md`, `docs/REPOSITORY.md`, `docs/skill-framework/README.md`) only
   describe the Cursor install flow.

## Goals

- Skills install and run identically in Claude Code and Cursor.
- Cursor remains the primary, fully-documented path — zero behavior change for existing Cursor
  users (`make install` / `bash scripts/install.sh` with no flags still does exactly what it does
  today).
- Claude Code support is additive: new flags, new Makefile targets, one new shared doc, short
  per-skill deltas. No rewrite of the six existing Cursor-specific `SETUP.md` walkthroughs.

## Non-goals

- Packaging skills as a Claude Code **plugin** (`.claude-plugin/plugin.json` + marketplace
  manifest). Deferred — plain directory-copy install is the agreed delivery mechanism for now.
- Migrating away from Cursor or dropping Cursor-specific docs.
- Rewriting each `SETUP.md`'s Cursor GUI walkthrough into a parallel Claude Code walkthrough of the
  same depth. A shared doc + short per-skill pointer covers the actual differences (config file
  location, restart semantics); the MCP server JSON snippets themselves are reused as-is since both
  editors consume the same `mcpServers` JSON shape.

## Design

### 1. `scripts/install.sh` — add `--agent` and `--target-dir`

```
bash scripts/install.sh [--agent cursor|claude-user|claude-project|all] [--target-dir DIR] [skill ...]
```

- `--agent cursor` (default, unchanged) → copies to `~/.cursor/skills/`.
- `--agent claude-user` → copies to `~/.claude/skills/`.
- `--agent claude-project` → copies to `<DIR>/.claude/skills/`, where `DIR` defaults to `$(pwd)`
  (the directory the script is run from) unless `--target-dir` is given. This lets a user run the
  installer from inside their own project to install project-scoped skills there.
- `--agent all` → installs to `~/.cursor/skills/` **and** `~/.claude/skills/` (project-level is
  opt-in only, since it writes into a project git tree — never bundled into "all").
- No `--agent` flag and no other args → identical to current behavior (Cursor, all skills).
- Positional skill-name args keep working exactly as today, combined with any `--agent` value.

Implementation: refactor the existing `install_skill` function to take a destination root as a
parameter instead of a hardcoded `SKILLS_DIR` global; add arg parsing for the two new flags; loop
over the resolved destination root(s).

### 2. `Makefile` — new targets, existing ones untouched

- `install-claude` → `bash scripts/install.sh --agent claude-user`
- `install-claude-<skill>` for each of the six skills (mirrors existing `install-<skill>` targets)
- Existing `install` / `install-<skill>` targets are unchanged (still Cursor-only, matching current
  docs and muscle memory).

### 3. New shared doc: `docs/skill-framework/shared/claude-code-setup.md`

One canonical reference, linked from every skill's `SETUP.md` and from the framework README. Covers:

- **Install paths** — `~/.claude/skills/<name>/` (user) vs `.claude/skills/<name>/` (project),
  and the `install.sh --agent` flags that produce each.
- **MCP config location** — Claude Code reads MCP servers from a project-local `.mcp.json` (checked
  in or gitignored per team convention) and/or `claude mcp add` (writes to user/project/local scope
  depending on `-s`), vs Cursor's single `~/.cursor/mcp.json`. The `mcpServers` JSON shape used in
  every skill's `SETUP.md` is unchanged — only the file it goes in and how it's invoked differs.
  Includes a `claude mcp add-json <name> '<json>'` example next to the equivalent raw file edit.
- **No GUI-plugin equivalent** — Cursor's one-click plugins (GitLab, Datadog, GitHub, Duo) have no
  Claude Code counterpart; use the same `npx`-based / self-hosted MCP server entries each `SETUP.md`
  already documents as the non-GUI alternative.
  Mapping table: Cursor GUI plugin → Claude Code MCP entry to use instead, cross-referencing each
  skill's `SETUP.md` § where the JSON snippet lives (GitLab, Jira/Atlassian, Datadog, GitHub,
  Jenkins, KubeSense).
- **Reload semantics** — no editor restart; a new Claude Code session picks up installed skills and
  `.mcp.json` changes.
- **Invocation** — unchanged: `/<skill-name>` or natural language both work the same way in Claude
  Code as in Cursor.

### 4. Per-skill `SETUP.md` deltas

Each of the six `SETUP.md` files gets one short new subsection (placed right after the existing
Cursor "Install" step), of this shape:

```markdown
### Claude Code

Install: `bash scripts/install.sh --agent claude-user <skill-name>` (or `claude-project` from
inside your repo). MCP servers: same JSON snippets above, placed in `.mcp.json` / via `claude mcp
add` instead of `~/.cursor/mcp.json` — see [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).
```

`pr-review/SETUP.md` (the only one with GUI-plugin-specific content — GitLab Duo, Jira OAuth via
Cursor Settings) gets one extra line noting to use the `npx`-based GitLab/Jira MCP entries already
documented in that same file instead of the GUI installer.

### 5. Top-level docs

- `README.md` — Install section gets a second code block for Claude Code, mirroring the existing
  Cursor one; per-skill Makefile target table gets the `install-claude-<skill>` equivalents noted.
- `docs/REPOSITORY.md` — layout tree comment for `scripts/install.sh` updated to mention both
  targets; `Makefile` bullet notes the new targets.
- `docs/skill-framework/README.md` — new row in the "Shared files" table pointing at
  `shared/claude-code-setup.md`.

### 6. Lint

No new lint target. `make lint-framework` (which checks required shared framework docs are present)
gets `shared/claude-code-setup.md` added to its required-file list, consistent with how the other
shared docs are already checked.

## Testing / verification

- `bash scripts/install.sh` (no args) still installs all six skills to `~/.cursor/skills/` —
  confirms zero regression to current behavior.
- `bash scripts/install.sh --agent claude-user pr-review` installs one skill to
  `~/.claude/skills/pr-review/`.
- `bash scripts/install.sh --agent claude-project --target-dir /tmp/x squad-map` installs into
  `/tmp/x/.claude/skills/squad-map/`.
- `make lint-framework` passes with the new required doc present, fails if it's removed (matches
  existing pattern for the other shared docs).
- Manual: install `pr-review` into a Claude Code session's `~/.claude/skills/`, confirm `/pr-review`
  appears and the skill loads (spot-check only — full MR review flow requires live GitLab MCP,
  out of scope for this change).

## Out of scope / deferred

- Claude Code plugin packaging (`.claude-plugin/plugin.json`, marketplace manifest) — revisit if
  plain directory-copy proves insufficient (e.g. team wants one-command `/plugin marketplace add`
  distribution).
- Any change to skill *behavior*, workflow phases, or MCP tool usage — this is purely a
  distribution/docs change.
