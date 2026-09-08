# Finding pipeline (authoritative order)

Every candidate finding in Phase 2 must pass this pipeline **in order**. Do not skip steps or reorder.
Load in Phase 2 with `reference/detection-vs-judgment.md` and `reference/finding-gates.md`.

## Pipeline

```text
1. Detect          → hypothesis from checklist / diff scan
2. Evidence        → diff anchor (+/- line in review boundary; one-hop reads cite path only)?
3. Don't-guess     → sufficient evidence to claim defect? (`finding-gates.md` §Don't-guess)
4. Execution path  → realistic path where defect occurs? (`finding-gates.md` §Execution path)
5. Dedupe          → not already raised on MR / within this review?
6. Non-negotiable  → if matched, waive path/guess gates per `finding-gates.md` §Non-negotiable
7. Contextual severity → L / I / Overall (contextual-severity.md)
7b. Per-finding confidence → High / Medium / Low + doc drift class when applicable
7b2. Blast radius / business impact → required on High/Critical; payments persona adds business impact chain
7b3. Observed / Assumption / Risk → when production exposure is inferred (finding-evidence-model.md)
7c. Finding ID       → assign stable `PRR-{CAT}-{NNN}` (see step 12); preserve on incremental re-review when matched
8. Feedback learning → category suppressions (review-feedback-learning.md)
9. Value filter    → expected value ≥ developer effort (SKILL.md principle)
10. Rank           → sort by L×I; apply root-cause grouping
11. Classify       → review finding (diff defect) vs engineering improvement (repo maturity — not emitted in severity table)
12. Output         → review findings table → Phase 2→3 gate; engineering improvements list → Phase 5
```

Record suppressions at steps 3–5 and 8–9 in **`review_metrics`** (`reference/review-metrics.md`).

## Step detail

### 1. Detect

Run checklist dimensions and persona-weighted scans. Emit **candidates only** — see
`reference/detection-vs-judgment.md`. A candidate is `{ hypothesis, location, evidence_snippet }`.

### 2. Evidence validation

- Anchor must be a `+` or `-` line (or context line that directly explains an adjacent changed line)
  from the Phase 1 review boundary.
- Build an **`evidence`** list: one or more `path:line` refs (primary anchor first; add secondary refs
  when the defect spans multiple hunks). **Required before emit** — step 12 rejects findings with an
  empty evidence list.
- No invented code, no line numbers outside the boundary (one-hop files may support reachability claims but
  are not diff anchors — cite the boundary hunk as primary evidence).
- Recorded `review_boundary.one_hop_reads[]` entries may support steps 3–4 when the defect depends on a
  direct caller/callee (`workflow/phase-1.md` §One-hop contextual reads).
- Out-of-diff suspicion → *"Out-of-diff: worth checking…"* in chat/Notes only — **not** a finding.

### 3. Don't-guess gate

**Distinct from execution path.** Ask: *Do I have enough evidence from the diff (+ optional full-file
context + recorded one-hop reads from Phase 1) to assert this defect — without inferring unseen
implementation or transitive callers?*

| Answer | Action |
|--------|--------|
| **YES** | Continue |
| **NO** | **Suppress** — or chat-only `⚠️ Unverifiable` (no severity, no post). Increment `review_metrics.suppressed.guess` |

See `reference/finding-gates.md` §Don't-guess.

### 4. Execution path gate

Ask: *Can I construct a **realistic** execution path where this defect occurs?*

| Answer | Action |
|--------|--------|
| **YES** | Continue (state path briefly when non-obvious) |
| **NO** | **Suppress** — increment `review_metrics.suppressed.path` |

See `reference/finding-gates.md` §Execution path. Non-negotiable matches may waive this step (step 6).

### 5. Dedupe

Scan Phase 1 step 3 feedback — inline threads, notes, prior `<!-- cursor-pr-review -->` summaries.
Same location, root cause, stack, or API misuse pattern → suppress. Within-review duplicates →
root-cause grouping (`workflow/phase-2.md` §Root cause grouping).

