# stakeholder-questionnaire — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-09-11 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | None — reads repository and caller-provided context only |

See [setup-freshness.md](../../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | Inspect repository evidence relevant to sharpening the questions, where applicable |

## Directory map

```
stakeholder-questionnaire/
  SKILL.md                 # Orchestrator (≤180 lines)
  examples.md
  workflow/                # Inputs → Draft → Report
  reference/                # Phase index, report format, smoke/pressure tests
```

## No visual HTML companion

Unlike `codebase-architecture-review`, `stakeholder-questionnaire` does not render an ephemeral HTML companion. Its
`STAKEHOLDER_QUESTIONNAIRE.md` / `stakeholder_questionnaire` report is the only output.

## Framework links

- [skill-framework README](../../docs/skill-framework/README.md)
- [codebase-design-principles](../../docs/skill-framework/shared/codebase-design-principles.md)
- [prompt-injection](../../docs/skill-framework/shared/prompt-injection.md)
- [safe-output](../../docs/skill-framework/shared/safe-output.md)
- [cross-skill-escalation](../../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install or an edit, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).
