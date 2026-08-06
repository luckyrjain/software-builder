# Comment Templates

Use these so every review looks consistent and every comment is actionable. All bodies are GitLab
Flavored Markdown.

> **Never include a secret value in a comment body.** If a token, key, password, or other credential
> appears in the diff, reference its **location only** (`file:line`), state that it must be **rotated**,
> and never echo or paraphrase the value. This applies to inline threads, summary notes, and Jira
> write-back.

## Inline comment (one per finding) → `create_merge_request_thread`

Format:

```
<emoji> **[Overall]** PRR-{CAT}-NNN — <one-line problem statement>
Likelihood: <H|M|L> · Impact: <H|M|L> · Overall: <Critical|High|Medium|Low>
Confidence: <High|Medium|Low>
Evidence: `path:line`[, `path:line`, …]
Blast radius: <who/what affected — required for High/Critical>
Business impact: <customer/compliance chain — payments High/Critical only>

<why it matters — 1–2 sentences, concrete>

Evidence detail — OEDR (config): Observed / Expected / Difference / Risk
Evidence detail — OUR (inferred): Observed / Unknown / Risk
(see finding-evidence-model.md; pick one format)

<suggested fix — prose, or a suggestion block when a precise change applies>
```

Nits and praise omit the Likelihood/Impact line and use `PRR-{CAT}-NNN` only when the finding was assigned an
ID (optional for bundled nits). See `reference/severity-rubric.md` for definitions and the risk matrix.

Example (added line, so `new_line` set, `old_line: null`):

```
🟠 **[High]** PRR-API-001 — `fetch_user` has no timeout, so a slow upstream blocks the request thread indefinitely.
Likelihood: High · Impact: Medium · Overall: High
Confidence: High
Evidence: `api/client.py:42`

Under upstream latency this exhausts the worker pool and cascades into a site-wide stall.

```suggestion:-0+0
    resp = httpx.get(url, timeout=5.0)
```
```

Architecture lens (§16 — prefix `arch · <concern>`):

```
🟡 **[Medium]** PRR-ARCH-001 — arch · coupling — `checkout/handler.go:14` imports `billing/internal/ledger` directly.
Likelihood: Medium · Impact: Medium · Overall: Medium
Confidence: High
Evidence: `checkout/handler.go:14`

Bypasses the `billing.Client` facade used elsewhere; couples checkout deploys to billing internals.
Related: `billing/internal/ledger/post.go` (unchanged).

Suggested fix: extend `billing.Client` with the needed operation instead of importing `internal/`.
```

**Root cause group** (one inline thread — anchor to first location; list all sites in body; reference
primary finding ID):

```
🟠 **[High]** PRR-DATA-001 — Root cause: Payment transaction date handling
Likelihood: High · Impact: High · Overall: High · Score: 9
Confidence: High
Evidence: `PdnScheduler.java:142`, `TxnDateUtil.java:28`
Blast radius: All PDN notifications
Business impact: Wrong notification date → customer debited on wrong day → dispute/compliance risk

Three manifestations of one date-calculation gap — fix once with shared `getTxnDate(gap)`.

**Sub-findings:** epoch mismatch · gap ignored · null on gap

**Affected locations:** `PdnScheduler.java:142`, `TxnDateUtil.java:28`

**Suggested systemic fix:** Single null-safe `getTxnDate(gap)` with consistent epoch handling.
```

**Root cause group** (validation pattern — multiple handlers):

```
🟡 **[Medium]** PRR-API-002 — Root cause: Missing defensive validation on handler inputs
Likelihood: High · Impact: Medium · Overall: High · Score: 6
Confidence: High
Evidence: `api/refund.py:42`, `api/capture.py:18`, `api/void.py:31`, `api/list.py:88`, `api/export.py:12`
Blast radius: All listed API endpoints

Five handlers accept user input without null/empty checks — same gap, one fix pattern.

**Sub-findings:** missing null check · missing empty-string guard

**Affected locations:** `api/refund.py:42`, `api/capture.py:18`, `api/void.py:31`, `api/list.py:88`, `api/export.py:12`

**Suggested systemic fix:** Add a shared `require_non_empty()` (or use the existing `validators` module) at handler entry; apply across these endpoints in one pass rather than five one-off checks.
```

