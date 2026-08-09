# prd-architect — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | Optional web search for material unknowns (generalized queries only) |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Install

```bash
cd software-builder
make install-prd-architect
```

Restart Cursor so the skill reloads.

### Claude Code only

```bash
cd software-builder
make install-claude-prd-architect
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/prd-architect.mdc` and `.kiro/steering/prd-architect.md`
point Cursor/Kiro at `prd-architect/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| None required | Analysis and drafting skill — no MCP, no repository access |

Optional: **domain-comprehension** when the PRD depends on unfamiliar existing-system behavior;
**loop-task-implementer** for post-Ready implementation.

## Config

No config file. Pass `request`, optional `source_material`, `mode_hint`, `depth_hint`, and `constraints`
at invocation — see [workflow/inputs.md](workflow/inputs.md).

## Directory map

```
prd-architect/
  SKILL.md                 # Orchestrator (≤180 lines)
  report-template.md       # Output skeleton
  examples.md
  prd-architect.eval.md    # Regression eval suite (maintainers)
  scripts/                 # Deterministic safe-output reference renderer
  workflow/                # Classify → Validate → Specify → Break → Repair → Gate
  reference/               # Rules, depth, triggers, output contract
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
| Output is draft + separate review comments | Re-check [reference/output-contract.md](reference/output-contract.md) — one final artifact |
| Bloated PRD with N/A sections | Re-check [reference/section-triggers.md](reference/section-triggers.md) |
| Validation request produced full PRD | Re-check [reference/response-modes.md](reference/response-modes.md) |
| Invented metrics or regulations | Re-check [reference/global-rules.md](reference/global-rules.md) § Evidence |
