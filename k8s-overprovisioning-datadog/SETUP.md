# Setup — k8s-overprovisioning-datadog

This skill queries Kubernetes utilization metrics through the Datadog MCP server. A git provider MCP
(GitLab or GitHub) is optional and only needed for the manifest-vs-running drift check.

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

Workflow modules live under `workflow/` — the top-level [SKILL.md](SKILL.md) is a thin orchestrator (~42 lines).

### Claude Code

`make install` above already installs this skill for Claude Code too (default installs to both
editors). For Claude Code **only**: `make install-claude-k8s-overprovisioning`. Datadog MCP: install
the `datadog` Claude Code plugin and run its `ddsetup` skill instead of the Cursor Datadog plugin
(§ 2). GitLab/GitHub MCP (§ 5): same JSON entries, via `claude mcp add-json` instead of
`~/.cursor/mcp.json`. Full mapping:
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

## 2. Enable Datadog MCP

1. Install the **Datadog** Cursor plugin (provides `plugin-datadog-datadog`).
2. On first use, run the **ddsetup** skill if Datadog MCP tools are missing.
3. Ensure these toolsets are enabled (via **ddtoolsets** if needed):
   - Metrics
   - Dashboards and notebooks
   - Monitors (required — `search_datadog_monitors` for active-alerts check in workload analysis)
   - Cloud Cost Management (optional — for $/mo savings; `aws.cost.*` queries need `use_cloud_cost: true`)
   - Traces (optional — for HTTP/Kafka workload context)

**Note:** every Datadog MCP call this skill makes (`get_datadog_metric`, `get_widget`,
`search_datadog_dashboards`, `get_datadog_metric_context`) requires a `telemetry.intent` string. The
skill supplies it automatically — no setup needed — but a server that rejects calls missing
`telemetry` is expected behavior, not a misconfiguration.

## 3. Datadog access

You need read access to:

- Kubernetes integration metrics (`kubernetes.*`, `kubernetes_state.*`)
- APM traces (optional, for traffic correlation)

Default analysis scope is `env:production` when the tag exists. Ask your platform team if you need a different org or site (`ddconfig` skill).

## 4. Shared dashboards

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

## 5. Git provider MCP (GitLab or GitHub, optional)

Needed only for the **manifest vs running** drift check and for finding `VerticalPodAutoscaler`,
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

## Framework conventions

- Index: [docs/skill-framework/README.md](../docs/skill-framework/README.md)
- Confidence: [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- Escalation: [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)
- Smoke tests: [smoke-test-conventions](../docs/skill-framework/shared/smoke-test-conventions.md)
- Examples: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md)
- Phases: [phase-glossary](../docs/skill-framework/shared/phase-glossary.md)
- Post-actions: [post-action-templates](../docs/skill-framework/shared/post-action-templates.md)

