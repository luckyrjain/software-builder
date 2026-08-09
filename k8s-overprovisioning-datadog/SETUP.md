# Setup — k8s-overprovisioning-datadog


## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | Kubernetes MCP, Datadog MCP |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
This skill discovers Kubernetes and observability MCP tools by capability. It prefers Kubernetes MCP
for live cluster truth and uses Datadog as a per-capability fallback and for unique historical and
operational telemetry. A git provider MCP is an optional configuration fallback.

**Ambient discovery is intended** — this skill deliberately does **not** set `disable-model-invocation`
in its frontmatter, so the agent can auto-apply it when you ask "is `<service>` overprovisioned?" in
natural language (no slash command required). Leave it unset unless you want to make invocation
explicit-only.

## 1. Install the skill

From a clone of this repo:

```bash
make install
# or: bash scripts/install.sh k8s-overprovisioning-datadog
```

Restart Cursor after installing.

Workflow modules live under `workflow/` — the top-level [SKILL.md](SKILL.md) is a thin orchestrator.

### Claude Code

`make install` above already installs this skill for Claude Code too (default installs to both
editors). For Claude Code **only**: `make install-claude-k8s-overprovisioning`. Datadog MCP: install
the `datadog` Claude Code plugin and run its `ddsetup` skill instead of the Cursor Datadog plugin
(§ 3). GitLab/GitHub MCP (§ 6): same JSON entries, via `claude mcp add-json` instead of
`~/.cursor/mcp.json`. Full mapping:
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo (not via an installed copy)?
`.cursor/rules/k8s-overprovisioning-datadog.mdc` and
`.kiro/steering/k8s-overprovisioning-datadog.md` point Cursor/Kiro at
`k8s-overprovisioning-datadog/SKILL.md` without an install step.

## 2. Enable a Kubernetes MCP (preferred)

Configure a Kubernetes MCP with read-only access to the target clusters. The skill matches
capabilities rather than a server name, so any MCP may be used when it can read:

- Deployments/StatefulSets and container requests/limits
- Pods, restarts, OOM state, events, and current usage
- HPA, VPA, KEDA ScaledObject, PDB, and ResourceQuota resources
- Historical metrics only when it exposes the required window and aggregation

Do not grant write permissions for this workflow. The skill never calls `apply`, `patch`, `delete`,
`scale`, or rollout mutations even if a connected server exposes them.

At runtime the skill announces detected coverage. A point-in-time Metrics API sample is useful for
current health but does not replace seven-day historical evidence. If Kubernetes MCP is absent,
unreachable, unauthorized, or lacks a capability, Datadog fallback is attempted for that capability.

## 3. Enable Datadog MCP (fallback and historical telemetry)

1. Install the **Datadog** Cursor plugin (provides `plugin-datadog-datadog`).
2. On first use, run the **ddsetup** skill if Datadog MCP tools are missing.
3. Ensure these toolsets are enabled (via **ddtoolsets** if needed):
   - Metrics
   - Dashboards and notebooks
   - Monitors (recommended — `search_datadog_monitors` for active-alerts checks)
   - Cloud Cost Management (optional — for $/mo savings; `aws.cost.*` queries need `use_cloud_cost: true`)
   - Traces (optional — for HTTP/Kafka workload context)

**Note:** every Datadog MCP call this skill makes (`get_datadog_metric`, `get_widget`,
`search_datadog_dashboards`, `get_datadog_metric_context`) requires a `telemetry.intent` string. The
skill supplies it automatically — no setup needed — but a server that rejects calls missing
`telemetry` is expected behavior, not a misconfiguration.

Datadog is not globally required. When a history-capable Kubernetes MCP supplies sufficient evidence,
the assessment continues without Datadog and marks Datadog-only signals unavailable.

## 4. Datadog access

You need read access to:

- Kubernetes integration metrics (`kubernetes.*`, `kubernetes_state.*`)
- APM traces (optional, for traffic correlation)

Default analysis scope is `env:production` when the tag exists. Ask your platform team if you need a different org or site (`ddconfig` skill).

## 5. Shared dashboards

The skill resolves dashboards via `search_datadog_dashboards` by **exact title** (see
[workflow/orchestrator.md](workflow/orchestrator.md)). Bookmark these for manual checks. The Datadog **site** varies
(`app.datadoghq.com` vs `app.datadoghq.eu`) — confirm yours via **ddconfig** before building links.

| Dashboard (search by this title) | Purpose |
|----------------------------------|---------|
| Kubernetes Services Overview | Fleet utilization fast-path |
| Service SLI | Latency / error budget context |
| Kubernetes Cost by Service | Namespace cost ranking |
| EKS Service Capacity | Node / cluster headroom |

### Org-specific dashboard IDs (calibration)

Dashboard IDs are **org-specific** — do not copy IDs from another org's runbook into this repo.

1. Run `search_datadog_dashboards` with each title above in your Datadog org.
2. Record the returned dashboard ID in a **local note** or team runbook (not committed here).
3. Use IDs only as shortcuts when search confirms the title still matches.

Template for your org (fill in after calibration):

