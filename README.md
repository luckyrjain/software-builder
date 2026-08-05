# ai-skills

Shared [Cursor Agent Skills](https://cursor.com/docs/agent/skills) for the team.

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
| [k8s-overprovisioning-datadog](k8s-overprovisioning-datadog/) | "Is `<service>` overprovisioned?" | K8s DORA report: CPU/memory/replica verdicts, waste, cost via Datadog | [README](k8s-overprovisioning-datadog/README.md) · [SETUP](k8s-overprovisioning-datadog/SETUP.md) |
| [incident-rca](incident-rca/) | "RCA for … between …" | Multi-source post-incident RCA (Datadog, KubeSense, GitLab, Jenkins, Jira) | [README](incident-rca/README.md) · [SETUP](incident-rca/SETUP.md) |
| [domain-comprehension](domain-comprehension/) | "map the domain …", "bounded contexts for …" | Evidence-backed domain map: bounded contexts, data ownership, dependency graphs, business flows, exec summary | [README](domain-comprehension/README.md) · [SETUP](domain-comprehension/SETUP.md) |
| [squad-map](squad-map/) | "map squads …", "who owns …" | Repo-to-squad mapping: GitLab group hierarchy + Datadog team tags → `SQUAD_MAP.md` | [README](squad-map/README.md) · [SETUP](squad-map/SETUP.md) |
| [mysql-to-postgres-sql](mysql-to-postgres-sql/) | "MySQL scrub …", "jdbc:postgresql …", "TIMESTAMPDIFF …" | Native SQL + JDBC rewrite for MySQL→PostgreSQL; scan gate, collection P0/P1 | [README](mysql-to-postgres-sql/README.md) · [SETUP](mysql-to-postgres-sql/SETUP.md) |

## Install

```bash
git clone https://gitlab.example.com/lucky.jain/ai-skills.git
cd ai-skills
make install
```

Install a single skill:

```bash
make install-pr-review
make install-k8s-overprovisioning
make install-incident-rca
make install-domain-comprehension
make install-squad-map
make install-mysql-to-postgres-sql
```

`install-incident-rca` also installs the external **`kubesense-mcp`** skill dependency
(`make install-incident-rca-deps`). See [incident-rca/dependencies.md](incident-rca/dependencies.md).

Or run the script directly:

```bash
bash scripts/install.sh                    # all skills
bash scripts/install.sh pr-review          # one skill
bash scripts/install.sh k8s-overprovisioning-datadog
bash scripts/install.sh incident-rca
bash scripts/install.sh domain-comprehension
bash scripts/install.sh squad-map
bash scripts/install.sh mysql-to-postgres-sql
```

By default, all targets copy skill directories to **both** `~/.cursor/skills/` and
`~/.claude/skills/`. **Restart Cursor** and start a new Claude Code session after installing.

To install for **only one editor**, use `--agent`:

```bash
bash scripts/install.sh --agent cursor            # Cursor only
bash scripts/install.sh --agent claude-user       # Claude Code only, all skills → ~/.claude/skills/
make install-claude                               # same, via Makefile
make install-claude-pr-review
make install-claude-k8s-overprovisioning
make install-claude-incident-rca
make install-claude-domain-comprehension
make install-claude-squad-map
make install-claude-mysql-to-postgres-sql
```

Or `--agent claude-project --target-dir <repo>` to install into one project's `.claude/skills/` only.
Details: [docs/skill-framework/shared/claude-code-setup.md](docs/skill-framework/shared/claude-code-setup.md).

## Develop

One-time setup — installs Python dev deps (`requirements.txt`: pytest, PyYAML) and the shellcheck pre-commit hook:

```bash
make setup
```

Run lint manually:

```bash
make lint               # all skill lint targets + shellcheck on scripts/*.sh
make lint-pr-review     # pr-review SKILL line limit, workflow frontmatter, anchors, pytest
make lint-k8s-skill     # k8s SKILL line limit, workflow frontmatter, report schema, anchors
make lint-incident-rca  # incident-rca SKILL line limit, workflow frontmatter, evidence JSON, anchors
make lint-domain-comprehension  # domain-comprehension SKILL line limit, frontmatter, anchors, manifest validator
make lint-squad-map             # squad-map SKILL line limit, frontmatter, anchors
make lint-mysql-to-postgres-sql # mysql SKILL line limit, scan fixtures, pressure harness, shellcheck
```

| Target | Checks |
|--------|--------|
| `lint-pr-review` | `SKILL.md` ≤ 180 lines; `workflow_version` frontmatter; dangling markdown anchors under `pr-review/`; `py_compile` + pytest for `diff-to-positions.py` |
| `lint-k8s-skill` | `SKILL.md` ≤ 150 lines; frontmatter; `report-schema.md` + templates; memory-sizing p95 rule; anchors |
| `lint-incident-rca` | `SKILL.md` ≤ 180 lines; frontmatter; valid `evidence.example.json`; causal-graph validator (CG-01–CG-08); anchors |
| `lint-framework` | shared `docs/skill-framework/` docs present; required sections; SETUP.md links; metadata footer examples parse |
| `lint-domain-comprehension` | `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; `templates/manifest.yaml` validator + pytest |
| `lint-squad-map` | `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; required reference files |
| `lint-mysql-to-postgres-sql` | `SKILL.md` ≤ 180 lines; workflow frontmatter; required references; scan fixtures + pressure harness; shellcheck on scan scripts |

Full detail: [docs/REPOSITORY.md](docs/REPOSITORY.md).

## CI

GitLab CI runs `make lint` on merge requests and the default branch (see [`.gitlab-ci.yml`](.gitlab-ci.yml)).
The job needs a project runner with `make`, `python3`, `pytest`, `shellcheck`, and **`ripgrep` (`rg`)** on the host (shell executor)
or a Docker/Linux runner (deps installed via `apt-get` in the pipeline).

## Configure MCP

| Skill | MCP servers | Setup |
|-------|-------------|-------|
| pr-review | GitLab (required), Jira (optional) | [pr-review/SETUP.md](pr-review/SETUP.md) |
| k8s-overprovisioning-datadog | Datadog | [k8s-overprovisioning-datadog/SETUP.md](k8s-overprovisioning-datadog/SETUP.md) |
| incident-rca | Datadog, KubeSense, GitLab, Jenkins, Jira (+ optional correlator CLI) | [incident-rca/SETUP.md](incident-rca/SETUP.md) |
| domain-comprehension | GitLab (optional, Session 0b via squad-map), Datadog (optional, P2b runtime validation) | [domain-comprehension/SETUP.md](domain-comprehension/SETUP.md) |
| squad-map | GitLab, Datadog (optional; CODEOWNERS fallback when both absent) | [squad-map/SETUP.md](squad-map/SETUP.md) |
| mysql-to-postgres-sql | None (code scan + rewrite) | Datadog (optional; post-cutover APM) — [mysql-to-postgres-sql/SETUP.md](mysql-to-postgres-sql/SETUP.md) |

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
