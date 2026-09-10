# research-brief — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-09-10 |
| **Review cadence** | Quarterly — or when skill pipeline rules change |
| **External services** | Web search/fetch (optional) — degrades to repository-only research when unavailable |

See [setup-freshness.md](../../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read-only repository access | Inspect repository evidence relevant to the research question; do not edit it |
| `host.web.search` / `host.web.fetch` (optional) | External primary-source research; without them, answer from repository evidence only and mark external-dependent claims `UNKNOWN` |

## Directory map

```
research-brief/
  SKILL.md                 # Orchestrator (≤180 lines)
  examples.md
  workflow/                # Inputs → Gather → Report
  reference/                # Phase index, report format, smoke/pressure tests
```

## No visual HTML companion

Unlike `codebase-architecture-review`, `research-brief` does not render an ephemeral HTML companion. Its
`RESEARCH_BRIEF.md` / `research_brief` report is the only output.

## Framework links

- [skill-framework README](../../docs/skill-framework/README.md)
- [codebase-design-principles](../../docs/skill-framework/shared/codebase-design-principles.md)
- [prompt-injection](../../docs/skill-framework/shared/prompt-injection.md)
- [safe-output](../../docs/skill-framework/shared/safe-output.md)
- [cross-skill-escalation](../../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install or an edit, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).
