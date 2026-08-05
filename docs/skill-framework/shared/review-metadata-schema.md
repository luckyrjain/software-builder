# Review metadata schema (shared)

**Normative.** Machine-readable YAML footer emitted by review-class skills at closeout.  
**Reference implementation:** pr-review Phase 5 (`review_metadata` fenced block).  
**Design spec:** [2025-06-30-review-platform-analytics-design.md](../../superpowers/specs/2025-06-30-review-platform-analytics-design.md).

## 1. Purpose

Provide a single v2 schema for `history`, `precision`, and `review_quality` blocks so posted review notes
are parseable across sessions without a database. v1 fields (`findings[]`, `findings_stats`,
`review_hash`) remain required where already specified in pr-review.

## 2. Top-level shape

```yaml
review_metadata:
  # --- v1 core (pr-review) ---
  review_type: full | incremental
  review_mode: pre_merge | incremental | retrospective   # lifecycle mode
  audit_type: pre_merge | incremental | retrospective    # dashboard alias; = review_mode
  started: "<ISO-8601>"
  finished: "<ISO-8601>"
  head_sha: "<full_sha>"
  review_hash: { scope, files, head, persona }
  findings: []
  recommendation: approve | comment | request_changes | retrospective_observation
  confidence: high | medium | low
  review_complete: true | false

  # --- retrospective audit (when review_mode: retrospective) ---
  merge_before_review: true | false
  merge_before_ci_green: true | false
  code_blockers_found: 0
  process_findings: 0
  suppressions_validated: 0

  # --- review context (dashboard / automation) ---
  review_context:
    mode: full | incremental | retrospective    # alias: review_type + review_mode combined view
    lifecycle: pre_merge | post_merge
    merge_blocking: true | false

  # --- v2 platform analytics (Phase 1) ---
  history: { ... }           # incremental re-review when prior footer parseable
  precision: { ... }         # every review with review_metrics recorded
  review_quality: { ... }    # when computable; omit on trivial mechanical MRs
  repository_health: { ... }  # v2 dimensions when repo context; stub schema_version: 2 otherwise
```

## 2.1 Retrospective audit fields (`review_mode: retrospective`)

Emit when Phase 1 confirms post-merge audit (`reference/review-modes.md`).

| Field | Type | Rule |
|-------|------|------|
| `review_mode` | enum | `pre_merge` \| `incremental` \| `retrospective` |
| `audit_type` | enum | Same as `review_mode` — dashboard alias |
| `recommendation` | enum | `retrospective_observation` — never `request_changes` for merge gate |
| `merge_before_review` | bool | `true` when MR was merged before this review ran |
| `merge_before_ci_green` | bool | `true` when merge timestamp precedes head pipeline success |
| `code_blockers_found` | int | Count of emitted Critical + High **code** findings (after grouping) |
| `process_findings` | int | Count of process/policy findings (merge-before-CI, Jira, template) |
| `suppressions_validated` | int | Prior threads/detections confirmed correctly dismissed |

## 2.2 `review_context` block (all reviews)

Nested block for downstream automation — maps from existing fields:

```yaml
review_context:
  mode: full              # full | incremental | retrospective
  lifecycle: pre_merge      # pre_merge | post_merge
  merge_blocking: true      # false when retrospective / post-merge audit
```

| `review_mode` | `lifecycle` | `merge_blocking` | `mode` |
|---------------|-------------|------------------|--------|
| `pre_merge` | `pre_merge` | `true` | `full` |
| `incremental` | `pre_merge` | `true` | `incremental` |
| `retrospective` | `post_merge` | `false` | `retrospective` |

Emit on every review. Flat `review_mode` / `audit_type` remain for legacy parsers.

## 3. `history` block

Emit on **incremental re-review** when at least one prior `review_metadata` block exists on the MR.

