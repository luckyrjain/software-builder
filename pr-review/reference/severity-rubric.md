# Severity Rubric

Every review comment gets **Likelihood**, **Impact**, and an **Overall** severity derived from the
risk matrix below (unless a hard-floor rule applies). Overall drives the **emoji/prefix** on the
comment and whether the finding **blocks merge**.

**Adaptive severity:** the same issue type has **different** Overall depending on path context
(checkout payment vs admin dashboard). Classify **context first**, then score — see
`reference/contextual-severity.md`. Do **not** use flat mappings (e.g. "missing logging → Medium").

Be consistent — the same class of issue **in the same context** should land at the same L/I/Overall
across reviews.

| Overall | Label | Blocks merge? | Meaning |
|---------|-------|---------------|---------|
| Critical | 🔴 `[Critical]` | **Yes** | Will cause real harm if merged: security vulnerability, data loss/corruption, broken authn/authz, crash on a common path, committed secret, breaking API/schema change with no compat path. |
| High | 🟠 `[High]` | **Yes** | A genuine defect that should not ship: logic bug, missing error handling on a real failure mode, race condition, significant performance regression, unmet acceptance criterion, no tests on critical new logic. |
| Medium | 🟡 `[Medium]` | No (track it) | Should be addressed soon: weak/incomplete edge-case handling, moderate perf concern, maintainability problem, scope creep, thin test coverage, missing observability on an important path. |
| Low | 🔵 `[Low]` | No | Minor: naming, small refactor, mild duplication, doc gap, inconsistent style not caught by lint. |
| Nitpick | ⚪ `nit:` | No | Subjective/optional preference. Prefix `nit:` so the author knows it's discretionary and can ignore it freely. |
| Praise | 🟢 `praise:` | No | Genuinely good code worth reinforcing — a clean abstraction, a thoughtful test, a tricky edge handled well. Use sparingly and sincerely — **max 2 per review**; each must cite a specific diff line. |

## Risk scoring (Likelihood × Impact → Overall)

Assess **every finding** except nits and praise. **Classify path context** per
`reference/contextual-severity.md`, then state all three explicitly:

```
Likelihood: <High|Medium|Low> · Impact: <High|Medium|Low> · Overall: <Critical|High|Medium|Low> · Context: <tier> (<path hint>)
```

### Likelihood — how often this defect would manifest in production

| Level | When to use |
|-------|-------------|
| **High** | Hot path, every request, default-on code, unauthenticated/public surface, migration on next deploy |
| **Medium** | Common path but gated (logged-in users, feature flag, retry path), or requires specific input |
| **Low** | Rare edge case, admin-only, dead code path, dev/test config, needs unlikely sequence |

### Impact — harm if it manifests

| Level | When to use |
|-------|-------------|
| **High** | Data loss/corruption, auth bypass, money wrong, PII leak, production outage, irreversible schema change |
| **Medium** | Wrong results for some users, degraded perf at scale, partial feature broken, rollback needed |
| **Low** | Cosmetic, minor inconsistency, tech-debt smell, non-prod config, fixable without incident |

### Overall — risk matrix

