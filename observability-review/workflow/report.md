---
workflow_version: 1.0
phase: report
produces:
  - OBSERVABILITY_REVIEW_REPORT.md
consumes:
  - metrics_findings
  - log_findings
  - tracing_findings
  - dashboard_findings
  - alert_findings
  - slo_findings
  - correlation_id_findings
---

# Report — derive verdict, build OBSERVABILITY_REVIEW_REPORT.md

Derive the `Coverage:` verdict from Analyze's seven category findings, fixed precedence, worst first:

1. **`Critical gaps`** — any of Analyze's checks proved a severe finding: a critical-path hop with no
   tracing spans at all (not merely unassessed), a component missing every golden-signal metric, an SLO
   with no alert tied to it, or no correlation-ID propagation across a critical-path hop. If any such
   finding exists, the verdict is `Critical gaps` regardless of what else is true.
2. **`Unknown — insufficient input`** — otherwise, if one or more of the seven categories had no supplied
   material to evaluate at all (every check in that category is `Unknown`), the verdict is `Unknown —
   insufficient input`. An unassessed category always outranks a merely-partial one, because "we don't
   know" must never be presented as if it were "we checked and it's mostly fine."
3. **`Partial gaps`** — otherwise, if every category had some material and at least one check came back
   `Partial`, `No`/`Missing`, or `Unknown` (e.g. one critical-path hop inside an otherwise-assessed
   category has no material) short of the `Critical gaps` bar, the verdict is `Partial gaps`.
4. **`Adequate`** — otherwise (every category assessed, every check clean).

When the verdict is not `Adequate`, state which category/categories set it in the one-line summary under
the verdict — never leave the reader with only the bare state name.

Cross-reference [SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation): a `Critical gaps`
or `Partial gaps` finding that plausibly explains slow incident detection gets a one-line
**incident-rca** pointer in Notes; if the caller mentioned an upcoming release, add a
**deployment-risk-review** pointer instead (or in addition — the two are not mutually exclusive).

Build per [reference/report-format.md](../reference/report-format.md).

## Machine artifact v2

Emit the common machine fields and map `Adequate` to `PASS`, `Partial gaps` to `CONDITIONAL`,
`Critical gaps` to `FAIL`, and `Unknown — insufficient input` to `UNKNOWN`. Preserve the human
verdict in `raw_verdict`; every unassessed category remains an explicit finding or unresolved item.
