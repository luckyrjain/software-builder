# Executive Summary (Phase 5 — final)

Load when rendering the **final Executive summary** — the capstone for EMs and staff engineers. Aggregate
from Phase 1 inventory, findings, §8 test quality, §17 rollback, Production risk, and Architectural
summary. Do not re-review the diff.

## When to include

- **Always** for completed reviews (including mechanical MRs — use brief form).
- This **replaces** a lone `Approve` / `Comment` / `Request changes` line as the primary takeaway;
  **Recommendation** inside the executive summary maps to those verdicts.

## Output order (end of Phase 5)

1. **Review findings** — defects in the MR diff (findings table, root-cause groups, §17/§8 tables)
2. **Not raised (suppressed)** — intentional omissions and merged clusters (`reference/not-raised.md`) — when applicable
3. **Engineering improvements** — repo maturity suggestions — **not** MR defects; omit when empty
4. **Positive observations** — genuine strengths (`reference/positive-observations.md`) — when ≥2 apply
5. `### Production risk` (non-mechanical MRs)
6. `### Architectural summary` (non-mechanical MRs)
7. **`## Executive Summary`** ← capstone verdict block
8. **`## Conclusion`** ← 2–4 sentences after Executive Summary; no agent CTAs

## Narrative

Open with **2–4 sentences**: what the MR does, overall quality, and the recommendation in plain language.
No jargon; readable by an EM who did not read every inline comment.

## Fields

| Field | Source / rules |
|-------|----------------|
| **Files reviewed** | From Phase 1: `N files changed` (+ deprioritised/truncated if any). Example: `12 changed, 2 deprioritised (generated)` |
| **Review cost** | See **Review cost metrics** subsection — files reviewed, commits in MR, estimated effort (minutes), coverage % |
| **Risk** | **Production risk** overall (Low / Medium / High). If Production risk omitted, derive from highest open finding Overall |
| **Evidence** | **Required** checklist of observed facts — checkmarks, concrete counts (`N/N` files, commands run, truncation status). Merges the former Verification checklist. See **Evidence** subsection below. |
| **Confidence** | **High** / **Medium** / **Low** — one interpretation line immediately after **Evidence** (not a separate "Confidence reason" section). Separate from per-finding confidence in the findings table. Never emit a bare label without justification. Per-finding and overall confidence bands: [confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md). Derivation rules: [review-metrics.md](review-metrics.md) §Review-level confidence. |
| **Inference** | **Optional on first review; required on incremental re-reviews.** 2–4 bullets max — judgment derived from evidence (regressions, scope category, merge risk). Separate block **after** Evidence; label `### Inference` or `## Inference`. |
| **Gate matrix** | **Code blockers** (findings + business impact) → **Decision gates** → **Technical blockers** → **Process blockers** → **Recommendation** — see §Gate matrix |
| **Recommendation reason** | **Required** on every review. One prose block **after** gate tables explaining *why* the verdict was reached. Use the `**Reason:**` label (see template). On 🔴 Request changes, cite blocking items briefly. |
| **Blocking issues** | When no Critical/High and no unmet AC: single line **`Blocking Issues: None`**. When blocking items exist, use **Major concerns** + **Must fix** subsections instead (do not also print "Blocking Issues: None"). |
| **Major concerns** | Bullet list: Critical/High themes + Production risk **High** drivers (max 5; one line each). **Omit section when empty** — do not print "Major concerns — none". |
| **Must fix** | Blocking items: all **Critical** and **High** findings (or root-cause groups) + unmet AC. **Order by blast radius × severity** — not discovery order. Example order: payment correctness → pool/config → security → retry/fallback → null handling → serialization. **Omit section when empty** — do not print "Must fix — none". |
| **Nice to have** | **Medium**, **Low**, bundled **nits** — rank **P1** / **P2** / **P3** (P1 = highest value follow-up). Omit section when none. |
| **Review findings** | Defects anchored in the MR diff — findings table + severity sections. Each row includes per-finding **Confidence** (High/Medium/Low). |
| **Engineering improvements** | Repo maturity items **outside** the diff defect scope (missing CI, lint anchor ideas, pressure-test gaps). **Not** counted in severity table or blocking gate. Optional **Repository maturity** score line when this section is non-empty (`reference/review-metrics.md`). |
| **Change classification** | From Phase 1 fast path: `Documentation` / `Templates` / `Metadata` / `No executable runtime code` / `Production code` / `Mixed` — print in executive summary when docs-only or metadata-only MR. |
| **Architecture score** | **Overall design** from Architectural summary → map label to score: Excellent/Good → **Strong**, Acceptable → **Adequate**, Needs Work → **Weak**, Major Concerns → **Critical**. If arch summary omitted: **Adequate** default for trivial MRs |
| **Testing score** | From §8 table **and** verification evidence (CI green on head, tests/validators executed). See **Testing score bands** below. |
| **Security score** | See §Security score bands — **never Clear** when any High app-level security finding (auth, exposure) is open; nuance deps vs application |
| **Recommendation** | ✅ Approve / 💬 Comment / 🔴 Request changes / 📋 Retrospective observation — see `reference/review-modes.md` for lifecycle modes |
| **Maintainability score** | **Maintainability** from Architectural summary (same Strong/Adequate/Weak/Critical map) |
| **Production readiness** | Pre-merge: Not ready when High/Critical blockers. **Retrospective:** **Ready · Operational improvements recommended** when zero runtime code blockers (`reference/review-modes.md`) |
| **Closing loop** | **Required on incremental re-reviews.** One sentence: incremental review complete, prior issues resolved/regressed, suitable for approval pending CI/repo policies. See re-review template in `reference/comment-templates.md`. |
| **Review lens** | Persona used (e.g. *Principal Engineer* — default). Surface near **Reviewed:** timestamp in summary notes. |
| **Verification vs inference** | **Evidence** — observed facts (lint executed, files read, truncation status). **Inference** — judgment (no regressions, scope category, merge risk). Never mix them in one bullet list; Evidence precedes Inference. |
| **Review scale** | Incremental re-reviews: commits, files, lines changed, reviewed fraction — see re-review template. |
| **Stop-search status** | *Review completed normally · stop-search threshold not triggered* — or cite threshold hit and count (`review_metrics.stop_search`). |
| **Review duration** | Telemetry block in `review_metadata` YAML: `started`, `finished`, `tool_calls`, `files_fetched`, `diff_pages` (`reference/review-metrics.md`). |

