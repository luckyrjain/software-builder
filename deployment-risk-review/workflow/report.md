---
workflow_version: 1.0
phase: report
produces:
  - DEPLOYMENT_RISK_REPORT.md
consumes:
  - blast_radius_finding
  - migration_risk_finding
  - rollback_complexity_finding
  - dependency_risk_finding
  - traffic_risk_finding
---

# Report — derive verdict, build DEPLOYMENT_RISK_REPORT.md

Derive the `Risk` verdict from the five findings using the fixed, worst-first precedence order:

1. **Critical** — an irreversible migration with no rollback plan, or a blast radius covering a
   critical/customer-facing path with no rollback plan at all. Check this first; if it matches,
   stop — the verdict is `Critical` regardless of the other four findings.
2. **High** — an irreversible migration with a rollback plan, a blast radius covering a
   critical/customer-facing path with a rollback plan, a peak-traffic deploy with no canary/
   staged-rollout coverage, **or** an unresolved evidence gap on Migration risk or Rollback
   complexity (the two highest-cost-of-being-wrong dimensions — a gap there floors the verdict at
   `High` until resolved, it never resolves to `Low`/`Moderate` by default).
3. **Moderate** — a reversible migration, a non-trivial blast radius with a rollback plan in place,
   or unresolved dependency risk on a non-critical path, with no `Critical`/`High` trigger present.
4. **Low** — reversible or no migration, a fast/safe rollback plan, contained blast radius, and
   either an off-peak deploy or adequate canary coverage, with no gap on any of the five checks.

Set `deployment_confidence` (`HIGH | MEDIUM | LOW | UNKNOWN`) from the number and severity of
evidence gaps recorded during Analyze: no gaps → `HIGH` or `MEDIUM` depending on how directly the
supplied evidence supports each finding; one gap → capped at `LOW`; two or more gaps → `UNKNOWN`.
`deployment_confidence` is a separate field from `Risk` — never collapse the two, and never let a
low `deployment_confidence` alone lower the `Risk` verdict below what the assessed evidence
supports (a gap raises `Risk` only via the explicit Migration-risk/Rollback-complexity floor above,
not by generic confidence penalty).

List every triggering condition when more than one applies — not just the one that decided the
verdict — so the report shows its full reasoning per
[reference/report-format.md § Rules](../reference/report-format.md#rules).

Build per [reference/report-format.md](../reference/report-format.md).

## Machine artifact v2

Emit the common machine fields and map Critical/High risk to `FAIL`, Low risk to `PASS`, and High
risk with unresolved required evidence to `UNKNOWN`. Preserve the human Risk verdict in `raw_verdict`
and keep evidence gaps in `unresolved`.
