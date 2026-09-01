# software-builder

[![Lint](https://github.com/luckyrjain/software-builder/actions/workflows/lint.yml/badge.svg)](https://github.com/luckyrjain/software-builder/actions/workflows/lint.yml)
<!-- skills-count:start -->
![Skills](https://img.shields.io/badge/skills-38-blue)
<!-- skills-count:end -->

Portable, evidence-driven agent skills for software delivery: code review, incident response,
architecture discovery, Kubernetes optimization, migrations, release readiness, and autonomous
implementation with independent review.

`software-builder` is a **skills and workflow library**, not another agent runtime or SDK. It gives
Cursor, Claude Code, ChatGPT/Codex, Kiro, GitHub Copilot, and other repository-capable agents shared
instructions, role boundaries, evidence rules, and reusable outputs while leaving model choice and
execution to the host agent.

**Start here:** [Prerequisites](#prerequisites) · [3-minute quickstart](#3-minute-quickstart) ·
[How it works](#how-it-works) · [Agent support](#install-for-your-specific-coding-agent) · [Skills](#skills) ·
[Integrations](#mcp-and-external-integrations) · [Documentation](#documentation)

## Why use it?

- **Portable workflows** — use the same skill definitions across several coding-agent harnesses.
- **Independent review** — multi-agent workflows isolate builders, reviewers, and orchestrators so
  implementers do not grade their own work.
- **Evidence over claims** — repository state, exact-commit CI, diffs, logs, and source data outrank
  agent summaries.
- **Composable skills** — higher-level workflows reuse focused skills instead of duplicating their
  logic.
- **Progressive loading** — agents begin with a compact `SKILL.md` and load detailed workflow or
  reference files only when needed.

## Prerequisites

### To use the skills

- **Git** to clone this repository and access target repositories.
- **Bash** and **Python 3** to run `scripts/install.sh` (macOS, Linux, or WSL) — the installer shells
  out to `python3` for every install path, including the quickstart below.
- A supported **repository-capable coding agent**: Cursor, Claude Code, ChatGPT/Codex, Kiro, GitHub
  Copilot, or a generic agent that can read a `SKILL.md` file.
- Read access to the repositories being analyzed. Workflows that implement changes also need branch
  write access; merge remains opt-in unless repository policy explicitly authorizes it.
- Only the external services required by the skill you plan to run. There is no repository-wide MCP
  prerequisite; several skills work with local files and Git alone.

### For multi-agent implementation workflows

For strong Builder/Reviewer isolation, the host should provide at least one of:

- native subagents or background agents;
- separate tasks or fresh sessions; or
- isolated Git worktrees.

If none is available, `loop-task-implementer` can use weaker, sequential role simulation. It must
perform explicit context resets and re-derive facts from the repository for each role. If it cannot,
the run must not claim role isolation and its findings remain `NEEDS_EVIDENCE`. To take work all the
way to merge readiness, the host also needs repository write access and visibility into CI for the
exact head commit. See the [platform adapters](loop-task-implementer/reference/platform-adapters.md)
and [host-capability requirements](loop-task-implementer/reference/mcp-capabilities.md).

### Only for contributing to this repository

- `make`
- Python 3 with `pip`
- `ripgrep` with PCRE2 support
- `shellcheck`, or Docker as its fallback

Run `make setup` once to install the Python development dependencies and configure the pre-commit
hook. The exact CI environment uses Python 3.12; see [`.github/workflows/lint.yml`](.github/workflows/lint.yml).

## 3-minute quickstart

Install one MCP-free multi-agent workflow first:

```bash
git clone https://github.com/luckyrjain/software-builder.git
cd software-builder
bash scripts/install.sh --agent cursor loop-task-implementer
test -f ~/.cursor/skills/loop-task-implementer/SKILL.md
```

Restart Cursor, open a small repository with a well-scoped task, and ask:

```text
Use loop-task-implementer to implement issue <issue-number>, run independent review,
fix accepted findings, and open a PR. Do not merge.
```

Replace `<issue-number>` with a real, well-scoped task in the repository.

Expected first-run behavior: the agent reports repository-policy discovery, separates Builder and
Reviewer contexts, runs two review lenses, verifies authoritative checks, and stops at a PR or an
explicit human-action gate rather than merging without authorization.

Using another host?

```bash
# Claude Code — user-wide
bash scripts/install.sh --agent claude-user loop-task-implementer
test -f ~/.claude/skills/loop-task-implementer/SKILL.md

# Claude Code — one project only
bash scripts/install.sh --agent claude-project --target-dir /path/to/project loop-task-implementer

# Cursor — one project only (omit --target-dir for global ~/.cursor/skills)
bash scripts/install.sh --agent cursor --target-dir /path/to/project loop-task-implementer

# ChatGPT / Codex — common manual location; adjust if your runtime uses another path
mkdir -p ~/.agents/skills
cp -R loop-task-implementer ~/.agents/skills/loop-task-implementer
test -f ~/.agents/skills/loop-task-implementer/SKILL.md
```

Kiro needs no copy step when this repository is open; its discovery files live under
`.kiro/steering/`. For every installation option, see
[Install for your specific coding agent](#install-for-your-specific-coding-agent).

## How it works

1. **Discover** — the host finds a skill through its installed directory, Cursor rule, Kiro steering
   file, or a direct `SKILL.md` reference.
2. **Route** — the skill decides which workflow phase or related skill applies to the request.
3. **Execute with boundaries** — read-only analysis stays read-only; multi-agent workflows isolate
   Orchestrator, Builder, and Reviewer roles and pass only a neutral evidence package between them.
4. **Verify** — outputs cite repository data, external evidence, and exact-commit checks. Missing
   optional capabilities are reported as degraded mode; an unmet required or provider `any_of` path is
   blocked instead of silently guessed.
5. **Stop safely** — posting, writing, and merging follow the skill's explicit approval and
   authorization gates.

Each skill directory has three entry points:

| File | Audience | Purpose |
|------|----------|---------|
| `README.md` | Humans | What the skill does, when to use it, and example outputs |
| `SETUP.md` | Humans | Skill-specific installation, integrations, smoke test, and troubleshooting |
| `SKILL.md` | Agent | Compact runtime instructions and links to on-demand workflow/reference files |

## Install for your specific coding agent

| Host | Install or discovery | Multi-agent isolation | Notes |
|------|----------------------|-----------------------|-------|
| **Cursor** | `bash scripts/install.sh --agent cursor` (global) or `--target-dir <repo>` for `<repo>/.cursor/skills/`; in-repo `.cursor/rules/` also works | Background agents, separate chats, or worktrees | Restart Cursor after installation. |
| **Claude Code** | `--agent claude-user`, `--agent claude-project`, or `make install-claude` | Subagents, fresh sessions, or worktrees | Start a new session after installation. |
| **ChatGPT / Codex** | Copy selected skills to the runtime's supported directory, commonly `~/.agents/skills/` | Separate tasks or fresh agent sessions; worktrees where available | Use repository connectors for remote state and local Git for implementation when available. |
| **GitHub Copilot** | Copy skills to `.github/skills/` (project) or `~/.copilot/skills/` (personal); `.claude/skills/` and `~/.agents/skills/` also work per GitHub's docs | Separate tasks or fresh agent sessions | Discovery is documented, not yet independently verified — see [docs/agent-compatibility.md](docs/agent-compatibility.md). |
| **Kiro** | Open this repository and use `.kiro/steering/<skill>.md` | Kiro specs plus separate role contexts | No installer copy is required for in-repo use. |
| **Generic repository agent** | Point the agent directly at `<skill>/SKILL.md` | Host-dependent; otherwise use the documented sequential fallback | State the active role and provide only that role's input package. |

The canonical cross-harness guidance, including the neutral handoff envelope, is in
[loop-task-implementer/reference/platform-adapters.md](loop-task-implementer/reference/platform-adapters.md).

### Verification status
<!-- agent-compatibility:start -->

Canonical, evidence-gated host compatibility (see [docs/agent-compatibility.md](docs/agent-compatibility.md) for full detail):

| Host | Verification | Maintainer support |
|------|--------------|---------------------|
| claude | UNVERIFIED | BEST_EFFORT |
| cursor | UNVERIFIED | BEST_EFFORT |
| github-copilot | UNVERIFIED | BEST_EFFORT |
| kiro | UNVERIFIED | BEST_EFFORT |
<!-- agent-compatibility:end -->

## Install

Install all skills or select only the workflow you need:

```bash
make install                         # all skills; Cursor + Claude Code by default
make install-pr-review               # one skill and any Makefile-declared dependencies
bash scripts/install.sh pr-review    # one skill; direct installer form
bash scripts/install.sh --agent cursor
bash scripts/install.sh --agent claude-user
```

The default installer discovers every root-level `*/SKILL.md`, copies full skill directories to both
`~/.cursor/skills/` and `~/.claude/skills/`, and replaces an existing installation of the same skill.
Review [scripts/README.md](scripts/README.md) before using a custom target or automating installation.

> Make target names usually follow `make install-<skill>`. The exception is
> `k8s-overprovisioning-datadog`, whose target is `make install-k8s-overprovisioning`.

## Skills

Choose a skill by the outcome you need. Each skill has one primary category even when it composes or
routes to skills in another category.

### Build, review, and release

| Skill | Invoke | What it does | Docs |
|-------|--------|--------------|------|
| [loop-task-implementer](loop-task-implementer/) | “Implement issue 42 and open a PR” | Isolated Builder → two-lens Reviewer → adjudication → remediation → PR loop | [README](loop-task-implementer/README.md) · [SETUP](loop-task-implementer/SETUP.md) |
| [backlog-runner](backlog-runner/) | Scheduled trigger | Pulls tracker tasks and runs `loop-task-implementer` in dependency order without merging | [README](backlog-runner/README.md) · [SETUP](backlog-runner/SETUP.md) |
| [pr-review](pr-review/) | `/pr-review` or “review this MR/PR” | GitHub/GHES PR or GitLab MR review with evidence-backed findings and optional inline posts | [README](pr-review/README.md) · [SETUP](pr-review/SETUP.md) |
| [pr-gatekeeper](pr-gatekeeper/) | Push webhook | Runs `pr-review` on every push to an open MR and applies unattended posting policy | [README](pr-gatekeeper/README.md) · [SETUP](pr-gatekeeper/SETUP.md) |
| [release-readiness-checker](release-readiness-checker/) | “Is this release ready?” | Aggregates review, Kubernetes, and incident signals into a release go/no-go report | [README](release-readiness-checker/README.md) · [SETUP](release-readiness-checker/SETUP.md) |
| [production-readiness-review](production-readiness-review/) | “Is PR #123 production ready?” | Read-only rollup of trusted CI, code-review, build-provenance, SCM-policy, change-impact, deployment-risk, and specialist-review evidence into one fail-closed verdict for one exact PR/MR/release candidate | [README](production-readiness-review/README.md) · [SETUP](production-readiness-review/SETUP.md) |
| [prd-architect](prd-architect/) | “Write a PRD for …” / “Should we build this?” | Validates ideas and turns specs into implementation-ready PRDs with Build Readiness gating | [README](prd-architect/README.md) · [SETUP](prd-architect/SETUP.md) |
| [change-impact-analyzer](change-impact-analyzer/) | “What services/contracts are affected by this change?” | Bounded, evidence-backed impact analysis for designs and exact PR/MR heads | [README](change-impact-analyzer/README.md) · [SETUP](change-impact-analyzer/SETUP.md) |
| [implementation-planner](implementation-planner/) | “Plan the implementation for `<task/PRD>`” | Deterministic, dependency-ordered implementation plan with source traceability, feeding `loop-task-implementer` | [README](implementation-planner/README.md) · [SETUP](implementation-planner/SETUP.md) |
| [test-writer](test-writer/) | “Write tests for MR !123” — level unspecified | Router: classifies the request and dispatches to exactly one of the five skills below | [README](test-writer/README.md) · [SETUP](test-writer/SETUP.md) |
| [unit-test-creator](unit-test-creator/) | “Write unit tests for `<file/module>`” | Isolated, fast, every external dependency mocked; detects the repo's test framework and never patches production code to force green | [README](unit-test-creator/README.md) · [SETUP](unit-test-creator/SETUP.md) |
| [integration-test-creator](integration-test-creator/) | “Write an integration test against the real DB” | Tests the real seam to one real adjacent dependency (testcontainers/docker-compose) — never mocks it | [README](integration-test-creator/README.md) · [SETUP](integration-test-creator/SETUP.md) |
| [contract-test-creator](contract-test-creator/) | “Write a Pact contract test for `<consumer>`” | Consumer-driven contract tests (Pact-style); every interaction shape traces to real observed usage | [README](contract-test-creator/README.md) · [SETUP](contract-test-creator/SETUP.md) |
| [e2e-test-creator](e2e-test-creator/) | “Write an e2e test for the checkout journey” | Full user-journey browser tests (Playwright/Cypress/Selenium); asserts on user-visible outcomes only | [README](e2e-test-creator/README.md) · [SETUP](e2e-test-creator/SETUP.md) |
| [api-test-creator](api-test-creator/) | “Write a Postman/API test for `POST /api/orders`” | Black-box request/response assertions (Postman/Newman) against a real running API — no browser | [README](api-test-creator/README.md) · [SETUP](api-test-creator/SETUP.md) |

### Incidents and reliability

| Skill | Invoke | What it does | Docs |
|-------|--------|--------------|------|
| [incident-rca](incident-rca/) | “RCA for … between …” | Multi-source post-incident investigation across observability and delivery systems | [README](incident-rca/README.md) · [SETUP](incident-rca/SETUP.md) |
| [incident-triage-agent](incident-triage-agent/) | Paging webhook | Produces page-fire triage and incident-resolved postmortem drafts | [README](incident-triage-agent/README.md) · [SETUP](incident-triage-agent/SETUP.md) |

### Architecture, ownership, and onboarding

| Skill | Invoke | What it does | Docs |
|-------|--------|--------------|------|
| [domain-comprehension](domain-comprehension/) | “Map the domain …” | Evidence-backed bounded contexts, ownership, dependencies, and business flows | [README](domain-comprehension/README.md) · [SETUP](domain-comprehension/SETUP.md) |
| [squad-map](squad-map/) | “Who owns …?” | Maps repositories and services to squads using GitLab, Datadog, and CODEOWNERS evidence | [README](squad-map/README.md) · [SETUP](squad-map/SETUP.md) |
| [who-owns-x-bot](who-owns-x-bot/) | `/who-owns <name>` | Returns one Slack-ready ownership answer by delegating to `squad-map` | [README](who-owns-x-bot/README.md) · [SETUP](who-owns-x-bot/SETUP.md) |
| [new-hire-guide](new-hire-guide/) | “Onboard `<name>` to `<squad>`” | Builds a squad-scoped onboarding tour from ownership and domain evidence | [README](new-hire-guide/README.md) · [SETUP](new-hire-guide/SETUP.md) |

### Architecture and specialized design review

Fills the gap between `prd-architect` and implementation: architecture decisions, implementation-oriented
design, and dedicated single-domain reviews.

| Skill | Invoke | What it does | Docs |
|-------|--------|--------------|------|
| [architecture-review](architecture-review/) | “Architecture review for `<feature>`” | Architecture decision, risks, scale limits, failure modes, security, operability, alternatives | [README](architecture-review/README.md) · [SETUP](architecture-review/SETUP.md) |
| [system-design](system-design/) | “Design the implementation for `<feature>`” | Components, APIs, events, data model, state machines, consistency, retries, capacity, rollout | [README](system-design/README.md) · [SETUP](system-design/SETUP.md) |
| [api-design-review](api-design-review/) | “Review the API design for `<feature>`” | REST/GraphQL/gRPC/async-event review: compatibility, pagination, idempotency, versioning, authZ | [README](api-design-review/README.md) · [SETUP](api-design-review/SETUP.md) |
| [database-review](database-review/) | “Review this schema/migration” | Schema, indexing, locking, transactions, migrations, query plans, replication, partitioning | [README](database-review/README.md) · [SETUP](database-review/SETUP.md) |
| [security-review](security-review/) | “Security review of `<target>`” | Dedicated authN/authZ, secrets, injection, SSRF, tenant isolation, crypto, dependency exposure | [README](security-review/README.md) · [SETUP](security-review/SETUP.md) |
| [performance-review](performance-review/) | “Performance review of `<target>`” | Algorithmic complexity, DB behavior, N+1, cache, memory, concurrency, connection pools, fanout | [README](performance-review/README.md) · [SETUP](performance-review/SETUP.md) |
| [capacity-planner](capacity-planner/) | “Forecast capacity for `<service>`” | Turns historical demand into RPS/CPU/memory/DB/queue/storage/replica requirements | [README](capacity-planner/README.md) · [SETUP](capacity-planner/SETUP.md) |
| [observability-review](observability-review/) | “Observability review for `<service>`” | Evaluates metrics, logs, tracing, dashboards, alerts, SLOs, correlation IDs for coverage gaps | [README](observability-review/README.md) · [SETUP](observability-review/SETUP.md) |
| [deployment-risk-review](deployment-risk-review/) | “Deployment risk review for `<change>`” | Blast radius, migration risk, rollback complexity, dependency risk, traffic risk, confidence | [README](deployment-risk-review/README.md) · [SETUP](deployment-risk-review/SETUP.md) |
| [resilience-review](resilience-review/) | “Resilience review of `<design/implementation>`” | Timeout budgets, retries, circuit breaking, load shedding, backpressure, queues, idempotency, partial failures, recovery | [README](resilience-review/README.md) · [SETUP](resilience-review/SETUP.md) |
| [dependency-upgrade-review](dependency-upgrade-review/) | “Review upgrading `<dependency>` to `<version>`” | Breaking changes, CVEs, API differences, transitive dependencies, rollout risk | [README](dependency-upgrade-review/README.md) · [SETUP](dependency-upgrade-review/SETUP.md) |
| [tech-debt-assessor](tech-debt-assessor/) | “Rank this tech debt backlog” | Ranks debt by business impact × engineering drag × operational risk ÷ effort | [README](tech-debt-assessor/README.md) · [SETUP](tech-debt-assessor/SETUP.md) |

### Infrastructure and cost

| Skill | Invoke | What it does | Docs |
|-------|--------|--------------|------|
| [k8s-overprovisioning-datadog](k8s-overprovisioning-datadog/) | “Is `<service>` overprovisioned?” | Kubernetes MCP-first analysis with per-capability Datadog fallback for CPU, memory, replicas, waste, and optional cost | [README](k8s-overprovisioning-datadog/README.md) · [SETUP](k8s-overprovisioning-datadog/SETUP.md) |
| [cost-optimization-sprint-planner](cost-optimization-sprint-planner/) | “Plan a cost-optimization sprint” | Sweeps deployments for waste and ranks monthly savings by squad | [README](cost-optimization-sprint-planner/README.md) · [SETUP](cost-optimization-sprint-planner/SETUP.md) |

### Migrations and program reporting

| Skill | Invoke | What it does | Docs |
|-------|--------|--------------|------|
| [mysql-to-postgres-sql](mysql-to-postgres-sql/) | “Rewrite MySQL SQL for PostgreSQL” | Scans and rewrites native SQL and JDBC usage for PostgreSQL | [README](mysql-to-postgres-sql/README.md) · [SETUP](mysql-to-postgres-sql/SETUP.md) |
| [migration-program-manager](migration-program-manager/) | “Migration status across all repos” | Rolls up `MIGRATION_STATUS.yaml` files by squad, risk, blockers, and staleness | [README](migration-program-manager/README.md) · [SETUP](migration-program-manager/SETUP.md) |
| [weekly-squad-digest](weekly-squad-digest/) | Scheduled trigger | Combines migration and cost rollups into one squad-grouped digest | [README](weekly-squad-digest/README.md) · [SETUP](weekly-squad-digest/SETUP.md) |

## MCP and external integrations

MCP is **skill-specific**, not a prerequisite for installing or browsing the repository.

| Workflow | Minimum external capability |
|----------|-----------------------------|
| `loop-task-implementer` | No MCP; uses the host's repository/Git access and CI visibility |
| `mysql-to-postgres-sql` | No MCP |
| `test-writer` | No MCP; router only, dispatches to the skills below |
| `unit-test-creator`, `integration-test-creator`, `contract-test-creator`, `e2e-test-creator`, `api-test-creator` | No MCP; use the host's repository read/write access and (optionally) its test-runner/browser/API access |
| `domain-comprehension`, `squad-map` | No MCP for repository/CODEOWNERS mode; GitLab and Datadog improve coverage |
| `migration-program-manager`, `weekly-squad-digest` | No MCP; aggregate files produced by upstream workflows |
| `pr-review` | One complete GitHub/GHES or GitLab metadata+diff read path; provider write access only for posting |
| `incident-rca` | At least one observability source: Datadog or KubeSense |
| `k8s-overprovisioning-datadog` | At least one sufficient evidence source: read-only Kubernetes MCP or Datadog |
| `cost-optimization-sprint-planner` | Datadog for its namespace pre-filter; then inherits the Kubernetes skill's per-deployment routing |
| `backlog-runner` | Jira or GitHub Issues access |
| `prd-architect`, `architecture-review`, `system-design`, `api-design-review`, `database-review`, `security-review`, `performance-review`, `capacity-planner`, `observability-review`, `deployment-risk-review`, `dependency-upgrade-review`, `tech-debt-assessor`, `change-impact-analyzer` | No MCP; analysis and report-drafting skills that read supplied content (and, at most, read-only repository access) |
| Composed skills | Inherit the capabilities of the skills they call |

Read the selected skill's `SETUP.md` before its first real run. The complete required/optional matrix
is in [docs/REPOSITORY.md § MCP dependencies](docs/REPOSITORY.md#mcp-dependencies-summary).

## Development and verification

```bash
make setup
make lint
```

`make lint` validates skill structure, workflow metadata, internal Markdown links, scripts, schemas,
fixtures, and test suites, then runs ShellCheck on `scripts/*.sh`. GitHub Actions runs the same command
for pushes and pull requests targeting `main` or `master`.

For one skill, use its documented lint target. Most follow `make lint-<skill>`; the Kubernetes skill
uses `make lint-k8s-skill`. See [Makefile targets](docs/REPOSITORY.md#makefile-targets) for the exact list.

## Documentation

| Document | What it covers |
|----------|----------------|
| [CONTEXT.md](CONTEXT.md) | Domain glossary — platform vocabulary (skills, hosts, composition, evidence doctrine) |
| [CONTEXT-MAP.md](CONTEXT-MAP.md) | How platform and target-system contexts relate |
| [docs/README.md](docs/README.md) | Full documentation index, skill file maps, routing, and design specs |
| [docs/REPOSITORY.md](docs/REPOSITORY.md) | Repository layout, installer, Make targets, CI, contribution process, and MCP matrix |
| [docs/skill-framework/README.md](docs/skill-framework/README.md) | Shared conventions for confidence, escalation, routing, phases, and outputs |
| [scripts/README.md](scripts/README.md) | Installer behavior, arguments, destinations, and requirements |
| [CHANGELOG.md](CHANGELOG.md) | Per-skill change history |

## Contributing

1. Edit the canonical skill in this repository, not an installed copy.
2. Keep `SKILL.md` compact; put detailed procedures under `workflow/` or `reference/`.
3. Run `make lint` and the skill's smoke test.
4. Record user-visible changes in `CHANGELOG.md`.
5. Open a pull request with the evidence used to verify the change.

Full guide, including security reporting and code ownership: [CONTRIBUTING.md](CONTRIBUTING.md) ·
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) · [SECURITY.md](SECURITY.md). More detail:
[docs/REPOSITORY.md § Contributing](docs/REPOSITORY.md#contributing).

## License

MIT — see [LICENSE](LICENSE).
