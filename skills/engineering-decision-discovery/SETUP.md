# engineering-decision-discovery — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-09-05 |
| **Review cadence** | Quarterly — or when interview/frontier rules change |
| **External services** | None — reads repository and caller-provided context only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | Inspect the scoped implementation, callers, tests, and configuration the host can read; no source, test, configuration, or ADR writes |
| A human turn, when `interaction_policy.human_available: true` | The frontier is asked of the user across one or more rounds; a chat-only host without a follow-up turn should set `human_available: false` instead of inventing answers |

## Directory map

```
engineering-decision-discovery/
  SKILL.md                 # Orchestrator (compact contract + routing description)
  examples.md
  workflow/                # Inputs → Tree → Frontier → Interaction → Report
  reference/                # Phase index, report format, smoke/pressure tests
```

## No source, test, configuration, registry, ADR, or external write

This skill never creates or edits source, tests, configuration, or a registry entry, never writes an ADR,
and never commits, pushes, opens a PR, or posts externally. `ENGINEERING_DECISION_RECORD.md` is a report
emitted for the session; turning it into an ADR is a separate, explicitly authorized action the user takes
outside this skill.

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [codebase-design-principles](../docs/skill-framework/shared/codebase-design-principles.md)
- [prompt-injection](../docs/skill-framework/shared/prompt-injection.md)
- [safe-output](../docs/skill-framework/shared/safe-output.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)

## Smoke test

After install or an edit, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).
