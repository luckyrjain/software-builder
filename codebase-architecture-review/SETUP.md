# codebase-architecture-review — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-31 |
| **Review cadence** | Quarterly — or when review evidence rules change |
| **External services** | None — reads repository and caller-provided context only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | Inspect bounded source, callers, tests, dependencies, configuration, docs, and optional Git history; do not edit them |
| Optional Git history | Inspect no more than 200 commits in 180 days; degrade safely if unavailable |

## Directory map

```
codebase-architecture-review/
  SKILL.md                 # Orchestrator (≤180 lines)
  examples.md
  workflow/                # Scope → Evidence → Candidates → Falsify → Report
  reference/               # Phase index, report format, smoke/pressure tests
```

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [codebase-design-principles](../docs/skill-framework/shared/codebase-design-principles.md)
- [prompt-injection](../docs/skill-framework/shared/prompt-injection.md)
- [safe-output](../docs/skill-framework/shared/safe-output.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install or an edit, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).
