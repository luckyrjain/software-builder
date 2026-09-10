# bug-diagnosis — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-09-09 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | None — reads repository and caller-provided context only |

See [setup-freshness.md](../../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | Inspect the implementation, tests, and observable behavior the host can read; do not edit them |

## Directory map

```
bug-diagnosis/
  SKILL.md                 # Orchestrator (≤180 lines)
  examples.md
  workflow/                # Inputs → Repro → Hypotheses → Report
  reference/                # Phase index, report format, smoke/pressure tests
```

## No visual HTML companion

Unlike `codebase-architecture-review`, `bug-diagnosis` does not render an ephemeral HTML companion. Its
`BUG_DIAGNOSIS_REPORT.md` / `bug_diagnosis_report` report is the only output.

## Framework links

- [skill-framework README](../../docs/skill-framework/README.md)
- [codebase-design-principles](../../docs/skill-framework/shared/codebase-design-principles.md)
- [prompt-injection](../../docs/skill-framework/shared/prompt-injection.md)
- [safe-output](../../docs/skill-framework/shared/safe-output.md)
- [cross-skill-escalation](../../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install or an edit, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).
