---
workflow_version: 1.0
phase: report
produces:
  - ARCHITECTURE_REVIEW_REPORT.md
consumes:
  - decision_rationale
  - risk_findings
  - scale_limit_findings
  - failure_mode_findings
  - security_findings
  - operability_findings
  - alternatives_findings
---

# Report — derive verdict, build ARCHITECTURE_REVIEW_REPORT.md

## Verdict derivation (fixed precedence, worst-first)

Evaluate in this order — the first matching state wins:

1. **`Rejected`** — any check found a fundamental, unmitigated flaw: a hard constraint from
   `proposal_text` is violated with no stated mitigation, a failure mode causes unrecoverable data loss
   or a security breach with no feasible fix within the proposal's own scope, or the design cannot
   plausibly meet its own stated scale requirement and no alternative path is offered.
2. **`Needs rework`** — not `Rejected`, but at least one required check surfaces a material, unresolved
   risk (a scale limit inside the stated growth horizon, a failure mode with no detection/recovery plan,
   a security trust-boundary gap, no named operability owner, no alternatives stated), **or** any
   required check landed on an explicit `Unknown` (an evidence gap on a required check — not a proven
   flaw, but still blocks a clean approval).
3. **`Approved with conditions`** — not `Rejected` or `Needs rework`, but the decision needs specific,
   named conditions met before/during implementation, including any `Unknown` confined strictly to an
   optional-input-dependent sub-check (`diagram_description`/`repo_context` absent) that doesn't
   otherwise block the decision.
4. **`Approved`** — none of the above: no material risk in any check, alternatives considered and
   justified, no `Unknown` anywhere.

When the verdict is not `Approved`, name every contributing finding in the one-line summary under the
verdict — not just the first or worst one found.

## Build

Populate every section from Analyze's six findings plus any recorded evidence gaps. A clean check still
gets an explicit "None found" row — never omitted. Quote grounding excerpts from `proposal_text`/
`design_description`/`diagram_description` through the safe rendered-output boundary before including
them.

Build per [reference/report-format.md](../reference/report-format.md).