```markdown
| Dashboard title | Your org ID | Verified date |
|-----------------|-------------|---------------|
| Kubernetes Services Overview | `<id>` | YYYY-MM-DD |
| Service SLI | `<id>` | YYYY-MM-DD |
| Kubernetes Cost by Service | `<id>` | YYYY-MM-DD |
| EKS Service Capacity | `<id>` | YYYY-MM-DD |
```

Many services also have a `UHD - <service-name>` dashboard for deep dives.

## 6. Git provider MCP (GitLab or GitHub, optional)

Used as fallback for the **manifest vs running** drift check and for finding `VerticalPodAutoscaler`,
`PodDisruptionBudget`, and namespace `ResourceQuota` resources — reads Deployment YAML / Helm
`values.yaml` / Terraform directly from the repo. **Without it, nothing is blocked**: the skill falls
back to asking you to paste the relevant CPU/memory/replica values.

**This org is GitLab-centric** (`git remote get-url origin` → `gitlab.yourco.com` or your self-hosted host), so a GitLab MCP
is usually the right provider. The skill picks the provider that matches your `origin` remote, using
`get_file_contents` / `get_repository_tree` (or the GitHub MCP equivalents). Configure whichever
matches your repos:

- **GitLab MCP** — see [pr-review/SETUP.md](../pr-review/SETUP.md) § 1 (PAT, `api` scope) and § 3
  (`@zereight/mcp-gitlab` MCP config). The same server works for this skill.
- **GitHub MCP** — install the official GitHub MCP plugin (Cursor Settings → MCP → Add), authenticating
  with a fine-grained PAT scoped to **Contents: Read** + **Metadata: Read** on the repos holding your
  Helm charts / manifests. Store the token in a shell env var (`GITHUB_PERSONAL_ACCESS_TOKEN`) and
  reference it as `${GITHUB_PERSONAL_ACCESS_TOKEN}` in `mcp.json` — never commit the raw token.

**Linux only — `npx` path issue (Cursor-specific):** Cursor's bundled npm can fail with
`npm ERR! enoent … /usr/share/cursor/resources/app/resources/lib`. Fix by pointing `command` at your
system `npx`:

```bash
which npx   # e.g. /usr/bin/npx  or  /home/you/.nvm/versions/node/v20.x.x/bin/npx
```

Set `"command": "/usr/bin/npx"` (your actual path), or install the server globally and use its binary
directly. Restart Cursor after either fix.

**Lookup guardrails (manifest / VPA / PDB / ResourceQuota):**

1. **Ask first when path is known** — if the user named a chart path, Helm release, or subdirectory, go
   directly there; do not enumerate the whole repo.
2. **Bounded search** — at most **two** traversal attempts (e.g. `deployments/<svc>/`, then
   `helm/<svc>/` or `k8s/<namespace>/`). Prefer targeted `get_file_contents`; avoid full
   `get_repository_tree` at repo root unless the tree is small.
3. **Stop and ask** — if `get_repository_tree` returns **> 500 entries** at the searched path, or the
   manifest is not found after two attempts, stop and ask the user for the Deployment/Helm values path.
   Do not guess paths or invent YAML.
4. **Never block the analysis** — if git MCP is unavailable or lookup fails, ask the user to paste
   `resources.requests` / `resources.limits` / `replicas` and continue.

### Verify

The skill probes git provider tools at runtime. If none is available it prompts you to paste manifest
values manually — only the automated drift / VPA / PDB / ResourceQuota lookups are affected.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Kubernetes MCP missing / unauthorized | Continue with Datadog fallback; record missing Kubernetes capabilities in the source profile |
| Datadog 403 / missing tools | Continue with sufficient Kubernetes evidence; otherwise run **ddsetup** / **ddconfig**. A source-scoped failure blocks only when no alternative can supply required evidence |
| `npm ERR! enoent … /usr/share/cursor/resources/app/resources/lib` (Linux, GitLab/GitHub MCP via `npx`) | Cursor's bundled npm can't find its own lib path — set `"command"` to your system `npx` (`which npx`) or install the server globally; restart Cursor (§6 above) |
| Git provider MCP configured but manifest lookup fails / hangs (dangling) | Skill falls back to asking you to paste `resources.requests/limits` and replica counts — manifest drift, VPA, PDB, and ResourceQuota checks are skipped, not blocked |
| `get_repository_tree` returns >500 entries | Skill stops traversal and asks for the exact Deployment/Helm values path rather than enumerating the whole repo |
| Rate limit (429) from Datadog | Narrow the time window; skill notes the gap and does not tight-loop retry |
| CCM / cost toolset unavailable | Cost appendix skipped (`cost_skipped`); assessment continues on utilization only |
| Kubernetes MCP live state only and no Datadog | Report live observations; defer sizing dimensions requiring history; use `STOP_REASON: insufficient_metrics` when no sizing verdict is supportable |
| Neither source has sufficient evidence | Return a blocked assessment listing attempted sources and missing capabilities; never guess a recommendation |

## Framework conventions

- Index: [docs/skill-framework/README.md](../docs/skill-framework/README.md)
- Confidence: [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- Escalation: [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)
- Smoke tests: [smoke-test-conventions](../docs/skill-framework/shared/smoke-test-conventions.md)
- Examples: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md)
- Phases: [phase-glossary](../docs/skill-framework/shared/phase-glossary.md)
- Post-actions: [post-action-templates](../docs/skill-framework/shared/post-action-templates.md)
