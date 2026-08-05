# Install script

Copies skill directories from this repository into the Cursor skills install path.

## What it does

`scripts/install.sh`:

1. Resolves the repo root (parent of `scripts/`).
2. For each skill name passed as an argument — or for every directory containing `SKILL.md` when no
   arguments are given — copies the full skill folder to `~/.cursor/skills/<skill-name>/`.
3. Replaces any existing install at the destination (`rm -rf` then `cp -r`).
4. Prints `Restart Cursor to load the skill(s).`

## Usage

```bash
# From repo root — all skills
bash scripts/install.sh
make install

# One skill
bash scripts/install.sh pr-review
bash scripts/install.sh k8s-overprovisioning-datadog
bash scripts/install.sh incident-rca
```

Makefile wrappers: `make install`, `make install-pr-review`, `make install-k8s-overprovisioning`,
`make install-incident-rca`.

## Requirements

- Bash with `set -euo pipefail`
- Write access to `~/.cursor/skills/`
- Each skill source must contain `SKILL.md` or the script exits with an error

## Quality gate

Staged changes to `scripts/*.sh` are linted by the pre-commit hook (`make setup-hooks`) and by
`make lint` (shellcheck locally or via Docker).

See [docs/REPOSITORY.md](../docs/REPOSITORY.md) for full repo documentation.
