# system-design — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-22 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | None — reads supplied architecture decision/PRD content and repository only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Install

```bash
cd software-builder
make install-system-design
```

Restart Cursor so the skill reloads.

### Claude Code only

```bash
cd software-builder
make install-claude-system-design
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/system-design.mdc` and `.kiro/steering/system-design.md`
point Cursor/Kiro at `system-design/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | No MCP required — analysis and report-drafting skill |

## Config

No config file. Pass inputs at invocation — see [workflow/inputs.md](workflow/inputs.md).

## Directory map

```
system-design/
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
| Every section comes back "Open question" | The supplied `architecture_decision_or_prd` is too sparse to design against — supply more detail or a fuller architecture-review decision; see [workflow/inputs.md](workflow/inputs.md) |
| Verdict stuck at `Ready with open questions` despite a detailed input | Check whether `existing_system_context` is missing where the design implies a migration from a current state — see [reference/report-format.md](reference/report-format.md) verdict rules |
