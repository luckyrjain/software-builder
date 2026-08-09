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
4. When the manifest entry includes `release_ref`, record it as the repo's **release candidate pin** for
   step 2 — do not substitute each MR's `merge_commit_sha` when the caller supplied an explicit pin.

## 2. Review each resolved MR — pr-review, retrospective mode, per gate-policy.md

Every MR resolved in step 1 is **already merged** — that is the query condition (`state: merged`). Invoke
**pr-review** per resolved MR with **explicit typed fields**, never a conversational exchange:

- `merge_request_iid`, `project`
- `review_mode: retrospective`, `audit_type: retrospective`
- `expected_head_sha`: when the manifest entry's `release_ref` is set, use that pin for every MR in the
  repo; otherwise use the MR's `merge_commit_sha` (or `diff_refs.head_sha` recorded at merge time from
  step 1's `list_merge_requests` result). If pr-review's `get_merge_request` returns a different SHA,
  treat it as a genuine anomaly (§Escalation) — especially when `release_ref` was caller-supplied.
- `posting_policy: forbidden`

Do **not** invoke with the bare phrase `"review !<iid> in <project>"` and rely on pr-review's own
merged-MR HARD STOP + a scripted "decline the post-merge audit" reply — declining is correct for
pr-gatekeeper's use case (a merged MR there is an unexpected race), but here it is the **normal, 100%
case**. Declining on every invocation would mean this skill never actually reviews a single MR while
still populating an MRs-reviewed row, which is the exact failure this typed invocation avoids: the typed
`review_mode: retrospective` selects pr-review's retrospective audit path directly (per
[phase-1.md](../../pr-review/workflow/phase-1.md) step 1's "If user confirms post-merge audit →" branch),
so the merged-MR stop and its confirmation ask never fire — avoided by construction, not scripted.

Full protocol: [reference/gate-policy.md § pr-review](../reference/gate-policy.md#pr-review-retrospective-audit-mode-typed-invocation-not-conversational).
Every *other* ask-point pr-review may still hit (200-file cap, pagination cap, baseline staleness,
Jira/Slack write-back) follows pr-gatekeeper's own enumerated policy verbatim, and `posting_policy:
forbidden` guarantees nothing is ever posted to GitLab regardless of which posting mode pr-review's own
Phase 0 detects. If pr-review's `get_merge_request` returns a `merge_commit_sha` different from
`expected_head_sha`, treat it as a genuine anomaly (§Escalation, not override) — record it in the report
rather than silently reviewing whatever commit pr-review found. Record each MR's severity-tagged findings
summary (counts by severity, not the full rendered chat review) for the report's MRs-reviewed section.

## 3. Rightsizing verdict per service — k8s-overprovisioning-datadog

Invoke **k8s-overprovisioning-datadog** once per service named in `release_manifest`, its own normal
single-service path ([resolve-service.md](../../k8s-overprovisioning-datadog/workflow/resolve-service.md)).
Record its own verdict (READY/BLOCKED recommendations, or whatever its own Human Report states) **as-is**
— this skill never re-labels or reinterprets it. If service-tag resolution is ambiguous, answer per
[reference/gate-policy.md § k8s-overprovisioning-datadog](../reference/gate-policy.md#k8s-overprovisioning-datadog) —
k8s itself asks or resolves from actually-observed evidence rather than defaulting; an unattended run like
this one will see that surface as `STOP_REASON: ambiguous_unresolved`, recorded honestly rather than
guessed. An `insufficient_metrics` or `ambiguous_unresolved` outcome is recorded honestly as such, never
upgraded to READY or treated as BLOCKED.

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

Per [reference/report-format.md](../reference/report-format.md). **Four-state overall verdict (P1
fix)** — an earlier two-state `Ready`/`Not ready` verdict forced every incident signal to `Not ready`,
even one incident-rca's own Phase 1 scope admits may be chronic noise unrelated to this release (see §4
above, "Known limitation, not a bug"), and every evidence gap (`insufficient_metrics`, `ambiguous_unresolved`, an unresolved
`since`) to the same `Not ready` bucket as an actual proven blocker — collapsing "we don't know" and "we
know it's bad" into one false-blocker state that a human reading the report cannot tell apart:

- **`NOT_READY`** — any MR has a `Critical`/`High` finding, **or** any service's k8s verdict is
  `BLOCKED`. These are proven blockers from a completed check, not an evidence gap.
- **`UNKNOWN`** — no `NOT_READY` condition, **and** any manifest entry's `since` didn't resolve, **or**
  any service's k8s verdict is `insufficient_metrics` or `ambiguous_unresolved`. An unreviewed MR range or an unobservable service
  is a genuine evidence gap, not a verified-clean release — but it is also not a *proven* problem, so it
  must not be silently folded into `NOT_READY` (which reads as "we found something wrong") or into
  `READY` (which reads as "we checked and it's fine"). `UNKNOWN` takes precedence over `CONDITIONAL`
  below when both apply — an evidence gap is reported as itself, not softened into "flagged but proceed."
- **`CONDITIONAL`** — no `NOT_READY` or `UNKNOWN` condition, **and** any service is flagged with an
  incident signal. Per §4's disclosed limitation, a flagged signal is "a release readiness signal worth a
  human look, not a confirmed release-caused problem" — `CONDITIONAL` says exactly that: nothing proven
  blocking, but a human should look before calling this `READY`.
- **`READY`** — none of the above: every MR clean, every k8s verdict `READY`/non-`BLOCKED` with
  sufficient metrics, every manifest entry resolved, every service's incident signal `Clear`.

Precedence when multiple conditions apply: `NOT_READY` > `UNKNOWN` > `CONDITIONAL` > `READY` — report the
single highest-precedence state, never downgrade a `NOT_READY` condition because an `UNKNOWN` one is also
present, and list every contributing condition (not just the one that set the verdict) in the report's
Notes section per [reference/report-format.md](../reference/report-format.md).

Every manifest entry appears in the report — a repo with no MRs, a service that's clear on both k8s and
incident-rca, still gets a row. Never silently drop a manifest entry from the report.

## Required outputs

| Output | Location | Required fields |
|--------|----------|-----------------|
| Release readiness report | `RELEASE_READINESS_REPORT.md` | Overall verdict, MRs reviewed, per-service rightsizing, per-service incident signal |
