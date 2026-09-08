# tech-debt-assessor — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-22 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | None — reads repository content and supplied backlog data only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Install

```bash
cd software-builder
make install-tech-debt-assessor
```

Restart Cursor so the skill reloads.

### Claude Code only

```bash
cd software-builder
make install-claude-tech-debt-assessor
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/tech-debt-assessor.mdc` and
`.kiro/steering/tech-debt-assessor.md` point Cursor/Kiro at `tech-debt-assessor/SKILL.md` without an
install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | No MCP required — analysis and report-drafting skill |

## Config

No config file. Pass inputs at invocation — see [workflow/inputs.md](workflow/inputs.md).

## Directory map

```
tech-debt-assessor/
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
| Every item lands in the same priority bucket | Re-check [reference/report-format.md](reference/report-format.md) § Rules — verify the four dimensions are actually being scored independently, not collapsed into one gut-feel number |
| Items with vague descriptions silently show a numeric score | Re-check [workflow/analyze.md](workflow/analyze.md) § Evidence gaps — an unscorable dimension must produce `Unknown`, never a guessed value |
