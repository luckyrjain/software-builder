# MCP Setup — Incident RCA

## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` in its frontmatter, so the agent
can auto-apply it when you ask "what caused the incident between …?" in natural language (no slash
command required). Leave it unset unless you want invocation to be explicit-only.

## External skill dependency — `kubesense-mcp`

Required when KubeSense MCP is connected. Installed automatically with `make install-incident-rca`.

```bash
make install-incident-rca-deps
# or: bash scripts/install-incident-rca-deps.sh
```

Details: [dependencies.md](dependencies.md) · pin: [skills-lock.json](skills-lock.json).

The agent must **read `kubesense-mcp` and `kubesense-logs`** before Phase 1 KubeSense queries
(discovery-first, 15–30 min windows, `search-logs` with `body` field).

## External dependency (optional) — `incident-rca` CLI

The hypothesis **correlator is a separate tool, not part of this repo.** The skill works **without**
it via a manual fallback ([reference/manual-scoring.md](reference/manual-scoring.md)) — the CLI only
automates ranking and base-report generation.

**Detect it:**

```bash
incident-rca --help        # exit 0 + usage  → CLI available (Phase 4 uses it)
                           # command not found → use manual scoring, label the report's Gaps section
```

**Install it (only if your team distributes it):**

```bash
cd /path/to/incident-rca   # the separate correlator repo, NOT this skills repo
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"    # requires Python ≥ 3.11
incident-rca --help
```

If you do not have the correlator, **skip this** — Phase 4 falls back to manual scoring and the report
notes the gap. Do not attempt to build a correlator from scratch to satisfy the skill.

## Cursor skill install

```bash
cd software-builder
make install-incident-rca
# Restart Cursor
```

### Claude Code

`make install-incident-rca` above already installs this skill for Claude Code too (default installs
to both editors). For Claude Code **only**:

```bash
cd software-builder
make install-claude-incident-rca
```