### Evidence — observed facts

Emit a `### Evidence` block (or `## Evidence` when standalone) with checkmark bullets and **concrete counts**. Include what applies; omit lines that are N/A.

| Bullet type | Example |
|-------------|---------|
| Coverage | `✓ 12/12 changed files reviewed in diff` |
| Commands | `✓ make lint executed successfully on head` |
| Truncation | `✓ No truncated diffs or skipped hunks` |
| Ticket | `✓ Linked Jira ticket with explicit AC` |
| Re-review | `✓ All prior inline threads resolved` |
| Classification | `✓ Change classification: Documentation · no executable runtime code` |

Immediately after the Evidence bullets, emit **one** confidence interpretation line:

```markdown
**Confidence:** High — full boundary reviewed; ticket linked; no truncation.
```

| Rating | Typical interpretation (pick what applies) |
|--------|---------------------------------------------|
| **High** | Entire incremental/full diff reviewed; no truncated or skipped files; ticket linked; team resolved prior bot findings quickly |
| **Medium** | Partial truncation; no ticket; fork diff-only; stop-search threshold hit; fast path (docs/lockfile); limited bot history |
| **Low** | Large cap hit; many files skipped; significant uncertainty; baseline stale (>30 commits) |

Do **not** emit a separate **Confidence reason** subsection — the single line above replaces it.

### Inference — judgment (after Evidence)

2–4 bullets max. Required on incremental re-reviews; optional on first review when judgment adds value.

```markdown
### Inference

- No regressions detected vs prior resolved findings
- Incremental change category: documentation/example — no runtime code changed
- Merge risk remains Low
```

### Gate matrix — code blockers, decision gates, technical vs process

Emit **four blocks** immediately **before** `**Reason:**`. Separate **what is wrong in code** from
**what blocks merge procedurally**.

#### 1. Code blockers

Emitted **Critical + High only** — Medium/Low findings stay in the findings table (not duplicated here).
One row per root-cause cluster:

```markdown
### Code blockers

| Finding | Severity | Blast radius | Business impact | Conf |
|---------|----------|--------------|-----------------|------|
| Wrong transaction date | High | All PDN notifications | Customer notified on wrong day | High |
| Hikari pool churn | High | Entire service | Payment failures under load | High |
| Resilience fallback | High | Juspay failure path | Failed notification retries | High |
| Kafka endpoint (no auth) | High | External callers | Unauthorized payment processing | Medium |
```

- **Business impact** column **required** on payments / production-critical MRs for High/Critical rows.
- Omit table when no Critical/High — print *Code blockers: None* as one line.

#### 2. Decision gates

Deterministic recommendation algorithm — makes verdict feel algorithmic:

