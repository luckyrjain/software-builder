# Install script

Copies skill directories from this repository into the coding agent's skills install path.

## What it does

`scripts/install.sh`:

1. Resolves the repo root (parent of `scripts/`).
2. For each skill name passed as an argument — or for every directory containing `SKILL.md` when no
   arguments are given — copies the full skill folder to the resolved destination root(s).
3. Destination depends on `--agent` (default `all`) and whether `--target-dir` is set:
   - **No `--target-dir` (global):** `cursor` / `cursor-project` → `~/.cursor/skills/`;
     `claude-user` / `claude-project` → `~/.claude/skills/`; `all` → both.
   - **With `--target-dir <repo>` (project):** `cursor` / `cursor-project` →
     `<repo>/.cursor/skills/`; `claude-project` → `<repo>/.claude/skills/`; `all` → both project
     dirs. (`claude-user` stays global.)
4. Replaces any existing install at each destination (`rm -rf` then `cp -r`).
5. Prints a restart/session reminder appropriate to the chosen `--agent`.

Kiro and ChatGPT/Codex are **not** handled by this script — Kiro needs no install step at all (see
`.kiro/steering/`), and Codex's skills-directory convention isn't uniform across setups, so copy
manually (`cp -R <skill> ~/.agents/skills/<skill>`). See root
[README.md § Install for your specific coding agent](../README.md#install-for-your-specific-coding-agent).

## Usage

```bash
# From repo root — all skills, both Cursor and Claude Code (global)
bash scripts/install.sh
make install

# One skill (global)
bash scripts/install.sh pr-review
bash scripts/install.sh k8s-overprovisioning-datadog
bash scripts/install.sh incident-rca
bash scripts/install.sh domain-comprehension
bash scripts/install.sh squad-map
bash scripts/install.sh mysql-to-postgres-sql
bash scripts/install.sh loop-task-implementer

# One agent only (global)
bash scripts/install.sh --agent cursor
bash scripts/install.sh --agent claude-user

# Project-local (into another repo's .cursor/skills / .claude/skills)
bash scripts/install.sh --target-dir /path/to/some/repo domain-comprehension squad-map
bash scripts/install.sh --agent cursor --target-dir /path/to/some/repo domain-comprehension
bash scripts/install.sh --agent claude-project --target-dir /path/to/some/repo domain-comprehension
```

Makefile wrappers: `make install`, `make install-<skill>` (per skill), `make install-claude`,
`make install-claude-<skill>`.

## Requirements

- Bash with `set -euo pipefail`
- Write access to the resolved destination root(s) (`~/.cursor/skills/`, `~/.claude/skills/`, or a
  project's `.cursor/skills/` / `.claude/skills/` when `--target-dir` is set)
- Each skill source must contain `SKILL.md` or the script exits with an error

## Quality gate

Staged changes to `scripts/*.sh` are linted by the pre-commit hook (`make setup-hooks`) and by
`make lint` (shellcheck locally or via Docker).

See [docs/REPOSITORY.md](../docs/REPOSITORY.md) for full repo documentation.
