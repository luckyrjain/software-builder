# Review metrics (framework observability)

Optional **self-metrics** about the reviewer — not the code under review. Improves the framework over
time; does not block merge. Record during Phase 2; emit in Phase 5 **Notes** when useful.

## Schema

```
review_metrics: {
  candidates: N,           # detector hypotheses before pipeline
  emitted: M,              # findings table rows (after grouping)
  posted: P,               # Phase 4 inline threads (if posting ran)
  suppressed: {
    guess: n1,             # don't-guess gate
    path: n2,              # execution path gate
    dedupe: n3,
    feedback: n4,          # feedback learning
    value: n5              # value filter
  },
  stop_search: true|false,
  context_cache: reused|built|refreshed,
  capability_profile: [kubernetes, react],  # short list
  persona: principal_engineer,
  fast_path: standard|lockfile-only|docs-only|...,
  incremental: {              # re-review only — Phase 1 step 3 baseline present
    baseline_sha: "<sha>",
    commits_since_baseline: N,
    previous_findings: N,
    resolved: N,
    remaining: N,
    new_findings: N,
    regressed: false|true,
    scope_category: documentation/example|production code|configuration|mixed,
    scope_detail: "no runtime code changed"
  },
  coverage: {                 # Phase 1 boundary vs reviewed scope
    changed_files_total: N,
    changed_files_reviewed: N,
    hunks_pct: 100|partial,
    truncated: false|true,
    skipped: false|true,
    lines_added: N,           # optional — git diff --stat or MR stats
    lines_deleted: N,
    coverage_pct: N           # (reviewed/total)*100 or null when partial
  },
  cost: {                     # Phase 5 executive summary — review cost metrics
    files_reviewed: N,
    files_total: N,
    commits_in_mr: N,         # full review: all MR commits; incremental: commits_since_baseline
    estimated_effort_min: N,  # reviewer estimate, round to nearest 5
    coverage_pct: N|partial
  },
  change_classification: documentation|templates|metadata|no_executable_runtime_code|production_code|mixed,
}
```

Each emitted finding carries structured fields (also mirrored in `review_metadata.findings[]`):

```
finding: {
  id: PRR-SEC-001,                # stable category-prefixed finding_id (PRR-{CAT}-{NNN})
  category: SEC,                  # enum — see finding-pipeline.md
  severity: critical|high|medium|low,
  confidence: high|medium|low,
  status: open|fixed|suppressed,
  location: path:line,             # primary anchor (= evidence[0])
  evidence: [path:line, ...],    # required; at least one entry
  doc_drift_class: reference_stale|implementation_stale|ambiguous|null
}
```

## Machine-readable footer (`review_metadata`)

Emit a fenced **` ```yaml `** block at the end of every summary note (first review and re-review) —
after `### Notes`, before the closing attribution line. Schema:

**`review_mode` / `audit_type` are declared once**, immediately after `review_type` below — do not
restate them later in the same block (a P1 fix: an earlier version of this schema listed them twice,
once here and again near `recommendation`/`confidence`; identical values made it harmless in practice,
but a literal YAML duplicate key is undefined/last-wins behavior and misleading to a reader hand-checking
the schema against a rendered footer).

```yaml
review_metadata:
  review_type: full | incremental
  review_mode: pre_merge | incremental | retrospective
  audit_type: pre_merge | incremental | retrospective
  started: "<ISO-8601>"          # Phase 0 or Phase 1 start
  finished: "<ISO-8601>"         # Phase 5 render time
  tool_calls: N                  # MCP + shell invocations during review
  files_fetched: N               # unique paths read or diff-scanned
  diff_pages: N                  # get_merge_request_diffs pages fetched
  head_sha: "<full_sha>"
  review_hash:                   # duplicate-review detection across sessions
    scope: full | incremental
    files: N                     # files_reviewed (incremental: incremental boundary count)
    head: "<short_sha>"          # first 8 chars of head_sha
    persona: principal_engineer
  persona: principal_engineer
  files_reviewed: N
  files_total: N
  commits_in_mr: N
  estimated_effort_min: N
  coverage_pct: N | partial
  change_classification: documentation | templates | metadata | no_executable_runtime_code | production_code | mixed
  findings:                      # structured array — replaces flat severity counts
    - id: PRR-SEC-001
      category: SEC
      severity: critical
      confidence: high
      status: open               # fixed | suppressed on re-review when applicable
      location: path:line
      evidence: [path:line]
    - id: PRR-DATA-001
      category: DATA
      severity: high
      confidence: high
      status: open
      location: other/path:42
      evidence: [other/path:42, other/path:88]
  findings_stats:                # incremental re-review counters (optional on first review)
    previous: N
    resolved: N
    remaining: N
    new: N
  engineering_improvements: N      # repo maturity items — not <review_target_noun> defects
  recommendation: approve | comment | request_changes | retrospective_observation
  confidence: high | medium | low   # overall review confidence
  merge_before_review: false
  merge_before_ci_green: false
  code_blockers_found: 0
  process_findings: 0
  suppressions_validated: 0
  review_context:
    mode: full | incremental | retrospective
    lifecycle: pre_merge | post_merge
    merge_blocking: true | false
  pipeline_status: success | failed | pending | not_configured | expected_but_missing | unavailable
  stop_search: false | true
  review_complete: true
  history:                       # v2 — incremental re-review when prior footer parseable
    approval_iteration: N
    first_review: { head_sha, finished, findings_count, highest_severity, recommendation }
    prior_review: { head_sha, finished, findings_count, highest_severity, recommendation }
    regressions: []               # or [{ id, location, prior_status, note }]
  precision:                     # v2 — every review with review_metrics
    prior_total: N
    prior_resolved: N
    prior_resolved_pct: N
    regression_count: N
    regression_rate: 0.0
    false_positives_withdrawn: N
    candidates: N
    emitted: N
    emission_rate: 0.0
  review_quality:                # v2 — omit on trivial mechanical MRs
    coverage_pct: N | partial
    evidence_pct: N
    confidence: high | medium | low
    emission_rate: 0.0
  repository_health:             # v2 — dimensions when repo context; stub schema_version: 2 otherwise
    schema_version: 2
    dimensions:
      ci: N | null
      documentation: N | null
      validation: N | null
      automation: N | null
      observability: N | null
```

