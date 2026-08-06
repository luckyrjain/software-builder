# PR Review — Examples

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md)

## Invocation

Slash command and natural language are equivalent — the agent loads this skill for either form.

### Skill routing keywords

Used by skill discovery when the YAML `description` is truncated. Match when the user clearly targets a
**GitLab merge request** (they often say "PR"):

| Category | Phrases |
|----------|---------|
| **Core** | `/pr-review`, review this pr, review this MR, review merge request, review MR N, review !IID |
| **Lifecycle** | re-review, check if blocking issues are fixed, post-merge audit, review merged MR, retrospective |
| **Discovery** | list open MRs, what MRs are open, check MR before merge |
| **Posting** | review and post |
| **Persona / focus** | review as SRE, security persona, architecture focus, architecture lens, review persona |
| **Keywords** | merge request, MR, !IID, GitLab |

**Do not route here:** GitHub pull request, local uncommitted diff only, post-incident RCA, K8s
rightsizing — see [SKILL.md §When NOT to use](SKILL.md#when-not-to-use).

| User says | Resolved target |
|-----------|-----------------|
| `review this pr https://gitlab.com/acme/backend/-/merge_requests/482` | `acme/backend` !482 |
| `review this MR !482` | `acme/backend` !482 (from `origin`) |
| `can you review my merge request?` (on `feat/PAY-1421-refund-webhook`) | Look up MRs → pick MR for that branch |
| `re-review !482` / `check if blocking issues are fixed on !482` | Incremental re-review on `!482` |
| `review my local changes` / `review unstaged diff` | **Wrong skill** — `/review-bugbot`, not pr-review |
| `/pr-review https://gitlab.com/acme/backend/-/merge_requests/482` | `acme/backend` !482 |
| `/pr-review !38 post-merge audit` | Retrospective mode on merged MR |
| `review merged MR !38` | `review_mode: retrospective` |
| `/pr-review MR 482` (in repo with `origin` → `acme/backend`) | `acme/backend` !482 |
| `/pr-review` on branch `feat/PAY-1421-refund-webhook` | Look up MRs → pick MR for that branch |
| `/pr-review` (list tool, 3 open MRs, no match) | List table → ask which IID to review |
| `/pr-review` (official MCP, only `search`) | Search by branch/ticket → ask for URL/IID if no hit |
| `what MRs are open?` / `list open MRs` | Table (or search result) — no review until user picks |
| `review and post https://gitlab…/merge_requests/482` | Same URL; skips Phase 3 only when mode is `full` or `summary-only` **and** MR is not a draft — `general-only` and draft MRs always require confirmation |
| `review and post …` with **general-only** MCP | ⚠️ warning + confirmation still required — never skips Phase 3 |
| `review MR 482, focus on migrations` | !482 + custom focus (overrides persona) |
| `review MR 482 as SRE` | !482 + **SRE persona** — §9/§17/rollback emphasis |
| `security persona on !482` | **Security persona** — §2 deep pass |
| `review !482 architecture focus` | !482 + §16 Architecture Lens forced (even without structural triggers) |
| `MR !482 reduced CPU limits — assess rightsizing before merge` | pr-review Phase 2 flags underprovisioned resources → **Handoff → k8s** per [cross-skill-escalation.md](../docs/skill-framework/shared/cross-skill-escalation.md) |
| `RCA for payment-api outage 14:00–16:00 UTC` | **Wrong skill** — route to incident-rca, not pr-review ([when NOT to use](SKILL.md)) |
| `review !482 and notify #eng-reviews on Slack` | pr-review Phase 0→5; Phase 3 gate → post MR → Slack notify on user confirm | [post-action-templates §5](../docs/skill-framework/shared/post-action-templates.md#5-slack-pr-review-) |

## Open MR list (GitLab repo, no target)

**Single-repo, list tool available** — one project, full list:

| IID | Title | Source → Target | Author | Draft | |
|-----|-------|-----------------|--------|-------|---|
| [!482](…) | Add refund webhook | `feat/PAY-1421` → `main` | @alice | | **← you are here** |

**Single-repo, `search` only** (official GitLab MCP) — best-effort by branch/ticket:

> Searched open MRs for `acme/backend` matching `PAY-1421` (not a complete list):

| IID | Title | Source → Target | Author | |
|-----|-------|-----------------|--------|---|
| [!482](…) | Add refund webhook | `feat/PAY-1421` → `main` | @alice | **← you are here** |

If search returns nothing, ask for the MR URL/IID rather than implying there are none.

**Project-level workspace** — warning + multi-repo table:

> ⚠️ **Project-level workspace scope** — listing open MRs across **3 repos** in this workspace:
> `acme/backend`, `acme/frontend`, `acme/worker`

| Project | IID | Title | Source → Target | Author | Draft | |
|---------|-----|-------|-----------------|--------|-------|---|
| `acme/backend` | [!482](…) | Add refund webhook | `feat/PAY-1421` → `main` | @alice | | **← you are here** |
| `acme/frontend` | [!91](…) | Fix checkout UI | `fix/checkout` → `main` | @bob | | |
| `acme/worker` | [!12](…) | Retry queue | `feat/retry` → `main` | @carol | ✓ | |

Which MR should I review? → user picks `acme/backend` !482.

## Edge-case outputs

**Closed / merged MR:**
> ⚠️ MR !482 is already **merged** (state: `merged`). Nothing to review unless you want a **post-merge audit**.
> Confirm: *post-merge audit* / *review merged MR* / *retrospective* to continue.

**Post-merge audit (retrospective):**
> **Review mode:** Retrospective — MR merged before review; audit posture, not merge gate.
>
> ### Review findings
> | ID | Overall | Conf | Finding |
> |----|---------|------|---------|
> | PRR-TEST-001 | 🟡 Medium | High | Test gap — LPC edge cases (implementation appears correct) |
> | PRR-PROC-001 | 🟡 Medium | High | Repository policy risk — merge 24s before CI green |
>
> ### Not raised (suppressed)
> | Candidate | Reason |
> | GitLab Duo division-guard | Correctly dismissed — `divide(..., 6, HALF_UP)` avoids scale exception |
>
> ### Positive observations
> - ✓ `divide(..., 6, HALF_UP)` — avoids BigDecimal scale exception on LPC path
> - ✓ Duplicate detection logic on notification retry
> - ✓ Snyk clean · full diff reviewed
>
> ### Executive Summary
> Post-merge audit of repayment LPC logic — no runtime blockers; process and test follow-ups recommended.
>
> **Confidence:** High — full diff reviewed; payment hot path verified; pipeline timeline inspected.
> **Traceability:** Medium — no linked Jira (does not reduce technical confidence).
>
> ### Code blockers
> Code blockers: None
>
> ### Decision gates
> | Gate | Result |
> | Runtime correctness | ✅ |
> | CI / process | ⚠️ |
> | **Recommendation** | **📋 Retrospective observation** |
>
> **Reason:** Post-merge audit — no action required unless follow-up MR planned for parameterized tests and merge-before-green policy.
>
> **Production readiness:** Ready · Operational improvements recommended
>
> ### Engineering improvements
> - Add parameterized LPC tests — example matrix:
>   `Outstanding | charged=2 | pct=50 | expected=66.6667` · `Partial | charged=1 | pct=50 | expected=33.3333`
> - Require green pipeline before merge on payment branches *(platform policy — not MR-specific)*

**Fork MR** (`source_project_id ≠ target_project_id`):
> ℹ️ Fork MR — review is **diff-only** via MCP. Fork branch not in local checkout; full-file context
> unavailable unless a fork remote is provided.

**No linked Jira ticket** (e.g. dependency bump, infra-only MR):
> ℹ️ No Jira ticket key found in title, branch, description, or remote links. Skipping AC check.
> Reviewing the diff for correctness, security, and quality only.

**Ticket found, no acceptance criteria:**
> ℹ️ Linked ticket: [INFRA-99](<url>) — *"Bump base image to Ubuntu 24.04"*. No acceptance criteria
> defined on the ticket. Falling back to MR description for stated intent.

**Multiple Jira tickets** (keys in title + label):
> Linked tickets: [PAY-1421](<url>) (primary — refund webhook), [PAY-1400](<url>) (epic parent).
> Merged acceptance criteria from both; AC for idempotency came from PAY-1421, rollout flag from PAY-1400.

**Draft MR gate (Phase 3):**
> ⚠️ **This MR is a draft** — review findings are ready but posting to a draft MR may clutter early
> work. Post anyway, or hold until the MR is marked ready?
> → [Post all comments] [Hold — don't post] [Cancel]

**Executive summary (pipeline running, no blockers):**
> ## Executive Summary
>
> Clean refactor with no blocking findings; CI still running on head.
>
> ### Evidence
>
> - ✓ 6/6 changed files reviewed in diff
> - ✓ No truncated diffs or skipped hunks
>
> **Confidence:** High — full boundary reviewed.
>
> | Gate | Status |
> |------|--------|
> | Critical findings | ✅ None |
> | High findings | ✅ None |
> | CI | ⏳ Pending |
> | Regression | N/A |
> | Review coverage | ✅ Complete (6/6) |
> | **Recommendation** | **💬 Comment** |
>
> **Reason:** Medium-only findings (no Critical/High); pipeline still running on head — merge after CI green.
>
> **Blocking Issues: None**
>
> **Nice to have**
> - **P2** — Scope creep in logging config (Medium · PRR-ARCH-001)
>
> | Architecture | Testing | Security | Maintainability | Production readiness |
> |--------------|---------|----------|-----------------|----------------------|
> | Good | Strong | Clear | Good | Ready |
>
> **Pipeline:** ⏳ running on head · **Approvals:** 1/2 required

**Executive summary (Low-only findings):**
> ## Executive Summary
>
> Minor doc gap only; no blocking defects.
>
> ### Evidence
>
> - ✓ Full diff reviewed; no truncation
>
> **Confidence:** High — Low-only findings; full boundary reviewed.
>
> | Gate | Status |
> |------|--------|
> | Critical findings | ✅ None |
> | High findings | ✅ None |
> | CI | ✅ Green |
> | Regression | N/A |
> | Review coverage | ✅ Complete (4/4) |
> | **Recommendation** | **✅ Approve** |
>
> **Reason:** Low-only findings per recommendation matrix — no Critical/High/Medium; safe to merge.
>
> **Blocking Issues: None**
>
> **Nice to have**
> - **P3** — Rename `amt` → `amount_cents` (Low · PRR-DOC-001)

**Large MR cap hit (20 pages / 200 files):**
> ⚠️ **Diff truncated — page/file cap reached.** Reviewed 200 files across 20 pages; 47 paths not
> fetched. Continue fetching, narrow scope (e.g. security paths only), or review partial boundary as-is?

**Custom focus (migrations only):**
> Custom focus: **migrations** — dimensions 5 (Data & migrations) + security on touched files only.
> Other checklist dimensions skipped (noted in summary).

**Repo review rules (`review-rules.yaml`):**
> **Repo review rules:** `review-rules.yaml` — domains active: payments (critical), search (critical), infra (critical)
>
> Changed `billing/ledger/post.go` matches **payments · critical** (`ledger`) — severity elevated; idempotency and money-type checks applied.

**Contextual severity (same issue, different paths):**
> | ID | Score | Overall | L | I | Conf | Location | Evidence | Finding |
> |----|-------|---------|---|---|------|----------|----------|---------|
> | PRR-OBS-001 | 6 | 🟠 High | H | M | High | `checkout/payment/capture.go:88` | `checkout/payment/capture.go:88` | **ctx: production-critical** — no structured logging on payment capture path |
> | PRR-OBS-002 | 1 | 🔵 Low | L | L | High | `admin/dashboard/stats.go:42` | `admin/dashboard/stats.go:42` | **ctx: internal** — no logging on rarely-used widget refresh |

**False-positive suppression:**
> Considered null-deref on `user.Name` at `handler.go:55` — **suppressed** (all call sites in diff guard `user != nil` before reach; no realistic path).

**Review persona (SRE, auto-detected):**
> **Review persona:** SRE *(auto-detected: terraform + migration in diff)*

**Fast path (docs-only):**
> **Fast path:** docs-only (3 files) — CI skipped; security checklist skipped (secret scan only).
> **Change classification:** Documentation · no executable runtime code

**Fast path (lockfile-only):**
> **Fast path:** lockfile-only — mechanical review; CI, architecture, and security checklists skipped.
> **Change classification:** Metadata · lockfile-only
>
> Dependency bump only; ✅ Approve if no advisory signal in manifest diff.

**Fast path (4 files, README + code):**
> **Fast path:** standard · 4 files — architecture lens skipped.

**Context cache (re-review):**
> ℹ️ **Context cache:** reusing CODEOWNERS, CLAUDE.md, architecture notes — unchanged in this delta.

**Finding pipeline (suppressed speculative):**
> Suppressed 3 findings — insufficient evidence (don't-guess gate). Emitted 2 after execution path + dedupe.

**Precedence (repo rules vs fast path):**
> Repo `always_review: observability` — running §9 despite docs fast path (`reference/precedence.md`).

**Capability discovery:**
> ℹ️ **Stack:** Kubernetes, Go — enabled deploy + rollback checks.

**Stop searching (threshold reached):**
> ℹ️ **Stop searching** — threshold reached (2 Critical · 3 High · 10 total findings). Remaining paths
> and optional dimensions not searched. Reply *exhaustive review* to continue.
>
> Executive summary **Confidence:** Medium — stop-search threshold; 14 of 38 changed files reviewed.

> | ID | Score | Overall | L | I | Conf | Location | Evidence | Finding |
> |----|-------|---------|---|---|------|----------|----------|---------|
> | PRR-MIG-001 | 4 | 🟡 Medium | M | M | High | `db/migrate/20260625_add_refund_idx.rb:8` | `db/migrate/20260625_add_refund_idx.rb:8` | Non-concurrent index on large `payments` table — lock risk in prod |

**AI / LLM finding (§15):**
> | ID | Score | Overall | L | I | Conf | Location | Evidence | Finding |
> |----|-------|---------|---|---|------|----------|----------|---------|
> | PRR-AI-001 | 9 | 🟠 High | H | H | High | `agents/review.py:88` | `agents/review.py:88` | Ticket body in system prompt without boundaries — prompt injection |

**Documentation drift:**
> | ID | Score | Overall | L | I | Conf | Location | Evidence | Finding |
> |----|-------|---------|---|---|------|----------|----------|---------|
> | PRR-DOC-001 | 2 | 🟡 Medium | L | M | High | `docs/schema.md:12` | `docs/schema.md:12`, `README.md:88` | doc drift · reference stale — README says v2, Schema says v3 |
> | PRR-DOC-002 | 1 | 🔵 Low | L | L | Medium | `README.md:88` | `README.md:88` | doc drift · ambiguous — Potential stale wording |

**Architecture lens (§16):**
> **Architecture lens** (triggered: cross-boundary import)
>
> | ID | Score | Overall | L | I | Conf | Location | Evidence | Finding |
> |----|-------|---------|---|---|------|----------|----------|---------|
> | PRR-ARCH-001 | 4 | 🟡 Medium | M | M | High | `checkout/handler.go:14` | `checkout/handler.go:14` | arch · coupling — imports `billing/internal/ledger`; bypasses `billing.Client` facade |

**Rollback safety (§17):**
> | Question | Status | Evidence |
> |----------|--------|----------|
> | Schema reversible? | ❌ | `db/migrate/…_add_status.rb` adds `NOT NULL` column with no default |
> | Feature flagged? | ❌ | New validation always on — no flag |

**Test quality (§8):**
> | Dimension | Status | Evidence |
> |-----------|--------|----------|
> | Coverage | ⚠️ | Unit tests for happy path only |
> | Negative cases | ❌ | No test for missing webhook signature |
> | Regression | ✅ | `test_refund.py` reproduces PAY-1421 |

**Re-run, head unchanged:**
> ℹ️ No new commits since `b835472`. Chat summary rendered; **Phase 3 and Phase 4 skipped** (no
> posting prompt — nothing new to post).

**Feedback learning (responsive team):**
> ℹ️ **Feedback learning:** this team resolves prior bot blocking findings quickly — confidence boosted.
>
> Executive summary **Confidence:** High — full diff; team resolved 4/4 prior blocking items within 1 commit cycle.

**Feedback learning (ignored category):**
> ℹ️ **Feedback learning:** `style-nit` raised in 2 prior reviews and still open — omitted 3 low-value
> naming nits. Security and AC findings unchanged.

### Scenario: Handoff to k8s — underprovisioned resources in MR

**User:** "Review MR !482 — it reduces CPU limits on checkout-api"

**Agent:**
1. Phase 0 (Detect) — MCP profile; GitLab ✅, k8s capability enabled
2. Phase 2 (Analyze) — flags underprovisioned resources on payment path (`k8s/deployment.yaml:42`)
3. Phase 5 (Closeout) — emits Handoff block; pr-review continues with remaining findings

**Expected fragments:**

```
**Handoff → k8s-overprovisioning-datadog**
- Service: `checkout-api`
- Env: `prod`
- Trigger: MR !482 reduces CPU limits 2000m → 500m on payment path
- Evidence: `k8s/deployment.yaml:42`, MR !482
- Ask: "Assess rightsizing for `checkout-api` in prod before merging MR !482"
```

```
pr-review continues with remaining findings; k8s assessment is a separate skill invocation.
```

---

## Phase 0 announcement examples

**Full posting** (`@zereight/mcp-gitlab`):
> **MCP check:** zereight GitLab MCP — mode `full`. Inline threads + summary available.

**Summary-only** (`create_note` but no inline threads):
> **MCP check:** GitLab MCP — mode `summary-only`. One MR summary note with `file:line` references; no inline threads.

**General comment only** (Cursor GitLab plugin / official GitLab Duo MCP):
> **MCP check:** GitLab official MCP — mode `general-only`.
>
> ⚠️ **GitLab MCP posting limitation** — comments will be a **single general note** on the MR, not inline on the diff. No line anchoring or Apply suggestion. For inline review, install `@zereight/mcp-gitlab` (see SETUP.md).

**Chat-only** (no write tools):
> **MCP check:** read-only — mode `chat-only`. Review appears in chat only.

## Chat output table (always)

After Phase 2, print **Review findings** sorted by **rank score (L × I)** descending, then Overall:

| ID | Score | Overall | L | I | Conf | Location | Evidence | Finding |
|----|-------|---------|---|---|------|----------|----------|---------|
| PRR-SEC-001 | 9 | 🔴 Critical | H | H | High | `payments/webhook.py:42` | `payments/webhook.py:42` | Signature check skipped when header absent |
| PRR-DATA-001 | 6 | 🟠 High | H | M | High | `payments/refund.py:88` | `payments/refund.py:88` | Refund amount uses `float` instead of `Decimal` |
| PRR-API-001 | 3 | 🟡 Medium | L | H | Medium | `payments/config.py:12` | `payments/config.py:12` | Rare admin path missing validation — low traffic |

### Engineering improvements *(not MR defects)*
- Add `.gitlab-ci.yml` — CI not configured in repo (non-blocking).

Repository maturity (informational)
CI: 8/10 | Docs: 9/10 | Lint: 10/10 | Automation: 7/10

### Architectural summary
| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Overall design** | Acceptable | Ships but coupling and flag debt need follow-up |
| Maintainability | Needs Work | `billing/internal` import bypasses facade |
| Complexity | Good | Linear control flow |
| Readability | Good | — |
| Future cost | Needs Work | Flag + coupling compound |

### Production risk
| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Production risk** | High | Critical finding open; payment path |
| Deployment risk | Medium | No canary noted in MR |
| Rollback difficulty | Medium | Deploy revert OK; data fix may be needed |
| Blast radius | High | All refund traffic |
| User impact | High | Forged refunds if signature gap ships |

### Executive Summary

Payment webhook MR has a critical signature gap on a production money path. Architecture is sound but security and test coverage block merge.

### Evidence

- ✓ 8/8 changed files reviewed in diff
- ✓ Full diff reviewed; no truncation

**Confidence:** High — full boundary reviewed; defect directly visible on cited lines.

| Gate | Status |
|------|--------|
| Critical findings | ⚠️ 1 |
| High findings | ⚠️ 1 |
| CI | ✅ Green |
| Regression | N/A |
| Review coverage | ✅ Complete (8/8) |
| **Recommendation** | **🔴 Request changes** |

**Reason:** Critical signature gap on production money path blocks merge.

**Major concerns**
- Signature verification missing on refund webhook
- No negative test for forged payload

**Must fix**
- `PRR-SEC-001` · `payments/webhook.py:42` (Critical)
- `PRR-DATA-001` · `payments/refund.py:88` (High)

**Nice to have**
- **P1** — Split logging refactor to separate MR (Medium)

| Architecture | Testing | Security | Maintainability | Production readiness |
|--------------|---------|----------|-----------------|----------------------|
| Acceptable | Weak | Critical issues | Needs Work | Not ready |

**Pipeline:** ✅ success on head · **Approvals:** 0/2 required

**Root cause groups** *(when ≥2 sites or manifestations share one fix):*
> **Payment transaction date handling** — Score 9 · Overall High · L:H · I:H · Conf: High  
> Blast radius: All PDN notifications · Sub-findings: epoch mismatch · gap ignored · null on gap  
> Systemic fix: single null-safe `getTxnDate(gap)`

## Payment service review (calibrated severity — 4 High, 4 Medium from ~15 candidates)

**Persona:** Payments SME *(auto-detected: PDN scheduler, Hikari, Juspay, Resilience4j, Jackson in diff)*

**Pre-emit:** 15 candidates → cluster + **High certainty gate (step 7a)** → **4 High**, **4 Medium**.

### Review findings

| ID | Score | Overall | L | I | Conf | Blast radius | Business impact | Location | Evidence | Finding |
|----|-------|---------|---|---|------|--------------|-----------------|----------|----------|---------|
| PRR-PAY-001 | 9 | 🟠 High | H | H | High | All PDN notifications | Customer debited on wrong day | `PdnScheduler.java:142` | 2 locations | Transaction date handling (cluster) |
| PRR-RES-001 | 7 | 🟠 High | H | H | High | Juspay failure path | Failed notification retries | `JuspayFallback.java:12` | 3 locations | Resilience fallback (cluster) |
| PRR-CFG-001 | 8 | 🟠 High | H | H | High | Entire service | Payment failures under load | `application.yml:44` | `application.yml:44` | Hikari max-lifetime OEDR |
| PRR-SEC-001 | 9 | 🟠 High | H | H | High | Credential exposure | Secret rotation required | `application.yml:88` | `application.yml:88` | Embedded credential on diff line |
| PRR-SER-001 | 4 | 🟡 Medium | M | M | Medium | Juspay callback path | Wrong payload mapping | `PdnWebClientApi.java:88` | 2 locations | Jackson TypeReference — OUR |
| PRR-CFG-002 | 4 | 🟡 Medium | M | M | Medium | Entire service | Rate limit misconfig | `RateLimitConfig.java:30` | `RateLimitConfig.java:30` | Bucket4j config mismatch |
| PRR-CFG-003 | 3 | 🟡 Medium | L | H | High | STG deploy | STG may lack DB config | `config/stg/database/postgres.yml` | deleted file | STG yaml deleted — may be consolidation |
| PRR-SEC-002 | 3 | 🟡 Medium | M | M | Medium | Test surface | Unauthorized if exposed | `KafkaTestController.java:22` | `KafkaTestController.java:22` | No visible auth — OUR |

### Root cause groups

**Payment transaction date handling** — PRR-PAY-001  
Sub-findings: epoch mismatch · gap ignored · null on gap · Systemic fix: `getTxnDate(gap)`

**Resilience fallback implementation** — PRR-RES-001  
Sub-findings: fallback signature · null status handling · reactive retry mismatch · Systemic fix: align `@Fallback` method + null-safe status

**Jackson response deserialization** — PRR-SER-001  
Sub-findings: TypeReference erasure · ObjectMapper config · Systemic fix: typed DTO + explicit mapper module

### Not raised (suppressed)

| Candidate | Reason |
|-----------|--------|
| Fallback signature (standalone) | Merged into PRR-RES-001 |
| Reactive retry mismatch (standalone) | Merged into PRR-RES-001 |
| TypeReference erasure (standalone) | Merged into PRR-SER-001 |
| Null-deref on guarded path | No realistic execution path |
| Style nits (3) | Value filter — P3 |

### Positive observations

- ✓ Structured PDN status model · transactional boundary migration
- ✓ Duplicate detection on notification path · consistent event model
- ✓ Feature-flag strategy for rollout · Snyk clean
- ✓ Full review coverage (24/24 files)

### Architectural summary *(fragment)*

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Overall design** | Good | Cleaner domain separation; event model consolidated |
| Maintainability | Acceptable | Resilience gaps noted — see PRR-RES-001 |
| Future cost | Acceptable | Feature flags present; sunset plan not in MR |

### Executive Summary *(fragment)*

### Evidence

- ✓ 24/24 changed files reviewed · payment hot path verified
- ✓ Pipeline on head (`abc1234`): ❓ no pipeline ran for this SHA
- ✓ Last successful pipeline: `def5678` — ✅ success (not head)

### Code blockers

| Finding | Severity | Blast radius | Business impact | Conf |
|---------|----------|--------------|-----------------|------|
| Wrong autodebit date | High | All PDN notifications | Customer debited on wrong day | High |
| Resilience fallback | High | Juspay failure path | Failed notification retries | High |
| Hikari max-lifetime | High | Entire service | Payment failures under load | High |
| Embedded credential | High | Config exposure | Secret rotation required | High |

*(Medium findings — Jackson, Bucket4j, STG config, Kafka test auth — in findings table only.)*

### Decision gates

| Gate | Result |
|------|--------|
| Runtime correctness | ❌ |
| Payment correctness | ❌ |
| Security (application) | ⚠️ |
| CI | ⚠️ |
| **Recommendation** | **🔴 Request changes** |

### Technical blockers

| Gate | Status |
|------|--------|
| Critical findings | ✅ None |
| High findings | ⚠️ 4 |
| Payment correctness | ❌ |
| Review coverage | ✅ Complete (24/24) |

### Process blockers

| Gate | Status |
|------|--------|
| Pipeline on head | ❓ No pipeline for head SHA |
| Last green pipeline | ✅ `def5678` (not head) |
| Jira / AC | ⚠️ No linked ticket |
| Approvals | 0/2 |

**Reason:** Four High code blockers on payment paths; Medium items tracked separately; pipeline never ran on head (distinct from failed).

**Must fix** *(blast-radius order)*:
1. `PRR-PAY-001` · Transaction date — `getTxnDate(gap)` · *Wrong autodebit date to Juspay*
2. `PRR-RES-001` · Resilience fallback — systemic fix
3. `PRR-CFG-001` · Hikari — `application.yml:44`
4. `PRR-SEC-001` · Rotate embedded credential — `application.yml:88`

**Nice to have (Medium):** Jackson DTO typing · Bucket4j config · STG yaml consolidation verify · Kafka test auth OUR

| Architecture | Testing | Security | Maintainability | Production readiness |
|--------------|---------|----------|-----------------|----------------------|
| Acceptable | Weak | Needs attention | Acceptable | Not ready |

*Nuance: No dependency vulnerabilities; one application-level security concern (Kafka controller).*

## Re-review

Prior summary contains `<!-- cursor-pr-review -->` and the machine-parseable line
`- head_sha: \`abc123…\``. New `head_sha: def456…` with 3 commits → review only files changed since
`abc123`, post re-review summary template from `reference/comment-templates.md`.

**Posted re-review comment (example):**

> ## 🤖 Code Review (re-review) — 2 new commits since last review
>
> **Reviewed:** 2026-06-25T10:15:00Z
>
> ### Resolved since last review
> - 🟠 Money math switched to `Decimal` — ✅
>
> ### Still open / new
> - 🟡 `refund.py:120` — new helper is untested.
>
> ### Executive Summary
>
> Previous High resolved; one new Medium on test coverage. Approve with minor follow-up.
>
> ### Evidence
>
> - ✓ 3/3 incremental changed files reviewed
> - ✓ All prior High findings resolved
>
> **Confidence:** High — incremental diff reviewed; prior blocking items fixed.
>
> ### Inference
>
> - No regressions vs prior resolved findings
> - Merge risk remains Low
>
> | Gate | Status |
> |------|--------|
> | Critical findings | ✅ None |
> | High findings | ✅ None |
> | CI | ✅ Green |
> | Regression | ✅ None |
> | Review coverage | ✅ Complete (3/3) |
> | Prior findings | ✅ 1/1 resolved |
> | **Recommendation** | **✅ Approve** |
>
> **Reason:** Previous High resolved; one new Medium on test coverage is non-blocking.
>
> **Pipeline:** ✅ success on head
>
> ### Notes
> - head_sha: `def456…`
> - Posting mode: `full`
>
> _Re-reviewed by Cursor `/pr-review`._

**Golden `review_metadata` footer (re-review with `history`):**

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
    emission_rate: 0.125
  review_quality:
    coverage_pct: 100
    evidence_pct: 100
    confidence: high
    emission_rate: 0.125
  repository_health:
    schema_version: 2
    dimensions:
      ci: 8
      documentation: 9
      validation: 10
      automation: 7
      observability: null
```