```yaml
history:
  approval_iteration: 2
  first_review:
    head_sha: "abc123def4567890abcdef1234567890abcdef12"
    finished: "2026-06-24T14:00:00Z"
    findings_count: 3
    highest_severity: high          # critical | high | medium | low | none
    recommendation: request_changes
  prior_review:
    head_sha: "def4567890abcdef1234567890abcdef12345678"
    finished: "2026-06-25T09:00:00Z"
    findings_count: 1
    highest_severity: medium
    recommendation: comment
  regressions:
    - id: PRR-DATA-001
      location: payments/refund.py:88
      prior_status: fixed
      note: "Decimal fix reverted in incremental diff"
```

| Field | Type | Rule |
|-------|------|------|
| `approval_iteration` | int | Count of prior bot review notes with parseable `review_metadata` + 1 |
| `first_review` | object | Snapshot from earliest parseable footer on MR |
| `prior_review` | object | Snapshot from immediately preceding footer |
| `regressions` | array | Empty when `regression_check: pass`; one entry per regressed finding ID |

**Review snapshot fields** (`first_review`, `prior_review`):

| Field | Type | Rule |
|-------|------|------|
| `head_sha` | string | Full commit SHA at that review |
| `finished` | ISO-8601 | `review_metadata.finished` from that note |
| `findings_count` | int | Length of `findings[]` or `findings_stats.previous + findings_stats.new` |
| `highest_severity` | enum | Max severity among emitted findings at that review |
| `recommendation` | enum | `approve` \| `comment` \| `request_changes` |

Omit the entire `history` key on first review with no prior footer.

## 4. `precision` block

Emit on every review where Phase 2 recorded `review_metrics`.

```yaml
precision:
  prior_total: 3
  prior_resolved: 3
  prior_resolved_pct: 100
  regression_count: 0
  regression_rate: 0.0
  false_positives_withdrawn: 0
  candidates: 12
  emitted: 3
  finding_precision: 0.25
```

| Field | Type | Rule |
|-------|------|------|
| `prior_total` | int | Count from prior `findings[]` (open + fixed at last review) |
| `prior_resolved` | int | Prior findings now `status: fixed` or absent from diff |
| `prior_resolved_pct` | number | `(prior_resolved / prior_total) × 100`; omit when `prior_total: 0` |
| `regression_count` | int | Regressed findings (same as `len(history.regressions)`) |
| `regression_rate` | number | `regression_count / prior_resolved` when `prior_resolved > 0`; else `0.0` |
| `false_positives_withdrawn` | int | Prior findings withdrawn as false positive (author resolved thread, no code change) |
| `candidates` | int | From `review_metrics.candidates` |
| `emitted` | int | From `review_metrics.emitted` |
| `finding_precision` | number | `emitted / candidates` when `candidates > 0` |

On first review: set `prior_total`, `prior_resolved`, `regression_count` to `0`; omit `prior_resolved_pct`.

## 5. `review_quality` block

Optional quality scorecard for framework tuning. Omit when all metrics N/A (e.g. lockfile-only fast path).

```yaml
review_quality:
  coverage_pct: 100
  evidence_pct: 85
  confidence: high
  finding_precision: 0.25
```

| Field | Type | Rule |
|-------|------|------|
| `coverage_pct` | number \| partial | `(changed_files_reviewed / changed_files_total) × 100` |
| `evidence_pct` | number | Share of emitted findings with ≥1 diff anchor and per-finding confidence `high` or `medium` |
| `confidence` | enum | Overall review confidence — same as top-level `confidence` |
| `finding_precision` | number | Same as `precision.finding_precision` |

## 6. `repository_health` block

Cross-MR repo maturity rollup. **Not computed live** unless the agent has repo context (clone path,
`make lint`, CI status). Emit dimension scores only when heuristics are observable — otherwise emit
`schema_version` stub or `null` per dimension.

```yaml
repository_health:
  schema_version: 2
  repo: payments-service          # optional — when user/MR provides repo identity
  dimensions:
    ci: 8                         # 0–10 or null when N/A
    documentation: 9
    validation: 10
    automation: 7
    observability: null           # N/A allowed — e.g. library with no runtime metrics
  composite: 8.5                  # optional mean of non-null dimensions (1 decimal)
```

