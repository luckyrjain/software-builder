---
workflow_version: 1.0
phase: report
produces:
  - SECURITY_REVIEW_REPORT.md
consumes:
  - authn_findings
  - authz_findings
  - secrets_findings
  - injection_findings
  - ssrf_findings
  - data_leakage_findings
  - cryptography_findings
  - dependency_exposure_findings
  - unknowns
---

# Report — derive verdict, build SECURITY_REVIEW_REPORT.md

Derive the overall verdict from Analyze's findings and gaps, precedence worst-first:

1. **`Fail — Critical/High findings present`** — any finding across any category is rated Critical
   or High. This wins even when other categories have unresolved gaps — a proven finding is not
   softened by an unrelated evidence gap.
2. **`Blocked — insufficient access`** — no Critical/High finding, but `## Unknowns` is non-empty
   (at least one category could not be completed). Distinct from both Pass states — an unchecked
   category is not the same as a checked-and-clean one.
3. **`Pass with findings`** — no Critical/High finding, no gaps, at least one Medium/Low finding.
4. **`Pass`** — no gaps, zero findings at any severity across all eight categories.

Build per [reference/report-format.md](../reference/report-format.md) — every category section
present (populated or "None found"), `## Unknowns` present whenever Analyze recorded a gap (omit
the section only when there are none), evidence excerpts escaped/fenced and redacted per that
file's § Safe rendered-output boundary.

## Machine artifact v2

Emit the common machine fields and map `Pass` to `PASS`, `Pass with findings` to `CONDITIONAL`,
Critical/High findings to `FAIL`, and `Blocked — insufficient access` to `UNKNOWN`. Preserve the
human verdict in `raw_verdict` and keep all evidence gaps in `findings` or `unresolved`.
