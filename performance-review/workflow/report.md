---
workflow_version: 1.0
phase: report
produces:
  - PERFORMANCE_REVIEW_REPORT.md
consumes:
  - complexity_findings
  - db_behavior_findings
  - n_plus_1_findings
  - cache_findings
  - memory_findings
  - concurrency_findings
  - connection_pool_findings
  - fanout_findings
  - evidence_gaps
---

# Report — derive verdict, build PERFORMANCE_REVIEW_REPORT.md

## Verdict derivation (precedence worst-first)

1. **`Blocked — insufficient evidence`** — `reviewed_content` provided no basis for evaluating a
   majority of the eight areas, or every attempted area hit an evidence gap. Check this first: a
   report with almost nothing actually evaluated must not be dressed up as a `Pass`.
2. **`Fail — regression risk`** — at least one finding across any area is assessed as a likely real
   performance regression (an N+1 pattern on an unbounded collection, an unbounded cache with no
   eviction, a connection pool sized well below realistic concurrent load, an O(n²) hotspot that
   scales with user/tenant/record count).
3. **`Pass with findings`** — one or more findings exist, or one or more (but not a majority of)
   evidence gaps exist, but nothing rises to `Fail — regression risk`.
4. **`Pass`** — no findings in any area, and no evidence gaps at all.

Apply in this order and stop at the first that matches — do not downgrade a `Fail — regression risk`
because an evidence gap is also present elsewhere; list every contributing finding and gap in the
report, not only the one that set the verdict.

## Build the report

Per [reference/report-format.md](../reference/report-format.md). Every one of the eight focus areas
gets its table populated from Analyze's findings for that area, with an explicit "None found" row when
Analyze produced nothing for it. Every evidence gap Analyze recorded appears in the report's Evidence
gaps section — never silently dropped and never merged into a "None found" row, which would misrepresent
an unchecked area as a checked-and-clean one.
