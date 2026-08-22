---
workflow_version: 1.0
phase: report
produces:
  - API_DESIGN_REVIEW_REPORT.md
consumes:
  - compatibility_findings
  - pagination_findings
  - idempotency_findings
  - error_semantics_findings
  - versioning_findings
  - authorization_findings
  - rate_limiting_findings
---

# Report — derive verdict, build API_DESIGN_REVIEW_REPORT.md

Derive the verdict from the seven checks' findings, precedence worst-first:

1. **`Rejected`** — a breaking change with no migration path and no versioning strategy at all, or an
   authorization gap on a sensitive/write endpoint that looks directly exploitable, or `api_spec` is too
   internally contradictory to review.
2. **`Changes required`** — one or more proven must-fix issues short of the above: an unabsorbed breaking
   change, a missing idempotency key on an unsafe method, inconsistent error shapes, a non-exploitable
   authorization gap, or no rate limiting on a public write endpoint.
3. **`Approved with conditions`** — only minor/recommended issues remain, **or** any check recorded an
   explicit evidence gap (Unknown) — an unresolved check never silently yields a bare `Approved`.
4. **`Approved`** — every check completed and clean, no evidence gaps.

Report the single highest-precedence state that applies; list every contributing finding (not only the
one that set the verdict) across the seven sections, never just the winning one.

Build per [reference/report-format.md](../reference/report-format.md).
