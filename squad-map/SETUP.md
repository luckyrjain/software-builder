# squad-map — Setup

## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` in its frontmatter, so the agent
can auto-apply it when you ask about squad ownership, who owns a repo, or team mapping in natural
language — e.g. "who owns api-disbursement?" — as well as an explicit invocation. Leave it unset
unless you want invocation to require an explicit ask.

## Install

```bash
cd software-builder
make install-squad-map
```

Restart Cursor so the skill reloads.

### Claude Code

`make install-squad-map` above already installs this skill for Claude Code too (default installs to
both editors). For Claude Code **only**:

```bash
cd software-builder
make install-claude-squad-map
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md) for MCP config location
differences (GitLab/Datadog server entries are unchanged).

### Kiro / in-repo discovery

Working directly in this repo (not via an installed copy)? `.cursor/rules/squad-map.mdc` and
`.kiro/steering/squad-map.md` point Cursor/Kiro at `squad-map/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Target workspace | Single repo, monorepo, or sibling git repos |
| Git read access | `git remote`, optional `git log` for CODEOWNERS fallback |

**Optional MCP (recommended):**

| MCP | Purpose |
|-----|---------|
| GitLab (`user-gitlab`) | Repo → group prefix → org squad |
| Datadog (`plugin-datadog-datadog`) | Service → `team` tag |

Without MCP, skill continues — CODEOWNERS fallback with confidence capped at LOW.

**GitLab MCP** — same server as pr-review; if you've already set that skill up, reuse the same
`~/.cursor/mcp.json` entry:

```json
"gitlab": {
  "command": "npx",
  "args": ["-y", "@zereight/mcp-gitlab"],
  "env": {
    "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_PERSONAL_ACCESS_TOKEN}",
    "GITLAB_API_URL": "https://gitlab.example.com/api/v4",
    "GITLAB_READ_ONLY_MODE": "false"
  }
}
```

Full PAT creation steps: [pr-review/SETUP.md § Create a GitLab PAT](../pr-review/SETUP.md#create-a-gitlab-personal-access-token-pat).

**Datadog MCP** — configured via the Cursor Datadog plugin, not a JSON block. Run the **ddsetup** skill
if Datadog MCP tools are missing: [k8s-overprovisioning-datadog/SETUP.md § Enable Datadog MCP](../k8s-overprovisioning-datadog/SETUP.md#2-enable-datadog-mcp).

## Config files

Optional at workspace root (see [reference/config-schema.md](reference/config-schema.md)):

- `squad-map-config.yaml` — standalone config
- `domain-config.yaml` — `ownership:` block used when squad-map-config absent (domain-comprehension integration)

**"Optional" means the file is optional, not the value.** When GitLab MCP is available, the skill needs
`squad_path_segment` one way or another — either from one of the files above, or (if neither exists) it
stops and asks you for it interactively before mapping anything. See
[config-schema.md § Finding your own value](reference/config-schema.md#finding-your-own-value-before-writing-a-config-file)
before writing a config file — the worked example there uses someone else's namespace, not yours.

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against a small
multi-repo workspace. Phase 0 should announce MCP profile; Phase 1 should create `SQUAD_MAP.md`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| GitLab ❌ | Enable `user-gitlab` MCP; verify `GITLAB_API_URL` matches repo origin host |
| Datadog ❌ | Run **ddsetup** / **ddconfig**; verify `search_datadog_services` |
| All UNKNOWN, or every repo maps to the same squad | Wrong `squad_path_segment` — see [config-schema.md § Finding your own value](reference/config-schema.md#finding-your-own-value-before-writing-a-config-file) |
| No squad data | At least one MCP or CODEOWNERS file in repos |
