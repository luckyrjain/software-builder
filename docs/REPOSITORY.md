# Repository guide

What the **software-builder** repo contains, how to install skills, and how quality checks work.

## Layout

```
software-builder/
├── README.md                 # Top-level install + usage (start here)
├── CHANGELOG.md              # Per-skill change history
├── Makefile                  # install + lint targets
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
└── test-writer/               # Detects a repo's test framework and writes/backfills real, running tests
```

Each skill directory follows the same pattern:

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
make install-test-writer
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
bash scripts/install.sh test-writer
```

With no arguments, `install.sh` discovers every `*/SKILL.md` under the repo root and installs each —
adding a new skill directory needs no script change to be picked up.

To install for only one editor, pass `--agent cursor` (Cursor only) or `--agent claude-user` (Claude
Code only, installs to `~/.claude/skills/`) — or use the `install-claude*` Makefile targets below for
the Claude-Code-only form. Kiro and ChatGPT/Codex aren't wired into this script (Kiro needs no install
step — see `.kiro/steering/`; Codex's skills directory isn't uniform, copy manually). See root
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
| `make install-test-writer` | Install only `test-writer/` |
| `make install-claude` | Run `scripts/install.sh --agent claude-user` for all skills |
| `make install-claude-<skill>` | Install only `<skill>/` for Claude Code (`pr-review`, `pr-gatekeeper`, `k8s-overprovisioning`, `incident-rca`, `incident-triage-agent`, `domain-comprehension`, `squad-map`, `who-owns-x-bot`, `new-hire-guide`, `release-readiness-checker`, `migration-program-manager`, `cost-optimization-sprint-planner`, `mysql-to-postgres-sql`, `loop-task-implementer`, `backlog-runner`, `weekly-squad-digest`, `test-writer`) |
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
| `make lint-mysql-to-postgres-sql` | mysql `SKILL.md` ≤ 180 lines; workflow frontmatter; required references; scan fixtures + pressure harness; shellcheck on scan scripts |
| `make lint-loop-task-implementer` | loop-task-implementer `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; required files (`SETUP.md`, `README.md`, `examples.md`, `report-template.md`, `reference/*`) |
| `make lint-backlog-runner` | backlog-runner `SKILL.md` ≤ 180 lines; `disable-model-invocation: true` set; workflow frontmatter; dangling anchors; required reference files |
| `make lint-weekly-squad-digest` | weekly-squad-digest `SKILL.md` ≤ 180 lines; `disable-model-invocation: true` set; workflow frontmatter; dangling anchors; required reference files |
| `make lint-test-writer` | test-writer `SKILL.md` ≤ 180 lines; workflow frontmatter; required references; detection-script pytest suite; shellcheck on `scripts/*.sh` |
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

### lint-test-writer

`test-writer/SKILL.md` must stay at or under **180 lines**. Each file under `workflow/` must declare
`workflow_version`/`phase`/`produces`/`consumes` frontmatter. Checks all required `reference/` files
exist, `examples.md` has an `## Invocation` section, and `SKILL.md` links both `skill-routing.md` and
`prompt-injection.md`. Runs dangling-anchor checks, shellcheck on
`scripts/detect-test-framework.sh`/`scripts/test-framework-markers.sh`, and the pytest suite
(`tests/test_detect_test_framework.py`) over the marker-file fixtures under
`tests/fixtures/test-framework-detect/`.

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
| **Trigger** | `push` to `main`/`master`, and any `pull_request` targeting either |

Run the exact same checks locally before pushing: `make setup` once (installs Python deps + the
shellcheck pre-commit hook), then `make lint`.

### Merge gate (optional — enable with branch protection)

By default, a failing or pending check does **not** block merging a PR. To require the `Lint` check to
pass before merge:

1. **Settings → Branches → Branch protection rules** → add/edit a rule for `main`.
2. Enable **Require status checks to pass before merging**, then select the **Lint** check (from
   `.github/workflows/lint.yml`) once it has run at least once on the repo.

To relax the gate later, remove the required check or disable the rule.

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
| test-writer | None — uses the host agent's own repo read/write access | Host's test-runner access (set `run_tests: false` to draft without executing) |

Per-skill setup: see each skill's `SETUP.md`.
