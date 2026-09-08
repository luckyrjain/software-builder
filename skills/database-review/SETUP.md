# database-review — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-22 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | None — reads supplied schema/migration content and repository only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Install

```bash
cd software-builder
make install-database-review
```

Restart Cursor so the skill reloads.

### Claude Code only

```bash
cd software-builder
make install-claude-database-review
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/database-review.mdc` and
`.kiro/steering/database-review.md` point Cursor/Kiro at `database-review/SKILL.md` without an install
step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | No MCP required — analysis and report-drafting skill |

## Config

No config file. Pass inputs at invocation — see [workflow/inputs.md](workflow/inputs.md).

## Directory map

```
database-review/
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
| Verdict never reaches `Approved` even on a clean-looking migration | Check whether `query_plan` was supplied — its absence forces at least `Approved with conditions` per [reference/report-format.md](reference/report-format.md); this is expected, not a bug |
| A dimension section is missing from the report | Should never happen — all eight sections are required per [reference/report-format.md](reference/report-format.md), each with a finding row or an explicit "None found"/`Unknown`; file a bug if one is missing |
