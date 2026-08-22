# Claude Code Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all six skills in this repo installable and usable in Claude Code, in addition to Cursor, without changing Cursor behavior.

**Architecture:** `scripts/install.sh` gains an `--agent` flag (`cursor` default / `claude-user` / `claude-project` / `all`) that selects the destination root it copies skill directories into. New Makefile targets wrap the Claude Code install path. One new shared doc (`docs/skill-framework/shared/claude-code-setup.md`) documents the MCP-config and install-path differences once; every skill's `SETUP.md` gets a short pointer to it instead of a full duplicate walkthrough.

**Tech Stack:** Bash (install script, `set -euo pipefail`), GNU Make, Markdown docs, existing `scripts/lint-dangling-md-links.sh` and `make lint-framework` checks.

## Global Constraints

- Zero behavior change for existing Cursor users: `bash scripts/install.sh` / `make install` with no new flags must do exactly what they do today (verified in Task 1).
- No Claude Code plugin packaging (`.claude-plugin/plugin.json`, marketplace manifest) — out of scope per design spec.
- Reuse existing `mcpServers` JSON snippets in each `SETUP.md` as-is; do not duplicate them for Claude Code — only document where the file goes and how it's invoked.
- Every new/edited shared doc must pass `make lint-framework` and `scripts/lint-dangling-md-links.sh` (no dangling relative links or anchors).
- `shellcheck scripts/install.sh` must pass (matches existing `make lint` requirement on `scripts/*.sh`).

---

### Task 1: `scripts/install.sh` — add `--agent` and `--target-dir`

**Files:**
- Modify: `scripts/install.sh` (full rewrite of the arg-handling/install-loop section, lines 1–39)

**Interfaces:**
- Produces: `scripts/install.sh [--agent cursor|claude-user|claude-project|all] [--target-dir DIR] [skill ...]` — consumed by Task 2 (Makefile targets) and Task 6 (verification).

- [ ] **Step 1: Replace `scripts/install.sh` with the flag-aware version**

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

AGENT="cursor"
TARGET_DIR=""
SKILLS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
  --agent)
    AGENT="$2"
    shift 2
    ;;
  --target-dir)
    TARGET_DIR="$2"
    shift 2
    ;;
  *)
    SKILLS+=("$1")
    shift
    ;;
  esac
done

case "${AGENT}" in
cursor | claude-user | claude-project | all) ;;
*)
  echo "error: unknown --agent '${AGENT}' (expected cursor|claude-user|claude-project|all)" >&2
  exit 1
  ;;
esac

dest_roots() {
  case "${AGENT}" in
  cursor)
    echo "${HOME}/.cursor/skills"
    ;;
  claude-user)
    echo "${HOME}/.claude/skills"
    ;;
  claude-project)
    local base="${TARGET_DIR:-$(pwd)}"
    echo "${base}/.claude/skills"
    ;;
  all)
    printf '%s\n%s\n' "${HOME}/.cursor/skills" "${HOME}/.claude/skills"
    ;;
  esac
}

install_skill() {
  local skill="$1"
  local dest_root="$2"
  local skill_src="${REPO_ROOT}/${skill}"
  local skill_dest="${dest_root}/${skill}"

  if [[ ! -f "${skill_src}/SKILL.md" ]]; then
    echo "error: skill not found at ${skill_src}/SKILL.md" >&2
    return 1
  fi

  mkdir -p "${dest_root}"
  if [[ -d "${skill_dest}" ]]; then
    echo "warning: replacing existing install at ${skill_dest}" >&2
  fi
  rm -rf "${skill_dest}"
  cp -r "${skill_src}" "${skill_dest}"
  echo "Installed ${skill} → ${skill_dest}"
}