Normative field definitions and examples:
[review-metadata-schema.md](../../docs/skill-framework/shared/review-metadata-schema.md).

## Review-level confidence

Overall executive-summary **Confidence** is derived from coverage, evidence depth, and review
completeness — not a simple max of per-finding confidence. Normative bands:
[confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md).

| Overall band | Derivation rule |
|--------------|-----------------|
| **High** | Full boundary reviewed; hot paths verified; pipeline/merge timeline inspected when retrospective. **Missing Jira does not cap to Medium** — note traceability separately. |
| **Medium** | Partial truncation; skipped files; fork diff-only; stop-search fired; fast path (docs/lockfile); `review_complete: false` |
| **Low** | Large cap hit; many files marked *not reviewed*; significant uncertainty; baseline stale (>30 commits); speculative findings dominate |

**Caps:**

- Partial review (`workflow/phase-5.md` §Partial review) → overall **Medium** maximum.
- Truncated diff with user declined continue → **Medium** unless only mechanical MR.
- Per-finding **High** on individual rows is allowed when overall is **Medium** (truncated MR case per shared anti-patterns).

Map to shared vocabulary for cross-skill comparison: High → HIGH, Medium → MEDIUM, Low → LOW;
when evidence is insufficient to rate → UNKNOWN.

Set `review_metadata.confidence` to the overall band (lowercase). Pair with the **Confidence:** interpretation
line immediately after the Evidence block in the executive summary.

**Traceability (optional second line):** when no Jira/ticket — `**Traceability:** Medium — no linked ticket; technical review confidence unaffected.`

## Recommendation matrix (normative — single source)

Map **highest emitted finding severity** to the executive-summary **Recommendation** and
`review_metadata.recommendation` **before** pipeline/AC/CODEOWNERS overrides. Count only emitted review
findings (Critical + High + Medium + Low — exclude nits, praise, engineering improvements).

When `review_mode: retrospective`, use retrospective matrix instead (`reference/review-modes.md`) —
never `request_changes` as merge gate.

| Highest severity | Display | `review_metadata.recommendation` |
|------------------|---------|----------------------------------|
| **Critical** | 🔴 **Request changes** | `request_changes` |
| **High** | 🔴 **Request changes** | `request_changes` |
| **Medium** | 💬 **Comment** | `comment` |
| **Low** | ✅ **Approve** | `approve` |
| **None** | ✅ **Approve** | `approve` |

**Low-only → Approve (not Comment):** Low findings belong in **Nice to have** (P2/P3), not a blocking Comment verdict.

**Incomplete review overrides the matrix:** when `review_metrics.review_complete: false`, the matrix
result above is capped by the Raises table below — an incomplete review can never render ✅ Approve
regardless of what severity was found in the portion actually reviewed.

**Retrospective override** (`review_mode: retrospective`):

| Any emitted findings | `review_metadata.recommendation` | Display |
|----------------------|----------------------------------|---------|
| Any | `retrospective_observation` | 📋 **Retrospective observation** |

**Raises** (apply after matrix; cite in **Reason** — detail in `workflow/phase-5.md` §Edge-case raises):

