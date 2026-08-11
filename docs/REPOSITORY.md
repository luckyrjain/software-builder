# Repository guide

What the **software-builder** repo contains, how to install skills, and how quality checks work.

## Layout

```
software-builder/
├── README.md                 # Top-level install + usage (start here)
├── CHANGELOG.md              # Per-skill change history
├── Makefile                  # install + lint targets
├── skills.yaml               # Platform skill registry (install deps, hosts, lint metadata)
├── generated/catalogue/      # Generated install-dependency graph (Mermaid)
├── docs/
│   ├── README.md             # Documentation index (this tree)
│   ├── REPOSITORY.md         # This file
│   └── skill-framework/      # Shared normative conventions + reference library
├── scripts/
│   └── install.sh            # Copies skill dirs → ~/.cursor/skills/ + ~/.claude/skills/ (default)
├── .githooks/
│   └── pre-commit            # shellcheck on staged scripts/*.sh
├── .cursor/rules/             # Per-skill Cursor discovery rules (in-repo, no install needed)
├── .kiro/steering/            # Per-skill Kiro discovery files (in-repo, no install needed)
├── pr-review/                 # GitLab MR review skill
├── pr-gatekeeper/             # Push-webhook-triggered pr-review auto-run wrapper
├── incident-rca/              # Post-incident RCA skill
├── incident-triage-agent/     # Paging-webhook-triggered incident-rca + squad-map composition
├── k8s-overprovisioning-datadog/  # K8s rightsizing / DORA skill
├── domain-comprehension/      # Evidence-backed domain/architecture mapping skill
├── squad-map/                 # Repo-to-squad ownership mapping skill
├── who-owns-x-bot/            # Single-shot Slack-bot-facing "who owns X" wrapper around squad-map
├── new-hire-guide/            # Personalized onboarding tour wrapper around domain-comprehension + squad-map
├── release-readiness-checker/ # Release go/no-go report wrapper around pr-review + k8s-overprovisioning-datadog + incident-rca
├── migration-program-manager/ # Org-wide MIGRATION_STATUS.yaml rollup, read-only aggregator (has real Python scripts)
├── cost-optimization-sprint-planner/ # Org-wide cost/waste sweep wrapper around k8s-overprovisioning-datadog
├── mysql-to-postgres-sql/     # MySQL → PostgreSQL native SQL migration skill
├── loop-task-implementer/     # Autonomous multi-task implement/review/PR loop skill
├── backlog-runner/            # Scheduled queue-management wrapper around loop-task-implementer
├── weekly-squad-digest/       # Scheduled digest combining migration-program-manager's + cost-optimization-sprint-planner's rollups
├── test-writer/               # Thin router: classifies a level-unspecified test-writing request and dispatches
├── unit-test-creator/         # Isolated, mocked, function/class-level test generation
├── integration-test-creator/  # Tests the real seam to one real adjacent dependency (never mocked)
├── contract-test-creator/     # Consumer-driven contract tests (Pact-style)
├── e2e-test-creator/          # Full user-journey browser tests (Playwright/Cypress/Selenium)
└── api-test-creator/          # Black-box Postman/Newman request/response tests against a real API
```

Each skill directory follows the same pattern:

<!-- registry-skills-table:start -->
| Skill | Category | Invocation | Install requires | Lint target |
|-------|----------|------------|------------------|-------------|
| `api-test-creator` | testing | ambient | — | `make lint-api-test-creator` |
| `backlog-runner` | automation | automation-only | loop-task-implementer | `make lint-backlog-runner` |
| `contract-test-creator` | testing | ambient | — | `make lint-contract-test-creator` |
| `cost-optimization-sprint-planner` | platform | ambient | k8s-overprovisioning-datadog, squad-map | `make lint-cost-optimization-sprint-planner` |
| `domain-comprehension` | architecture | ambient | squad-map | `make lint-domain-comprehension` |
| `e2e-test-creator` | testing | ambient | — | `make lint-e2e-test-creator` |
| `incident-rca` | incident | ambient | — | `make lint-incident-rca` |
| `incident-triage-agent` | incident | automation-only | incident-rca, squad-map | `make lint-incident-triage-agent` |
| `integration-test-creator` | testing | ambient | — | `make lint-integration-test-creator` |
| `k8s-overprovisioning-datadog` | platform | ambient | — | `make lint-k8s-skill` |
| `loop-task-implementer` | automation | ambient | — | `make lint-loop-task-implementer` |
| `migration-program-manager` | migration | ambient | mysql-to-postgres-sql, squad-map | `make lint-migration-program-manager` |
| `mysql-to-postgres-sql` | migration | ambient | — | `make lint-mysql-to-postgres-sql` |
| `new-hire-guide` | architecture | ambient | domain-comprehension, squad-map | `make lint-new-hire-guide` |
| `pr-gatekeeper` | review | automation-only | pr-review | `make lint-pr-gatekeeper` |
| `pr-review` | review | ambient | — | `make lint-pr-review` |
| `prd-architect` | product | ambient | — | `make lint-prd-architect` |
| `release-readiness-checker` | release | ambient | pr-review, k8s-overprovisioning-datadog, incident-rca | `make lint-release-readiness-checker` |
| `squad-map` | architecture | ambient | — | `make lint-squad-map` |
| `test-writer` | product | ambient | unit-test-creator, integration-test-creator, contract-test-creator, e2e-test-creator, api-test-creator | `make lint-test-writer` |
| `unit-test-creator` | testing | ambient | — | `make lint-unit-test-creator` |
| `weekly-squad-digest` | migration | automation-only | migration-program-manager, cost-optimization-sprint-planner | `make lint-weekly-squad-digest` |
| `who-owns-x-bot` | architecture | automation-only | squad-map | `make lint-who-owns-x-bot` |
<!-- registry-skills-table:end -->

