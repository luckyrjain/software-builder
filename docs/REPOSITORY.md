# Repository guide

What the **ai-skills** repo contains, how to install skills, and how quality checks work.

## Layout

```
ai-skills/
├── README.md                 # Top-level install + usage (start here)
├── CHANGELOG.md              # Per-skill change history
├── Makefile                  # install + lint targets
├── docs/
│   ├── README.md             # Documentation index (this tree)
│   └── REPOSITORY.md         # This file
├── scripts/
│   └── install.sh            # Copies skill dirs → ~/.cursor/skills/ + ~/.claude/skills/ (default)
├── .githooks/
│   └── pre-commit            # shellcheck on staged scripts/*.sh
├── pr-review/                # GitLab MR review skill
├── incident-rca/             # Post-incident RCA skill
├── k8s-overprovisioning-datadog/  # K8s rightsizing / DORA skill
├── mysql-to-postgres-sql/    # MySQL → PostgreSQL native SQL migration skill
└── squad-map/                # Repo-to-squad ownership mapping
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
git clone https://gitlab-ee.mpokket.org/lucky.jain/ai-skills.git
cd ai-skills
make install          # all skills with a SKILL.md at repo root level
make install-pr-review
make install-k8s-overprovisioning
make install-incident-rca
make install-mysql-to-postgres-sql
```

`scripts/install.sh` copies the entire skill directory to **both** `~/.cursor/skills/<skill-name>/`
and `~/.claude/skills/<skill-name>/` by default, replacing any existing install at each. **Restart
Cursor** and start a new Claude Code session after installing.

Install one skill explicitly:

```bash
bash scripts/install.sh pr-review
bash scripts/install.sh k8s-overprovisioning-datadog
bash scripts/install.sh incident-rca
bash scripts/install.sh mysql-to-postgres-sql
```

With no arguments, `install.sh` discovers every `*/SKILL.md` under the repo root and installs each.

To install for only one editor, pass `--agent cursor` (Cursor only) or `--agent claude-user` (Claude
Code only, installs to `~/.claude/skills/`) — or use the `install-claude*` Makefile targets below for
the Claude-Code-only form. See
[docs/skill-framework/shared/claude-code-setup.md](skill-framework/shared/claude-code-setup.md).

## Makefile targets

| Target | What it does |
|--------|--------------|
| `make install` | Run `scripts/install.sh` for all skills |
| `make install-pr-review` | Install only `pr-review/` |
| `make install-k8s-overprovisioning` | Install only `k8s-overprovisioning-datadog/` |
| `make install-incident-rca` | Install only `incident-rca/` |
| `make install-mysql-to-postgres-sql` | Install only `mysql-to-postgres-sql/` |
| `make install-claude` | Run `scripts/install.sh --agent claude-user` for all skills |
| `make install-claude-<skill>` | Install only `<skill>/` for Claude Code (`pr-review`, `k8s-overprovisioning`, `incident-rca`, `domain-comprehension`, `squad-map`, `mysql-to-postgres-sql`) |
| `make lint` | Run all lint targets below + shellcheck on `scripts/*.sh` |
| `make lint-pr-review` | pr-review `SKILL.md` ≤ 180 lines; each `workflow/*.md` has `workflow_version` frontmatter; dangling markdown anchors; script pytest |
| `make lint-k8s-skill` | k8s `SKILL.md` ≤ 150 lines; workflow frontmatter; decision graph schema v3; render/markdown.md; dangling anchors; memory-sizing p95 rule; templates |
| `make lint-incident-rca` | incident-rca `SKILL.md` ≤ 180 lines; each `workflow/*.md` has `workflow_version` frontmatter; valid `evidence.example.json`; dangling anchors; causal-graph example validated (CG-01–CG-08) |
| `make lint-domain-comprehension` | domain-comprehension `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; `templates/manifest.yaml` validator + pytest |
| `make lint-squad-map` | squad-map `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; required reference files |
| `make lint-mysql-to-postgres-sql` | mysql `SKILL.md` ≤ 180 lines; workflow frontmatter; required references; scan fixtures + pressure harness; shellcheck on scan scripts |
| `make lint-framework` | shared `docs/skill-framework/` files present; required sections; SETUP.md links; metadata footer examples parse |
| `make setup-hooks` | Set `git config core.hooksPath .githooks` (shellcheck pre-commit) |

### lint-incident-rca

`incident-rca/SKILL.md` must stay at or under **180 lines**. Each file under `workflow/` must declare
`workflow_version`, `produces`, and `consumes` in YAML frontmatter. Validates `reference/evidence.example.json`
parses as JSON and checks markdown anchor links under `incident-rca/` (including `workflow/`).

### lint-pr-review