| Condition | Effect |
|-----------|--------|
| CODEOWNERS approval gap on changed path | Emitted as a Medium finding in Phase 2 ([workflow/phase-2.md](../workflow/phase-2.md#codeowners-approval-cross-check)) — already reflected via the matrix, not a post-hoc raise |
| Head pipeline pending/running/failed (related) | May raise per `reference/severity-rubric.md` §The blocking gate |
| Unmet AC | May raise to 🔴 **Request changes** |
| `review_metrics.review_complete: false` (stop-search fired, or a partial diff boundary accepted after a pagination/file cap — see `workflow/phase-1.md` step 2 and `workflow/phase-2.md` §Stop searching) | **Caps the verdict — never ✅ Approve.** Downgrade Approve to 💬 **Comment**, label **INCOMPLETE REVIEW**; cap overall confidence at Medium. Also forces Phase 3 to always confirm before posting, even on "review and post" (`workflow/posting.md` §Phase 3) — an incomplete review is never auto-posted as a finished one. |

Pipeline and AC rules may **raise** the verdict but must **not** downgrade below what findings alone require without explicit **Reason** text. The `review_complete: false` row is a **cap**, not a raise — it can only push the displayed recommendation down from Approve, never up past what findings otherwise require.

**Pointers only elsewhere:** `reference/severity-rubric.md` §The blocking gate (CI/pipeline modifiers) ·
`workflow/phase-5.md` §Recommendation · `reference/executive-summary.md` §Gate matrix.

## Review quality score (footer + optional prose)

Emit `review_quality` in the Phase 5 `review_metadata` YAML footer when metrics are computable. Optional
prose subsection in executive summary for human readers — omit on trivial mechanical MRs.

| Metric | Footer field | Definition |
|--------|--------------|------------|
| **Coverage %** | `review_quality.coverage_pct` | `(changed_files_reviewed / changed_files_total) × 100` from `review_metrics.coverage` |
| **Evidence %** | `review_quality.evidence_pct` | Share of emitted findings with ≥1 diff anchor and per-finding Confidence High or Medium |
| **Confidence** | `review_quality.confidence` | Overall review confidence band — same as top-level `confidence` |
| **Emission rate** | `review_quality.emission_rate` | `emitted / candidates` after pipeline filters — also in `precision.emission_rate` |

**Not precision, by name on purpose (P1 fix):** this field was previously named `finding_precision`.
Statistical precision is `true_positives / (true_positives + false_positives)` — it requires knowing,
after the fact, which emitted findings were actually correct. This field has no such ground truth; it is
`emitted / candidates`, the **share of detector hypotheses that survived the review pipeline's filters**
— a yield/emission rate, not a correctness rate. A reviewer that emits nothing (`emitted: 0`) scores
`0.0` here even on a perfectly clean, correctly-reviewed MR — the opposite of what "precision" implies.
The closest thing this framework has to actual precision is `false_positives_withdrawn` below (findings
a human later dismissed without a code change) relative to cumulative `emitted` — an approximation valid
only for findings that were later revisited, not a live metric.

**Precision block (footer):** mirrors incremental statistics for dashboards:

| Metric | Footer field | Definition |
|--------|--------------|------------|
| Prior resolved | `precision.prior_resolved` / `precision.prior_total` | N/N from incremental dedupe |
| Regression rate | `precision.regression_rate` | `regression_count / prior_resolved` when `prior_resolved > 0` |
| False positives withdrawn | `precision.false_positives_withdrawn` | Prior findings withdrawn as false positive — the closest available proxy to true precision, since it reflects an actual human correctness judgment rather than a pipeline yield rate |

**History block (footer, incremental only):** `history.first_review`, `history.prior_review`,
`history.regressions[]`, `history.approval_iteration` — see
`reference/incremental-rerun.md` §Parsing prior metadata.

Omit `review_quality` prose block on trivial mechanical MRs or when all metrics would be N/A.

**Incremental-only:** `baseline_sha`, `commits_incremental`, `scope_category`, `regression_check:
pass|fail`, `lines_added`, `lines_deleted`.

**Duplicate detection:** Phase 1 step 3 may compare `review_hash` (`scope` + `files` + `head` +
`persona`) across prior `<!-- cursor-pr-review -->` notes. When hash matches head and scope, skip
re-posting or offer chat-only refresh.

**Parsing (Phase 1 step 3):** prefer `review_metadata.head_sha` and `review_metadata.findings[]`
when YAML present; fall back to `- head_sha:` in Notes. Match prior finding IDs from the structured
array for incremental ID preservation.

## Repository maturity (informational)

Optional one-line score in Phase 5 **Engineering improvements** section — **omit when that section is
empty**. Derived from engineering-improvement items, **not** from MR defect findings.

Normative rubric and YAML footer shape: [repository-health.md](repository-health.md). Dimensions map to
`repository_health.dimensions` in the Phase 5 footer (`ci`, `documentation`, `validation`, `automation`,
`observability` — `null` when N/A).

| Dimension | Heuristic (0–10) |
|-----------|------------------|
| **CI** | 10 = green pipeline on head; 8 = CI configured but not run; 5 = partial CI; 0 = no CI config |
| **Documentation** | 10 = README + runbooks + skill refs aligned; 7 = minor drift; 4 = missing key docs |
| **Validation** | 10 = `make lint` (or equivalent) passes on head; 5 = lint configured but failing; 0 = no lint |
| **Automation** | 10 = hooks + anchor lint + pressure tests; 7 = partial; 4 = manual-only workflows |
| **Observability** | 10 = APM + dashboards + SLOs; 7 = partial; **null** when not applicable |

Example (Engineering improvements block only):

```text
Repository maturity (informational)
CI: 8/10 | Documentation: 9/10 | Validation: 10/10 | Automation: 7/10 | Observability: N/A
```

Score from observed repo state and listed improvement bullets — do not inflate when CI was not executed.
Emit matching `repository_health` block in YAML footer when dimensions are scored.

## When to record

| Phase | Action |
|-------|--------|
| Phase 1 | On incremental re-review: set `incremental.*` from prior summary + `mr_discussions`; set `coverage.*` from review boundary; parse prior `findings[]` for ID preservation |
| Phase 2 | Increment counters as pipeline steps suppress or emit; assign `PRR-{CAT}-{NNN}` IDs; build structured findings array; update `incremental.new_findings`, `remaining`, `regressed` |
| Phase 4 | Set `posted` after threads created |
| Phase 5 | Emit statistics, coverage, review cost, verification/inference, **`review_hash`**, v2
  **`history`** / **`precision`** / **`review_quality`** / stub **`repository_health`**, and
  **`review_metadata` YAML footer** in summary |

## Incremental statistics (re-review)

Compute in Phase 1 step 3 / Phase 2:

| Field | Rule |
|-------|------|
| `previous_findings` | Count from prior `review_metadata.findings[]` (or severity table fallback) |
| `resolved` | Prior finding `status: fixed` or no longer present at same evidence anchor |
| `remaining` | `previous_findings - resolved` still open in diff or unresolved threads |
| `new_findings` | Emitted findings with new `PRR-{CAT}-{NNN}` IDs not in prior array |
| `regressed` | `true` if a fixed finding's problematic code reappears — triggers ❌ regression check line |

## Coverage (all reviews)

| Field | Rule |
|-------|------|
| `changed_files_total` | Unique paths in Phase 1 review boundary |
| `changed_files_reviewed` | Paths actually read or diff-scanned (exclude deprioritised lock/vendor if listed in Notes) |
| `hunks_pct` | `100` unless API/page cap truncated diffs — then `partial` |
| `truncated` | `true` if page/file cap hit (`workflow/phase-1.md` step 2) |
| `skipped` | `true` if any boundary file marked *not reviewed* in Notes |

## Scope category (incremental re-review)

Classify **incremental boundary files only** (commits since baseline):

| Category | Paths |
|----------|-------|
| `documentation/example` | `.md`, `.mdx`, `.json` examples, templates, skill refs — default for skills repos |
| `production code` | Runtime source in incremental diff |
| `configuration` | CI, IaC, Docker, Makefile-only incremental |
| `mixed` | More than one category |

Set `scope_detail` to one short phrase: *no runtime code changed*, *no API changes*, etc.

## Notes template line

```markdown
- review_metrics: candidates=12, emitted=3, suppressed={guess:4, path:3, dedupe:1, feedback:1, value:0}, stop_search=false, context_cache=reused, cost={files:"12/12", commits:5, effort_min:15, coverage_pct:100}
- review_metrics: incremental={previous:3, resolved:3, remaining:0, new:0, regressed:false, scope:"documentation/example"}, coverage={files:"1/1", truncated:false, skipped:false}, change_classification:documentation
```

Omit on first trivial reviews or when all zeros except emitted.

## Using metrics for improvement

| Metric | Interpretation |
|--------|----------------|
| High `suppressed.path` | Checklist may be too speculative — tune detectors |
| High `suppressed.guess` | Good — gate working; or diff context too thin |
| High `suppressed.feedback` | Team ignores categories — verify non-negotiable not affected |
| `emitted` >> `posted` | chat-only mode or gate blocked posting |
| Low `emitted` / high `candidates` | Healthy filtering |

Cross-MR persistence: the **`review_metadata` YAML footer** (with `review_hash` and structured
`findings[]`) is the supported machine-readable artifact for dashboards and structured re-reviews;
prose Notes lines remain optional.

## Feedback learning link

When `suppressed.feedback > 0`, Phase 5 Confidence may note *"adapted frequency for ignored categories"*
(`reference/review-feedback-learning.md`). Cap: if `suppressed.feedback` would hide a non-negotiable
category, **do not increment** — emit instead.