### 6. Non-negotiable baseline

If the candidate matches `reference/finding-gates.md` §Non-negotiable, **emit** even when path narrative is
thin — still requires diff anchor (step 2). Never suppressed by fast path, persona, or feedback learning.

### 7. Contextual severity

Classify path context; score L/I/Overall per `reference/contextual-severity.md` and
`reference/severity-rubric.md`. Never flat severity by issue type alone.

### 7a. High certainty gate (before emit)

**Overall High** requires **both**:

1. **Impact** — production-critical path (payments, money, pool, confirmed credential, resilience on hot path)
2. **Certainty** — defect on cited diff line, OEDR with known Expected, or non-negotiable hard floor

A hard floor (`reference/severity-rubric.md` §Hard floors) satisfies **Certainty** on its own, but never
substitutes for **Impact** — both prongs are still required. A hard-floor finding on an **elevated**
(not production-critical) path satisfies Certainty but fails Impact: demote to Medium here, same as any
other Impact-incomplete case, even though the floor's own wording says "always at least High." Hard
floors never apply at all on **internal**/**generated** tiers (severity-rubric.md) — run the context
matrix there instead.

**Demote to Medium** (keep confidence honest) when matrix would yield High but certainty is incomplete:

| Pattern | Overall | Conf | Evidence format |
|---------|---------|------|-----------------|
| Payment date / money path bug (grouped) | **High** | High | OEDR or direct logic error |
| Resilience fallback (signature visible) | **High** | High | Annotation + method on diff |
| Hikari `max-lifetime` wrong on diff | **High** | High | OEDR |
| Embedded credential on diff line | **High** | High | Secret pattern — rotate, never echo |
| Jackson `TypeReference` / erasure | **Medium** | Medium | OAR — unless runtime failure verified |
| Bucket4j / rate-limit config mismatch | **Medium** | Medium–High | OAR or OEDR partial |
| Env config file deleted (`config/stg/…`) | **Medium** | High | Unless diff shows broken import or STG still loads path |
| Test/Kafka controller, no auth in diff | **Medium** | Medium | **OUR** — Observed / Unknown / Risk |

**Pre-emit gate:** *Would payments on-call page at 3am?* No → not High.

**Target:** ~4–5 High rows on dense payment MRs — not 8 inflated Highs.

See `reference/severity-rubric.md` §High certainty gate, `reference/domain-overrides.md`.

### 7b. Per-finding confidence and documentation drift

Assign **per-finding Confidence** (High / Medium / Low) — independent of overall review confidence in
Phase 5 and **independent of Overall severity**. A Critical finding may be Medium confidence when
production exposure depends on an unconfirmed assumption.

| Per-finding confidence | When |
|------------------------|------|
| **High** | Defect on cited diff line; OEDR with known Expected — e.g. `max-lifetime: 3000`, wrong operator, secret in diff, Resilience4j `@Fallback` signature mismatch visible in annotation + method |
| **Medium** | OAR with Assumption; runtime config dependency — e.g. Bucket4j+Redis startup, missing auth without profile in diff, Jackson TypeReference erasure, generic deserialization path |
| **Low** | Stale wording, speculative drift, docs-only, or needs runtime confirmation |

**Anti-pattern:** marking every Critical/High finding **High** confidence — severity ≠ confidence.
Calibrate per finding; expect a mix on payment-service and infra MRs.

When docs disagree with implementation, set `doc_drift_class`:

| Class | Label in finding |
|-------|------------------|
| Reference stale | `doc drift · reference stale — …` |
| Implementation stale | `doc drift · implementation stale — …` |
| Ambiguous | `doc drift · ambiguous — …` + Confidence: Low |

See `reference/executive-summary.md` §Documentation drift classification.

### 7b2. Blast radius and business impact

For every emitted finding with Overall **High** or **Critical**, assign **blast radius** — who or what
is affected if the defect manifests (one short phrase):

| Finding type | Example blast radius |
|--------------|---------------------|
| Payment date bug | All PDN notifications |
| Hikari pool misconfig | Entire service |
| Unauthenticated controller | External callers |
| Retry/fallback gap | Juspay failure path |

Record in findings table **Blast radius** column (use `—` for Medium/Low). Required in inline comments
for High/Critical.

When **payments** persona or domain is active (`reference/review-personas.md`, `domain-overrides.md`),
add **business impact** — required on High/Critical; one-line customer/compliance consequence:

```markdown
Business impact: Wrong notification date → customer debited on wrong day → dispute/compliance risk
```

Emit in findings table **Business impact** column, Code blockers table, and inline comments.

### 7b3. Evidence structure (OEDR / OAR)

Per `reference/finding-evidence-model.md`:

- **OEDR** — Observed / Expected / Difference / Risk for config comparisons
- **OAR** — Observed / Assumption / Risk when production exposure is inferred

Default Confidence to **Medium** when Assumption is non-empty and unconfirmed.

### 8. Feedback learning

Apply Phase 1 signals **after** severity, **before** value filter. Never suppress non-negotiable
categories. Increment `review_metrics.suppressed.feedback` when omitting.

### 9. Value filter

Drop findings where fix effort > harm prevented. Zero emitted findings is valid — output **No actionable
findings** (not an empty table; nits may have been observed and filtered per signal-over-noise).

**Engineering improvements** (missing CI, anchor lint ideas, pressure-test coverage) bypass the severity
table — route to Phase 5 **Engineering improvements** section instead. Do not count toward blocking gate.

### 10. Rank and group

Sort by **blast radius × L×I** descending (tie-break: Overall severity). Apply **root-cause grouping**
and **thematic clustering** before counting findings for gate matrix and stop-search.

**Group when any apply:**

- **≥2 locations** share the same root cause, **or**
- **≥2 manifestations** of one logical defect (same systemic fix), **or**
- Multiple finding IDs would recommend the **same single fix**, **or**
- **Thematic cluster** — same subsystem + same fix owner (one Jira ticket, not three)

**Thematic cluster patterns** (merge before emit):

| Cluster | Merge into one finding | Sub-findings (examples) |
|---------|------------------------|-------------------------|
| **Resilience** | `PRR-RES-001 · Resilience fallback implementation` | fallback signature · null status handling · reactive retry mismatch |
| **Serialization** | `PRR-SER-001 · Jackson response deserialization` | TypeReference erasure · ObjectMapper config |
| **Payment date** | `PRR-PAY-001 · Transaction date handling` | epoch mismatch · gap ignored · null on gap |
| **Connection pool** | `PRR-CFG-001 · Hikari pool configuration` | max-lifetime · related pool knobs in same change |

**Pre-emit gate:** *Would a senior engineer file one Jira ticket or three?* One ticket → one finding.

Each **group/cluster = one row** in the findings table and **one** in the gate matrix. List
manifestations under **Sub-findings** in the root-cause block.

**Target:** ~8–10 top-level findings for a ~15-candidate payment MR — not 15 fragmented rows.

**Anti-pattern:** seven High rows from four clusters; Resilience + Jackson split across 6 IDs.

Emit grouped entries under `## Root cause groups` (`workflow/phase-2.md`). Singleton findings stay in
the main table.

### 11. Classify output channel

| Channel | Examples | Blocking gate |
|---------|----------|---------------|
| **Review finding** | Bug, security gap, AC miss, doc drift with wrong implementation | Yes — severity table |
| **Engineering improvement** | No `.gitlab-ci.yml`, suggest pressure tests, lint anchor hygiene | No — separate Phase 5 section |

### 12. Output

Each emitted review finding is a structured record:

```
finding: {
  id: PRR-SEC-001,               # stable category-prefixed ID — see ID assignment below
  category: SEC,                 # category enum
  severity: critical|high|medium|low,
  confidence: high|medium|low,
  status: open,                  # fixed|suppressed on incremental re-review when applicable
  location: path:line,            # primary anchor (= evidence[0])
  evidence: [path:line, ...],    # required; at least one entry
  likelihood, impact, overall,  # from step 7
  blast_radius: "<phrase>|null", # required when overall is high|critical
  business_impact: "<phrase>|null", # required High/Critical on payments/production-critical
  sub_findings: ["...", ...]|null,  # cluster manifestations (was subissues)
  observed, expected, difference, risk, assumption: "<text>|null",
  finding: "<prose>",             # problem statement — no evidence refs duplicated here
  doc_drift_class: ...|null,
  grouped: true|false             # true when root-cause group row
}
```

**Finding ID assignment (`PRR-{CAT}-{NNN}`):**

**Format:** `PRR-<CATEGORY>-<NNN>` — category code (uppercase) + zero-padded sequence **per category**.

**Category enum** (assign from primary defect type; one category per finding):

| Code | Use when |
|------|----------|
| **SEC** | Security — auth, injection, secrets, crypto |
| **DATA** | Money types, data integrity, PII handling |
| **API** | API contract, validation, breaking HTTP/RPC behavior |
| **SPEC** | OpenAPI, protobuf, JSON Schema breaking changes |
| **SCHEMA** | DB schema, migrations DDL (non-lock focus) |
| **MIG** | Migration deploy risk — locks, backfill, irreversible DDL |
| **CI** | Pipeline, build, test infra in diff |
| **TEST** | Missing or weak tests on changed logic |
| **DOC** | Documentation drift |
| **ARCH** | Architecture — coupling, boundaries, §16 lens |
| **OBS** | Observability — logging, metrics, tracing gaps |
| **PERF** | Performance, resource exhaustion |
| **AC** | Acceptance-criteria miss |
| **OWN** | CODEOWNERS approval gap |
| **REVERT** | Revert completeness (§19) |
| **AI** | LLM / agent safety (§15) |
| **OPS** | Deploy, rollback, feature-flag ops (when not MIG) |

Add new codes sparingly; prefer the closest existing category.

**Assignment rules:**

1. On **first review**, assign the next unused `NNN` **within the category** in **rank order** (highest
   L×I first). Example: first security finding → `PRR-SEC-001`; first doc drift → `PRR-DOC-001` (independent
   sequences).
2. On **incremental re-review**, **preserve** the prior `id` when the finding matches an
   unchanged item (same `file:line` + snippet hash, or same `id` in prior `review_metadata`
   findings array with matching evidence). Assign **new** IDs only to genuinely new findings — next
   `NNN` for that category only; never renumber resolved items.
3. Reference IDs in inline comments, summary severity sections, and `review_metadata.findings[]`.

**Migration from legacy `PRR-001` sequential IDs:** Prior summaries may use flat `PRR-NNN`. On
incremental re-review, **preserve legacy IDs as-is** when matching prior findings. New reviews use
category-prefixed IDs only. Do not renumber legacy IDs mid-MR.

- **`emitted` ≥ 1** — print **Review findings** chat table (sorted by blast radius × L×I) with **ID**,
  **Conf**, **Blast radius**, **Business impact** (High/Critical on payments; `—` otherwise), and **Evidence** columns.
- **`emitted` = 0** — print **No actionable findings** under Review findings; do not render an empty table header.
- **Engineering improvements** — optional bullet list after review findings; never mixed into severity counts.

Pass emitted review findings to Phase 2→3 gate. Attach `review_metrics` and the structured findings
array to Phase 5 Notes when useful.

## Stop searching interaction

Stop-search thresholds count findings **after** steps 5–10 (emitted rows only). Stop means do not open
**new** hunks/dimensions — not ignore a defect on the current hunk. Non-negotiable checks on paths
already under review still run.

## Precedence

When pipeline steps conflict with fast path, persona, or repo YAML, **`reference/precedence.md`** wins.