The ` ```suggestion ` block renders an **Apply suggestion** button in GitLab. The `:-a+b` suffix sets
the replacement range **relative to the commented line**: `a` = lines above it and `b` = lines below
it that the suggestion also replaces. So `:-0+0` replaces only the commented line; `:-1+2` replaces the
line above, the commented line, and the two lines below (4 lines total). The replacement text inside
the block is the full new content for that range. Use suggestions only when you can write the exact
replacement; otherwise describe the fix in prose.

Nitpicks:

```
⚪ nit: prefer a guard clause here to cut the nesting — non-blocking, your call.
```

Bundled nits (one thread when the inline budget is tight — anchor to the first listed file):

```
⚪ **Nits** (bundled)

- `payments/refund.py:42` — nit: prefer a guard clause to cut nesting.
- `payments/refund.py:88` — nit: rename `amt` → `amount_cents` for clarity.
- `payments/webhook.py:12` — nit: stale comment above handler.
```

Praise:

```
🟢 praise: nice — the idempotency key on this handler makes the webhook safe to retry.
```

**Test gap (retrospective or pre-merge — implementation may be correct):**

```
🟡 **[Medium]** PRR-TEST-001 — Missing parameterized tests for LPC percentage edge cases.
Likelihood: Medium · Impact: Medium · Overall: Medium
Confidence: High
Evidence: `LpcCalculator.java:88`

**Risk:** Future regressions on LPC percentage edge cases.

**Current implementation:** Appears correct — no behavior regression observed in diff.

**Evidence:** `divide(..., 6, HALF_UP)` handles scale; happy path logic verified in review.

**Gap:** Table-driven edge-case tests missing — recommend follow-up MR with case matrix.
```

**Process finding — merge-before-CI:**

```
🟡 **[Medium]** PRR-PROC-001 — Repository policy risk: merge before CI green on head.
Likelihood: High · Impact: Medium · Overall: Medium
Confidence: High

**Repository policy risk:** Merge completed ~24s before pipeline passed on head.

**Recommendation:** Require green pipeline before merge on payment branches.
```

**Retrospective summary header** (post-merge audit):

```
<!-- cursor-pr-review -->
## 📋 Post-merge audit — !<iid> · <source_branch> → <target_branch> (merged)

**Review mode:** Retrospective · **MR state:** merged
**Reviewed:** <ISO-8601>
```

## Summary comment (exactly one) → `create_note`

The **first line must be** the idempotency marker so re-runs can detect a prior review:

**When all emitted findings are zero** (Critical + High + Medium + Low + nits = 0): do **not** print
empty `### 🔴 Critical` / `### 🟠 High` / … sections or a findings table with only header rows. After
the severity count table (all zeros), use:

