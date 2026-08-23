# architecture-review — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-22 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | None — reads supplied PRD/design content and repository only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Install

```bash
cd software-builder
make install-architecture-review
```

Restart Cursor so the skill reloads.

### Claude Code only

```bash
cd software-builder
make install-claude-architecture-review
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/architecture-review.mdc` and
`.kiro/steering/architecture-review.md` point Cursor/Kiro at `architecture-review/SKILL.md` without an
install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | No MCP required — analysis and report-drafting skill |

## Config

No config file. Pass inputs at invocation — see [workflow/inputs.md](workflow/inputs.md).

## Directory map

```
architecture-review/
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
| Verdict lands on `Approved` despite an unresolved failure mode or missing alternatives | Check `workflow/analyze.md` recorded the gap as `Unknown` rather than skipping it — see [reference/report-format.md § Rules](reference/report-format.md#rules) for the required precedence |
| A required section is missing from `ARCHITECTURE_REVIEW_REPORT.md` | Should never happen — every check gets a row even when clean, per [reference/report-format.md](reference/report-format.md); file a bug if one is missing |
| Skill doesn't trigger on an obvious architecture-review request | Check the request isn't actually a PRD-authoring ask (→ prd-architect) or an implementation-level design ask (→ system-design) — see [SKILL.md § When to use / NOT to use](SKILL.md#when-to-use-not-to-use) |