| Dimension | Type | Heuristic (0–10) |
|-----------|------|------------------|
| `ci` | int \| null | 10 = green pipeline on head; 8 = CI configured but not run; 5 = partial; 0 = none |
| `documentation` | int \| null | 10 = README + runbooks + skill refs aligned; 7 = minor drift; 4 = missing key docs |
| `validation` | int \| null | 10 = `make lint` / test suite passes; 5 = configured but failing; 0 = none |
| `automation` | int \| null | 10 = hooks + anchor lint + pressure tests; 7 = partial; 4 = manual-only |
| `observability` | int \| null | 10 = APM + dashboards + SLOs; 7 = partial; **null** when not applicable |

Normative rubric: [pr-review/reference/repository-health.md](../../../pr-review/reference/repository-health.md).
Prose mirror (optional): `Repository maturity (informational)` line in Phase 5 Engineering improvements.

**Phase 2 minimum (no repo context):** `{ schema_version: 2 }` — same as Phase 1 stub with bumped version.

## 7. Complete example — incremental re-review

```yaml
review_metadata:
  review_type: incremental
  started: "2026-06-25T10:10:00Z"
  finished: "2026-06-25T10:15:00Z"
  baseline_sha: "abc123def4567890abcdef1234567890abcdef12"
  head_sha: "def4567890abcdef1234567890abcdef12345678"
  review_hash:
    scope: incremental
    files: 3
    head: "def45678"
    persona: principal_engineer
  findings:
    - id: PRR-TEST-001
      category: TEST
      severity: medium
      confidence: high
      status: open
      location: payments/refund_test.py:12
      evidence: [payments/refund_test.py:12]
  findings_stats:
    previous: 2
    resolved: 1
    remaining: 1
    new: 1
  regression_check: pass
  recommendation: approve
  confidence: high
  review_complete: true
  history:
    approval_iteration: 2
    first_review:
      head_sha: "abc123def4567890abcdef1234567890abcdef12"
      finished: "2026-06-24T14:00:00Z"
      findings_count: 2
      highest_severity: high
      recommendation: request_changes
    prior_review:
      head_sha: "abc123def4567890abcdef1234567890abcdef12"
      finished: "2026-06-24T14:00:00Z"
      findings_count: 2
      highest_severity: high
      recommendation: request_changes
    regressions: []
  precision:
    prior_total: 2
    prior_resolved: 1
    prior_resolved_pct: 50
    regression_count: 0
    regression_rate: 0.0
    false_positives_withdrawn: 0
    candidates: 8
    emitted: 1
    finding_precision: 0.125
  review_quality:
    coverage_pct: 100
    evidence_pct: 100
    confidence: high
    finding_precision: 0.125
  repository_health:
    schema_version: 2
    dimensions:
      ci: 8
      documentation: 9
      validation: 10
      automation: 7
      observability: null
```

## 8. `assessment_metadata` — cross-skill shape

Non–pr-review skills emit **`assessment_metadata`** (not `review_metadata`) at closeout. Reuse v2 block
names and types where applicable; only the top-level key and skill-specific core fields differ.

| Block | pr-review | incident-rca | k8s-overprovisioning |
|-------|-----------|--------------|---------------------|
| Top-level key | `review_metadata` | `assessment_metadata` | `assessment_metadata` |
| Quality block | `review_quality` | `investigation_quality` | `investigation_quality` |
| `history` | MR approval iterations | Investigation iterations on same incident/service | Prior DORA runs on same service |
| `precision` | Finding resolve rate | Hypothesis / signal selectivity | Recommendation confidence stats |

### 8.1 incident-rca field mapping

Detail: [incident-rca/reference/assessment-metadata.md](../../../incident-rca/reference/assessment-metadata.md).