```markdown
### Decision gates

| Gate | Result |
|------|--------|
| Runtime correctness | ❌ |
| Payment correctness | ❌ *(omit when not payments MR)* |
| Security (application) | ⚠️ |
| CI | ❌ |
| **Recommendation** | **🔴 Request changes** |
```

| Gate | Derivation |
|------|------------|
| **Runtime correctness** | ❌ when any High/Critical non-payment defect on hot path; ✅ when none |
| **Payment correctness** | ❌ when any High/Critical on payment/PDN/ledger path (payments persona) |
| **Security (application)** | ⚠️ when High app-level SEC finding; ✅ when Clear; ❌ when Critical security |
| **CI** | ❌ failed/cancelled on head; ⏳ pending; ✅ green |
| **Recommendation** | From recommendation matrix + raises |

#### 3. Technical blockers

Code and runtime gates — **not** process:

```markdown
### Technical blockers

| Gate | Status |
|------|--------|
| Critical findings | ⚠️ N *(unique clusters)* |
| High findings | ⚠️ N |
| Runtime correctness | ❌ |
| Payment correctness | ❌ |
| Review coverage | ✅ Complete (N/N) / ⚠️ Partial |
| Regression *(re-review)* | ✅ None / ⚠️ … / N/A |
```

#### 4. Process blockers

Merge policy — **not** code defects:

```markdown
### Process blockers

| Gate | Status |
|------|--------|
| CI pipeline | ❌ Cancelled on head |
| CODEOWNERS | ⚠️ Pending @payments-team |
| Jira / AC | ⚠️ No linked ticket |
| Approvals | 0/2 |
| Prior findings *(re-review)* | ✅ N/N resolved |
```

**Recommendation** appears as the **final row of Decision gates** — not duplicated in Process blockers.

Matrix verdict: [review-metrics.md](review-metrics.md) §Recommendation matrix. Code blockers drive
**Request changes** on pre-merge; **retrospective** mode uses **Retrospective observation** only
(`reference/review-modes.md`).

### Retrospective (post-merge) executive summary

When `review_mode: retrospective`:

1. Open narrative: *Post-merge audit — MR already merged to `{target}`.*
2. **Confidence: High** when full diff + hot paths reviewed; optional **Traceability:** line if no Jira.
3. Decision gates **Recommendation** row: **📋 Retrospective observation** — not Comment or Request changes.
4. **Reason:** *Post-merge audit — no action required unless follow-up MR planned.*
5. **Production readiness:** *Ready · Operational improvements recommended* when no runtime code blockers.
6. Validate suppressions in Inference or Not raised when prior Duo/bot threads were correctly dismissed.
7. Process findings (merge-before-CI) under Process blockers — operational policy wording.

### Pipeline status taxonomy

Use **exactly one** primary label in the executive summary — do not say *"no pipeline for head"* without classifying:

| Label | When |
|-------|------|
| ✅ **success on head** | Pipeline for `head_sha` completed green |
| ❌ **failed on head** | Pipeline for `head_sha` failed (blocks Approve by default) |
| ⏳ **pending/running** | Pipeline for `head_sha` not finished — do not Approve |
| ❓ **not configured** | No `.gitlab-ci.yml` / `.github/workflows` (or equivalent) in repo — CI not set up |
| ❓ **expected but missing** | Repo has CI config but no pipeline ran for `head_sha` (misconfiguration or webhook gap) |
| ❓ **unavailable** | MCP cannot fetch pipeline data — say so explicitly |

Secondary context (older MR pipelines) may be cited separately and labelled *secondary*.

### Recommendation matrix

**Normative copy:** [review-metrics.md](review-metrics.md) §Recommendation matrix (normative — single source).
Apply highest emitted severity → **Recommendation** before pipeline/AC/CODEOWNERS overrides. Do not
duplicate the table here.

**Low-only → Approve:** Low findings alone do not force Comment — list them under **Nice to have**.

**Edge-case raises** (apply after matrix; cite in **Reason**):

| Condition | Effect |
|-----------|--------|
| CODEOWNERS approval gap on a changed path | Raise ✅ Approve → 💬 **Comment** (`workflow/phase-5.md`) |
| Head pipeline pending/running/failed (related) | May raise verdict per `reference/severity-rubric.md` |
| Unmet AC | May raise to 🔴 **Request changes** |
| Stop-search threshold hit | Does **not** lower the matrix verdict — cap overall **Confidence** at Medium and note partial coverage in **Reason** (`workflow/phase-5.md` §Partial review) |

### Per-finding confidence (findings table)

