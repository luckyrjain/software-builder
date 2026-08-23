# performance-review — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-22 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | None — reads supplied code/query content and repository only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Install

```bash
cd software-builder
make install-performance-review
```

Restart Cursor so the skill reloads.

### Claude Code only

```bash
cd software-builder
make install-claude-performance-review
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/performance-review.mdc` and
`.kiro/steering/performance-review.md` point Cursor/Kiro at `performance-review/SKILL.md` without an
install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | No MCP required — analysis and report-drafting skill |

## Config

No config file. Pass inputs at invocation — see [workflow/inputs.md](workflow/inputs.md).

## Directory map

```
performance-review/
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
| A known N+1 pattern in the smoke-test input doesn't surface as a finding | Check `workflow/analyze.md` § 3 ran against the actual loop body, not just the surrounding function signature; verify the finding landed in the N+1 table, not folded into DB behavior only |
| Verdict reads `Pass` despite an evidence gap being recorded | Bug — per [reference/report-format.md](reference/report-format.md) § Rules, any evidence gap forces at least `Pass with findings`, never a bare `Pass` |
