# capacity-planner — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-22 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | None — reads supplied historical demand data only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Install

```bash
cd software-builder
make install-capacity-planner
```

Restart Cursor so the skill reloads.

### Claude Code only

```bash
cd software-builder
make install-claude-capacity-planner
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/capacity-planner.mdc` and
`.kiro/steering/capacity-planner.md` point Cursor/Kiro at `capacity-planner/SKILL.md` without an install
step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | No MCP required — analysis and report-drafting skill |

## Config

No config file. Pass inputs at invocation — see [workflow/inputs.md](workflow/inputs.md).

## Directory map

```
capacity-planner/
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
| Headroom verdict reads `Sufficient` despite an unresolved evidence gap | Re-check [reference/report-format.md](reference/report-format.md) § Rules — an evidence gap must drive `Unknown`, never be silently dropped |
| A forecast section is missing from the output entirely | Re-check [workflow/analyze.md](workflow/analyze.md) — every section (including `Unknown` ones) must appear per [reference/report-format.md](reference/report-format.md) |