Each **review finding** row carries its own **ID** (`PRR-SEC-001`, `PRR-DOC-002`, … — category-prefixed;
see `reference/finding-pipeline.md`), **Confidence** (High / Medium / Low), and **Evidence** (`file:line`
list) — separate from the **Finding** prose column and from overall review confidence in the executive
summary.

| Per-finding rating | When |
|--------------------|------|
| **High** | Defect directly on cited diff line; config/value unambiguous; no unconfirmed assumption |
| **Medium** | Strong inference; OAR Assumption; runtime config — Bucket4j+Redis, auth without profile, Jackson erasure |
| **Low** | Stale wording, speculative drift, or docs-only inconsistency without runtime impact |

**Anti-pattern:** Confidence: High on every Critical/High row — calibrate per finding.

**Evidence** is a first-class column — use **OEDR** or **OAR** per `reference/finding-evidence-model.md`.

### Documentation drift classification

When documentation disagrees with implementation, classify explicitly in the finding (do not treat all
doc issues as MR defects):

| Class | Meaning | Typical severity |
|-------|---------|------------------|
| **Consistency issue — reference docs stale** | Implementation correct; README/schema/docs outdated | Low–Medium |
| **Consistency issue — implementation stale** | Docs/spec correct; code does not match | Medium–High |
| **Ambiguous drift** | Cannot determine source of truth from diff alone | Low + per-finding Confidence: Low |

Prefix finding text: `doc drift · reference stale — …` or `doc drift · implementation stale — …`.

### Review cost metrics

Emit in executive summary (table or bullet block) and in `review_metrics.cost`:

| Field | Source |
|-------|--------|
| **Files reviewed** | `coverage.changed_files_reviewed` / `coverage.changed_files_total` |
| **Commits in MR** | `get_merge_request_commits` count (full review) or `commits_incremental` (re-review) |
| **Estimated effort** | Reviewer estimate in minutes (round to nearest 5; e.g. `~15 min`) |
| **Coverage %** | `(changed_files_reviewed / changed_files_total) × 100`, or `partial` when hunks truncated |

Example:

```markdown
**Review cost**
| Files reviewed | Commits | Est. effort | Coverage |
|----------------|---------|-------------|----------|
| 12 / 12 | 5 | ~15 min | 100% |
```

### Nice-to-have priority (P1 / P2 / P3)

Rank follow-ups when **Nice to have** is non-empty:

| Rank | Criteria |
|------|----------|
| **P1** | Would materially improve correctness, operability, or reviewer confidence on next MR |
| **P2** | Worth doing soon; low merge risk if deferred |
| **P3** | Cosmetic, optional polish, or repo-wide maturity outside this MR's scope |

### Blocking issues — visual noise rule

When **no** Critical/High findings and **no** unmet AC:

- Print **`Blocking Issues: None`** as a single line.
- **Do not** print empty **Major concerns** or **Must fix** sections.

When blocking items exist, print **Major concerns** and **Must fix** instead — omit "Blocking Issues: None".

### Score scales (use exactly these labels)

**Architecture / Maintainability:** Strong · Adequate · Weak · Critical

**Testing:** Strong · Adequate · Weak · Critical

**Testing score bands** — use **Strong** when verification evidence supports it; do not default to
Adequate when CI/tests/validators have run successfully:

| Band | When |
|------|------|
| **Strong** | §8 mostly ✅ **and** head pipeline green (or lint/tests/validators executed successfully on head when no CI); regression + negative cases covered on changed hot paths |
| **Adequate** | Mixed ⚠️ on non-blocking §8 dims; or CI not run but manual test evidence in diff/MR is solid |
| **Weak** | Any ❌ on critical §8 dims; no tests on changed hot path; validators not run when repo expects them |
| **Critical** | Blocking test gap on payments/auth/security-critical path |

**Security:** Clear · Needs attention · Minor gaps · Material gaps · Critical issues

### Security score bands

| Band | When |
|------|------|
| **Clear** | No security findings; dependency scan clean; no app-level auth/exposure concerns |
| **Needs attention** | Any **High** app-level finding (missing auth, exposed endpoint) — **even if Snyk/deps clean** |
| **Minor gaps** | Medium-only security findings |
| **Material gaps** | Multiple High security or dependency advisories in diff |
| **Critical issues** | Critical — secrets, injection, auth bypass |

**Anti-pattern:** Security **Clear** alongside High unauthenticated-controller finding.

When mixed: add nuance line — *No dependency vulnerabilities; one application-level security concern.*

**Production readiness:** Ready · Ready with caveats · Not ready · **Ready · Operational improvements recommended** *(retrospective only)*

## Template

