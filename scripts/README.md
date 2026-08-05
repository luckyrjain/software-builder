# Install script

Copies skill directories from this repository into the coding agent's skills install path.

## What it does

`scripts/install.sh`:

1. Resolves the repo root (parent of `scripts/`).
2. For each skill name passed as an argument — or for every directory containing `SKILL.md` when no
   arguments are given — copies the full skill folder to the resolved destination root(s).
3. Destination depends on `--agent` (default `all`): `cursor` → `~/.cursor/skills/`; `claude-user` →
   `~/.claude/skills/`; `claude-project` → `<--target-dir or cwd>/.claude/skills/`; `all` (default) →
   both `~/.cursor/skills/` and `~/.claude/skills/`.
4. Replaces any existing install at each destination (`rm -rf` then `cp -r`).
5. Prints a restart/session reminder appropriate to the chosen `--agent`.

Kiro and ChatGPT/Codex are **not** handled by this script — Kiro needs no install step at all (see
`.kiro/steering/`), and Codex's skills-directory convention isn't uniform across setups, so copy
manually (`cp -R <skill> ~/.agents/skills/<skill>`). See root
[README.md § Install for your specific coding agent](../README.md#install-for-your-specific-coding-agent).

## Usage

```bash
# From repo root — all skills, both Cursor and Claude Code
bash scripts/install.sh
make install

# One skill
bash scripts/install.sh pr-review
bash scripts/install.sh k8s-overprovisioning-datadog
bash scripts/install.sh incident-rca
bash scripts/install.sh domain-comprehension
bash scripts/install.sh squad-map
bash scripts/install.sh mysql-to-postgres-sql
bash scripts/install.sh loop-task-implementer

# One agent only
bash scripts/install.sh --agent cursor
bash scripts/install.sh --agent claude-user
bash scripts/install.sh --agent claude-project --target-dir /path/to/some/repo
```

Makefile wrappers: `make install`, `make install-<skill>` (per skill), `make install-claude`,
`make install-claude-<skill>`.

## Requirements

- Bash with `set -euo pipefail`
- Write access to the resolved destination root(s) (`~/.cursor/skills/`, `~/.claude/skills/`, or a
  project's `.claude/skills/`)
- Each skill source must contain `SKILL.md` or the script exits with an error

## Quality gate

Staged changes to `scripts/*.sh` are linted by the pre-commit hook (`make setup-hooks`) and by
`make lint` (shellcheck locally or via Docker).

See [docs/REPOSITORY.md](../docs/REPOSITORY.md) for full repo documentation.
