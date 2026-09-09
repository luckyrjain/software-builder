# local-diff-review — Setup

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
| Read-only repository access | Inspect the diff, its enclosing files, and this repo's documented conventions; do not edit them |

## Directory map

```
local-diff-review/
  SKILL.md                 # Orchestrator (≤180 lines)
  examples.md
  workflow/                # Inputs → Standards → Spec → Report
  reference/                # Phase index, report format, smoke/pressure tests
```

## No visual HTML companion

Unlike `codebase-architecture-review`, `local-diff-review` does not render an ephemeral HTML companion. Its
`LOCAL_DIFF_REVIEW.md` / `local_diff_review` report is the only output.

## Framework links

- [skill-framework README](../../docs/skill-framework/README.md)
- [codebase-design-principles](../../docs/skill-framework/shared/codebase-design-principles.md)
- [prompt-injection](../../docs/skill-framework/shared/prompt-injection.md)
- [safe-output](../../docs/skill-framework/shared/safe-output.md)
- [cross-skill-escalation](../../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install or an edit, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).
