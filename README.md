# ai-skills

Shared agent skills for the team — [Cursor Agent Skills](https://cursor.com/docs/agent/skills) natively,
plus cross-agent support for Claude Code, Kiro, and ChatGPT/Codex. See
[Install for your specific coding agent](#install-for-your-specific-coding-agent) below.

## Documentation

| Document | What it covers |
|----------|----------------|
| [docs/README.md](docs/README.md) | Full documentation index — every skill, file map, cross-skill routing |
| [docs/REPOSITORY.md](docs/REPOSITORY.md) | Repo layout, `Makefile`, `scripts/install.sh`, lint targets, git hooks |
| [CHANGELOG.md](CHANGELOG.md) | Per-skill change history |

Each skill has a human **`README.md`** (what it does) separate from **`SKILL.md`** (agent instructions).

## Skills

| Skill | Invoke | What it does | Docs |
|-------|--------|--------------|------|
| [pr-review](pr-review/) | `/pr-review` or "review this MR/PR …" | GitLab MR review: diff + Jira AC, severity findings, optional inline posts | [README](pr-review/README.md) · [SETUP](pr-review/SETUP.md) |
| [pr-gatekeeper](pr-gatekeeper/) | Push webhook (not human chat) | Auto-runs pr-review on every push to an open MR; posts inline when pr-review's own rules allow unattended posting | [README](pr-gatekeeper/README.md) · [SETUP](pr-gatekeeper/SETUP.md) |
| [k8s-overprovisioning-datadog](k8s-overprovisioning-datadog/) | "Is `<service>` overprovisioned?" | K8s DORA report: CPU/memory/replica verdicts, waste, cost via Datadog | [README](k8s-overprovisioning-datadog/README.md) · [SETUP](k8s-overprovisioning-datadog/SETUP.md) |
| [incident-rca](incident-rca/) | "RCA for … between …" | Multi-source post-incident RCA (Datadog, KubeSense, GitLab, Jenkins, Jira) | [README](incident-rca/README.md) · [SETUP](incident-rca/SETUP.md) |
| [incident-triage-agent](incident-triage-agent/) | Paging webhook (not human chat) | Page-fire triage doc + incident-resolved postmortem draft, composing incident-rca + squad-map | [README](incident-triage-agent/README.md) · [SETUP](incident-triage-agent/SETUP.md) |
| [domain-comprehension](domain-comprehension/) | "map the domain …", "bounded contexts for …" | Evidence-backed domain map: bounded contexts, data ownership, dependency graphs, business flows, exec summary | [README](domain-comprehension/README.md) · [SETUP](domain-comprehension/SETUP.md) |
| [squad-map](squad-map/) | "map squads …", "who owns …" | Repo-to-squad mapping: GitLab group hierarchy + Datadog team tags → `SQUAD_MAP.md` | [README](squad-map/README.md) · [SETUP](squad-map/SETUP.md) |
| [who-owns-x-bot](who-owns-x-bot/) | `/who-owns <name>` (Slack slash command; not ambient chat) | Single-shot "who owns X" Slack reply — thin wrapper delegating to squad-map | [README](who-owns-x-bot/README.md) · [SETUP](who-owns-x-bot/SETUP.md) |
| [mysql-to-postgres-sql](mysql-to-postgres-sql/) | "MySQL scrub …", "jdbc:postgresql …", "TIMESTAMPDIFF …" | Native SQL + JDBC rewrite for MySQL→PostgreSQL; scan gate, collection P0/P1 | [README](mysql-to-postgres-sql/README.md) · [SETUP](mysql-to-postgres-sql/SETUP.md) |
| [loop-task-implementer](loop-task-implementer/) | "implement issue 42 …", "work through these tasks …" | Autonomous multi-task loop: isolated Builder → two-lens independent Reviewer → adjudicated remediation → PR. Platform-neutral, no Datadog/GitLab/Jira MCP required | [README](loop-task-implementer/README.md) · [SETUP](loop-task-implementer/SETUP.md) |

## Install

```bash
git clone https://gitlab.example.com/lucky.jain/ai-skills.git
cd ai-skills
make install
```

Install a single skill:

```bash
make install-pr-review
make install-pr-gatekeeper
make install-k8s-overprovisioning
make install-incident-rca
make install-incident-triage-agent
make install-domain-comprehension
make install-squad-map
make install-who-owns-x-bot
make install-mysql-to-postgres-sql
make install-loop-task-implementer
```

`install-incident-rca` also installs the external **`kubesense-mcp`** skill dependency
(`make install-incident-rca-deps`). See [incident-rca/dependencies.md](incident-rca/dependencies.md).

Or run the script directly:

```bash
bash scripts/install.sh                    # all skills
bash scripts/install.sh pr-review          # one skill
bash scripts/install.sh pr-gatekeeper
bash scripts/install.sh k8s-overprovisioning-datadog
bash scripts/install.sh incident-rca
bash scripts/install.sh incident-triage-agent
bash scripts/install.sh domain-comprehension
bash scripts/install.sh squad-map
bash scripts/install.sh who-owns-x-bot
bash scripts/install.sh mysql-to-postgres-sql
bash scripts/install.sh loop-task-implementer
```

With no arguments, `install.sh` discovers every `*/SKILL.md` under the repo root and installs all of
them — so a newly-added 8th skill needs no script changes to be picked up by `make install`.

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

Run lint manually:

```bash
make lint               # all skill lint targets + lint-framework + shellcheck on scripts/*.sh
make lint-pr-review     # pr-review SKILL line limit, workflow frontmatter, anchors, pytest
make lint-pr-gatekeeper # pr-gatekeeper SKILL line limit, frontmatter, anchors, required files
make lint-k8s-skill     # k8s SKILL line limit, workflow frontmatter, report schema, anchors
make lint-incident-rca  # incident-rca SKILL line limit, workflow frontmatter, evidence JSON, anchors
make lint-incident-triage-agent # incident-triage-agent SKILL line limit, frontmatter, anchors, required files
make lint-domain-comprehension  # domain-comprehension SKILL line limit, frontmatter, anchors, manifest validator
make lint-squad-map             # squad-map SKILL line limit, frontmatter, anchors
make lint-who-owns-x-bot        # who-owns-x-bot SKILL line limit, frontmatter, anchors, required files
make lint-mysql-to-postgres-sql # mysql SKILL line limit, scan fixtures, pressure harness, shellcheck
make lint-loop-task-implementer # loop-task-implementer SKILL line limit, workflow frontmatter, required files, anchors
```

| Target | Checks |
|--------|--------|
| `lint-pr-review` | `SKILL.md` ≤ 180 lines; `workflow_version`/`phase`/`produces`/`consumes` frontmatter; dangling markdown anchors under `pr-review/`; `py_compile` + pytest for `diff-to-positions.py` |
| `lint-pr-gatekeeper` | `SKILL.md` ≤ 180 lines; `disable-model-invocation: true` set; workflow frontmatter; dangling anchors; required reference files |
| `lint-k8s-skill` | `SKILL.md` ≤ 150 lines; frontmatter; `report-schema.md` + templates; memory-sizing p95 rule; anchors |
| `lint-incident-rca` | `SKILL.md` ≤ 180 lines; frontmatter; valid `evidence.example.json`; causal-graph validator; anchors |
| `lint-incident-triage-agent` | `SKILL.md` ≤ 180 lines; `disable-model-invocation: true` set; workflow frontmatter; dangling anchors; required reference files |
| `lint-domain-comprehension` | `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; `templates/manifest.yaml` validator + pytest; pressure harness |
| `lint-squad-map` | `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; required reference files; pytest |
| `lint-who-owns-x-bot` | `SKILL.md` ≤ 180 lines; `disable-model-invocation: true` set; workflow frontmatter; dangling anchors; required reference files |
| `lint-mysql-to-postgres-sql` | `SKILL.md` ≤ 180 lines; workflow frontmatter; required references; scan fixtures + pressure harness; shellcheck on scan scripts |
| `lint-loop-task-implementer` | `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; required files (`SETUP.md`/`README.md`/`examples.md`/`report-template.md`/`reference/*`) |
| `lint-framework` | shared `docs/skill-framework/` docs present; required sections; SETUP.md links; metadata footer examples parse; every skill has a `.cursor/rules/*.mdc` + `.kiro/steering/*.md` discovery file |

Full detail: [docs/REPOSITORY.md](docs/REPOSITORY.md).

## CI

GitLab CI runs `make lint` on merge requests and the default branch (see [`.gitlab-ci.yml`](.gitlab-ci.yml)).
The job needs a project runner with `make`, `python3`, `pytest`, `shellcheck`, and **`ripgrep` (`rg`)** on the host (shell executor)
or a Docker/Linux runner (deps installed via `apt-get` in the pipeline).

## Configure MCP

| Skill | MCP servers | Setup |
|-------|-------------|-------|
| pr-review | GitLab (required), Jira (optional) | [pr-review/SETUP.md](pr-review/SETUP.md) |
| pr-gatekeeper | None of its own — delegates to pr-review | [pr-gatekeeper/SETUP.md](pr-gatekeeper/SETUP.md) |
| k8s-overprovisioning-datadog | Datadog | [k8s-overprovisioning-datadog/SETUP.md](k8s-overprovisioning-datadog/SETUP.md) |
| incident-rca | Datadog, KubeSense, GitLab, Jenkins, Jira (+ optional correlator CLI) | [incident-rca/SETUP.md](incident-rca/SETUP.md) |
| incident-triage-agent | None of its own — delegates to incident-rca + squad-map | [incident-triage-agent/SETUP.md](incident-triage-agent/SETUP.md) |
| domain-comprehension | GitLab (optional, Session 0b via squad-map), Datadog (optional, P2b runtime validation) | [domain-comprehension/SETUP.md](domain-comprehension/SETUP.md) |
| squad-map | GitLab, Datadog (optional; CODEOWNERS fallback when both absent) | [squad-map/SETUP.md](squad-map/SETUP.md) |
| who-owns-x-bot | None of its own — delegates to squad-map | [who-owns-x-bot/SETUP.md](who-owns-x-bot/SETUP.md) |
| mysql-to-postgres-sql | None (code scan + rewrite) | Datadog (optional; post-cutover APM) — [mysql-to-postgres-sql/SETUP.md](mysql-to-postgres-sql/SETUP.md) |
| loop-task-implementer | None (uses the host agent's own repo/git access, not an MCP server) | [loop-task-implementer/reference/mcp-capabilities.md](loop-task-implementer/reference/mcp-capabilities.md) |

---

## Usage (pr-review)

**GitLab merge request review** — invoke with `/pr-review` or natural language (e.g. "review this MR …",
"review !482"). GitLab MRs only (not GitHub). The skill resolves the target MR from what you type, loads
Jira context when a ticket is linked, and posts severity-labelled comments when GitLab MCP write tools are
configured (see [SETUP.md](pr-review/SETUP.md)).

Auto-invokes from natural-language asks when the request clearly targets a GitLab MR — see
[pr-review/SETUP.md](pr-review/SETUP.md) for why `disable-model-invocation` is left unset.

Common forms:

```
/pr-review https://gitlab.example.com/lucky.jain/ai-skills/-/merge_requests/1
review this pr https://gitlab.example.com/lucky.jain/ai-skills/-/merge_requests/1
/pr-review !482 in backend/payments
review this MR !482
/pr-review                       # current branch's MR, or pick from open MRs
review and post !482             # posts after confirmation (see note below)
review !482, focus on migrations # narrows dimensions; security still applied
re-review !482                   # incremental re-review after new commits
list open MRs                    # table only, no review until you pick one
```

`review and post …` skips the confirmation gate **only** when the posting mode is `full` or
`summary-only` and the MR is not a draft; `general-only` and draft MRs always require confirmation.

In a **multi-repo workspace**, open MRs are listed across all GitLab repos unless you pass an explicit
URL or `!IID in group/repo`.

**The full invocation table and edge cases** (draft MRs, fork MRs, large diffs, re-runs, posting modes)
live in [pr-review/examples.md](pr-review/examples.md).

### What you get (pr-review)

- Full review in chat (findings table, verdict, pipeline status)
- Optional GitLab posts: inline threads on diff lines + summary note (depends on MCP — see SETUP.md)
- Jira acceptance-criteria check when a ticket key is found in the MR title, branch, labels, or links

---

## Usage (pr-gatekeeper)

A GitLab push webhook invokes this skill with a structured payload — it does **not** auto-invoke from
ambient chat (`disable-model-invocation: true`). A human asking to review an MR routes to **pr-review**
directly (see [pr-gatekeeper/SETUP.md](pr-gatekeeper/SETUP.md)).

### Examples

| Webhook sends | What happens |
|------------------|----------------|
| Push to MR !482, project authorized, `full`/`summary-only` mode, non-draft | pr-review posts inline, no confirmation prompt (pr-review's own skip condition met) |
| Push to MR !482, `general-only` mode or draft MR | pr-review always holds — routed to notification instead |
| Push to MR !482, project not authorized to auto-post | Same as above — held, routed to notification |

### What you get (pr-gatekeeper)

- Whatever pr-review itself produces — this skill adds no review logic of its own
- A routed notification (reusing pr-review's own manual-notify template) whenever pr-review's own rules
  mean this push can't auto-post

---

## Usage (k8s-overprovisioning-datadog)

Attach the skill or ask in natural language. The agent queries Datadog for the last 7 days by default.

### Examples

| You say | What happens |
|---------|----------------|
| `Is example-service overprovisioned in production?` | Resolves `kube_deployment`, compares CPU/memory requests vs usage, checks HPA and throttling |
| `Review K8s resource utilization for payment-service` | Full report with per-pod breakdown and recommendations |
| `What cost could we save right-sizing payment-service?` | Waste estimate plus monthly $ savings and prioritized recommendations |

### What you get (k8s-overprovisioning-datadog)

A **Deployment Optimization Readiness Assessment (DORA — not the DevOps Research & Assessment
metrics)**, not just a rightsizing number:

- **Verdict per dimension** — CPU, memory, and replicas each judged separately: overprovisioned /
  right-sized / mixed / **mixed / cyclic** / underprovisioned
- **Optimization readiness checklist** — what telemetry is present vs missing
- **Decision confidence (0–1)** on every recommendation, not just telemetry quality
- **Estimated waste** in cores and GiB; **cost progression** (reserved CPU → node count → cloud cost)
- **Monthly $ savings** labelled observed (CCM) / estimated / resource-only — never invented
- **Rollback triggers** and staged rollout for every replica/HPA change
- **SLO correlation** — ties each change to p99 latency, error rate, and domain SLAs
- Kafka consumer-lag / partition validation and burst guards for event-driven services
- Links to relevant Datadog dashboards (org-specific IDs, with search fallback)

Auto-invokes from natural-language asks (no slash command) — see why `disable-model-invocation` is left
unset in [k8s-overprovisioning-datadog/SETUP.md](k8s-overprovisioning-datadog/SETUP.md).

---

## Usage (incident-rca)

Attach the skill or ask in natural language. Needs MCP servers (Datadog/KubeSense + GitLab/Jenkins/Jira),
the **`kubesense-mcp`** external skill when using KubeSense ([dependencies.md](incident-rca/dependencies.md)),
and an **optional** hypothesis-correlator CLI. The CLI is a separate tool — the skill works without it
via a manual-scoring fallback. See the
[external dependency section](incident-rca/SETUP.md#external-dependency-optional-incident-rca-cli) in
[SETUP.md](incident-rca/SETUP.md).

### Examples

| You say | What happens |
|---------|----------------|
| `RCA for neo-disbursement-service 2026-06-28 14:00–16:00 UTC — 5xx on transfer-money` | Service-scoped observability + change correlation + Jira |
| `Root cause analysis last Tuesday 2–4pm — Kafka consumer lag` | Symptom-scoped org-wide discovery → top services → correlate |
| `RCA for INC-4521` | Jira-anchored window; full multi-source investigation |

### What you get (incident-rca)

- Executive summary with primary hypothesis and confidence (HIGH / MEDIUM / LOW / UNKNOWN)
- Unified timeline (deploys/change events, error spikes, tickets, infra signals)
- Evidence table with deep links
- Alternate + ruled-out hypotheses and an explicit gaps / next-steps section
- Markdown report via the optional `incident-rca` CLI, or built from the template + manual scoring when
  the CLI is absent

Auto-invokes from natural-language asks (no slash command) — see why `disable-model-invocation` is left
unset in [incident-rca/SETUP.md](incident-rca/SETUP.md).

---

## Usage (incident-triage-agent)

A PagerDuty/Opsgenie webhook invokes this skill with a structured payload — it does **not** auto-invoke
from ambient chat (`disable-model-invocation: true`). A human asking for an RCA or ownership lookup
routes to **incident-rca** / **squad-map** directly (see
[incident-triage-agent/SETUP.md](incident-triage-agent/SETUP.md)).

### Examples

| Webhook sends | What happens |
|-------------------|----------------|
| `event_type: page_triggered` | Fast, 30-min-window incident-rca run + squad-map ownership → on-call triage doc |
| `event_type: incident_resolved` | Full-window, full-thoroughness incident-rca run + squad-map ownership → postmortem draft with pre-assigned follow-up owners |

### What you get (incident-triage-agent)

- **Triage:** likely cause (or "no defensible root cause"), owning team (or UNKNOWN), gaps, pointer to
  the full RCA
- **Postmortem:** incident-rca's full report, unedited except for squad-map owner-column substitution in
  its own Corrective/Preventive/Post-RCA-actions tables

---

## Usage (domain-comprehension)

Attach the skill or ask in natural language. Needs a workspace with source code and the
`understand-anything` toolchain (Node ≥ 22); GitLab and Datadog MCP are optional enrichments
(see [domain-comprehension/SETUP.md](domain-comprehension/SETUP.md)).

### Examples

| You say | What happens |
|---------|----------------|
| `Map the lending domain across these repos` | Full comprehension run: Session 0 → P0…P5, evidence-backed deliverables |
| `What are the bounded contexts and who owns the data?` | `BOUNDED_CONTEXTS.md` + `DATA_OWNERSHIP.md` with per-conclusion evidence and confidence |
| `Resume the domain comprehension` | Reads `manifest.yaml` and continues from the last incomplete phase |

### What you get (domain-comprehension)

- `EXEC_SUMMARY.md` — five questions answered with overall confidence
- Bounded contexts, data ownership, dependency graph (4 architecture views), business flows, state machines
- `RISK_MAP.md` (top architecture smells), `UNKNOWNS.md` / `KNOWN_OMISSIONS.md` (no speculation)
- `manifest.yaml` — machine-readable completion state for deterministic resume

---

## Usage (squad-map)

Attach the skill or ask in natural language. Maps repos to GitLab org squads and Datadog runtime teams
(see [squad-map/SETUP.md](squad-map/SETUP.md)).

### Examples

| You say | What happens |
|---------|----------------|
| `Map squads for repos in /Projects — org acme, segment 2` | Discovers repos → GitLab + Datadog MCP → `SQUAD_MAP.md` |
| `Who owns api-disbursement?` | Single-repo lookup with confidence and evidence |
| `Refresh squad map` | Re-queries MCP even if `SQUAD_MAP.md` exists |

### What you get (squad-map)

- **`SQUAD_MAP.md`** — per-repo GitLab squad, Datadog team, confidence, evidence
- Conflicts table when org squad ≠ runtime team
- Summary in chat: mapped count, confidence breakdown, conflict count

Auto-invokes from natural-language asks — see [squad-map/SETUP.md](squad-map/SETUP.md).

---

## Usage (who-owns-x-bot)

A Slack slash-command handler invokes this skill with a structured `query` — it does **not** auto-invoke
from ambient chat (`disable-model-invocation: true`). A human asking "who owns X" in an interactive
session routes to **squad-map** directly (see [who-owns-x-bot/SETUP.md](who-owns-x-bot/SETUP.md)).

### Examples

| Caller sends | What happens |
|----------------|----------------|
| `query: api-disbursement` | Delegates to squad-map → one Slack reply: squad + confidence + evidence |
| `query: legacy-ledger` (known GitLab/Datadog conflict) | Ambiguous reply — both squads listed, no silent pick |
| `query:` (empty) | Usage-hint reply, no squad-map lookup |

### What you get (who-owns-x-bot)

- One Slack message — Resolved, Ambiguous, or Unknown (never a fabricated squad name)
- No file written by this skill (squad-map may still write/update its own `SQUAD_MAP.md`)

---

## Usage (mysql-to-postgres-sql)

Attach the skill or ask in natural language. Scans a repo for MySQL-only SQL dialect and rewrites it
for PostgreSQL during a `jdbc:mysql` → `jdbc:postgresql` cutover. No MCP required — pure static
scan/rewrite via ripgrep (needs PCRE2 support: `rg --pcre2-version`).

### Examples

| You say | What happens |
|---------|----------------|
| `Scan this repo for MySQL dialect before the PG cutover` | Runs `scripts/scan-mysql-dialect.sh`, reports hits with file:line |
| `Migrate this service's native SQL to PostgreSQL` | Per-service inventory → scan → rewrite → datasource config → verify → merge gate |
| `Rewrite TIMESTAMPDIFF and DATE_FORMAT calls for PG` | Applies `reference/function-translations.md` mappings |

### What you get (mysql-to-postgres-sql)

- Scan gate result (exit 0/1) with exact file:line hits, or a clean pass
- Rewritten SQL/JDBC config following `reference/function-translations.md` and `reference/migration-edge-cases.md`
- `MIGRATION_STATUS.yaml` + `templates/SERVICE_PG_MIGRATION.md` per-service deliverable
- Escalates to **pr-review** for the migration MR and to **incident-rca** on a cutover regression

Auto-invokes from natural-language asks — see [mysql-to-postgres-sql/SETUP.md](mysql-to-postgres-sql/SETUP.md).

---

## Usage (loop-task-implementer)

Attach the skill or ask in natural language — platform-neutral, works the same in Cursor,
ChatGPT/Codex, Claude Code, or Kiro. Takes one or more tasks from requirements to a verified,
PR-ready state: isolated Builder implements, two independent Reviewer lenses (Safety/State and
Contracts/Operations) each run in a fresh context, findings are adjudicated with evidence, and the
Orchestrator only completes the repository action when explicitly authorized.

### Examples

| You say | What happens |
|---------|----------------|
| `Use loop-task-implementer to complete the next task.` | Discovers repo policy, selects one eligible task, dispatches a fresh Builder |
| `Implement issue 42, review it deeply, fix findings, and open a PR.` | Full loop: Builder → Lens A/B → adjudicate → remediate → PR |
| `Work through these tasks one by one and stop when each is ready to merge.` | Repeats the loop per task, stopping at `HUMAN_ACTION_REQUIRED` unless autonomous merge is authorized |

### What you get (loop-task-implementer)

- A completion report per task (task/repo, branch/PR, lens statuses, accepted/contested findings,
  authoritative checks, completion state, exact human action required if any) — see
  [loop-task-implementer/report-template.md](loop-task-implementer/report-template.md)
- Never merges without explicit authorization — `autonomous_merge_authorized` defaults to `false`
- No Datadog/GitLab/Jira MCP dependency; see
  [loop-task-implementer/reference/mcp-capabilities.md](loop-task-implementer/reference/mcp-capabilities.md)
  for what it needs from the host agent instead

Setup, cross-agent install paths, and the full role-prompt reference:
[loop-task-implementer/SETUP.md](loop-task-implementer/SETUP.md).
