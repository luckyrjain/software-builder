# software-builder

[![Lint](https://github.com/luckyrjain/software-builder/actions/workflows/lint.yml/badge.svg)](https://github.com/luckyrjain/software-builder/actions/workflows/lint.yml)
![Skills](https://img.shields.io/badge/skills-16-blue)

Shared agent skills for the team — [Cursor Agent Skills](https://cursor.com/docs/agent/skills) natively,
plus cross-agent support for Claude Code, Kiro, and ChatGPT/Codex. See
[Install for your specific coding agent](#install-for-your-specific-coding-agent) below.

**Contents:** [Documentation](#documentation) · [Skills](#skills) · [Install](#install) ·
[Develop](#develop) · [CI](#ci) · [Configure MCP](#configure-mcp)

## Documentation

| Document | What it covers |
|----------|----------------|
| [docs/README.md](docs/README.md) | Full documentation index — every skill's file map, cross-skill routing, design specs |
| [docs/REPOSITORY.md](docs/REPOSITORY.md) | Repo layout, `Makefile` targets, `scripts/install.sh`, lint targets, MCP dependencies, git hooks, CI/CD |
| [docs/skill-framework/README.md](docs/skill-framework/README.md) | Shared normative conventions every skill follows (confidence bands, escalation, routing, phase glossary, …) |
| [CHANGELOG.md](CHANGELOG.md) | Per-skill change history |
| [scripts/README.md](scripts/README.md) | What `scripts/install.sh` does |

Each skill has a human **`README.md`** (what it does, usage examples, what you get) separate from
**`SKILL.md`** (agent instructions) and **`SETUP.md`** (install steps for that skill specifically) — this
file only orients; the per-skill `README.md` linked below is the source of truth for what each skill does.

## Skills

| Skill | Invoke | What it does | Docs |
|-------|--------|--------------|------|
| [pr-review](pr-review/) | `/pr-review` or "review this MR/PR …" | GitLab MR review: diff + Jira AC, severity findings, optional inline posts | [README](pr-review/README.md) · [SETUP](pr-review/SETUP.md) |
| [pr-gatekeeper](pr-gatekeeper/) | Push webhook (not human chat) | Auto-runs pr-review on every push to an open MR; posts inline when pr-review's own rules allow unattended posting | [README](pr-gatekeeper/README.md) · [SETUP](pr-gatekeeper/SETUP.md) |
| [incident-rca](incident-rca/) | "RCA for … between …" | Multi-source post-incident RCA (Datadog, KubeSense, GitLab, Jenkins, Jira) | [README](incident-rca/README.md) · [SETUP](incident-rca/SETUP.md) |
| [incident-triage-agent](incident-triage-agent/) | Paging webhook (not human chat) | Page-fire triage doc + incident-resolved postmortem draft, composing incident-rca + squad-map | [README](incident-triage-agent/README.md) · [SETUP](incident-triage-agent/SETUP.md) |
| [k8s-overprovisioning-datadog](k8s-overprovisioning-datadog/) | "Is `<service>` overprovisioned?" | K8s DORA report: CPU/memory/replica verdicts, waste, cost via Datadog | [README](k8s-overprovisioning-datadog/README.md) · [SETUP](k8s-overprovisioning-datadog/SETUP.md) |
| [domain-comprehension](domain-comprehension/) | "map the domain …", "bounded contexts for …" | Evidence-backed domain map: bounded contexts, data ownership, dependency graphs, business flows, exec summary | [README](domain-comprehension/README.md) · [SETUP](domain-comprehension/SETUP.md) |
| [squad-map](squad-map/) | "map squads …", "who owns …" | Repo-to-squad mapping: GitLab group hierarchy + Datadog team tags → `SQUAD_MAP.md` | [README](squad-map/README.md) · [SETUP](squad-map/SETUP.md) |
| [who-owns-x-bot](who-owns-x-bot/) | `/who-owns <name>` (Slack slash command; not ambient chat) | Single-shot "who owns X" Slack reply — thin wrapper delegating to squad-map | [README](who-owns-x-bot/README.md) · [SETUP](who-owns-x-bot/SETUP.md) |
| [new-hire-guide](new-hire-guide/) | "onboard `<name>`, joining `<squad>`" | Personalized onboarding tour: resolves the new hire's squad's repos via squad-map, runs domain-comprehension unscoped, curates `ONBOARDING_TOUR.md` down to those repos | [README](new-hire-guide/README.md) · [SETUP](new-hire-guide/SETUP.md) |
| [release-readiness-checker](release-readiness-checker/) | "is this release ready to ship?" with a `release_manifest` | Release go/no-go report: pr-review (MRs since last release, never posts) + k8s-overprovisioning-datadog (per-service verdict) + incident-rca (per-service incident signal, Phase 1 only) | [README](release-readiness-checker/README.md) · [SETUP](release-readiness-checker/SETUP.md) |
| [migration-program-manager](migration-program-manager/) | "migration status across all repos" with a `program_manifest` | Org-wide rollup of `MIGRATION_STATUS.yaml` joined to `SQUAD_MAP.md`, ranked by staleness/blocked count per squad — pure read-only aggregator | [README](migration-program-manager/README.md) · [SETUP](migration-program-manager/SETUP.md) |
| [cost-optimization-sprint-planner](cost-optimization-sprint-planner/) | "where's the money", cost optimization sprint, with a `sweep_scope` | Org-wide cost/waste sweep: loops k8s-overprovisioning-datadog once per deployment, joins to `SQUAD_MAP.md`, ranked by `monthly_savings_total` per squad | [README](cost-optimization-sprint-planner/README.md) · [SETUP](cost-optimization-sprint-planner/SETUP.md) |
| [mysql-to-postgres-sql](mysql-to-postgres-sql/) | "MySQL scrub …", "jdbc:postgresql …", "TIMESTAMPDIFF …" | Native SQL + JDBC rewrite for MySQL→PostgreSQL; scan gate, collection P0/P1 | [README](mysql-to-postgres-sql/README.md) · [SETUP](mysql-to-postgres-sql/SETUP.md) |
| [loop-task-implementer](loop-task-implementer/) | "implement issue 42 …", "work through these tasks …" | Autonomous multi-task loop: isolated Builder → two-lens independent Reviewer → adjudicated remediation → PR. Platform-neutral, no Datadog/GitLab/Jira MCP required | [README](loop-task-implementer/README.md) · [SETUP](loop-task-implementer/SETUP.md) |
| [backlog-runner](backlog-runner/) | Scheduled trigger (not human chat) | Pulls N tickets from a tracker query, runs loop-task-implementer per ticket overnight in dependency order, never merges | [README](backlog-runner/README.md) · [SETUP](backlog-runner/SETUP.md) |
| [weekly-squad-digest](weekly-squad-digest/) | Scheduled trigger (not human chat) | Combines migration-program-manager's and cost-optimization-sprint-planner's own rollup JSON outputs into one squad-grouped digest — never re-runs either aggregator | [README](weekly-squad-digest/README.md) · [SETUP](weekly-squad-digest/SETUP.md) |

## Install

```bash
git clone https://github.com/luckyrjain/software-builder.git
cd software-builder
make install                # every skill
make install-pr-review      # one skill (make install-<skill> for any name in the table above)
```

`scripts/install.sh` copies skill directories to **both** `~/.cursor/skills/` and `~/.claude/skills/` by
default. **Restart Cursor** and start a new Claude Code session after installing. The full per-skill
`make install-<skill>` / `bash scripts/install.sh <skill>` command reference, and what each target's
dependency chain also installs, is in [docs/REPOSITORY.md](docs/REPOSITORY.md#install).

`install-incident-rca` also installs the external **`kubesense-mcp`** skill dependency
(`make install-incident-rca-deps`). See [incident-rca/dependencies.md](incident-rca/dependencies.md).

With no arguments, `install.sh` discovers every `*/SKILL.md` under the repo root and installs all of
them — so a newly-added skill needs no script changes to be picked up by `make install`.

### Install for your specific coding agent

By default, `make install` / `bash scripts/install.sh` copies skill directories to **both**
`~/.cursor/skills/` and `~/.claude/skills/`. **Restart Cursor** and start a new Claude Code session
after installing. For a different agent, or to install to only one:

| Agent | Command | Notes |
|-------|---------|-------|
| **Cursor** | `bash scripts/install.sh --agent cursor` (or `make install-<skill>` then ignore the Claude Code copy) | Installs to `~/.cursor/skills/<skill>/`. Skills ship in stable Cursor builds as of early 2026 — update Cursor if `/pr-review` etc. don't appear after restart. |
| **Claude Code** | `bash scripts/install.sh --agent claude-user` (all skills, `~/.claude/skills/`) or `make install-claude`; per-skill: `make install-claude-<skill>` | No restart needed — a new Claude Code session picks it up. `--agent claude-project --target-dir <repo>` installs into one project's `.claude/skills/` only, instead of user-wide. Full MCP-path mapping: [claude-code-setup.md](docs/skill-framework/shared/claude-code-setup.md). |
| **Kiro** | No install step — keep this repo cloned and open it (or symlink `.kiro/steering/` into your project). Ask Kiro to "use the `<skill>` steering workflow"; it reads `.kiro/steering/<skill>.md`, which points at `<skill>/SKILL.md` in this tree. | Steering files exist for every skill in `.kiro/steering/`. |
| **ChatGPT / Codex** | `mkdir -p ~/.agents/skills && cp -R <skill> ~/.agents/skills/<skill>` (repeat per skill, or loop over `*/SKILL.md`) | Not wired into `scripts/install.sh` — Codex's skills directory convention isn't uniform across setups, so copy manually. Prefer separate Codex tasks or fresh agent sessions for role isolation where a skill needs it (loop-task-implementer). |
| **Any other repo-capable agent (generic fallback)** | Point the agent at `<skill>/SKILL.md` directly, state the active role/phase if the skill has one, and don't hand it other roles' private context. | No install needed if the agent can just read files from a working copy of this repo. |

**Working directly in this repo** (not via an installed copy)? Every skill also has an in-repo
discovery file so Cursor/Kiro can find it without an install step:

```
.cursor/rules/<skill>.mdc       # Cursor rule — points at <skill>/SKILL.md
.kiro/steering/<skill>.md       # Kiro steering — same
```

See each skill's `SETUP.md` § "Kiro / in-repo discovery" (or, for loop-task-implementer, the fuller
[reference/platform-adapters.md](loop-task-implementer/reference/platform-adapters.md), which is the
canonical cross-agent reference this table summarizes).

## Develop

One-time setup — installs Python dev deps (`requirements.txt`: pytest, PyYAML) and the shellcheck pre-commit hook:

```bash
make setup
```

```bash
make lint               # every skill's lint target + lint-framework + shellcheck on scripts/*.sh
make lint-pr-review      # one skill's lint target (make lint-<skill> for any name in the Skills table above)
```

What each `lint-<skill>` target actually checks (line limits, required frontmatter, schema validators,
pytest suites, `disable-model-invocation` policy) is in
[docs/REPOSITORY.md § Makefile targets](docs/REPOSITORY.md#makefile-targets).

## CI

GitHub Actions runs `make lint` on every push and pull request against `main`
(see [`.github/workflows/lint.yml`](.github/workflows/lint.yml)). No self-hosted runner needed — it runs on
`ubuntu-latest` and installs `python3`, `pytest`, `shellcheck`, and `ripgrep` itself. More detail (branch
protection, running lint locally before pushing) is in
[docs/REPOSITORY.md § CI/CD](docs/REPOSITORY.md#cicd).

## Configure MCP

Most skills need at least one MCP server (GitLab, Jira, Datadog, KubeSense) configured before their first
real run; a few (mysql-to-postgres-sql, loop-task-implementer, migration-program-manager,
weekly-squad-digest) need none at all. The full per-skill required/optional MCP table is in
[docs/REPOSITORY.md § MCP dependencies](docs/REPOSITORY.md#mcp-dependencies-summary) — each skill's own
`SETUP.md` (linked in the Skills table above) has the actual configuration steps.
