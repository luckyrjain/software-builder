---
workflow_version: 1.0
phase: run-check
produces:
  - release_readiness_report
consumes:
  - release_manifest
  - incident_lookback_hours
  - target_branch
---

# Run check — resolve MR ranges, invoke all three skills, aggregate

## 1. Resolve each repo's MR range (genuinely new logic)

For each `release_manifest` entry:

1. If `since` is a tag/ref, resolve it to a commit and that commit's timestamp via the repo's git/GitLab
   MCP access (same read-only access pr-review already has). If `since` is already an explicit timestamp,
   use it directly. **If `since` doesn't resolve** (unknown tag/ref, or an unparseable timestamp): do not
   drop the entry. Record it in the report's Notes section as unresolved (per
   [reference/report-format.md](../reference/report-format.md)), mark that entry's MRs-reviewed row
   "unresolved — `since` could not be resolved," and continue processing every other manifest entry.
2. Query the GitLab MCP's `list_merge_requests` tool (the same tool pr-review's own
   [mcp-capabilities.md](../../pr-review/reference/mcp-capabilities.md) documents for enumerating open
   MRs) with `state: merged`, `target_branch` (this skill's own input, default the repo's configured
   release branch), and a merge-date filter after the resolved `since` timestamp. **This is a new query
   shape** — pr-review's own docs only ever exercise this tool for open-MR enumeration, never a merged-
   in-a-date-range query. **Paginate exhaustively** — same requirement pr-review's own
   [inputs.md](../../pr-review/workflow/inputs.md#resolution-branches) places on its open-MR listing
   ("list open MRs per project, paginating each — this gives the full set"); a single-page result is not
   the full MR range for a repo with more merges than one page holds. If the connected GitLab MCP server
   doesn't support a merge-date filter parameter, fall back to listing **all** merged MRs against
   `target_branch`, paginating exhaustively, and filtering client-side by `merged_at` — never stop at the
   first page and never guess a smaller set.
3. Record the resolved MR list per repo. A repo with zero MRs since `since` is not an error — record it
   as "no changes this release" in the report, not a HARD STOP.

## 2. Review each resolved MR — pr-review, per gate-policy.md

Invoke **pr-review** once per resolved MR with the phrase `"review !<merge_request_iid> in <project>"`
(never "review and post") and answer every ask-point per
[reference/gate-policy.md § pr-review](../reference/gate-policy.md#pr-review-reuses-pr-gatekeepers-own-policy-unchanged) —
this reuses pr-gatekeeper's own real, working policy rather than assuming pr-review has a settable
"quiet" mode (it doesn't — `posting_mode` is derived by pr-review's own Phase 0 from connected MCP write
tools, never a caller input). Whatever mode pr-review's Phase 0 detects, nothing is ever posted to
GitLab, per that policy. Record each MR's severity-tagged findings summary (counts by severity, not the
full rendered chat review) for the report's MRs-reviewed section.

## 3. Rightsizing verdict per service — k8s-overprovisioning-datadog

Invoke **k8s-overprovisioning-datadog** once per service named in `release_manifest`, its own normal
single-service path ([resolve-service.md](../../k8s-overprovisioning-datadog/workflow/resolve-service.md)).
Record its own verdict (READY/BLOCKED recommendations, or whatever its own Human Report states) **as-is**
— this skill never re-labels or reinterprets it. If service-tag resolution is ambiguous, answer per
[reference/gate-policy.md § k8s-overprovisioning-datadog](../reference/gate-policy.md#k8s-overprovisioning-datadog) —
rely on the `env:production` default, or "proceed with unknown" rather than guessing a deployment name.
An `insufficient_metrics` outcome is recorded honestly as such, never upgraded to READY or treated as
BLOCKED.

Kubernetes MCP and Datadog failures remain **source-scoped** inside the wrapped assessment. Continue and
record the returned degraded verdict when Kubernetes MCP or Datadog still supplies sufficient evidence;
only an `auth_failure` covering **all viable sources** is recorded as a blocked k8s result.

## 4. Incident signal per service — incident-rca, Phase 1 only

Invoke **incident-rca** once per service named in `release_manifest`:

- `service`: the manifest entry's service name (a valid anchor on its own — no other anchor needed)
- `from_time`: `now - incident_lookback_hours`, explicit UTC (`Z` suffix)
- `to_time`: `now`, explicit UTC

Supplying both fields explicitly in UTC, with `incident_lookback_hours` never below its documented
1-hour minimum (see [workflow/inputs.md](inputs.md)), means incident-rca's own anchor-missing HARD STOP,
timezone-confirmation ask, and short-window ask/HARD STOP all never fire — avoided by construction, not
scripted. See [reference/gate-policy.md § incident-rca](../reference/gate-policy.md#incident-rca) for the
complete enumeration.

**incident-rca's Phase 1 checkpoint always fires** (it's not conditional on signal density) and this
skill **always answers "stop here,"** per [reference/gate-policy.md](../reference/gate-policy.md) —
including overriding Phase 1's own default-to-proceed on a strong signal. Treat the Phase 1 evidence
(error/infra signal counts) as this service's incident-readiness signal:

- **Zero signals** → clear.
- **Any signal** (strong or sparse) → flagged, record the signal counts and a direct incident-rca
  follow-up pointer (service + the same window this skill used) — **never** continue to Phase 2 to
  investigate further inside this skill.

## 5. Build `RELEASE_READINESS_REPORT.md`

Per [reference/report-format.md](../reference/report-format.md). Overall verdict:

- **Not ready** if any MR has a `Critical`/`High` finding, any service's k8s verdict is `BLOCKED` **or
  `insufficient_metrics`**, any manifest entry's `since` didn't resolve, or any service is flagged with an
  incident signal.
- **Ready** otherwise.

Every manifest entry appears in the report — a repo with no MRs, a service that's clear on both k8s and
incident-rca, still gets a row. Never silently drop a manifest entry from the report.

## Required outputs

| Output | Location | Required fields |
|--------|----------|-----------------|
| Release readiness report | `RELEASE_READINESS_REPORT.md` | Overall verdict, MRs reviewed, per-service rightsizing, per-service incident signal |
