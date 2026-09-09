# codebase-architecture-review — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-31 |
| **Review cadence** | Quarterly — or when review evidence rules change |
| **External services** | Tailwind Play CDN (cdn.tailwindcss.com), Mermaid ESM (cdn.jsdelivr.net/npm/mermaid@11) — needed only to render the ephemeral HTML companion; the Markdown report and typed artifact need none |

See [setup-freshness.md](../../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

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

## Visual HTML report (host-rendered by default)

The review also renders, by default, one ephemeral, self-contained HTML companion, written by the host into
OS temporary storage (for example `architecture-review-20260905T120000Z.html`) — never into the
repository. This companion is not a durable artifact: it is never added to `codebase_architecture_report`
or to `skill_result.artifacts`, and it carries no information the Markdown report does not already state.

Rendering it needs outbound network access to two pinned CDNs at render time — Tailwind
(`cdn.tailwindcss.com`) and Mermaid ESM (`cdn.jsdelivr.net/npm/mermaid@11`). If either CDN is unreachable,
or the host has no browser to open the file in, the HTML still shows the Markdown report and fenced diagram
source; this is expected degraded behavior, not a failure, and it never blocks the canonical Markdown
report. See [reference/html-report.md](reference/html-report.md) for the full contract.

## Framework links

- [skill-framework README](../../docs/skill-framework/README.md)
- [codebase-design-principles](../../docs/skill-framework/shared/codebase-design-principles.md)
- [prompt-injection](../../docs/skill-framework/shared/prompt-injection.md)
- [safe-output](../../docs/skill-framework/shared/safe-output.md)
- [cross-skill-escalation](../../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install or an edit, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).