```markdown
### Findings

No actionable findings.

### Engineering improvements *(omit when empty — not MR defects)*

- Add `.gitlab-ci.yml` running `make lint` — repo has no CI configured (non-blocking).
- Consider anchor-lint for `](reference/*.md#...)` links in skill docs.
```

On incremental re-reviews with no new issues, use *No new actionable findings in incremental diff* under
**Still open / new** — see re-review template below.

**Output structure:** split **Review findings** (diff defects, severity-scored) from **Engineering
improvements** (repo maturity). Only review findings count in the severity table and blocking gate.

```
<!-- cursor-pr-review -->
## 🤖 Code Review — !<iid> · <source_branch> → <target_branch>

**Reviewed:** <ISO-8601 timestamp, e.g. 2026-06-25T09:35:00Z>
**Review lens:** <persona> *(e.g. Principal Engineer — default)*

Linked ticket: [PAY-1421](<jira_url>) — _Add refund webhook_

| Severity | Count |
|----------|-------|
| 🔴 Critical | 1 |
| 🟠 High | 2 |
| 🟡 Medium | 3 |
| 🔵 Low | 1 |
| ⚪ Nits | 4 |

### 🔴 Critical
- **`PRR-SEC-001`** · **`payments/webhook.py:42`** — L: High · I: High · Overall: Critical · Confidence: High — Signature check skipped when
  the header is absent; forged refund events accepted. → inline thread above.

### 🟠 High
- **`PRR-DATA-001`** · **`payments/refund.py:88`** — L: Medium · I: High · Overall: High · Confidence: High — Refund amount uses `float`; use
  `Decimal` to avoid rounding loss on money.
- **No tests** cover the new refund path.

### 🟡 Medium
- **`PRR-ARCH-002`** · `webhook.py` — scope creep in logging config (split into its own MR?).
- **`PRR-DOC-001`** · `docs/schema.md:12` — doc drift · reference stale — README says v2, schema says v3 · Confidence: High · Evidence: `docs/schema.md:12`, `README.md:88`
- **`PRR-API-003`** · Empty-`items` case in `summarize_refunds` is unhandled.

### Root cause groups
**Payment transaction date handling** — Score 9 · Overall High · L: High · I: High · Conf: High  
Blast radius: All PDN notifications · Business impact: Wrong debit date → dispute/compliance risk  
Affected: `PdnScheduler.java:142`, `TxnDateUtil.java:28`  
Sub-findings: epoch mismatch · gap ignored · null on gap  
Systemic fix: single null-safe `getTxnDate(gap)`.

**Missing defensive validation** — Score 6 · Overall High · L: High · I: Medium  
Affected: `refund.py:42`, `capture.py:18`, `void.py:31`  
Systemic fix: shared `require_non_empty()` at handler boundary.

### 🔵 Low
- **`PRR-DOC-002`** · **`payments/setup.py:12`** — missing doc for new public API field.

### ⚪ Nits
- `refund.py:42` — nit: prefer guard clause over nested `if`.
- `webhook.py:12` — nit: stale comment above handler.
- *(Or one bundled inline nit thread when ≥3 nits or Phase 4 cap requires it.)*

### Rollback safety *(include when §17 ran; omit if not risky)*
| Question | Status | Evidence |
|----------|--------|----------|
| Can this be rolled back? | ⚠️ | Deploy revert OK; schema needs forward migration |
| Backward compatible? | ✅ | Additive column with default |
| Schema reversible? | ❌ | `NOT NULL` without backfill — no `down` path |
| Feature flagged? | ❌ | New path always on |
| Kill switch? | ⚠️ | No documented disable toggle |
| Migration safe? | ⚠️ | Index on large table — lock risk |
| Dual write / backfill? | N/A | No data migration |
| Canary possible? | ⚠️ | Not in MR description |

### Test quality *(include when production logic changed; omit for docs-only)*
| Dimension | Status | Evidence |
|-----------|--------|----------|
| Coverage | ⚠️ | Happy path only in `test_refund.py` |
| Edge cases | ❌ | Empty refund list untested |
| Negative cases | ❌ | Invalid signature not asserted |
| Concurrency | N/A | — |
| Failure injection | ❌ | No upstream timeout test |
| Regression | ✅ | Test references PAY-1421 bug |
| Property tests | N/A | — |
| Integration | ⚠️ | No webhook integration test |
| Contract | N/A | — |
| Load | N/A | — |

### ✅ Acceptance criteria
- [x] Accepts Stripe refund webhooks
- [x] Updates ledger entry
- [ ] **Verifies webhook signature** ← not met (see Critical)
- [ ] **Idempotent on duplicate delivery** ← not met (no idempotency key)

### Architectural summary
| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Overall design** | Good | Clear handler/service split; fits existing `payments/` layout |
| Maintainability | Acceptable | Direct `billing/internal` import tightens coupling (see arch finding) |
| Complexity | Good | Straightforward flow; no unnecessary indirection |
| Readability | Good | Names and structure match repo conventions |
| Future cost | Needs Work | New flag without sunset; coupling may slow billing changes |

### Production risk
| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Production risk** | Medium | Reversible deploy; webhook path is production-critical |
| Deployment risk | Low | Standard rolling deploy; no migration |
| Rollback difficulty | Medium | Schema additive only — see §17 |
| Blast radius | Medium | All refund webhooks until revert |
| User impact | Medium | Wrong refunds if signature bug ships |

### Executive Summary

Refund webhook handler is well-structured but ships without signature verification — a **Critical**
security gap on a production money path. Request changes before merge.

### Evidence

- ✓ 8/8 changed files reviewed in diff
- ✓ Full diff reviewed; linked Jira ticket with explicit AC
- ✓ No truncated diffs or skipped hunks

**Confidence:** High — full boundary reviewed; ticket linked; no truncation.

### Code blockers

| Finding | Severity | Blast radius | Business impact | Conf |
|---------|----------|--------------|-----------------|------|
| Webhook signature verification | Critical | All refund webhooks | Forged refunds accepted | High |

### Decision gates

| Gate | Result |
|------|--------|
| Runtime correctness | ❌ |
| Payment correctness | ❌ |
| Security (application) | ❌ |
| CI | ✅ |
| **Recommendation** | **🔴 Request changes** |

### Technical blockers

| Gate | Status |
|------|--------|
| Critical findings | ⚠️ 1 |
| High findings | ⚠️ 1 |
| Runtime correctness | ❌ |
| Review coverage | ✅ Complete (8/8) |

### Process blockers

| Gate | Status |
|------|--------|
| CI pipeline | ✅ Green |
| CODEOWNERS | ✅ Satisfied |
| Jira / AC | ✅ Met |
| Approvals | 1/2 |

**Reason:** Critical signature gap on production money path blocks merge; Decimal and test gaps are High but secondary.

**Review cost**
| Files reviewed | Commits | Est. effort | Coverage |
|----------------|---------|-------------|----------|
| 8 / 8 | 4 | ~25 min | 100% |

**Major concerns**
- Webhook signature not verified — forged refunds possible
- Money path uses `float` instead of `Decimal`

**Must fix**
- `PRR-SEC-001` · Webhook signature — `payments/webhook.py:42` (Critical · All refund webhooks)
- `PRR-DATA-001` · Decimal for money — `payments/refund.py:88` (High · Refund ledger writes)

**Nice to have**
- **P1** — Scope creep in logging config (Medium)
- **P2** — Negative test for forged webhook payload

| Architecture | Testing | Security | Maintainability | Production readiness |
|--------------|---------|----------|-----------------|----------------------|
| Good | Weak | Needs attention | Adequate | Not ready |

**Pipeline:** ✅ success on head · **Approvals:** 1/2 required

### Engineering improvements *(not MR defects)*
- Add `.gitlab-ci.yml` with `make lint` — CI not configured in repo (non-blocking).

Repository maturity (informational)
CI: 8/10 | Docs: 9/10 | Lint: 10/10 | Automation: 7/10

### Notes
- Stop searching: threshold reached (2 Critical · 3 High · 10 total) — partial review. *(omit if full pass)*
- Fast path: lockfile-only; CI/arch/security checklists skipped. *(omit if standard path)*
- Context cache: CODEOWNERS, CLAUDE.md, review-rules.yaml @ head_sha abc123. *(omit on first review; optional)*
- review_metrics: candidates=12, emitted=3, suppressed={guess:4, path:3, dedupe:1, feedback:0, value:0}, stop_search=false. *(optional — framework tuning)*
- Repo rules: payments (critical: ledger, money, idempotency); search (latency). *(omit if no review-rules.yaml)*
- Deprioritised: `tests/fixtures/*` (generated) — not reviewed line by line. *(list all skipped paths)*
- Not reviewed: `src/large_file.py` — diff truncated by API; `assets/logo.png` — binary. *(list all truncated or binary files; omit section if none)*
- Posting mode: `full` *(replace with the actual mode detected in Phase 0)*
- head_sha: `<full_sha>` *(machine-parseable — re-reviews parse this exact line; always include the full commit SHA)*

```yaml
review_metadata:
  review_type: full
  started: "2026-06-25T09:30:00Z"
  finished: "2026-06-25T09:35:00Z"
  tool_calls: 24
  files_fetched: 8
  diff_pages: 1
  head_sha: "<full_sha>"
  review_hash:
    scope: full
    files: 8
    head: "<short_sha>"
    persona: principal_engineer
  persona: principal_engineer
  files_reviewed: 8
  files_total: 8
  commits_in_mr: 4
  estimated_effort_min: 25
  coverage_pct: 100
  change_classification: production_code
  findings:
    - id: PRR-SEC-001
      category: SEC
      severity: critical
      confidence: high
      status: open
      location: payments/webhook.py:42
      evidence: [payments/webhook.py:42]
    - id: PRR-DATA-001
      category: DATA
      severity: high
      confidence: high
      status: open
      location: payments/refund.py:88
      evidence: [payments/refund.py:88]
    - id: PRR-ARCH-002
      category: ARCH
      severity: medium
      confidence: high
      status: open
      location: webhook.py:120
      evidence: [webhook.py:120]
  engineering_improvements: 1
  recommendation: request_changes
  confidence: high
  pipeline_status: success
  stop_search: true
  review_complete: true
  precision:
    prior_total: 0
    prior_resolved: 0
    regression_count: 0
    regression_rate: 0.0
    false_positives_withdrawn: 0
    candidates: 12
    emitted: 3
    emission_rate: 0.25
  review_quality:
    coverage_pct: 100
    evidence_pct: 100
    confidence: high
    emission_rate: 0.25
  repository_health:
    schema_version: 2
```

### Out-of-diff recommendations *(drop section if empty)*
- Worth checking `<file>` — `<reason>` but it was not in this diff.

### Posting notes *(drop section if empty)*
- N findings could not be anchored inline — see entries above.

_Reviewed by Cursor `/pr-review`. Reply to any thread to discuss; resolve when addressed._
```

Adapt sections to what you actually found — drop empty severities, drop the acceptance-criteria block
if there's no linked ticket. Pipeline and approvals live in **Executive Summary**, not Notes. Within each
severity section (### Critical, ### High, …), list findings **highest rank score (L × I) first**.

## Re-review summary (when the marker already exists)

Render **in chat and in the posted summary** when Phase 1 recorded an incremental baseline. Load
`reference/incremental-rerun.md` for dedupe; populate counters from `review_metrics.incremental` and
Phase 1 boundary.

```
<!-- cursor-pr-review -->
## 🤖 Code Review (re-review) — !<iid> · <source_branch> → <target_branch>

**Reviewed:** <ISO-8601 timestamp>
**Review lens:** <persona> *(e.g. Principal Engineer — default)*
**Baseline:** `<baseline_sha>` → **Head:** `<head_sha>` · <N> commit(s) since baseline

### Incremental scope
<N> <scope_category> file(s) · <scope_detail>

**Change classification:** Documentation · Templates · Metadata · No executable runtime code · Production code · Mixed *(pick best fit; enables automation)*

Scope categories (pick the best fit for files in the incremental boundary):
- **documentation/example** — `.md`, `.mdx`, examples, templates, skill reference files; no runtime code
- **production code** — application/service logic in the incremental diff
- **configuration** — CI, IaC, manifests, build scripts only
- **mixed** — more than one category in the incremental boundary

Scope detail examples: *no runtime code changed* · *no API changes* · *docs + example JSON only*

### Review scale
| Metric | Value |
|--------|-------|
| Commits (incremental) | <N> |
| Files (incremental) | <N> |
| Lines changed (incremental) | ~<N> additions / ~<N> deletions *(from git or MR stats when available)* |
| Reviewed | <reviewed>/<total> files · 100% hunks |

| Metric | Value |
|--------|------:|
| Previous findings | <N> |
| Resolved | <N> |
| Remaining | <N> |
| New findings | <N> |

**Regression check:** ✅ No previously resolved issue reintroduced. *(or ❌ Regressed: `<file:line>` — brief)*

**Coverage:** <reviewed>/<total> changed files · hunks <100%|partial> · truncated: <Yes\|No> · skipped: <Yes\|No>

**Review status:** Review completed normally · stop-search threshold not triggered. *(or: Review stopped
after <N> <severity> finding(s) per review policy — see Notes.)*

Linked ticket: [PAY-1421](<jira_url>) — _Add refund webhook_ *(omit if none)*

| Severity | Count |
|----------|-------|
| 🟡 Medium | 0 |
| ⚪ Nits | 0 |

### Findings

No actionable findings.

*(When `new_findings` ≥ 1, replace with severity sections listing items.)*

### Resolved since last review
- **`PRR-DATA-001`** 🟠 Money math switched to `Decimal` — ✅
- **`PRR-DOC-001`** 🟡 `evidence.example.json:70` — list_deployments replaced with documented fallback — ✅
- 🟡 MR title/description — scope and optional CLI clarified — ✅ *(metadata fixes count as resolved)*

### Still open / new

No new actionable findings in incremental diff.

### Executive Summary

Previous Critical and High findings are resolved; incremental diff limited to documentation/example updates. No regressions detected.

### Evidence

- ✓ `make lint` executed successfully on head
- ✓ 13/13 incremental changed files reviewed in diff
- ✓ No truncated diffs or skipped hunks
- ✓ All prior inline threads resolved
- ✓ Change classification: Documentation · no executable runtime code

**Confidence:** High — entire incremental diff reviewed; all prior threads resolved.

### Inference

- ✓ No regressions detected vs prior resolved findings
- ✓ Incremental change category: documentation/example — no runtime code changed
- ✓ Merge risk remains Low

| Gate | Status |
|------|--------|
| Critical findings | ✅ None |
| High findings | ✅ None |
| CI | ❓ Not configured |
| Regression | ✅ None |
| Review coverage | ✅ Complete (13/13) |
| Prior findings | ✅ 3/3 resolved |
| **Recommendation** | **✅ Approve** |

**Reason:** All prior findings resolved; incremental diff is documentation-only with no security or deployment surface; safe to merge pending repo CI policy.

**Review cost**
| Files reviewed | Commits | Est. effort | Coverage |
|----------------|---------|-------------|----------|
| 13 / 13 | 5 | ~10 min | 100% |

**Blocking Issues: None**

**Nice to have**
- **P2** — Add `.gitlab-ci.yml` running `make lint` (non-blocking)

| Architecture | Testing | Security | Maintainability | Production readiness |
|--------------|---------|----------|-----------------|----------------------|
| Good | Strong | Clear | Good | Ready |

**Pipeline:** ❓ not configured (no `.gitlab-ci.yml` in repo) · **Approvals:** 2/2 required

> **Incremental review complete.** All previously reported issues are resolved, no regressions were found, and the current change set is suitable for approval pending repository CI/policy requirements.

### Engineering improvements *(not MR defects)*
- Add `.gitlab-ci.yml` running `make lint` — repo has no CI configured.

Repository maturity (informational)
CI: 8/10 | Docs: 9/10 | Lint: 10/10 | Automation: 7/10

### Notes
- head_sha: `<full_sha>` *(machine-parseable — re-reviews parse this exact line; always include the full commit SHA)*
- Posting mode: `full` *(actual mode from Phase 0)*
- review_metrics: incremental={previous:3, resolved:3, remaining:0, new:0}, coverage={files:"13/13", truncated:false, skipped:false}, stop_search=false

```yaml
review_metadata:
  review_type: incremental
  started: "2026-06-25T10:10:00Z"
  finished: "2026-06-25T10:15:00Z"
  tool_calls: 18
  files_fetched: 13
  diff_pages: 1
  baseline_sha: "<baseline_sha>"
  head_sha: "<head_sha>"
  review_hash:
    scope: incremental
    files: 13
    head: "<short_sha>"
    persona: principal_engineer
  persona: principal_engineer
  scope_category: documentation/example
  change_classification: documentation
  commits_incremental: 5
  commits_in_mr: 5
  files_reviewed: 13
  files_total_incremental: 13
  lines_added: 333
  lines_deleted: 55
  estimated_effort_min: 10
  coverage_pct: 100
  coverage:
    hunks_pct: 100
    truncated: false
    skipped: false
  findings: []
  findings_stats:
    previous: 3
    resolved: 3
    remaining: 0
    new: 0
  engineering_improvements: 1
  regression_check: pass
  stop_search: false
  recommendation: approve
  confidence: high
  pipeline_status: not_configured
  review_complete: true
  history:
    approval_iteration: 2
    first_review:
      head_sha: "<baseline_sha>"
      finished: "2026-06-24T14:00:00Z"
      findings_count: 3
      highest_severity: high
      recommendation: request_changes
    prior_review:
      head_sha: "<baseline_sha>"
      finished: "2026-06-24T14:00:00Z"
      findings_count: 3
      highest_severity: high
      recommendation: request_changes
    regressions: []
  precision:
    prior_total: 3
    prior_resolved: 3
    prior_resolved_pct: 100
    regression_count: 0
    regression_rate: 0.0
    false_positives_withdrawn: 0
    candidates: 6
    emitted: 0
    emission_rate: 0.0
  review_quality:
    coverage_pct: 100
    evidence_pct: 100
    confidence: high
    emission_rate: 0.0
  repository_health:
    schema_version: 2
```

_Re-reviewed by Cursor `/pr-review`._
```

**Empty incremental diff:** when head changed but no new findings and no file changes in boundary, still
emit statistics, regression check, coverage, Evidence + Inference inside Executive Summary, and closing loop — *"No new
actionable findings in incremental diff"* is valid and preferred over inventing feedback.

## Optional Jira write-back → `addCommentToJiraIssue`

**Best-effort only.** Jira permissions and workflow rules vary by project — comment posting can fail on
Epics, closed issues, or restricted issue types. If the API rejects the call, log the error in chat and
move on; **never halt** the review or retry in a loop. Do not transition issue state unless the user
explicitly requested it (transitions often require custom fields).

```
Code review completed on GitLab MR !123 (<web_url>).
Review summary: <summary_note_url>
Recommendation: Comment
Reason: Non-blocking documentation inconsistencies. No runtime risk. Safe to merge after discretionary cleanup.
```

Build `<summary_note_url>` from the note just posted: re-fetch `get_merge_request_notes` (or
`get_workitem_notes`) and use the `web_url` of the note whose body starts with
`<!-- cursor-pr-review -->`, or `<mr_web_url>#note_<note_id>` if `web_url` is absent.

On success, confirm in chat: *"Posted review summary to Jira `PAY-1421`."* On failure, confirm GitLab
review is still complete and quote the API error — do not treat Jira failure as a posting rollback.