MCP servers (§ below): same JSON entries, via `.mcp.json` / `claude mcp add-json` instead of
`~/.cursor/mcp.json`. Datadog: use the `datadog` Claude Code plugin's `ddsetup` skill instead of the
Cursor Datadog plugin. Full mapping: [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo (not via an installed copy)? `.cursor/rules/incident-rca.mdc` and
`.kiro/steering/incident-rca.md` point Cursor/Kiro at `incident-rca/SKILL.md` without an install step.

## Minimum viable setup

This skill lists 5 MCP servers below plus an external skill and an optional CLI — that's the full
picture, not the starting point. You don't need all of it for a first, real RCA:

- **Datadog + GitLab alone** gets you a working RCA at **MEDIUM** confidence (deploy correlation +
  error/metric signals) — this is the fastest path to a first real result.
- **Add KubeSense** if your org's logs live there instead of Datadog, or to push confidence toward
  HIGH with a second observability source.
- **Add Jenkins + Jira** for deploy-job attribution and ticket context — genuinely useful, not required
  for a first run.
- **Skip the correlator CLI entirely** — manual scoring ([reference/manual-scoring.md](reference/manual-scoring.md))
  reproduces its ranking by hand; most teams never install it.

Configure Datadog + GitLab first, run one real RCA, then add the rest as you find you need it.

**Before adopting elsewhere:** [reference/org-profiles.md](reference/org-profiles.md) documents real,
org-specific guardrails (not illustrative examples) for the org this skill was built against —
adopters at a different org should add their own section there rather than inherit those STOP rules
as-is.

## MCP servers

Configure in **Cursor Settings → MCP**. All are read-only for RCA.

| Server | ID | Required | Purpose |
|--------|-----|----------|---------|
| Datadog | `plugin-datadog-datadog` | Recommended | Logs, traces, metrics, RUM, change events, incidents |
| KubeSense | `user-kubesense` | Optional | Logs/traces/metrics (fallback or supplement) |
| GitLab | `user-gitlab` | Recommended | Merged MRs, commits, diffs |
| Jenkins | `user-jenkins` | Recommended | Prod build SHA + change sets |
| Jira | `user-Atlassian-MCP-Server` | Optional | Incident tickets, human context |

**KubeSense log bodies (acme):** read the official **`kubesense-mcp`** skill first. Use MCP
`search-logs` with `body` in `fields` (15–30 min windows). If MCP body fetch fails after one retry,
run `python3 incident-rca/scripts/kubesense_logs.py <workload>` (or `make kubesense-errors`). See
[dependencies.md](dependencies.md) and [reference/kubesense-spl.md](reference/kubesense-spl.md).

At least **one observability source** (Datadog or KubeSense) is required.

### Datadog first-time setup

If Datadog MCP tools are missing, run the **ddsetup** skill before investigating; on a 403, run
**ddconfig** to fix the site/API key. Every Datadog call requires a `telemetry.intent` string (the
skill supplies it) — a server rejecting calls without `telemetry` is expected behavior, not a
misconfiguration. `load_datadog_skill` for `datadog/logs`, `datadog/traces`, `datadog/metrics` when
querying.

### Shared dashboards

Resolve dashboards via `search_datadog_dashboards` by **exact title** (see
[reference/query-investigation.md](reference/query-investigation.md) §Step 2). Bookmark these for
manual checks. The Datadog **site** varies (`app.datadoghq.com` vs `app.datadoghq.eu`) — confirm
yours via **ddconfig** before building links.

| Dashboard (search by this title) | Purpose |
|----------------------------------|---------|
| `database-slow-query` | Slow DB queries — top signatures, latency, client attribution during DB saturation / `query_governance` RCA |

**Fast-path ID** `uwk-w92-5ys` — use only when `search_datadog_dashboards` confirms the title:
`https://app.datadoghq.com/dashboard/uwk-w92-5ys/database-slow-query` (set time window from RCA
inputs; do not copy incident-specific `from_ts` / `to_ts` params).

Dashboard IDs are **org-specific** — do not copy IDs from another org's runbook into this repo.
Calibrate in a local note:

```markdown
| Dashboard title | Your org ID | Verified date |
|-----------------|-------------|---------------|
| database-slow-query | `uwk-w92-5ys` | YYYY-MM-DD |
```

### Jira

```json
"atlassian": {
  "url": "https://mcp.atlassian.com/v1/mcp"
}
```

Official Rovo server, OAuth on first use. Jira Server/DC: use
[`sooperset/mcp-atlassian`](https://github.com/sooperset/mcp-atlassian) instead. Full PAT/OAuth detail:
[pr-review/SETUP.md § Jira / Atlassian](../pr-review/SETUP.md#jira-atlassian).

Run `getAccessibleAtlassianResources` once per session to obtain `cloudId`. If more than one Atlassian
server is connected, probe each and use the one that owns the incident project. Adjust JQL project keys
(`INC`, `OPS`) in [reference/query-playbook.md](reference/query-playbook.md) to match your org.

### GitLab

```json
"gitlab": {
  "command": "npx",
  "args": ["-y", "@zereight/mcp-gitlab"],
  "env": {
    "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_PERSONAL_ACCESS_TOKEN}",
    "GITLAB_API_URL": "https://gitlab.example.com/api/v4",
    "GITLAB_READ_ONLY_MODE": "true"
  }
}
```

`GITLAB_READ_ONLY_MODE` can stay `"true"` here — incident-rca never posts, only reads merged MRs, commits,
and diffs. Same server as pr-review/squad-map — PAT creation steps:
[pr-review/SETUP.md § Create a GitLab PAT](../pr-review/SETUP.md#create-a-gitlab-personal-access-token-pat).
Ensure the token (or plugin auth) can read merge requests and commits for affected projects. If more
than one GitLab MCP server is connected, the skill matches the affected repo's host to the right
server. (There is **no** `list_deployments` tool — deploy timelines come from Datadog change stories,
Jenkins, and merged MRs.)

### Jenkins

```json
"jenkins": {
  "command": "npx",
  "args": ["-y", "@mister-good-deal/host-mcp-jenkins"],
  "env": {
    "JENKINS_URL": "https://jenkins.example.com",
    "JENKINS_USER": "your-username",
    "JENKINS_API_TOKEN": "${JENKINS_API_TOKEN}"
  }
}
```

Generate the API token from your Jenkins user profile (**Jenkins → your name → Configure → API
Token**), store it as a shell env var the same way as the GitLab PAT — never paste it raw into
`mcp.json`. Ensure the MCP can reach prod deploy jobs. Use `findJobsWithScmUrl` to map repos → jobs.
The skill never triggers or updates builds.

## Framework conventions

- Index: [docs/skill-framework/README.md](../docs/skill-framework/README.md)
- Confidence: [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- Escalation: [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)
- Smoke tests: [smoke-test-conventions](../docs/skill-framework/shared/smoke-test-conventions.md)
- Examples: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md)
- Phases: [phase-glossary](../docs/skill-framework/shared/phase-glossary.md)
- Post-actions: [post-action-templates](../docs/skill-framework/shared/post-action-templates.md)

## Verify connectivity

Ask in chat:

> Run Phase 0 MCP capability check for incident-rca

Expected: all configured servers listed with ✅ (and CLI ✅/❌). See
[reference/smoke-test.md](reference/smoke-test.md) for a full end-to-end check.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `incident-rca: command not found` | Expected if the optional correlator isn't installed — use manual scoring (report notes the gap), or install it per above |
| Datadog 403 / auth error | Run **ddsetup** / **ddconfig**; verify site + API key; retry (≤2×) |
| No observability data | Configure Datadog or KubeSense MCP; widen the time window |
| No deploy events | Check `get_change_stories` env/service; try Jenkins; widen the ±30 min padding |
| Empty Jira results | Verify `cloudId`; broaden JQL; search by symptom text |
| LOW confidence | Normal when only one source has data — list gaps explicitly (single source caps at MEDIUM) |
