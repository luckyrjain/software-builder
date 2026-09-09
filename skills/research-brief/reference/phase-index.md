# Phase index

Read one `workflow/` file per active phase; do not bulk-load the workflow or references.

| Step | Read now | Produces |
|------|----------|-----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `research_question` |
| **Gather** | [workflow/gather.md](../workflow/gather.md) | `findings` |
| **Report** | [workflow/report.md](../workflow/report.md) | `RESEARCH_BRIEF.md`, `research_brief` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller situation | Behavior |
|-------------------|----------|
| A bounded research question is named | Inputs → Gather → Report |
| No research question named | Inputs HARD STOP — ask; no Gather phase |
| `host.web.search`/`host.web.fetch` available | Gather cites repository and external sources as needed |
| `host.web.search`/`host.web.fetch` unavailable | Gather marks every external-dependent claim `UNKNOWN`; Report states the degraded mode explicitly |
| Scope becomes an unbounded "research everything about X," the question is actually about this codebase's own current behavior, or findings surface a decision that needs interrogating | Offer the one applicable escalation; do not invoke it |