```yaml
assessment_metadata:
  assessment_type: full | incremental
  started: "<ISO-8601>"
  finished: "<ISO-8601>"
  service: "<service>"
  incident_window:
    from: "<ISO-8601>"
    to: "<ISO-8601>"
  primary_hypothesis: deploy_regression
  confidence: high
  assessment_complete: true
  history:
    investigation_iteration: 2
    first_investigation:
      finished: "<ISO-8601>"
      primary_hypothesis: infra_capacity
      confidence: medium
    prior_investigation:
      finished: "<ISO-8601>"
      primary_hypothesis: deploy_regression
      confidence: high
  precision:
    hypotheses_evaluated: 5
    hypotheses_ranked: 2
    primary_score: 0.88
    signals_total: 8
    signals_in_window: 7
    counter_evidence_count: 2
  investigation_quality:
    coverage_pct: 100
    evidence_pct: 90
    source_diversity: 3
    confidence: high
```

### 8.2 k8s-overprovisioning field mapping

Detail: [k8s-overprovisioning-datadog/workflow/report.md](../../../k8s-overprovisioning-datadog/workflow/report.md)
§Assessment metadata footer.

```yaml
assessment_metadata:
  assessment_type: full | repeat
  started: "<ISO-8601>"
  finished: "<ISO-8601>"
  service: "<kube_deployment>"
  final_decision: KEEP_CONFIGURATION
  assessment_confidence: 0.9
  assessment_complete: true
  history:
    assessment_iteration: 4
    review_after: "7d"
    next_assessment_due: "2026-07-05T11:18:00Z"
    scheduled_recheck_prompt: "Re-run rightsizing assessment for neo-disbursement prod — 7d post-change verification"
    first_assessment:
      finished: "<ISO-8601>"
      final_decision: TRIM_RESOURCES
      assessment_confidence: 0.72
    prior_assessment:
      finished: "<ISO-8601>"
      final_decision: KEEP_CONFIGURATION
      assessment_confidence: 0.85
  precision:
    recommendations_evaluated: 4
    recommendations_ready: 0
    recommendations_deferred: 2
    recommendations_blocked: 1
    avg_decision_confidence: 0.9
  investigation_quality:
    coverage_pct: 100
    evidence_pct: 95
    telemetry_coverage_stars: 3
    confidence: very_high
```

### 8.3 domain-comprehension field mapping

Detail: [domain-comprehension/reference/assessment-metadata.md](../../../domain-comprehension/reference/assessment-metadata.md).

```yaml
assessment_metadata:
  assessment_type: full | incremental
  started: "<ISO-8601>"
  finished: "<ISO-8601>"
  domain: "<domain_name>"
  workspace_root: "<path>"
  delivery_mode: full | executive_summary
  overall_confidence: high          # HIGH | MEDIUM | LOW | UNKNOWN — from confidence-rubric minimum rule
  assessment_complete: true
  history:
    comprehension_iteration: 2
    first_comprehension:
      finished: "<ISO-8601>"
      overall_confidence: medium
      repos_analyzed: 8
    prior_comprehension:
      finished: "<ISO-8601>"
      overall_confidence: high
      repos_analyzed: 12
  precision:
    repos_total: 14
    repos_analyzed: 12
    repos_unknown: 2
    bounded_contexts: 6
    unknowns_open: 3
    sections_high: 4
    sections_medium: 2
    sections_low: 1
    sections_unknown: 1
  investigation_quality:
    coverage_pct: 86
    evidence_pct: 80
    five_questions_complete: 4
    five_questions_unknown: 1
    confidence: medium
```

Omit `history` on first engagement with no prior footer. `overall_confidence` MUST follow
`confidence-bands.md` §2.1 — never contradict `EXEC_SUMMARY.md`.

### 8.4 squad-map field mapping

Detail: [squad-map/reference/assessment-metadata.md](../../../squad-map/reference/assessment-metadata.md).

