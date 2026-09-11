# merge-conflict-analysis — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-09-11 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | None — reads repository state only |

See [setup-freshness.md](../../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | Inspect conflicted files, commit history, and (where discoverable) originating PR/issue text for both sides; never stage, commit, or continue/abort the merge or rebase |

## Directory map

```
merge-conflict-analysis/
  SKILL.md                 # Orchestrator (≤180 lines)
  examples.md
  workflow/                # Inputs → Analyze → Report
  reference/                # Phase index, report format, smoke/pressure tests
```

## No visual HTML companion

Unlike `codebase-architecture-review`, `merge-conflict-analysis` does not render an ephemeral HTML
companion. Its `MERGE_CONFLICT_ANALYSIS.md` / `merge_conflict_analysis` report is the only output.

## Framework links

- [skill-framework README](../../docs/skill-framework/README.md)
- [codebase-design-principles](../../docs/skill-framework/shared/codebase-design-principles.md)
- [prompt-injection](../../docs/skill-framework/shared/prompt-injection.md)
- [safe-output](../../docs/skill-framework/shared/safe-output.md)
- [cross-skill-escalation](../../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install or an edit, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).
