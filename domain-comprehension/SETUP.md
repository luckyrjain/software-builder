# domain-comprehension — Setup

## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` in its frontmatter, so the agent
can auto-apply it when you ask to map a domain, understand bounded contexts, or onboard into an
unfamiliar codebase in natural language — e.g. "map the lending domain across these repos", "what
are the bounded contexts here?" — as well as an explicit invocation. Leave it unset unless you want
invocation to require an explicit ask.

## Install

```bash
cd software-builder
make install-domain-comprehension
```

Restart Cursor so the skill reloads.

### Claude Code

`make install-domain-comprehension` above already installs this skill for Claude Code too (default
installs to both editors). For Claude Code **only**:

```bash
cd software-builder
make install-claude-domain-comprehension
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md) for MCP config location
differences (this skill's optional GitLab/Datadog enrichments use the same server entries).

### Kiro / in-repo discovery

Working directly in this repo (not via an installed copy)? `.cursor/rules/domain-comprehension.mdc`
and `.kiro/steering/domain-comprehension.md` point Cursor/Kiro at `domain-comprehension/SKILL.md`
without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Target workspace | Single repo, monorepo, or sibling git repos |
| understand-anything plugin | Recommended for P0.5 mechanical pass — see below |
| Node.js ≥ 22, pnpm ≥ 10 | For `/understand` bundled scripts — see below |
| Git read access | `git log`, branch/SHA per repo |

### understand-anything (recommended, not required)

A **separate Cursor Agent Skill**, not part of this repo. Install it via Cursor's skill marketplace
(search "understand" / "understand-anything"), or symlink `.cursor/skills/understand-anything` from a
local clone if your org distributes it that way — ask whoever set up your Cursor environment if neither
turns it up. Verify it's installed: `/understand --full` should appear as a command, or check for
`.cursor/skills/understand-anything/SKILL.md`.

**Skip it if you can't find it** — P0.5 mechanical analysis falls back to manual grep + `git log`
heuristics (lower confidence, slower, but it works). Nothing else in this skill is blocked by its
absence.

### Node.js version

`/understand`'s bundled scripts are ESM-only and use Node 22 features
(`--experimental-strip-types`, `fs.glob`) — most teams run Node 18/20 LTS, so check before you hit a
confusing failure mid-run:

```bash
node --version   # must be >= 22 for /understand; anything lower silently isn't the issue if it's absent entirely
```

If Node is too old, `/understand` fails with a syntax/runtime error partway through P0.5 rather than a
clean "skip." Either upgrade Node for this workspace (`nvm install 22`), or skip understand-anything
entirely per above — don't try to run it on an older Node and debug the failure.

**Optional MCP:**

| MCP | Purpose |
|-----|---------|
| GitLab + Datadog | Session 0b squad mapping via **squad-map** skill — [squad-map/SETUP.md](../squad-map/SETUP.md) |
| Datadog | P2b runtime dependency validation |
| KubeSense | P2b log-pattern evidence (runs alongside or independently of Datadog) |

Without MCP, skill continues — squad-map uses CODEOWNERS fallback; P2b runs on whichever of
Datadog/KubeSense is available, skipped only if both are missing.

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)
- [phase-glossary](../docs/skill-framework/shared/phase-glossary.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against a small
workspace. Session 0 should create deliverables without modifying application source.

## Domain packs

Optional pre-fill from [reference/domain-packs/](reference/domain-packs/README.md):

- `fintech-payout` — disbursement / payout / bank rails
- `auth-identity` — authentication, authorization, session management, SSO/federation
- `e-commerce-checkout` — cart, checkout, order, inventory, fulfillment, refunds

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `/understand` stalls on ignore prompt | Apply batch policy in [understand-anything.md](reference/understand-anything.md) |
| Sub-agent cannot run `/understand` | Run sequentially in main session |
| Huge repo graphs | Per-repo `.understandignore` — exclude vendor/generated |
| No squad data | Enable GitLab + Datadog MCP; run Session 0b — [squad-map/SETUP.md](../squad-map/SETUP.md) |
| Datadog 403 / missing tools | **ddsetup** / **ddconfig**; skip P2b runtime validation |
| KubeSense unavailable | Treat as ❌; P2b continues on Datadog alone if available, else skip |
| `manifest.yaml` validation fails | `python3 domain-comprehension/scripts/validate_manifest_yaml.py manifest.yaml --workspace-root <root>` |
| `schema_version` must be 2 | Copy new fields from `templates/manifest.yaml` (`evidence_summary`, `overall_confidence`, new artifacts) |