```yaml
assessment_metadata:
  assessment_type: full | incremental
  started: "<ISO-8601>"
  finished: "<ISO-8601>"
  workspace_root: "<path>"
  assessment_complete: true
  history:
    mapping_iteration: 2
    first_mapping:
      finished: "<ISO-8601>"
      repos_mapped: 10
      conflict_count: 1
    prior_mapping:
      finished: "<ISO-8601>"
      repos_mapped: 12
      conflict_count: 0
  precision:
    repos_total: 14
    repos_mapped: 12
    repos_unmapped: 2
    confidence_high: 6
    confidence_medium: 3
    confidence_low: 2
    confidence_unknown: 1
    conflict_count: 1
  investigation_quality:
    coverage_pct: 86
    gitlab_mcp: true
    datadog_mcp: true
    confidence: medium
```

`confidence_*` counts are per-row owner bands — not migration risk tiers. Omit `history` on first run.

### 8.5 mysql-to-postgres-sql field mapping

Detail: [mysql-to-postgres-sql/reference/assessment-metadata.md](../../../mysql-to-postgres-sql/reference/assessment-metadata.md).

```yaml
assessment_metadata:
  assessment_type: single_service | fleet
  started: "<ISO-8601>"
  finished: "<ISO-8601>"
  service: "<service_name>"
  service_path: "<path>"
  migration_risk_tier: P0          # P0 | P1 | P2 | dialect-only — NOT a confidence band
  scan_gate: pass                  # pass | fail
  shadow_compare: pass             # pass | fail | pending | n/a
  confidence: high                 # shadow / verification quality only — see confidence-bands §2.2
  assessment_complete: true
  history:
    migration_iteration: 2
    first_assessment:
      finished: "<ISO-8601>"
      scan_gate: fail
      migration_risk_tier: P0
    prior_assessment:
      finished: "<ISO-8601>"
      scan_gate: pass
      shadow_compare: pass
  precision:
    scan_hits_initial: 14
    scan_hits_remaining: 0
    files_rewritten: 3
    shadow_users_compared: 12
  investigation_quality:
    coverage_pct: 100
    evidence_pct: 90
    confidence: high
```

Fleet-wide status may also be tracked in workspace `MIGRATION_STATUS.yaml` (see skill `templates/`).

## 9. Parsing rules (consumers)

1. Locate fenced ` ```yaml ` block containing `review_metadata:` (pr-review) or `assessment_metadata:`
   (incident-rca, k8s, domain-comprehension, squad-map, mysql-to-postgres-sql) in the posted note or report file.
2. Prefer structured fields over prose Notes lines.
3. For incremental mode, `baseline_sha` or prior `head_sha` is the dedupe baseline (pr-review).
4. `approval_iteration` / `investigation_iteration` / `assessment_iteration` may be recomputed by
   counting prior footers if `history` absent (legacy).
5. Optional lint: `python3 scripts/validate_metadata_footer.py <path.yaml>` — golden examples under
   [shared/examples/](examples/).

## 10. Cross-skill adoption

| Skill | Footer key | `history` | `precision` | Quality block | `repository_health` | Status |
|-------|------------|-----------|-------------|---------------|---------------------|--------|
| pr-review | `review_metadata` | MR iterations | Finding resolve rate | `review_quality` | v2 dimensions (when repo context) | ✅ **v2** |
| incident-rca | `assessment_metadata` | Investigation iterations | Hypothesis/signal stats | `investigation_quality` | — | ✅ **Phase 2** |
| k8s-overprovisioning-datadog | `assessment_metadata` | Prior DORA runs | Recommendation confidence | `investigation_quality` | — | ✅ **Phase 2** |
| domain-comprehension | `assessment_metadata` | Comprehension iterations | Repo/section stats | `investigation_quality` | — | ✅ **stub** §8.3 |
| squad-map | `assessment_metadata` | Mapping iterations | Per-row confidence counts | `investigation_quality` | — | ✅ **stub** §8.4 |
| mysql-to-postgres-sql | `assessment_metadata` | Per-service migration runs | Scan/shadow stats | `investigation_quality` | — | ✅ **stub** §8.5 |

When other skills adopt blocks, reuse field names and types from §3–§5; map quality block to
`investigation_quality` when the deliverable is not an MR review.
