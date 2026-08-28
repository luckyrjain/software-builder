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
   report validation (step 5 Notes). When `release_ref` is a 40-character git SHA, resolve
   `target_branch` HEAD after step 1 and compare — on mismatch, record a release-pin anomaly per
   [reference/gate-policy.md § Escalation](../reference/gate-policy.md#escalation-not-override). Image
   digests are recorded for deploy verification only; do not compare them to git SHAs.

## 2. Review each resolved MR — pr-review, retrospective mode, per gate-policy.md

Every MR resolved in step 1 is **already merged** — that is the query condition (`state: merged`). Invoke
**pr-review** per resolved MR with **explicit typed fields**, never a conversational exchange — this is
this skill's `mr_context` InvocationEnvelope
([invocation-envelope.md](../../docs/skill-framework/shared/invocation-envelope.md)):

- `merge_request_iid`, `project` — exact scope
- `review_mode: retrospective`, `audit_type: retrospective` — interaction policy
- `expected_head_sha`: the MR's `merge_commit_sha` (or `diff_refs.head_sha` recorded at merge time from
  step 1's `list_merge_requests` result) — **always per-MR**, never the manifest `release_ref`
- `posting_policy: forbidden` — allowed actions

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
  any service's k8s verdict is `insufficient_metrics` or `ambiguous_unresolved`, **or** any manifest
  entry's `release_ref` git SHA does not match `target_branch` HEAD. An unreviewed MR range, an
  unobservable service, or a release-pin mismatch is a genuine evidence gap, not a verified-clean release
  — but it is also not a *proven* problem, so it must not be silently folded into `NOT_READY` (which
  reads as "we found something wrong") or into `READY` (which reads as "we checked and it's fine").
  `UNKNOWN` takes precedence over `CONDITIONAL` below when both apply — an evidence gap is reported as
  itself, not softened into "flagged but proceed."
- **`CONDITIONAL`** — no `NOT_READY` or `UNKNOWN` condition, **and** any service is flagged with an
  incident signal. Per §4's disclosed limitation, a flagged signal is "a release readiness signal worth a
  human look, not a confirmed release-caused problem" — `CONDITIONAL` says exactly that: nothing proven
  blocking, but a human should look before calling this `READY`.
- **`READY`** — none of the above: every MR clean, every k8s verdict `READY`/non-`BLOCKED` with
  sufficient metrics, every manifest entry resolved, every `release_ref` git SHA matches `target_branch`
  HEAD (or no git `release_ref` was supplied), every service's incident signal `Clear`.

Precedence when multiple conditions apply: `NOT_READY` > `UNKNOWN` > `CONDITIONAL` > `READY` — report the
single highest-precedence state, never downgrade a `NOT_READY` condition because an `UNKNOWN` one is also
present, and list every contributing condition (not just the one that set the verdict) in the report's
Notes section per [reference/report-format.md](../reference/report-format.md).

Every manifest entry appears in the report — a repo with no MRs, a service that's clear on both k8s and
incident-rca, still gets a row. Never silently drop a manifest entry from the report.

## 6. Manifest v2 — conditional production-readiness gate

Steps 1–4 below apply only to an entry carrying `production_readiness_required: true` (see
[inputs.md § Manifest v2](inputs.md#manifest-v2-optional-per-entry)); a v1 entry skips them entirely and
behaves exactly as steps 1–5 above always have. Step 5 (final freshness fence) is a general
release-candidate identity check and applies to every entry, v1 included, whenever a mutable `release_ref`
is being tracked across this run — it is not gated on `production_readiness_required`.

1. **Reuse first.** If one or more trusted `production_readiness_report`s are available whose canonical
   repo/service and `head_revision_or_digest` exactly match this entry's `release_ref`, whose environment
   matches whenever either side declares one (an entry that omits `environment` never reuses a report
   produced for some other declared environment — only "neither side declares one" is a harmless match),
   and whose own `source_revision` matches this entry's, when supplied, use one. A caller- or file-supplied
   report can never satisfy this by itself — only a runtime-validated/direct-child result is trusted for the
   gate. Conflict detection runs first, on every such trusted, identity-matching report: if two or more
   disagree in verdict, that is conflicting authoritative evidence, not a pick-one — the dimension is
   `UNKNOWN` until reconciled, and this is never bypassed by a `production_readiness_ref` pin. Only once the
   matching set agrees is the entry's `production_readiness_ref` applied, and only to select which of the
   (already-agreeing) reports is attributed as the reused source — a pin that names no report in that
   agreeing set (a typo, a stale ref) never suppresses the reuse itself, since every remaining report already
   agrees in verdict and attribution alone cannot change the resolved status.
2. **Otherwise, invoke only when safe.** If `release_ref` is itself shaped like a source revision (a git
   commit SHA), or a `source_revision` is separately known, and production-readiness-review is available,
   invoke it once with
   this entry's repo/service/environment/`source_revision`/`release_ref` plus `since`, via
   `assessment_context`. A manifest-declared `criticality` is untrusted caller text — this skill has no
   authoritative source to vet it against — so it is passed only as a `caller`-authority input (never folded
   into the candidate's identity, and never defaulted to "unknown" when absent), letting
   production-readiness-review apply its own documented authoritative-wins-over-caller precedence rather
   than treating this caller's tier claim as ground truth. If this skill has already assembled `code_review_coverage` from authoritative SCM
   enumeration (never from the manifest entry's own text — a `release_manifest` field can never self-attest
   "already reviewed"), pass it too, so production-readiness-review reuses that coverage and never revisits
   pr-review within this same release-root run. That coverage bundle is bound to the exact candidate it was
   assembled for by its own `repo`, `service`, AND `candidate_source_revision` — a bundle that omits
   `repo`/`service`, or one assembled for a different manifest entry, is never applied here merely because
   they happen to share a (caller-controlled) `source_revision` string. A `code_review_coverage` bundle
   that is not `COMPLETE` with an empty `uncovered_change_refs`, and host/runtime-authoritative, never
   triggers an invocation; the dimension is `UNKNOWN` directly (never a bypass of the recursion guard by
   re-reviewing, and never a "trust me, it's complete" claim honored).
3. **Otherwise, `UNKNOWN`.** Missing report, insufficient candidate identity, or the child unavailable
   all land here — never a silently skipped gate and never an inferred `READY`.
4. **Cap the release verdict, never widen it.** Production readiness `NOT_READY` caps the release
   verdict to `NOT_READY`; `UNKNOWN` caps it to `UNKNOWN`; `CONDITIONAL` caps it to at most `CONDITIONAL`;
   `READY` never changes what steps 1–5 already found. This never causes the pr-review/k8s/incident-rca
   checks in steps 2–4 above to be skipped — they always run regardless of the production-readiness
   outcome, and a check that itself resolves to an evidence gap counts as unresolved exactly like one that
   never ran.
5. **Final freshness fence.** Immediately before emitting the report, re-resolve every mutable
   `release_ref`; if it resolves to a different identity than at the start of this run, or a reused
   report's deployable digest no longer matches, the affected entry (and therefore the overall verdict)
   is `UNKNOWN` — old and new evidence are never combined.

## Required outputs

| Output | Location | Required fields |
|--------|----------|-----------------|
| Release readiness report | `RELEASE_READINESS_REPORT.md` | Overall verdict, MRs reviewed, per-service rightsizing, per-service incident signal |