Take the **higher** of the row/column intersection; then apply [hard floors](#hard-floors) if any match.

| Impact ↓ / Likelihood → | Low | Medium | High |
|-------------------------|-----|--------|------|
| **Low** | Low | Low | Low |
| **Medium** | Low | Medium | **High** |
| **High** | Medium | **High** | **Critical** |

Examples: Likelihood **High** + Impact **Medium** → Overall **High** (rank score **6**). Likelihood
**Low** + Impact **High** → Overall **Medium** (rank score **3**) — ranks **below** L:High I:Medium
Overall:High (score **6**) even though both might matter; the near-certain issue comes first.

### Ranking findings (sort order)

**Do not sort by Overall label alone.** Sort by **rank score = Likelihood × Impact** (probability ×
harm), highest first. Map levels to weights: **High = 3**, **Medium = 2**, **Low = 1**.

| L | I | Rank score | Example Overall |
|---|---|------------|-----------------|
| H | H | **9** | Critical |
| H | M | **6** | High |
| M | H | **6** | High |
| M | M | **4** | Medium |
| H | L | **3** | Low |
| L | H | **3** | Medium |
| M | L | **2** | Low |
| L | M | **2** | Low |
| L | L | **1** | Low |

A finding rated **Overall High** with **Likelihood Medium** (score 6) correctly outranks **Overall
Medium** with **Likelihood High** on the same impact (also 6) — tie-break by **Overall** (Critical >
High > Medium > Low), then `file:line`. A theoretical **Overall High** driven only by a hard floor
with **Likelihood Low** still gets rank score **1–3** and sorts below likely failures.

**Inline thread budget** (Phase 4): allocate slots by **rank score** first, then Overall — not Overall
alone. Nits and praise sort last (no score).

### Hard floors (override the matrix)

These are always **Critical** regardless of Likelihood:

- Committed secret / credential in the diff
- SQL/command injection on user-controlled input
- AuthN/AuthZ bypass on a protected resource
- Breaking API/schema change with no compat path on a production contract

These are always at least **High** — **on production-critical or elevated paths** (`reference/contextual-severity.md` path tiers). On **internal**/**generated** paths, run the context matrix instead; do not apply these floors there:

- Unmet acceptance criterion on a linked ticket
- CI pipeline failed on MR head (unless clearly unrelated)
- Missing error handling on external I/O on a common path

When the matrix and a hard floor disagree **on the same path tier**, **use the higher Overall** and say
which rule applied.

## High certainty gate (payments and production-critical paths)

**Do not emit Overall High** unless **impact + certainty** both apply (`finding-pipeline.md` step 7a).

| Criterion | High allowed | Demote to Medium |
|-----------|--------------|------------------|
| Logic/money bug on hot path | ✓ | — |
| Config value wrong on diff (OEDR) | ✓ | — |
| Confirmed credential in diff | ✓ | — |
| Resilience fallback signature on diff | ✓ | — |
| Generic deserialization / TypeReference | — | ✓ unless runtime failure verified |
| Missing auth, profile not in diff | — | ✓ — use OUR |
| Env yaml deleted, no broken import | — | ✓ — may be intentional consolidation |
| Bucket4j / Redis startup inference | — | ✓ |

**Anti-pattern:** eight High findings on one MR — experienced engineers discount inflated severity.

Nits and praise: omit Likelihood/Impact lines.

## Stop searching (Phase 2)

After dedupe and root-cause grouping, count findings in **this review** (each **root-cause group = one**;
each manifestation merged into a group does **not** add to the count; exclude nits and praise).
**Stop searching** when **any** threshold is met:

- **≥ 2** Overall **Critical**, **or**
- **≥ 5** Overall **High** (Critical excluded from this count), **or**
- **≥ 10** total (Critical + High + Medium + Low)

Then do not scan additional files, hunks, or optional checklist dimensions unless the user requested
**exhaustive** review. Full rules: `workflow/phase-2.md` §Stop searching.

## Recommendation matrix

**Normative copy:** [review-metrics.md](review-metrics.md) §Recommendation matrix (normative — single source).
Do not duplicate the table here.

Map **emitted review findings** to merge **Recommendation** using that table **before** pipeline/AC
overrides. Nits never affect the matrix.

## The blocking gate
- **Any Critical or High open → verdict is 🔴 Request changes** (see matrix above).
- **Pipeline selection:** use the pipeline whose `sha` matches `diff_refs.head_sha`. If none, note
  *no pipeline for head commit* and treat pipeline status as ❓ unavailable for verdict purposes.
- **Pipeline `success` on head commit** — eligible for ✅ Approve when no Critical/High remain and AC
  met.
- **Pipeline `pending` / `running` / `waiting_for_resource` on head** — max 💬 Comment; never ✅
  Approve (state ⏳; merge should wait for CI).
- **Pipeline `failed` on head commit** — default 🔴 Request changes.
- **Pipeline `failed` but clearly unrelated to this MR** (e.g. default-branch-only job, infra flake on
  an unchanged path) — 💬 Comment allowed; **must state why** in the summary. Do not Approve until
  head pipeline is green unless the team explicitly waives CI for that MR.

> **Severity vs. verdict distinction:** The CI hard floor (at least High severity for pipeline failure) applies to the **finding** — you always emit a High finding for a failed head pipeline. The "clearly unrelated → Comment" relaxation applies to the **merge verdict** — you can set the overall verdict to Comment rather than Request Changes when the failure is demonstrably unrelated to the changed code. Both rules apply simultaneously: emit the High finding AND set a Comment verdict, explaining the unrelated failure in the verdict text.
- **Medium only** (no Critical/High) → 💬 **Comment** per matrix — mergeable at author's discretion.
- **Low only** or **none** → ✅ **Approve** per matrix when AC met, test quality **Strong or Adequate** (§8;
  prefer **Strong** when CI green and tests/validators ran — `reference/executive-summary.md` §Testing score
  bands), and head pipeline **success** — or **no pipeline for head commit** (note ❓ in summary). Low findings
  still appear in **Nice to have**; they do not force Comment.

**Test quality threshold (§8):** **Strong** when mostly ✅ and CI/tests/validators verified on head.
**Adequate** when:
- No ❌ on Coverage, Negative cases, or Regression for changed logic paths.
- Any ❌ on payments, auth, or security-critical paths = **High** finding regardless of overall test coverage percentage.
- ⚠️ (partial/unclear) on those paths = **Medium** finding.
- For mechanical changes (rename, reformat, lockfile) the test quality check is skipped.

When inline posting is available (`full` mode), prefer **threads** (`create_merge_request_thread`) for
Critical/High so they stand out on the diff. Unresolved threads may block merge depending on project
settings — mark blocking findings clearly in the summary regardless. Low/nits can be plain notes or
bundled into one nit comment.

## Calibration examples

**Critical**
- `eval()` / `os.system()` on request-derived input; SQL built by string concatenation from user input.
- An endpoint that previously required auth now reachable unauthenticated.
- `DROP COLUMN` / non-nullable column added with no default in a migration that can't roll back.
- An API key, DB password, or private key visible in the diff. *(Flag + advise rotation; never repeat the value.)*
- A response/serialization change that silently breaks existing clients.
- A newly added dependency with a known critical CVE (CVSS ≥ 9.0) or a pinned-safe version removed.

**High**
- Off-by-one or inverted condition that returns wrong results.
- A network/IO call with no timeout and no error handling on the unhappy path.
- Unbounded query / N+1 introduced on a hot path.
- A new payment/auth branch with zero test coverage.
- Bug fix with no regression test reproducing the original failure.
- API contract change with no updated contract or integration test.
- The MR doesn't actually satisfy the ticket's stated acceptance criteria.
- CSRF protection absent on a state-changing endpoint accessible to browser clients.
- CORS wildcard (`*`) permitted on a credentialed endpoint.
- Rate limiting absent on a new auth, login, or OTP endpoint.
- Mass assignment: a privileged field (role, admin flag, account balance) writable from untrusted input.
- A newly added dependency with a known high CVE (CVSS 7.0–8.9).
- **CI pipeline failed** on the MR head commit (blocking unless clearly unrelated).
- N+1 query introduced on a hot list endpoint (L: High, I: Medium → Overall High).
- Unbounded retry loop or missing backoff on external call — retry storm risk (L: Medium, I: High → Overall High).
- Queue handler republishes failed message to same queue without DLQ — amplification loop (L: Medium, I: High → Overall High).
- Irreversible migration (`DROP COLUMN`, non-null without default) with no expand-contract or rollback plan (L: High, I: High → Overall Critical).
- Risky behavior change with no feature flag or kill switch on payments/auth path (L: High, I: High → Overall High).
- Checkout handler imports `billing/internal/ledger` directly — bypasses `billing.Client` facade; cross-domain coupling on a payment path.
- New import completes a cycle across top-level domains (`orders` ↔ `inventory`).
- DB/ORM model returned directly from a public API handler (domain leakage at the boundary).
- Feature flag defaults to enabling unsafe behavior on a production path.

**Medium**
- Edge case (empty list, null, very large input) plausibly unhandled but not on the critical path.
- Duplicated logic that should be factored before it spreads.
- Refactor touches files unrelated to the ticket (scope creep) — track so it isn't lost.
- Important new path has no log/metric on a **standard** API path — **Medium** (L: M, I: M).
- Same gap on **checkout/payment** path — **High** (L: H, I: M) — see `contextual-severity.md`.
- Same gap on **admin/dashboard** — **Low** (L: L, I: L) — not Medium by default.
- Rate limiting absent on a lower-sensitivity public endpoint (search, contact form).
- `==` used to compare a secret or token (should use constant-time equality).
- Mass assignment on a non-sensitive field that shouldn't be user-editable.
- A newly added dependency with a low/medium CVE or an advisory with no confirmed exploit vector yet.
- UI component imports repository layer directly (heuristic boundary smell; no documented layer rule).
- New feature flag wraps core logic with no sunset plan or tracking ticket.
- Core business logic moved into a route handler closure with no extraction path (testability).
- N+1 on an admin-only path (L: Low, I: Medium → Overall Low/Medium).
- Missing cache TTL on non-critical read path; unbounded in-memory list on rarely-used export.
- New payment/auth path with no metrics or alerts (L: High, I: High → Overall High) — **production-critical** context.
- Important new handler with no structured logging (L: Medium, I: Medium → Overall Medium) — **standard** context only; use **High** when path is production-critical per `contextual-severity.md`.
- New feature flag with no exposure metric or rollout observability (L: Medium, I: Low → Overall Low).
- MR template rollback section blank on a migration-touching change (L: Medium, I: Low → Overall Low).
- Happy-path unit tests only — no negative cases for validation or auth errors (L: Medium, I: Medium → Overall Medium).
- No integration test for cross-service flow introduced in diff (L: Low, I: Medium → Overall Low/Medium).

**Low / Nitpick**

**Low** — objective, fixable quality gap the team would want tracked:
- Variable name that obscures intent; a comment that's now stale.
- Missing doc for a new public API field; inconsistent style not caught by lint.
- Thin test coverage on a non-critical path.
- New feature flag with no cleanup note — worth a follow-up ticket before the flag becomes permanent.

**Nitpick** — subjective preference; author may ignore freely (prefix `nit:`):
- `nit:` prefer a guard clause over the nested `if`.
- `nit:` this could be a list comprehension.
- Formatting or naming where multiple valid choices exist.

When unsure between Low and Nitpick, ask: *"Would the team file a follow-up ticket?"* → Low. *"Pure taste?"* → Nitpick.

When unsure whether to report at all, apply the **review principle** (`SKILL.md` §Review principle) and **execution path gate**
(`reference/finding-gates.md` §Execution path) — if no realistic path, suppress. If expected value < developer
effort, **omit**. Checklist tables (§8, §17) may show ✅/N/A without generating a finding row.

When unsure between two levels, pick the **higher** one and say why in the comment — it's cheaper for
the author to downgrade a concern than to miss a real one.