Requires **pytest** (`python3 -m pip install pytest`). `pr-review/SKILL.md` must stay at or under **180
lines**. Each file under `workflow/` must declare `workflow_version`, `produces`, and `consumes` in YAML
frontmatter. Tests live in `pr-review/tests/` and cover diff position mapping for inline GitLab comments.

### lint-k8s-skill

Enforces a thin orchestrator: `k8s-overprovisioning-datadog/SKILL.md` must stay at or under **150 lines**.
Each file under `workflow/` must declare `workflow_version`, `produces`, and `consumes` in YAML frontmatter.
Also validates internal markdown link anchors and ensures the memory sizing section in `thresholds.md` does not positively assert p95 (memory uses a peak proxy, not p95).

### lint-domain-comprehension

Requires **pytest** (`python3 -m pip install pytest`). `domain-comprehension/SKILL.md` must stay at or under **180 lines**. Each file under `workflow/` must declare `workflow_version`, `produces`, and `consumes` in YAML frontmatter. Validates `templates/manifest.yaml` parses and the manifest validator (`scripts/validate_manifest_yaml.py`) runs successfully via pytest in `tests/test_validate_manifest.py`. Checks markdown anchor links under `domain-comprehension/` (including `workflow/` and `reference/`).

### lint-mysql-to-postgres-sql

Requires **ripgrep** (`rg`) with PCRE2 on the host running lint. `mysql-to-postgres-sql/SKILL.md` must stay at or under **180 lines**. Each file under `workflow/` must declare `workflow_version` frontmatter. Runs scan gate fixtures (`tests/fixtures/mysql-dialect/`), the pressure-test harness (`tests/run_pressure_tests.sh`), dangling anchor checks, and shellcheck on `scripts/scan-mysql-dialect.sh` and `scripts/scan-report.sh`.

## Git hooks

After `make setup-hooks`, the pre-commit hook runs **shellcheck** on any staged file under `scripts/*.sh`.
Uses local `shellcheck` or falls back to Docker (`koalaman/shellcheck-alpine:stable`).

## CI/CD

[`.gitlab-ci.yml`](../.gitlab-ci.yml) runs `make lint` on merge requests and pushes to the default branch.

| Requirement | Notes |
|-------------|--------|
| **Runner** | Project runner required (shared runners may be unavailable on self-hosted instances) |
| **Shell executor** | Host must have `make`, `python3`, `pytest`, `shellcheck`, `ripgrep` (`rg`) |
| **Docker executor** | Uses `python:3.12-slim`; `before_script` installs deps via `apt-get` (includes `ripgrep`) |
| **Untagged jobs** | Runner must accept untagged jobs unless you add matching `tags:` to the lint job |

### Shared runners (team recommendation)

Many self-hosted GitLab instances do not expose shared runners for personal projects. **For team repos,
prefer a group or instance runner** so MR pipelines are not tied to one developer's laptop.

| Option | When to use |
|--------|-------------|
| **Group runner** | **Recommended for teams** — ask platform/DevOps to attach a runner to the `lucky.jain` (or org) namespace; all projects in the group inherit it |
| **Instance runners** | Org-wide — admin enables under **Admin → CI/CD → Runners**; per-project **Enable shared runners** under **Settings → CI/CD → Runners** |
| **Project runner** | Solo or bootstrap — register on a team VM or workstation ([GitLab runner docs](https://docs.gitlab.com/runner/register/)); use a `glrt-` authentication token from **New project runner** (not the legacy `GR…` registration token) |

Keep the runner online for MR pipelines to run; an offline runner leaves jobs pending.

### Merge gate (optional — enable with reliable CI)

By default, merge is **not** blocked when CI fails or is pending (`only_allow_merge_if_pipeline_succeeds: false`).
Pipelines are informational until you enable the merge gate below.

**Enable only when a reliable shared or group runner is available** — a personal Mac runner going offline
would block the whole team.

1. **Settings → Merge requests → Merge checks** → enable **Pipelines must succeed**.
2. Or via API / project settings: set `only_allow_merge_if_pipeline_succeeds` to `true` on the project.

```bash
# Example (requires Maintainer + API token) — do not run until a group runner is online
curl --request PUT --header "PRIVATE-TOKEN: <token>" \
  "https://gitlab-ee.mpokket.org/api/v4/projects/<project_id>" \
  --data "only_allow_merge_if_pipeline_succeeds=true"
```

To disable the gate later, set the same field to `false`.

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
| incident-rca | ≥1 observability (Datadog or KubeSense) | GitLab, Jenkins, Jira; optional `incident-rca` CLI |
| k8s-overprovisioning-datadog | Datadog | Git provider (manifest drift) |
| mysql-to-postgres-sql | None | Datadog (optional; post-cutover APM verification) |

Per-skill setup: see each skill's `SETUP.md`.
