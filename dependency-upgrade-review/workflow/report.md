---
workflow_version: 1.0
phase: report
produces:
  - DEPENDENCY_UPGRADE_REPORT.md
consumes:
  - breaking_changes
  - cve_findings
  - api_differences
  - transitive_impact
  - rollout_risk
---

# Report — derive verdict, build DEPENDENCY_UPGRADE_REPORT.md

Derive the verdict from Analyze's five check outputs using the fixed, worst-first precedence order:

1. **`Do not upgrade yet`** — any proven blocker: a breaking change with no available mitigation or
   caller-side fix, or a CVE affecting `target_version` with no fix available.
2. **`Blocked — insufficient info`** — no proven blocker from step 1, but at least one check recorded an
   evidence gap (no `changelog_text`, no `manifest_excerpt`). The CVE check's training-cutoff caveat (see
   [workflow/analyze.md](../workflow/analyze.md)) is disclosed in every report but is not itself an
   evidence gap and does not trigger this state on its own.
3. **`Upgrade with mitigations`** — no proven blocker, no evidence gap, but at least one breaking change,
   CVE, or transitive conflict was found and each has a stated mitigation.
4. **`Safe to upgrade`** — none of the above; every check completed and found nothing blocking.

Build per [reference/report-format.md](../reference/report-format.md).