```markdown
## Executive Summary

<2–4 sentence narrative>

### Evidence

- ✓ 12/12 changed files reviewed in diff
- ✓ Full diff reviewed; no truncation or skipped hunks
- ✓ Linked Jira ticket with explicit AC
- ✓ Change classification: Documentation · no executable runtime code

**Confidence:** High — full boundary reviewed; ticket linked; no truncation.

### Inference

- Merge risk remains Medium until signature gap is fixed
- Production money path affected — deploy revert alone insufficient if forged events accepted

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
| Review coverage | ✅ Complete (12/12) |
| Regression | N/A |

### Process blockers

| Gate | Status |
|------|--------|
| CI pipeline | ✅ Green |
| CODEOWNERS | ✅ Satisfied |
| Jira / AC | ✅ Met |
| Approvals | 1/2 |

**Reason:** Critical signature gap on production money path blocks merge; all other findings are addressable post-merge.

**Review cost**
| Files reviewed | Commits | Est. effort | Coverage |
|----------------|---------|-------------|----------|
| 12 / 12 | 3 | ~20 min | 100% |

**Major concerns**
- Webhook signature not verified — forged refunds possible
- …

**Must fix**
- `PRR-SEC-001` · Webhook signature — `payments/webhook.py:42` (Critical · All refund webhooks)
- `PRR-DATA-001` · Decimal for money — `payments/refund.py:88` (High · Refund ledger writes)

**Nice to have**
- **P1** — Scope creep in logging config (Medium) — split to separate MR
- **P2** — Add negative test for empty refund list
- **P3** — Rename `amt` → `amount_cents` (nit)

| Architecture | Testing | Security | Maintainability | Production readiness |
|--------------|---------|----------|-----------------|----------------------|
| Adequate | Weak | Critical issues | Adequate | Not ready |
```

Security score **Critical issues** when Critical SEC finding open — not **Clear**.

**Pipeline:** ✅ success on head · **Approvals:** 1/2 · **Merge train:** idle
```

## Conclusion

Rendered heading: **`## Conclusion`**. Always the last narrative section before `review_metadata` YAML
(or Jira offer in chat). 2–4 sentences restating the recommendation, key blocking concern (if any), and
next step for the author. No `Type ACT`, posting confirmations, or MCP setup steps in the report body.

Example:

```markdown
## Conclusion

Request changes until webhook signature verification lands on the production money path. Medium-severity
items can follow in a fast-follow MR once CI is green on head.
```

**Clean merge (no blockers):**

```markdown
## Executive Summary

Dependency bump only; no production logic changed.

### Evidence

- ✓ 2/2 changed files reviewed in diff
- ✓ Dependency bump only; full diff reviewed
- ✓ No truncated diffs or skipped hunks

**Confidence:** High — mechanical MR; full boundary reviewed.

### Code blockers

Code blockers: None

### Decision gates

| Gate | Result |
|------|--------|
| Runtime correctness | ✅ |
| CI | ✅ |
| **Recommendation** | **✅ Approve** |

### Technical blockers

| Gate | Status |
|------|--------|
| Critical findings | ✅ None |
| High findings | ✅ None |
| Review coverage | ✅ Complete (2/2) |

### Process blockers

| Gate | Status |
|------|--------|
| CI pipeline | ✅ Green |
| Approvals | 1/1 |

**Reason:** No production logic changed; no open Critical/High findings; full diff reviewed.

**Review cost**
| Files reviewed | Commits | Est. effort | Coverage |
|----------------|---------|-------------|----------|
| 2 / 2 | 1 | ~5 min | 100% |

**Blocking Issues: None**

**Nice to have**
- **P3** — Pin advisory note in MR description for audit trail

| Architecture | Testing | Security | Maintainability | Production readiness |
|--------------|---------|----------|-----------------|----------------------|
| — | — | Clear | — | Ready |
```

```markdown
## Conclusion

Safe dependency bump with no production logic touched — approve once pipeline succeeds on head.
```

Include **Pipeline** (using taxonomy above), **Approvals**, and **Merge train** lines inside the
executive summary (not a separate mini-verdict). Omit approval line if unavailable. Include merge-train
warning inline when active.

**Incremental re-reviews** prepend the re-review block from `reference/comment-templates.md` (statistics,
regression check, coverage, scope category) **before** the Executive Summary section.

Mechanical MR brief form — use **Blocking Issues: None** and **Reason:** (not separate empty concern sections).
Use **—** for scores N/A on mechanical MRs.

**Canvas:** when findings exceed ~15 rows, offer [canvas](~/.cursor/skills-cursor/canvas/SKILL.md) for
severity distribution — [post-action-templates.md](../../docs/skill-framework/shared/post-action-templates.md) §6.