| File | Audience | Purpose |
|------|----------|---------|
| `README.md` | Humans | What the skill does, when to use it, outputs |
| `SKILL.md` | Cursor agent | Orchestrator: workflow index, guardrails, lazy-load rules |
| `SETUP.md` | Humans | MCP servers, install steps, smoke tests |
| `examples.md` | Humans | Invocation patterns and sample prompts |
| `reference/` or `workflow/` | Agent (on demand) | Detailed procedures loaded one file at a time |

**SKILL.md is not documentation for humans** — it is optimized for agent context economy (thin orchestrator,
detail in reference files). Use each skill's `README.md` for a plain-language overview.

## Install

```bash
git clone https://github.com/luckyrjain/software-builder.git
cd software-builder
make install          # all skills with a SKILL.md at repo root level
make install-pr-review
make install-pr-gatekeeper
make install-k8s-overprovisioning
make install-incident-rca
make install-incident-triage-agent
make install-domain-comprehension
make install-squad-map
make install-who-owns-x-bot
make install-new-hire-guide
make install-release-readiness-checker
make install-migration-program-manager
make install-cost-optimization-sprint-planner
make install-mysql-to-postgres-sql
make install-loop-task-implementer
make install-backlog-runner
make install-weekly-squad-digest
make install-unit-test-creator
make install-integration-test-creator
make install-contract-test-creator
make install-e2e-test-creator
make install-api-test-creator
make install-test-writer   # chains all five above
```

`scripts/install.sh` copies the entire skill directory to **both** `~/.cursor/skills/<skill-name>/`
and `~/.claude/skills/<skill-name>/` by default, replacing any existing install at each. **Restart
Cursor** and start a new Claude Code session after installing.

Install one skill explicitly:

```bash
bash scripts/install.sh pr-review
bash scripts/install.sh pr-gatekeeper
bash scripts/install.sh k8s-overprovisioning-datadog
bash scripts/install.sh incident-rca
bash scripts/install.sh incident-triage-agent
bash scripts/install.sh domain-comprehension
bash scripts/install.sh squad-map
bash scripts/install.sh who-owns-x-bot
bash scripts/install.sh new-hire-guide
bash scripts/install.sh release-readiness-checker
bash scripts/install.sh migration-program-manager
bash scripts/install.sh cost-optimization-sprint-planner
bash scripts/install.sh mysql-to-postgres-sql
bash scripts/install.sh loop-task-implementer
bash scripts/install.sh backlog-runner
bash scripts/install.sh weekly-squad-digest
bash scripts/install.sh unit-test-creator
bash scripts/install.sh integration-test-creator
bash scripts/install.sh contract-test-creator
bash scripts/install.sh e2e-test-creator
bash scripts/install.sh api-test-creator
bash scripts/install.sh test-writer
```

With no arguments, `install.sh` discovers every `*/SKILL.md` under the repo root and installs each —
adding a new skill directory needs no script change to be picked up.