if [[ ${#SKILLS[@]} -eq 0 ]]; then
  shopt -s nullglob
  for skill_src in "${REPO_ROOT}"/*/SKILL.md; do
    SKILLS+=("$(basename "$(dirname "${skill_src}")")")
  done
  shopt -u nullglob
fi

while IFS= read -r dest_root; do
  for skill in "${SKILLS[@]}"; do
    install_skill "${skill}" "${dest_root}"
  done
done < <(dest_roots)

case "${AGENT}" in
cursor)
  echo "Restart Cursor to load the skill(s)."
  ;;
claude-user | claude-project)
  echo "Skill(s) available in your next Claude Code session."
  ;;
all)
  echo "Restart Cursor and start a new Claude Code session to load the skill(s)."
  ;;
esac
```

- [ ] **Step 2: Verify default (no-flag) behavior is unchanged**

Run from repo root:

```bash
rm -rf /tmp/cc-verify-cursor && HOME=/tmp/cc-verify-cursor bash scripts/install.sh
ls /tmp/cc-verify-cursor/.cursor/skills/
```

Expected: directory listing shows all six skill dirs (`pr-review`, `k8s-overprovisioning-datadog`,
`incident-rca`, `domain-comprehension`, `squad-map`, `mysql-to-postgres-sql`), and the script prints
`Restart Cursor to load the skill(s).` — identical to pre-change behavior, just under a scratch `$HOME`.

- [ ] **Step 3: Verify `--agent claude-user`**

```bash
rm -rf /tmp/cc-verify-claude && HOME=/tmp/cc-verify-claude bash scripts/install.sh --agent claude-user pr-review
ls /tmp/cc-verify-claude/.claude/skills/
test -f /tmp/cc-verify-claude/.claude/skills/pr-review/SKILL.md && echo OK
```

Expected: `pr-review` only, `OK` printed, message `Skill(s) available in your next Claude Code session.`

- [ ] **Step 4: Verify `--agent claude-project --target-dir`**

```bash
rm -rf /tmp/cc-verify-project && mkdir -p /tmp/cc-verify-project
bash scripts/install.sh --agent claude-project --target-dir /tmp/cc-verify-project squad-map
test -f /tmp/cc-verify-project/.claude/skills/squad-map/SKILL.md && echo OK
```

Expected: `OK` printed.

- [ ] **Step 5: shellcheck**

```bash
shellcheck scripts/install.sh
```

Expected: no warnings/errors.

- [ ] **Step 6: Clean up scratch dirs and commit**

```bash
rm -rf /tmp/cc-verify-cursor /tmp/cc-verify-claude /tmp/cc-verify-project
git add scripts/install.sh
git commit -m "feat(install): support Claude Code targets via --agent/--target-dir"
```

---

### Task 2: Makefile — Claude Code install targets

**Files:**
- Modify: `Makefile` (`.PHONY` line 1; add targets after the existing `install-*` block, i.e. after line 25)

**Interfaces:**
- Consumes: `scripts/install.sh --agent claude-user [skill]` from Task 1.
- Produces: `make install-claude`, `make install-claude-pr-review`, `make install-claude-k8s-overprovisioning`, `make install-claude-incident-rca`, `make install-claude-domain-comprehension`, `make install-claude-squad-map`, `make install-claude-mysql-to-postgres-sql` — referenced by Task 5 (README/REPOSITORY docs).

- [ ] **Step 1: Add new target names to `.PHONY`**

In `Makefile` line 1, change:

```makefile
.PHONY: install install-pr-review install-k8s-overprovisioning install-incident-rca install-incident-rca-deps install-domain-comprehension install-squad-map install-mysql-to-postgres-sql lint lint-framework lint-pr-review lint-k8s-skill lint-k8s lint-incident-rca lint-domain-comprehension lint-squad-map lint-mysql-to-postgres-sql setup-hooks setup kubesense-errors
```

to:

```makefile
.PHONY: install install-pr-review install-k8s-overprovisioning install-incident-rca install-incident-rca-deps install-domain-comprehension install-squad-map install-mysql-to-postgres-sql install-claude install-claude-pr-review install-claude-k8s-overprovisioning install-claude-incident-rca install-claude-domain-comprehension install-claude-squad-map install-claude-mysql-to-postgres-sql lint lint-framework lint-pr-review lint-k8s-skill lint-k8s lint-incident-rca lint-domain-comprehension lint-squad-map lint-mysql-to-postgres-sql setup-hooks setup kubesense-errors
```

- [ ] **Step 2: Add the targets after the existing `install-mysql-to-postgres-sql` target**

In `Makefile`, after the block ending at line 25 (`bash scripts/install.sh mysql-to-postgres-sql`), insert:

```makefile

install-claude:
	bash scripts/install.sh --agent claude-user

install-claude-pr-review:
	bash scripts/install.sh --agent claude-user pr-review

install-claude-k8s-overprovisioning:
	bash scripts/install.sh --agent claude-user k8s-overprovisioning-datadog

install-claude-incident-rca: install-incident-rca-deps
	bash scripts/install.sh --agent claude-user incident-rca

install-claude-domain-comprehension: install-claude-squad-map
	bash scripts/install.sh --agent claude-user domain-comprehension

install-claude-squad-map:
	bash scripts/install.sh --agent claude-user squad-map

install-claude-mysql-to-postgres-sql:
	bash scripts/install.sh --agent claude-user mysql-to-postgres-sql
```

(This mirrors the existing Cursor target's dependency structure: `install-claude-incident-rca` depends
on `install-incident-rca-deps` — same external `kubesense-mcp` dependency install, agent-agnostic — and
`install-claude-domain-comprehension` depends on `install-claude-squad-map`, matching
`install-domain-comprehension: install-squad-map` above it.)

- [ ] **Step 3: Verify**

```bash
rm -rf /tmp/cc-verify-make && HOME=/tmp/cc-verify-make make install-claude-pr-review
test -f /tmp/cc-verify-make/.claude/skills/pr-review/SKILL.md && echo OK
rm -rf /tmp/cc-verify-make
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "feat(makefile): add install-claude targets"
```

---

### Task 3: Shared Claude Code setup doc + framework wiring

**Files:**
- Create: `docs/skill-framework/shared/claude-code-setup.md`
- Modify: `docs/skill-framework/README.md` (Shared files table, after the `review-metadata-schema.md` row)
- Modify: `Makefile` (`lint-framework` target, the shared-doc existence loop at line ~503)

**Interfaces:**
- Produces: `docs/skill-framework/shared/claude-code-setup.md` — linked from Task 4 (per-skill `SETUP.md` deltas) as `../docs/skill-framework/shared/claude-code-setup.md`.

- [ ] **Step 1: Write `docs/skill-framework/shared/claude-code-setup.md`**

```markdown
# Claude Code setup

**Normative.** How to install and configure any skill in this repo for **Claude Code**, as an
alternative to Cursor. `SKILL.md` frontmatter (`name` + `description`) is
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
| `bash scripts/install.sh` | `~/.cursor/skills/` (default, unchanged) |
| `bash scripts/install.sh --agent claude-user` | `~/.claude/skills/` |
| `bash scripts/install.sh --agent claude-project --target-dir <repo>` | `<repo>/.claude/skills/` |
| `bash scripts/install.sh --agent all` | both `~/.cursor/skills/` and `~/.claude/skills/` |

`make install-claude` and `make install-claude-<skill>` wrap the `claude-user` form — see the root
[README.md](../../../README.md#install) and [docs/REPOSITORY.md](../../REPOSITORY.md#install).

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
claude mcp add-json gitlab '{"command":"npx","args":["-y","@zereight/mcp-gitlab"],"env":{"GITLAB_PERSONAL_ACCESS_TOKEN":"${GITLAB_PERSONAL_ACCESS_TOKEN}","GITLAB_API_URL":"https://gitlab.example.com/api/v4"}}' -s project
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

## 4. Verify

```bash
bash scripts/install.sh --agent claude-user <skill-name>
claude mcp list   # confirms configured servers are reachable
```

Then start a Claude Code session and confirm `/<skill-name>` appears, or ask a natural-language
question that should auto-invoke it (per that skill's `SETUP.md` § Use it / Smoke test).
```

- [ ] **Step 2: Add a row to `docs/skill-framework/README.md`'s Shared files table**

In `docs/skill-framework/README.md`, after the `review-metadata-schema.md` row (currently the last row
of the table, right before the `## How skills link here` heading), add:

```markdown
| [shared/claude-code-setup.md](shared/claude-code-setup.md) | Claude Code install paths + MCP config location, mapped from the Cursor equivalents used throughout each skill's `SETUP.md` |
```

Also add a `| claude-code-setup.md | Complete |` row to the `## Status` table at the bottom of that
file, in the same file, right after the `| review-metadata-schema.md | ... |` row.

- [ ] **Step 3: Add `claude-code-setup` to the `lint-framework` required-shared-docs loop**

In `Makefile`, around line 503, change:

```makefile
	@for f in confidence-bands cross-skill-escalation post-action-templates \
		smoke-test-conventions examples-conventions phase-glossary review-metadata-schema \
		skill-routing prompt-injection; do \
```

to:

```makefile
	@for f in confidence-bands cross-skill-escalation post-action-templates \
		smoke-test-conventions examples-conventions phase-glossary review-metadata-schema \
		skill-routing prompt-injection claude-code-setup; do \
```

- [ ] **Step 4: Verify dangling links and lint-framework**

```bash
bash scripts/lint-dangling-md-links.sh docs/skill-framework/README.md docs/skill-framework/shared/*.md
```

Expected: exit 0, no `dangling:` lines printed.

```bash
make lint-framework
```

Expected: ends with `lint-framework: ok`. (This step will still show failures related to Task 4's
`SETUP.md` links until Task 4 lands — rerun after Task 4 for a clean pass; for now confirm no new
failures beyond what already existed before this task, and specifically that
`docs/skill-framework/shared/claude-code-setup.md` existence/non-empty check passes.)

- [ ] **Step 5: Commit**

```bash
git add docs/skill-framework/shared/claude-code-setup.md docs/skill-framework/README.md Makefile
git commit -m "docs(framework): add shared Claude Code setup doc"
```

---

### Task 4: Per-skill `SETUP.md` — Claude Code subsection

**Files:**
- Modify: `pr-review/SETUP.md` (after line 129, the `Restart Cursor so skills and MCP servers reload.` line ending § 2)
- Modify: `k8s-overprovisioning-datadog/SETUP.md` (after line 22, the workflow-modules sentence ending § 1)
- Modify: `incident-rca/SETUP.md` (after line 54, the ```` ``` ```` closing the Cursor install code block)
- Modify: `domain-comprehension/SETUP.md` (after line 10, `Restart Cursor so the skill reloads.`)
- Modify: `squad-map/SETUP.md` (after line 10, `Restart Cursor so the skill reloads.`)
- Modify: `mysql-to-postgres-sql/SETUP.md` (after line 10, `Restart Cursor so the skill reloads.`)

**Interfaces:**
- Consumes: `docs/skill-framework/shared/claude-code-setup.md` from Task 3 (linked via relative path).

- [ ] **Step 1: `pr-review/SETUP.md`**

After line 129 (`Restart Cursor so skills and MCP servers reload.`), insert:

```markdown

### Claude Code

Install: `bash scripts/install.sh --agent claude-user pr-review` (or `claude-project` from inside
your repo). MCP servers: reuse the same JSON snippets from § 3 below, placed in `.mcp.json` / via
`claude mcp add-json` instead of `~/.cursor/mcp.json` — the GitLab plugin / Duo MCP path in § 3 is
Cursor-GUI-only, so use the `@zereight/mcp-gitlab` inline-posting entry instead. Full mapping:
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).
```

- [ ] **Step 2: `k8s-overprovisioning-datadog/SETUP.md`**

After line 22 (`Workflow modules live under \`workflow/\` — the top-level [SKILL.md](SKILL.md) is a
thin orchestrator (~42 lines).`), insert:

```markdown

### Claude Code

Install: `bash scripts/install.sh --agent claude-user k8s-overprovisioning-datadog`. Datadog MCP:
install the `datadog` Claude Code plugin and run its `ddsetup` skill instead of the Cursor Datadog
plugin (§ 2). GitLab/GitHub MCP (§ 5): same JSON entries, via `claude mcp add-json` instead of
`~/.cursor/mcp.json`. Full mapping: [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).
```

- [ ] **Step 3: `incident-rca/SETUP.md`**

After line 54 (the closing ```` ``` ```` of the Cursor install code block under `## Cursor skill
install`), insert:

```markdown

### Claude Code install

```bash
cd ai-skills
make install-claude-incident-rca
```

MCP servers (§ below): same JSON entries, via `.mcp.json` / `claude mcp add-json` instead of
`~/.cursor/mcp.json`. Datadog: use the `datadog` Claude Code plugin's `ddsetup` skill instead of the
Cursor Datadog plugin. Full mapping: [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).
```

- [ ] **Step 4: `domain-comprehension/SETUP.md`**

After line 10 (`Restart Cursor so the skill reloads.`), insert:

```markdown

### Claude Code

```bash
cd ai-skills
make install-claude-domain-comprehension
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md) for MCP config location
differences (this skill's optional GitLab/Datadog enrichments use the same server entries).
```

- [ ] **Step 5: `squad-map/SETUP.md`**

After line 10 (`Restart Cursor so the skill reloads.`), insert:

```markdown

### Claude Code

```bash
cd ai-skills
make install-claude-squad-map
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md) for MCP config location
differences (GitLab/Datadog server entries are unchanged).
```

- [ ] **Step 6: `mysql-to-postgres-sql/SETUP.md`**

After line 10 (`Restart Cursor so the skill reloads.`), insert:

```markdown

### Claude Code

```bash
cd ai-skills
make install-claude-mysql-to-postgres-sql
```

No restart needed — a new Claude Code session picks it up. This skill has no required MCP servers;
see [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md) if you wire the
optional post-cutover Datadog check.
```

- [ ] **Step 7: Verify dangling links across all six `SETUP.md`**

```bash
bash scripts/lint-dangling-md-links.sh pr-review/SETUP.md k8s-overprovisioning-datadog/SETUP.md \
  incident-rca/SETUP.md domain-comprehension/SETUP.md squad-map/SETUP.md mysql-to-postgres-sql/SETUP.md
```

Expected: exit 0, no `dangling:` lines.

- [ ] **Step 8: Re-run `make lint-framework`**

```bash
make lint-framework
```

Expected: ends with `lint-framework: ok` (this closes out the Task 3 caveat — every `SETUP.md` still
links `skill-framework`, unaffected by these additions).

- [ ] **Step 9: Commit**

```bash
git add pr-review/SETUP.md k8s-overprovisioning-datadog/SETUP.md incident-rca/SETUP.md \
  domain-comprehension/SETUP.md squad-map/SETUP.md mysql-to-postgres-sql/SETUP.md
git commit -m "docs(setup): add Claude Code install/MCP notes to each skill"
```

---

### Task 5: Top-level docs — README, REPOSITORY, CHANGELOG

**Files:**
- Modify: `README.md` (Install section, after line 43 — the closing ```` ``` ```` of the `bash scripts/install.sh ...` block)
- Modify: `docs/REPOSITORY.md` (Install section, after line 61 — the closing ```` ``` ```` of the per-skill `bash scripts/install.sh <skill>` block; Makefile targets table, after line 73)
- Modify: `CHANGELOG.md` (`## Repository` section, add a new dated entry at the top of that section)

- [ ] **Step 1: `README.md`**

Find the line `All targets copy skill directories to \`~/.cursor/skills/\`. **Restart Cursor** after
installing.` (end of the `## Install` section, right before `## Develop`). Insert immediately after
it:

```markdown

Install for **Claude Code** instead of Cursor — same skills, different target:

```bash
make install-claude                       # all skills → ~/.claude/skills/
make install-claude-pr-review
make install-claude-k8s-overprovisioning
make install-claude-incident-rca
make install-claude-domain-comprehension
make install-claude-squad-map
make install-claude-mysql-to-postgres-sql
```

Or `bash scripts/install.sh --agent claude-user [skill]`, or `--agent claude-project --target-dir
<repo>` to install into one project's `.claude/skills/`. Details:
[docs/skill-framework/shared/claude-code-setup.md](docs/skill-framework/shared/claude-code-setup.md).
```

- [ ] **Step 2: `docs/REPOSITORY.md` — Install section**

Find the line `With no arguments, \`install.sh\` discovers every \`*/SKILL.md\` under the repo root
and installs each.` (last line of the `## Install` section, right before `## Makefile targets`).
Insert immediately after it:

```markdown

For Claude Code, use `--agent claude-user` (installs to `~/.claude/skills/` instead of
`~/.cursor/skills/`) or the `install-claude*` Makefile targets below. No restart needed — a new
Claude Code session picks up installed skills. See
[docs/skill-framework/shared/claude-code-setup.md](skill-framework/shared/claude-code-setup.md).
```

- [ ] **Step 3: `docs/REPOSITORY.md` — Makefile targets table**

After line 73 (the `| \`make install-mysql-to-postgres-sql\` | Install only
\`mysql-to-postgres-sql/\` |` row), insert:

```markdown
| `make install-claude` | Run `scripts/install.sh --agent claude-user` for all skills |
| `make install-claude-<skill>` | Install only `<skill>/` for Claude Code (`pr-review`, `k8s-overprovisioning`, `incident-rca`, `domain-comprehension`, `squad-map`, `mysql-to-postgres-sql`) |
```

- [ ] **Step 4: `CHANGELOG.md`**

In the `## Repository` section, add a new subsection right after the `## Repository` heading (before
the existing `### Repo hygiene (2026-07-02)` entry):

```markdown

### Claude Code compatibility (2026-07-09)

- `scripts/install.sh` gained `--agent cursor|claude-user|claude-project|all` and `--target-dir`;
  default (no-flag) behavior unchanged.
- New `make install-claude` / `make install-claude-<skill>` targets.
- New `docs/skill-framework/shared/claude-code-setup.md` — install paths + MCP config location
  mapping for Claude Code, linked from every skill's `SETUP.md`.
```

- [ ] **Step 5: Verify dangling links on the edited top-level docs**

```bash
bash scripts/lint-dangling-md-links.sh README.md docs/REPOSITORY.md
```

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/REPOSITORY.md CHANGELOG.md
git commit -m "docs: document Claude Code install path at the repo level"
```

---

### Task 6: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Full lint**

```bash
make lint
```

Expected: ends with all `lint-*` targets passing and shellcheck clean on `scripts/*.sh`, no errors.

- [ ] **Step 2: End-to-end install smoke test — all four agent modes**

```bash
rm -rf /tmp/cc-final
HOME=/tmp/cc-final bash scripts/install.sh
HOME=/tmp/cc-final bash scripts/install.sh --agent claude-user
mkdir -p /tmp/cc-final-project
bash scripts/install.sh --agent claude-project --target-dir /tmp/cc-final-project
HOME=/tmp/cc-final-all bash scripts/install.sh --agent all pr-review

test -d /tmp/cc-final/.cursor/skills/pr-review && \
test -d /tmp/cc-final/.claude/skills/pr-review && \
test -d /tmp/cc-final-project/.claude/skills/pr-review && \
test -d /tmp/cc-final-all/.cursor/skills/pr-review && \
test -d /tmp/cc-final-all/.claude/skills/pr-review && \
echo "ALL OK"

rm -rf /tmp/cc-final /tmp/cc-final-project /tmp/cc-final-all
```

Expected: `ALL OK` printed.

- [ ] **Step 3: Confirm git status is clean except intended commits**

```bash
git status
git log --oneline -8
```

Expected: working tree clean (aside from any pre-existing unrelated uncommitted changes noted before
this work started — `docs/skill-framework/README.md`, `k8s-overprovisioning-datadog/*`,
`pr-review/reference/finding-gates.md` — leave those untouched); the last 6 commits are the ones from
Tasks 1–5.

- [ ] **Step 4: Report completion**

No further commit needed for this step — it's a verification checkpoint only.
