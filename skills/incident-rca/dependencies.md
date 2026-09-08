# External dependencies — incident-rca

## Required skill — `kubesense-mcp`

When KubeSense MCP (`user-kubesense`) is connected, install the official KubeSense MCP skill **before**
running Phase 1 log/trace/metrics queries.

| Field | Value |
|-------|-------|
| **Skill name** | `kubesense-mcp` |
| **Source** | [kubesense-ai/kubesense-mcp-skills](https://github.com/kubesense-ai/kubesense-mcp-skills) |
| **Install** | `make install-incident-rca-deps` or `bash scripts/install-incident-rca-deps.sh` |
| **Pin** | [skills-lock.json](skills-lock.json) — `kubesense-mcp` skill; optional `optionalExternal.incident-rca-correlator-cli.commitSha` when correlator installed |

### Nested skills (lazy-load from `kubesense-mcp`)

| Skill | RCA use |
|-------|---------|
| `kubesense-logs` | Phase 1 — error counts, raw logs, `body` text |
| `kubesense-apm` | Phase 1 — trace latency, error spans |
| `kubesense-metrics` | Phase 1 — pod restarts, CPU, PromQL |

**Do not** duplicate KubeSense query recipes in incident-rca — read the official skill first, then apply
incident-rca evidence mapping ([evidence-schema.md](reference/evidence-schema.md)).

## Optional escalation-target skills

These are **not** loaded or consumed by incident-rca itself — they are handoff targets named in `SKILL.md`'s
cross-skill escalation table and [cross-skill-escalation.md](../docs/skill-framework/shared/cross-skill-escalation.md).
incident-rca hands off a query/panel spec; installing and running the target skill is the responsibility
of whoever picks up the handoff, not this skill's Phase 0 capability check.

| Skill | Escalation trigger | Source |
|-------|--------------------|--------|
| `kubesense-alerts` | RCA recommends a monitor/alert fix | [kubesense-ai/kubesense-mcp-skills](https://github.com/kubesense-ai/kubesense-mcp-skills) |
| `kubesense-dashboards` | RCA needs a dashboard for soak/post-incident verification | [kubesense-ai/kubesense-mcp-skills](https://github.com/kubesense-ai/kubesense-mcp-skills) |

Not pinned in [skills-lock.json](skills-lock.json) — unlike `kubesense-mcp`, incident-rca never calls
these directly, so there is no version-compat surface to pin against.

### Verify installed

```bash
test -f ~/.cursor/skills/kubesense-mcp/SKILL.md \
  || test -f .agents/skills/kubesense-mcp/SKILL.md \
  || test -f ../.agents/skills/kubesense-mcp/SKILL.md
```

Phase 0 profile line: `kubesense-mcp ✅` or `kubesense-mcp ❌`.

### MCP server (still required)

Skills guide **how** to query; the MCP server provides tools. Configure in `~/.cursor/mcp.json`:

```json
"kubesense": {
  "url": "https://<kubesense-host>/mcp",
  "headers": { "Authorization": "Bearer ${env:KUBESENSE_API_KEY}" }
}
```

## Optional — SPL CLI fallback

When MCP `search-logs` with `body` fails after retry, use
[reference/kubesense-spl.md](reference/kubesense-spl.md) and `scripts/kubesense_logs.py`.

## Optional — correlator CLI

The hypothesis **correlator is a separate tool, not part of this repo.** When installed, record its commit
SHA in `skills-lock.json` → `optionalExternal.incident-rca-correlator-cli.commitSha` for reproducible
Phase 4 runs. Verify with `incident-rca --help`. Full setup: [SETUP.md](SETUP.md#external-dependency-optional-incident-rca-cli).

Without the correlator, Phase 4 falls back to [manual-scoring.md](reference/manual-scoring.md).