To install for only one editor, pass `--agent cursor` (Cursor only) or `--agent claude-user` (Claude
Code only, installs to `~/.claude/skills/`) — or use the `install-claude*` Makefile targets below for
the Claude-Code-only form. Pass `--target-dir <repo>` to install into that project's
`.cursor/skills/` / `.claude/skills/` instead; omit it for the default **global** user install. Kiro
and ChatGPT/Codex aren't wired into this script (Kiro needs no install step — see `.kiro/steering/`;
Codex's skills directory isn't uniform, copy manually). See root
[README.md § Install for your specific coding agent](../README.md#install-for-your-specific-coding-agent)
and [docs/skill-framework/shared/claude-code-setup.md](skill-framework/shared/claude-code-setup.md).

## Makefile targets

| Target | What it does |
|--------|--------------|
| `make install` | Run `scripts/install.sh` for all skills |
| `make install-pr-review` | Install only `pr-review/` |
| `make install-pr-gatekeeper` | Install only `pr-gatekeeper/` (also runs `install-pr-review`) |
| `make install-k8s-overprovisioning` | Install only `k8s-overprovisioning-datadog/` |
| `make install-incident-rca` | Install only `incident-rca/` (also runs `install-incident-rca-deps`) |
| `make install-incident-triage-agent` | Install only `incident-triage-agent/` (also runs `install-incident-rca` and `install-squad-map`) |
| `make install-domain-comprehension` | Install only `domain-comprehension/` (also runs `install-squad-map`) |
| `make install-squad-map` | Install only `squad-map/` |
| `make install-who-owns-x-bot` | Install only `who-owns-x-bot/` (also runs `install-squad-map`) |
| `make install-new-hire-guide` | Install only `new-hire-guide/` (also runs `install-domain-comprehension` and `install-squad-map`) |
| `make install-release-readiness-checker` | Install only `release-readiness-checker/` (also runs `install-pr-review`, `install-k8s-overprovisioning`, and `install-incident-rca`) |
| `make install-migration-program-manager` | Install only `migration-program-manager/` (also runs `install-mysql-to-postgres-sql` and `install-squad-map`) |
| `make install-cost-optimization-sprint-planner` | Install only `cost-optimization-sprint-planner/` (also runs `install-k8s-overprovisioning` and `install-squad-map`) |
| `make install-mysql-to-postgres-sql` | Install only `mysql-to-postgres-sql/` |
| `make install-loop-task-implementer` | Install only `loop-task-implementer/` |
| `make install-backlog-runner` | Install only `backlog-runner/` (also runs `install-loop-task-implementer`) |
| `make install-weekly-squad-digest` | Install only `weekly-squad-digest/` (also runs `install-migration-program-manager` and `install-cost-optimization-sprint-planner`) |
| `make install-unit-test-creator` | Install only `unit-test-creator/` |
| `make install-integration-test-creator` | Install only `integration-test-creator/` |
| `make install-contract-test-creator` | Install only `contract-test-creator/` |
| `make install-e2e-test-creator` | Install only `e2e-test-creator/` |
| `make install-api-test-creator` | Install only `api-test-creator/` |
| `make install-test-writer` | Install only `test-writer/` (also runs all five `install-*-test-creator` targets above — the router is useless without them) |
| `make install-claude` | Run `scripts/install.sh --agent claude-user` for all skills |
| `make install-claude-<skill>` | Install only `<skill>/` for Claude Code (`pr-review`, `pr-gatekeeper`, `k8s-overprovisioning`, `incident-rca`, `incident-triage-agent`, `domain-comprehension`, `squad-map`, `who-owns-x-bot`, `new-hire-guide`, `release-readiness-checker`, `migration-program-manager`, `cost-optimization-sprint-planner`, `mysql-to-postgres-sql`, `loop-task-implementer`, `backlog-runner`, `weekly-squad-digest`, `unit-test-creator`, `integration-test-creator`, `contract-test-creator`, `e2e-test-creator`, `api-test-creator`, `test-writer`) |
| `make lint` | Run all lint targets below + shellcheck on `scripts/*.sh` |
| `make lint-pr-review` | pr-review `SKILL.md` ≤ 180 lines; each `workflow/*.md` has `workflow_version`/`phase`/`produces`/`consumes` frontmatter; dangling markdown anchors; script pytest |
| `make lint-pr-gatekeeper` | pr-gatekeeper `SKILL.md` ≤ 180 lines; `disable-model-invocation: true` set; workflow frontmatter; dangling anchors; required reference files |
| `make lint-k8s-skill` | k8s `SKILL.md` ≤ 150 lines; workflow frontmatter; decision graph schema v3; render/markdown.md; dangling anchors; memory-sizing p95 rule; templates |
| `make lint-incident-rca` | incident-rca `SKILL.md` ≤ 180 lines; workflow frontmatter; valid `evidence.example.json`; dangling anchors; causal-graph example validated |
| `make lint-incident-triage-agent` | incident-triage-agent `SKILL.md` ≤ 180 lines; `disable-model-invocation: true` set; workflow frontmatter; dangling anchors; required reference files |
| `make lint-domain-comprehension` | domain-comprehension `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; `templates/manifest.yaml` validator + pytest; pressure harness |
| `make lint-squad-map` | squad-map `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; required reference files; pytest |
| `make lint-who-owns-x-bot` | who-owns-x-bot `SKILL.md` ≤ 180 lines; `disable-model-invocation: true` set; workflow frontmatter; dangling anchors; required reference files |
| `make lint-new-hire-guide` | new-hire-guide `SKILL.md` ≤ 180 lines; `disable-model-invocation` **not** set; workflow frontmatter; dangling anchors; required reference files |
| `make lint-release-readiness-checker` | release-readiness-checker `SKILL.md` ≤ 180 lines; `disable-model-invocation` **not** set; workflow frontmatter; dangling anchors; required reference files |
| `make lint-migration-program-manager` | migration-program-manager `SKILL.md` ≤ 180 lines; `disable-model-invocation` **not** set; workflow frontmatter; dangling anchors; required reference files; aggregator pytest |
| `make lint-cost-optimization-sprint-planner` | cost-optimization-sprint-planner `SKILL.md` ≤ 180 lines; `disable-model-invocation` **not** set; workflow frontmatter; dangling anchors; required reference files |
| `make lint-mysql-to-postgres-sql` | mysql `SKILL.md` ≤ 180 lines; workflow frontmatter; required references; scan fixtures + pressure harness; AST-backed secondary checker (`.sql` files, see [ast-vs-regex-scan.md](../mysql-to-postgres-sql/reference/ast-vs-regex-scan.md)); shellcheck on scan scripts |
| `make lint-loop-task-implementer` | loop-task-implementer `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; required files (`SETUP.md`, `README.md`, `examples.md`, `report-template.md`, `reference/*`) |
| `make lint-backlog-runner` | backlog-runner `SKILL.md` ≤ 180 lines; `disable-model-invocation: true` set; workflow frontmatter; dangling anchors; required reference files |
| `make lint-weekly-squad-digest` | weekly-squad-digest `SKILL.md` ≤ 180 lines; `disable-model-invocation: true` set; workflow frontmatter; dangling anchors; required reference files |
| `make lint-unit-test-creator` | unit-test-creator `SKILL.md` ≤ 180 lines; workflow frontmatter; required references; detection-script pytest suite; shellcheck on `scripts/*.sh` |
| `make lint-integration-test-creator` | integration-test-creator, same shape as above |
| `make lint-contract-test-creator` | contract-test-creator, same shape as above |
| `make lint-e2e-test-creator` | e2e-test-creator, same shape as above |
| `make lint-api-test-creator` | api-test-creator, same shape as above |
| `make lint-test-writer` | test-writer `SKILL.md` ≤ 180 lines; workflow frontmatter; required references; confirms no `scripts/`/`tests/` exist (router only); dangling anchors across test-writer and all four dispatch targets' SKILL.md/workflow files |
| `make lint-framework` | shared `docs/skill-framework/` files present; required sections; SETUP.md links; metadata footer examples parse; every skill has a `.cursor/rules/*.mdc` + `.kiro/steering/*.md` discovery file |
| `make setup-hooks` | Set `git config core.hooksPath .githooks` (shellcheck pre-commit) |

### lint-incident-rca

`incident-rca/SKILL.md` must stay at or under **180 lines**. Each file under `workflow/` must declare
`workflow_version`, `produces`, and `consumes` in YAML frontmatter. Validates `reference/evidence.example.json`
parses as JSON and checks markdown anchor links under `incident-rca/` (including `workflow/`).

### lint-incident-triage-agent

`incident-triage-agent/SKILL.md` must stay at or under **180 lines** and must set
`disable-model-invocation: true` (it is a paging-webhook-only automation entry point, not an
ambient-chat skill — unlike incident-rca or squad-map). Each file under `workflow/` must declare
`workflow_version`, `phase`, `produces`, and `consumes` in YAML frontmatter. Checks markdown anchor links
and required `reference/` files (`phase-index.md`, `lazy-load-index.md`, `unattended-gate-policy.md`,
`triage-doc-format.md`, `postmortem-format.md`, `smoke-test.md`). No scripts or tests — this skill has no
investigation or ownership logic of its own beyond deciding when to invoke incident-rca/squad-map and how
to answer their gates unattended.

### lint-pr-review

Requires **pytest** (`python3 -m pip install pytest`). `pr-review/SKILL.md` must stay at or under **180
lines**. Each file under `workflow/` must declare `workflow_version`, `produces`, and `consumes` in YAML
frontmatter. Tests live in `pr-review/tests/` and cover diff position mapping for inline GitLab comments.

### lint-pr-gatekeeper

`pr-gatekeeper/SKILL.md` must stay at or under **180 lines** and must set
`disable-model-invocation: true` (it is a webhook-only automation entry point, not an ambient-chat skill
— unlike pr-review). Each file under `workflow/` must declare `workflow_version`, `phase`, `produces`,
and `consumes` in YAML frontmatter. Checks markdown anchor links and required `reference/` files
(`phase-index.md`, `lazy-load-index.md`, `auto-post-policy.md`, `smoke-test.md`). No scripts or tests —
this skill has no review logic of its own beyond deciding whether pr-review's Phase 4 may run.

### lint-k8s-skill

Enforces a thin orchestrator: `k8s-overprovisioning-datadog/SKILL.md` must stay at or under **150 lines**.
Each file under `workflow/` must declare `workflow_version`, `produces`, and `consumes` in YAML frontmatter.
Also validates internal markdown link anchors and ensures the memory sizing section in `thresholds.md` does not positively assert p95 (memory uses a peak proxy, not p95).

### lint-domain-comprehension

Requires **pytest** (`python3 -m pip install pytest`). `domain-comprehension/SKILL.md` must stay at or under **180 lines**. Each file under `workflow/` must declare `workflow_version`, `produces`, and `consumes` in YAML frontmatter. Validates `templates/manifest.yaml` parses and the manifest validator (`scripts/validate_manifest_yaml.py`) runs successfully via pytest in `tests/test_validate_manifest.py`. Checks markdown anchor links under `domain-comprehension/` (including `workflow/` and `reference/`).

### lint-who-owns-x-bot

`who-owns-x-bot/SKILL.md` must stay at or under **180 lines** and must set
`disable-model-invocation: true` (it is an automation entry point, not an ambient-chat skill — unlike
squad-map). Each file under `workflow/` must declare `workflow_version`, `phase`, `produces`, and
`consumes` in YAML frontmatter. Checks markdown anchor links and required `reference/` files
(`phase-index.md`, `lazy-load-index.md`, `slack-format.md`, `smoke-test.md`). No scripts or tests — this
skill has no logic of its own beyond delegating to squad-map and formatting the reply.

### lint-new-hire-guide

`new-hire-guide/SKILL.md` must stay at or under **180 lines** and must **not** set
`disable-model-invocation` — unlike who-owns-x-bot/pr-gatekeeper/incident-triage-agent/backlog-runner, a
human is always present for this flow, so ambient chat invocation is intended. Each file under
`workflow/` must declare `workflow_version`, `phase`, `produces`, and `consumes` in YAML frontmatter.
Checks markdown anchor links and required `reference/` files (`phase-index.md`, `lazy-load-index.md`,
`tour-format.md`, `smoke-test.md`). No scripts or tests — this skill has no logic of its own beyond
composing domain-comprehension and squad-map and curating the result.

### lint-release-readiness-checker

`release-readiness-checker/SKILL.md` must stay at or under **180 lines** and must **not** set
`disable-model-invocation` — a human is present for this flow, but the fan-out over potentially many MRs
and services still needs one scripted gate answer (incident-rca's Phase 1 checkpoint), documented in
`reference/gate-policy.md` rather than in the lint target itself. Each file under `workflow/` must declare
`workflow_version`, `phase`, `produces`, and `consumes` in YAML frontmatter. Checks markdown anchor links
and required `reference/` files (`phase-index.md`, `lazy-load-index.md`, `gate-policy.md`,
`report-format.md`, `smoke-test.md`). No scripts or tests — this skill has no
review/rightsizing/incident-investigation logic of its own beyond the MR-range resolver and aggregation.

### lint-migration-program-manager

`migration-program-manager/SKILL.md` must stay at or under **180 lines** and must **not** set
`disable-model-invocation` — unlike who-owns-x-bot/pr-gatekeeper/incident-triage-agent/backlog-runner, this
is a pure read-only aggregator over mysql-to-postgres-sql's and squad-map's already-produced files; it never
invokes either skill live, so there's no wrapped-skill gate to police and no reason to disable ambient
invocation. Each file under `workflow/` must declare `workflow_version`, `phase`, `produces`, and `consumes`
in YAML frontmatter. Checks markdown anchor links and required `reference/` files (`phase-index.md`,
`lazy-load-index.md`, `report-format.md`, `smoke-test.md`) plus `scripts/aggregate_migration_status.py`'s
existence. Runs `python3 -m pytest migration-program-manager/tests/ -q`
(`tests/test_aggregate_migration_status.py`, 50 cases covering the `SQUAD_MAP.md` parser, the squad join,
status derivation, and staleness tracking) if pytest is installed.

### lint-cost-optimization-sprint-planner

`cost-optimization-sprint-planner/SKILL.md` must stay at or under **180 lines** and must **not** set
`disable-model-invocation` — a human is present for this flow, but the fan-out over potentially many
deployments still needs a gate-policy file (every live k8s-overprovisioning-datadog gate answered with
its own documented fallback, cost-rate resolved once sweep-wide) and a sweep-policy file (session-level
state, candidate-list construction, failure isolation, batch-level stop conditions), modeled on
backlog-runner's `queue-policy.md`. Each file under `workflow/` must declare `workflow_version`, `phase`,
`produces`, and `consumes` in YAML frontmatter. Checks markdown anchor links and required `reference/`
files (`phase-index.md`, `lazy-load-index.md`, `gate-policy.md`, `sweep-policy.md`, `report-format.md`,
`smoke-test.md`). No scripts or tests — this skill has no rightsizing/cost-analysis logic of its own
beyond the pre-filter query pass, the sweep loop, and the aggregation.

### lint-mysql-to-postgres-sql

Requires **ripgrep** (`rg`) with PCRE2 on the host running lint. `mysql-to-postgres-sql/SKILL.md` must stay at or under **180 lines**. Each file under `workflow/` must declare `workflow_version` frontmatter. Runs scan gate fixtures (`tests/fixtures/mysql-dialect/`), the pressure-test harness (`tests/run_pressure_tests.sh`), dangling anchor checks, and shellcheck on `scripts/scan-mysql-dialect.sh` and `scripts/scan-report.sh`.

### lint-unit-test-creator / lint-integration-test-creator / lint-contract-test-creator / lint-e2e-test-creator / lint-api-test-creator

All five share one Makefile template (`LINT_TEST_CREATOR_TARGET`, parameterized by skill name, script
filenames, and pytest file). Each skill's `SKILL.md` must stay at or under **180 lines**. Each file under
`workflow/` must declare `workflow_version`/`phase`/`produces`/`consumes` frontmatter. Checks all required
`reference/` files exist (`skill-contract`, `phase-index`, `lazy-load-index`, `gate-policy`,
`test-quality-deltas`, `framework-detection`, `report-format`, `smoke-test`, `pressure-tests`),
`reference/skill-contract.md` links the shared `test-creation-principles.md`, `examples.md` has an
`## Invocation` section, and `SKILL.md` links both `skill-routing.md` and `prompt-injection.md`. Runs
dangling-anchor checks, shellcheck on `scripts/*.sh`, and the skill's own pytest suite over its
detection-script fixtures.

### lint-test-writer

`test-writer/SKILL.md` must stay at or under **180 lines**. Each file under `workflow/` must declare
`workflow_version`/`phase`/`produces`/`consumes` frontmatter. Checks all required `reference/` files
exist (`skill-contract`, `phase-index`, `lazy-load-index`, `level-classification`, `smoke-test`,
`pressure-tests`), confirms **no** `scripts/` or `tests/` directory exists (this skill is a router with
no detection/generation logic of its own), `examples.md` has an `## Invocation` section, and `SKILL.md`
links both `skill-routing.md` and `prompt-injection.md`. Runs dangling-anchor checks across test-writer's
own files **and** all five dispatch targets' `SKILL.md`/`workflow/*.md` (test-writer's `workflow/delegate.md`
links directly into each dispatch target's own files).

## Git hooks

After `make setup-hooks`, the pre-commit hook runs **shellcheck** on any staged file under `scripts/*.sh`.
Uses local `shellcheck` or falls back to Docker (`koalaman/shellcheck-alpine:stable`).

## CI/CD

[`.github/workflows/lint.yml`](../.github/workflows/lint.yml) runs `make lint` on every push and pull
request against `main` (or `master`), on GitHub's own `ubuntu-latest` runner — **no self-hosted runner to
provision or keep online.** The job installs everything `make lint` needs itself (`python3`, `pytest`,
`shellcheck`, `ripgrep`) before running it; see the workflow file for the exact steps.

| Requirement | Notes |
|-------------|--------|
| **Runner** | GitHub-hosted `ubuntu-latest` — always available, nothing to register |
| **Dependencies** | Installed fresh each run via `apt-get` (`shellcheck`, `ripgrep`) and `pip` (`requirements.txt`) |
| **Trigger** | `push` to `main`/`master`, any `pull_request` targeting either, a weekly Monday-04:17 UTC `schedule`, and manual `workflow_dispatch` |

The scheduled run and `workflow_dispatch` exist so drift (a dependency advisory, a newly-broken
external link) surfaces even when no PR is open against `main` — see [#10](https://github.com/luckyrjain/software-builder/issues/10).

Run the exact same checks locally before pushing: `make setup` once (installs Python deps + the
shellcheck pre-commit hook), then `make lint`.

### Security workflows

Proportionate to what this repo actually executes — shell/Python helpers (`scripts/`, `*/scripts/`),
an installer that writes outside the repo tree, and skill docs that describe MCP write-authority
workflows — six additional, independent checks run alongside `lint.yml`:

| Workflow | What it catches | Trigger |
|----------|------------------|---------|
| [`dependency-review.yml`](../.github/workflows/dependency-review.yml) | A PR introducing a dependency with a known high-severity advisory | `pull_request` |
| [`codeql.yml`](../.github/workflows/codeql.yml) | Python static-analysis findings (injection, path traversal, etc.) — every tracked `.py` file repo-wide, not just `scripts/`/`*/scripts/` (the motivating case, but not the only Python this repo carries — skill-local test files and a couple of runtime templates live outside those dirs too) | push, PR, weekly |
| [`secret-scan.yml`](../.github/workflows/secret-scan.yml) | A committed credential/token (Gitleaks), plus a self-test proving the scanner still fires | push, PR, weekly |
| [`scorecard.yml`](../.github/workflows/scorecard.yml) | OpenSSF Scorecard supply-chain posture (branch protection, pinned deps, etc.) | push to `main`, weekly |
| `make lint`'s `lint-actions-security` step | Actions-YAML risks (script injection via untrusted `${{ }}` expansion, a workflow with **no** `permissions:` block at all, credential persistence) via [zizmor](https://docs.zizmor.sh/), default (`regular`) persona | every `make lint` run |
| `make lint`'s `lint-actions-pinning` step | Any `uses:` reference not pinned to a full commit SHA (a mutable tag can be repointed after review) | every `make lint` run |

The last two run locally too — `scripts/check_pinned_actions.py` needs no extra dependency.
`lint-actions-security` needs `zizmor`, installed from `requirements.lock` by `make setup`; if it
isn't on `PATH` (e.g. you skipped `make setup`), the target prints a `SKIPPED:` line to stderr and
`make lint` still exits 0 — the Actions-YAML security lint silently did not run. This mirrors how
`lint-framework`'s `pytest` step already behaves when `pytest` isn't installed locally; CI always has
both installed via `requirements.lock`, so this gap is local-only. Separately, without a
`GH_TOKEN`/`GITHUB_TOKEN` in your shell, `lint-actions-security` falls back to
`zizmor --no-online-audits` (skips checks that need live GitHub API access, e.g. verifying an action
ref against its upstream tag history) — CI always runs the full set via the workflow's own token. A
token that's present but the online audit still can't reach the GitHub API (a transient network blip
or rate limit, distinguished from a real finding by zizmor's own `fatal: no audit was performed`
error) triggers the same offline fallback rather than failing the whole `make lint` run — this keeps a
GitHub-side hiccup from blocking a release (`release.yml`'s lint step now runs online-audit-capable)
on something unrelated to the actual code.

zizmor's default persona flags a workflow with no `permissions:` block at all, but does **not** flag
permissions that are merely broader than necessary while still present (e.g. workflow-level
`contents: write` on a single-job workflow, which zizmor's stricter `--persona=auditor` would flag as
better expressed at the job level) — `make lint` doesn't pass that flag today. Not a gap unique to
this repo's setup; a deliberate default/strict split zizmor itself ships with.

**Secret-scan negative test.** `secret-scan.yml`'s `negative-test` job proves the scanner still
detects a known-bad pattern, independent of whether this run's actual repo content is clean. The
fixture is a random AWS-access-key-ID-shaped string (`AKIA` + 16 characters from gitleaks' own
`aws-access-token` regex's character class), generated fresh every run — **not** AWS's well-known
`AKIAIOSFODNN7EXAMPLE` placeholder, which gitleaks' own default config now allowlists (a
`.+EXAMPLE$` rule, added precisely because that string is so widely recognized as a non-functional
example) — using it would make this negative test pass even if real-leak detection were broken. The
fixture is generated at CI-run-time and scanned in isolation; it is **not** committed to git history,
deliberately. Two reasons: it avoids permanently storing a secret-shaped string in the repository,
and it sidesteps an unknown risk noted below — whether a committed one would trip this repo's own
push protection.

**Native GitHub secret scanning / push protection: unverified, and likely off.** No tool available to
this effort could read the repository's Code Security settings directly. One indirect signal: a
request to run GitHub's secret-scanning check against this repository returned *"Repository does not
have GitHub Advanced Security enabled"* — which suggests native secret scanning / push protection are
not active (GHAS covers those on private repos; a public repo can still have push protection toggled
on separately, so this isn't conclusive). **A repo admin should confirm and toggle these on** at
**Settings → Code security → Secret scanning** — the dedicated `secret-scan.yml` workflow above exists
specifically because this native coverage couldn't be confirmed.

**Not added as required merge-gate checks (yet).** These are new, and CodeQL/Scorecard in particular
can be noisy on a first baseline run. Watch a few real runs before deciding whether to add any of
their job names to the `main` ruleset's required-status-checks list (see the Merge gate section below)
— `lint` is deliberately the only check documented there as required today.

### Merge gate — repo-admin settings (GitHub UI only)

**A green `Lint` badge and a ruleset are not the same thing.** CI proves the commit passes
`make lint`; the ruleset decides whether GitHub will let you merge. Nothing in this repository can
change rulesets — only a repo admin can, from **Settings** (not a PR).

#### Recommended ruleset for a solo maintainer (you are the only developer)

GitHub does **not** let a PR author approve their own PR. If the ruleset requires one or more
approving reviews (especially CODEOWNER review), a solo maintainer will see **Review required** /
**Blocked** even when CI is green and you are the only person on the repo.

**Keep these protections:**

1. **Require a pull request before merging** — keeps an audit trail; you still open PRs from branches.
2. **Require status checks to pass** → add the exact job name `lint` from
   [`.github/workflows/lint.yml`](../.github/workflows/lint.yml) (it must have run at least once before
   GitHub lists it).
3. **Require branches to be up to date before merging** (optional but recommended).
4. **Block force pushes** and **restrict branch deletion** on `main`.

**Do not enable (until a second reviewer exists):**

- **Require pull request approvals** (or set required approvals to **0**).
- **Require review from CODEOWNERS** — with one maintainer who authors every PR, this is a
  self-approval deadlock.

**Optional bypass (if you want approvals later but need to merge your own work today):**

- In the ruleset, under **Bypass list**, add **Repository admin** (your account). Admins can merge
  without an approval while the rule stays in place for future contributors.

#### When a second contributor joins

Re-enable **Require pull request approvals** (≥1) and **Require review from CODEOWNERS** on
platform paths (`Makefile`, `scripts/`, `docs/skill-framework/`, `.github/`). Until then, CODEOWNERS
is documentation of who owns sensitive paths, not a merge gate.

#### One-time setup checklist

1. **Settings → Rules → Rulesets** → edit (or create) the ruleset targeting `main`.
2. Apply the solo-maintainer settings above — or match the canonical spec in
   [`docs/github-ruleset-main.json`](../github-ruleset-main.json) (enforcement `active`, required
   status check `lint`, squash-only merges, zero required approvals, no CODEOWNER review).
3. **Settings → General → Pull Requests** → pick one merge strategy (squash recommended) and enable
   **Automatically delete head branches**.
4. Verify: `make verify-github-ruleset` (requires `gh auth login` with repo read access) should print
   `ok: GitHub ruleset matches docs/github-ruleset-main.json`.
5. Smoke-test the gate: open a throwaway PR with a deliberately failing `make lint` change — merge
   should be blocked by CI, not by missing approval. Close without merging.

Repo admins without API access can apply the JSON fields manually in the ruleset UI; the `_documentation`
block in the file explains each field but is stripped by the verifier.

#### Unblock an existing PR right now

If a PR shows **Review required** / `mergeStateStatus: BLOCKED` but `lint` passed:

1. Edit the `main` ruleset as above (remove approval requirement or add admin bypass).
2. Refresh the PR page — the merge button should enable without a self-approval.

`CODEOWNERS` in this repo flags platform-sensitive paths for human review once multiple maintainers
exist; it does not replace CI and should not block a solo maintainer from merging.

### GitHub repository metadata (admin UI only)

These improve discoverability but cannot be changed from a PR:

1. **Settings → General → Description** — e.g. *Portable agent skills for code review, incident RCA,
   K8s optimization, migrations, and autonomous implementation.*
2. **Settings → General → Topics** — e.g. `agent-skills`, `cursor`, `claude-code`, `devops`,
   `incident-response`, `kubernetes`, `software-engineering`.
3. Link the [Code of Conduct](../CODE_OF_CONDUCT.md) under **Settings → General → Features** if
   GitHub offers a community standards field (the file is also linked from CONTRIBUTING).

## Contributing

1. Edit the skill in its directory under this repo (not directly in `~/.cursor/skills/`).
2. Run `make lint` before pushing.
3. Record user-visible changes in `CHANGELOG.md` under the skill's section (newest first).
4. For pr-review workflow changes, update the matching `workflow/*.md` and any `reference/*.md` the phase
   points to; keep `SKILL.md` as an index only.
5. Re-run the skill's smoke test after substantive edits (`reference/smoke-test.md` or k8s
   `workflow/render.md` § Smoke test).

## MCP dependencies (summary)

| Skill | Required MCP | Optional MCP |
|-------|--------------|--------------|
| pr-review | GitLab (read; write for posting) | Jira (ticket context + write-back) |
| pr-gatekeeper | None — delegates to pr-review | Requires pr-review installed and configured for GitLab posting |
| incident-rca | ≥1 observability (Datadog or KubeSense) | GitLab, Jenkins, Jira; optional `incident-rca` CLI |
| incident-triage-agent | None — delegates to incident-rca + squad-map | Requires both installed and configured |
| k8s-overprovisioning-datadog | At least one sufficient evidence source: read-only Kubernetes MCP or Datadog | Git provider (manifest drift); Datadog for unique historical/operational telemetry and cost |
| domain-comprehension | None | GitLab (Session 0b via squad-map), Datadog (P2b runtime validation) |
| squad-map | None | GitLab, Datadog (CODEOWNERS fallback when both absent) |
| who-owns-x-bot | None — delegates to squad-map | Requires squad-map installed and configured |
| new-hire-guide | None — inherits domain-comprehension's + squad-map's | Requires both installed and configured |
| release-readiness-checker | None — inherits pr-review's, k8s-overprovisioning-datadog's, and incident-rca's | Requires all three installed and configured |
| migration-program-manager | None — no MCP calls at all, pure file aggregation | Requires mysql-to-postgres-sql (and ideally squad-map) already run in the target workspaces |
| cost-optimization-sprint-planner | Datadog (for the namespace pre-filter) — otherwise delegates to k8s-overprovisioning-datadog's own | Requires k8s-overprovisioning-datadog installed and configured (and ideally squad-map) |
| mysql-to-postgres-sql | None | Datadog (optional; post-cutover APM verification) |
| loop-task-implementer | None — uses the host agent's own repo/git access, not an MCP server | See [loop-task-implementer/reference/mcp-capabilities.md](../loop-task-implementer/reference/mcp-capabilities.md) for host-capability requirements |
| backlog-runner | Issue-tracker MCP (Jira or GitHub Issues) — required here, optional for loop-task-implementer itself | Requires loop-task-implementer installed and configured |
| weekly-squad-digest | None — no MCP calls at all, pure file aggregation | Requires migration-program-manager and cost-optimization-sprint-planner each already run at least once |
| test-writer | None — router only, dispatches to the skills below | Requires at least one of the four dispatch targets installed and configured |
| unit-test-creator, integration-test-creator, contract-test-creator, e2e-test-creator, api-test-creator | None — use the host agent's own repo read/write access | Host's test-runner/browser/API access (set `run_tests: false` to draft without executing) |

Per-skill setup: see each skill's `SETUP.md`.
