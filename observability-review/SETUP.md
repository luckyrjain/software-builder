# observability-review — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-22 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | None — reads supplied metrics/logs/dashboard/alert configuration and repository only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Install

```bash
cd software-builder
make install-observability-review
```

Restart Cursor so the skill reloads.

### Claude Code only

```bash
cd software-builder
make install-claude-observability-review
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/observability-review.mdc` and
`.kiro/steering/observability-review.md` point Cursor/Kiro at `observability-review/SKILL.md` without an
install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | No MCP required — analysis and report-drafting skill |

## Config

No config file. Pass inputs at invocation — see [workflow/inputs.md](workflow/inputs.md).

## Directory map

```
observability-review/
  SKILL.md                 # Orchestrator (≤180 lines)
  examples.md
  workflow/                # Inputs → Analyze → Report
  reference/                # Phase index, report format, smoke/pressure tests
```

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [prompt-injection](../docs/skill-framework/shared/prompt-injection.md)
- [skill-routing](../docs/skill-framework/shared/skill-routing.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Every category shows `Unknown` even though material was supplied | Check Inputs actually parsed `observability_material` per category (§ Normalization in [workflow/inputs.md](workflow/inputs.md)) rather than treating it as one opaque blob |
| A category with no supplied material shows a `Missing`/`No` verdict instead of `Unknown` | Bug — re-check [workflow/analyze.md](workflow/analyze.md) is distinguishing "no material to assess" from "assessed and found lacking"; see [reference/report-format.md § Rules](reference/report-format.md#rules) |
