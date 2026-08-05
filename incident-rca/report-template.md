# Incident RCA — Report Template

Copy and fill. Title: **Incident Root Cause Analysis**.

**Format few-shot (RENDER):** Load [reference/gold-rca-excerpt.md](reference/gold-rca-excerpt.md) before
authoring — match section order and narrative shape, not content.

> **Maintainer reference:** Extended section templates below document every mandatory field. During live
> RCAs, load **gold excerpt +** [workflow/phase-5.md](workflow/phase-5.md) — do not bulk-load this entire file.

Depth bar for senior / executive postmortems: [reference/root-cause-depth.md](reference/root-cause-depth.md).
Evidence matrix and quality labels: [reference/evidence-quality.md](reference/evidence-quality.md).

**Mandatory section order** — complete RCAs follow this sequence (specialized sections noted):

1. Executive summary → 2. Incident scope → 3. Customer impact → 4. Detection analysis →
5. Unified timeline → 6. Causal chain → 7. Causal graph → 8. Initiating event / trigger / root cause →
9. Ranked hypotheses → 10. Evidence matrix → 11. Evidence coverage → (blast radius, query sections) →
12. Recovery analysis → 13. Corrective actions → 14. Preventive actions → 15. Gaps → 16. Conclusion

```markdown
## Executive summary

[One paragraph: window, symptom, primary hypothesis, confidence band, immediate action. **Headline metrics stated once here** — do not repeat the same figures in Root cause or Evidence.]

Example: *Between 2026-06-28 14:00–16:00 UTC, neo-disbursement-service experienced a 5xx spike on transfer-money. **Deploy regression** (MR !482) is the leading hypothesis (**HIGH** confidence): deploy at 14:20 UTC preceded the spike at 14:45. Immediate action: rollback or hotfix `TransferMoneyHandler`.*

**Optional chat tiers:** TL;DR (3 bullets) · 2-min read (this section + Conclusion) · 5-min read (through Ranked hypotheses) · Full RCA

---

## Incident scope

| Field | Value |
|-------|-------|
| Window | `<from>` → `<to>` UTC |
| Environment | production |
| Service | `<service or org-wide>` |
| Symptom | `<symptom or —>` |
| Incident class | Deploy / Dependency / Capacity / Configuration / Software defect / Data quality / Security / Network / Third-party / Unknown |
| Confidence | HIGH / MEDIUM / LOW / UNKNOWN — see basis below |

---

## Customer impact

[Required — use **Unknown** for unavailable fields; do not omit the section.]

| Field | Value |
|-------|-------|
| Affected users | `<count or Unknown>` |
| Affected endpoints / flows | `<list or Unknown>` |
| Availability impact | `<e.g. partial outage, elevated errors, or Unknown>` |
| Latency impact | `<e.g. p95 +800ms, or Unknown>` |
| Revenue / business impact | `<if known or Unknown>` |
| SLO breached | `<yes/no/Unknown — which SLO>` |
| Duration | `<minutes or Unknown>` |

---

## Detection analysis

[Who noticed and how long until detection.]

| Field | Value |
|-------|-------|
| Detected by | customer / pager / synthetic / Slack / on-call / Unknown |
| Symptom onset | `<time UTC>` |
| First alert / ticket | `<time UTC or Unknown>` |
| MTTD | `<duration or Unknown>` |
| Monitoring gap | `<what failed to alert early, or None noted>` |

---

## Unified timeline

[Include **remediation** rows when mitigation occurred. **Evidence quality** column: Observed / Correlated / Inferred / Assumed.]

| Time (UTC) | Type | Evidence quality | Source | Event |
|------------|------|------------------|--------|-------|
| 14:20 | deploy | Correlated | gitlab | Production deploy MR !482 |
| 14:45 | error_signal | Observed | datadog | 5xx spike on transfer-money |
| 14:47 | infra_signal | Observed | datadog | DB latency exceeded threshold |
| 14:48 | infra_signal | Inferred | datadog | Application retries likely increased queue depth |
| 14:50 | jira | Observed | jira | INC-4521 created |
| 15:10 | remediation | Observed | ops | Rollback initiated |
| 15:25 | recovery | Observed | datadog | Error rate returned to baseline |

---

## Causal chain

[Propagation order with `↓` — mechanism narrative. Not a duplicate of the timeline table.]

Example:
```text
14:20 UTC — production deploy MR !482
↓
14:45 UTC — 5xx spike on transfer-money handler
↓
14:50 UTC — INC-4521 opened
```

---

## Causal graph

[Compact vertical graph — trigger → intermediate failures → customer-visible symptom. Easier to scan than prose. Distinct from timeline (chronological) and causal chain (mechanism narrative).]

Example:
```text
Deploy (MR !482)
↓
OpenSearch query regression (N+1 pattern)
↓
Search latency / thread-pool saturation
↓
Application thread starvation
↓
Kafka consumer backlog
↓
API timeout
↓
Customer 5xx errors
```

Label each node **(Observed)** or **(Inferred)** when not all nodes are directly logged. Graph must be
**acyclic** — no circular `↓` chains. If feedback loops exist (latency ↔ retries), describe them in
prose **after** the graph once the initiating event is identified. Customer-visible symptoms at the **bottom**.

---

## Initiating event / trigger / root cause / contributing factors

**[Hypothesis label]** — primary (H1), score `<0–100>` *(omit primary label if all hypotheses ≤ MEDIUM — use Unknown conclusion)*

Do **not** stop at an infrastructure symptom alone — use layered causality ([root-cause-depth.md](reference/root-cause-depth.md)):

### Confirmed failure
[What broke — observable with evidence]

### Initiating event
[What first disturbed the system — traffic spike, campaign, external event — **Unknown** if not established]

### Immediate trigger
[Proximate event that directly caused failure — deploy, query, config change — **Unknown** if not established]

### Root cause
[Why the system failed — design/process gap; e.g. missing integration test]

### Contributing factors
[Conditions that amplified impact — shared cluster, no circuit breaker, missing timeout]

### Underlying / systemic cause
[Organizational gap — no perf regression suite, governance — evidence-safe wording]

**Confidence:** HIGH

**Reason**
✓ Signal agreement — …
✓ Source diversity — …
✓ Counter-evidence — …
✓ Window coverage — …

**Remaining uncertainty**
- …

[Short rationale — cross-reference executive summary metrics; do not re-list every number.]

---

## Ranked hypotheses

[Integer scores 0–100 from [evidence-quality.md](reference/evidence-quality.md). **Supporting evidence and contradicting evidence required** for every hypothesis below.]

| ID | Hypothesis | Score | Confidence | Key evidence | Counter-evidence |
|----|------------|-------|------------|--------------|------------------|
| H1 | deploy_regression | 84 | HIGH | Deploy + diff on path + error spike | Infra CPU elevated |
| H2 | infra_capacity | 63 | MEDIUM | CPU 94%, no deploy on service | Query explains saturation |
| H3 | kafka_lag_spike | 31 | LOW | Lag spike timing only | No consumer group match |

### H1 — deploy_regression (score 84, HIGH)

**Supporting evidence**
- …

**Contradicting evidence**
- … *(or "None found after checking infra signals and alternate deploy windows")*

**Remaining uncertainty**
- … *(or "None")*

### H2 — infra_capacity (score 63, MEDIUM)

**Supporting evidence**
- …

**Contradicting evidence**
- …

**Remaining uncertainty**
- …

*(Repeat for each ranked hypothesis H3+; omit ruled-out hypotheses or list under Ruled out.)*

---

## Evidence matrix

[Required — every material signal mapped to hypothesis ID. Column **Evidence quality**: Observed / Correlated / Inferred / Assumed. Include **Freshness** when collected long after incident.]

| Signal | Source | Time (UTC) | Supports | Evidence quality | Confidence | Freshness | Link |
|--------|--------|------------|----------|------------------|------------|-----------|------|
| 500s on transfer-money | Datadog | 14:45 | H1 | Observed | HIGH | Fresh | [traces](…) |
| Production deploy MR !482 | GitLab | 14:20 | H1 | Correlated | HIGH | Fresh | [deployment](…) |
| CPU p95 94% | Datadog | 14:47 | H2 | Observed | MEDIUM | Acceptable | [metrics](…) |
| Diff touches TransferMoneyHandler | GitLab | — | H1 | Observed | HIGH | — | [MR](…) |

---

## Evidence coverage

[Required on complete RCAs — from Phase 4. Explains confidence ceiling. Spec: [evidence-coverage.md](reference/evidence-coverage.md).]

| Domain | Status | Coverage | Freshness | Notes |
|--------|--------|----------|-----------|-------|
| Traces | ✅ Complete | 100% | Fresh | |
| Logs | ✅ Complete | 100% | Acceptable | |
| Metrics | ✅ Complete | 100% | Fresh | |
| Deploy metadata | ✅ Complete | 100% | Fresh | |
| Git diff | ⚠ Missing | 0% | — | Blocks deploy HIGH |
| Customer telemetry | ⚠ Partial | 65% | Stale | |
| Feature flags | ❌ Missing | 0% | — | Not queried |
| Infrastructure events | ✅ Complete | 100% | Fresh | |
| Tickets | ✅ Complete | 100% | Fresh | |

**Overall investigation completeness:** 91%

**Confidence ceiling:** MEDIUM

**Blocking gaps:** Git diff unavailable

---

## Five whys

| Why | Answer |
|-----|--------|
| Why …? | … |
| Why …? | … |

(3–5 rows; stop at Unknown rather than speculate.)

---

## What we know vs what we don't know

### Confirmed
- …

### Unknown
- …

---

## Blast radius

[When multiple services affected. **One sentence** explaining the shared dependency, then tree or table.
Include **primary service**, **dependency tree**, and **upstream top-3 callers** (first 10 min) when
OpenSearch/ES, Redis, or Kafka is involved.]

> All affected services depended on `<dependency>` for `<purpose>`, making it a common point of failure.

```text
<dependency — e.g. opensearch-cluster>
├── <top-caller-1>  ← upstream (first 10m @base_service)
├── <top-caller-2>
├── <top-caller-3>
├── <service-a>     ← downstream impact
├── <service-b>
└── <service-c>
```

---

## Trigger workload analysis

[When query-engine saturation — synthesize from **Query execution profile** (Phase 1 APM) and
**Executed queries investigated** (Phase 3 follow-up).]

| Field | Value |
|-------|-------|
| Index / table | |
| Query pattern | |
| Client service(s) | |
| Legitimate vs abusive | **Unknown** |

---

## Query execution profile

[Required for **OpenSearch/Elasticsearch** incidents — populated in Phase 1 from `aggregate_spans`:
`service:elasticsearch`, group by `resource_name` + `@base_service`. Gives index + caller + HTTP status
even when slow logs are absent.]

| Resource / index | Caller (@base_service) | HTTP status | Span count | p95 (ms) | Error count | Link |
|------------------|------------------------|-------------|------------|----------|-------------|------|
| | | | | | | |

If the Phase 1 APM pass returned no spans, state what was tried (including `@db.system:elasticsearch`
fallback) — do not leave blank.

---

## Executed queries investigated

[Required when [query-investigation.md](reference/query-investigation.md) was triggered. For OpenSearch/ES,
Phase 1 APM pass is already done — Phase 3 adds logs, DBM, and engine slowlog gaps. Omit for pure deploy regressions.]

### Investigation attempts

- [ ] APM `aggregate_spans` / slow `search_datadog_spans` *(OpenSearch/ES: done in Phase 1 — check here)*
- [ ] Log aggregation (`analyze_datadog_logs`) for slowlog / query text
- [ ] Datadog DBM top `query_signature` (if DB)
- [ ] Engine slow log via ops — **not in Datadog**

### Top queries / workloads (incident window)

| Rank | Query / resource | Client | Pattern | Count / p95 | Source | Link |
|------|------------------|--------|---------|-------------|--------|------|
| 1 | | | | | | |

If no query identified after attempts, state what was tried — do not leave blank.

---

## Key metrics snapshot

[Optional but recommended for `infra_capacity`. Minute or 5-min buckets for metrics that drove the conclusion.]

| Time (UTC) | CPU | Queue / lag | Rejects / errors | Throughput | Notes |
|------------|-----|-------------|------------------|------------|-------|
| … | … | … | … | … | … |

---

## Recovery analysis

[What ended the incident and how long recovery took. Required when mitigation occurred or recovery is known.]

| Field | Value |
|-------|-------|
| Recovery trigger | `<what action/event ended the incident — rollback, scale-up, etc.>` |
| Recovery mechanism | rollback / autoscale / restart / traffic drop / manual fix / self-recovery / Unknown |
| Recovery owner | `<team/person or Unknown>` |
| Mitigation | `<what was done — e.g. rollback MR !482>` |
| Effect | `<e.g. latency ↓94%, error rate → baseline>` |
| Verification | `<e.g. 30 min stable post-recovery>` |
| Why recovery worked | `<mechanism — removed bad deploy, added capacity, drained queue>` |
| Residual risk | High / Medium / Low / Unknown — `<what could recur if root cause not fixed>` |
| Time to recover (MTTR) | `<duration>` |
| Primary recovery delay | `<diagnosis / deploy / queue drain / approval / Unknown>` |

### Recovery timeline

| Milestone | Time (UTC) | Notes |
|-----------|------------|-------|
| Symptom onset | | |
| First alert | | |
| Decision | | |
| Mitigation started | | |
| Mitigation complete | | |
| Recovery confirmed | | |

**MTTR:** `<duration>` — primary delay: `<diagnosis / deploy / queue drain / approval>`.

---

## Ruled out

- [Hypothesis]: [why ruled out — for JVM/memory, note GC/heap/circuit breakers checked or Not checked]

---

## Resolution & remediation

### Immediate mitigation
[What restored service — rollback, scale-up, traffic shed. Label as mitigation, not permanent fix.]

### Permanent fixes
[Summary pointing to P0/P1/P2 below — query fix, alerting, isolation, capacity.]

---

## Corrective actions

[Restore service, fix code, increase capacity — immediate ownership.]

| Action | Owner | Priority | ETA | Notes |
|--------|-------|----------|-----|-------|
| Rollback / hotfix MR !482 | `<team>` | P0 | `<date>` | Restore service |
| Increase OpenSearch headroom | `<team>` | P0 | `<date>` | Temporary capacity |

### P0 — corrective (before next similar incident)
- [ ] …

---

## Preventive actions

[Tests, alerts, architecture, documentation — reduce recurrence. Distinct audience from corrective.]

| Action | Owner | Priority | ETA | Notes |
|--------|-------|----------|-----|-------|
| Add perf regression test | `<team>` | P1 | `<sprint>` | Root cause fix |
| Enable slow query logging | `<team>` | P1 | `<sprint>` | Detection gap |
| Update runbook | `<team>` | P2 | `<quarter>` | On-call enablement |

### P1 — preventive (this sprint)
- [ ] …

### P2 — preventive (this quarter)
- [ ] …

---

## Gaps / investigation follow-up

[Missing evidence or analysis not yet done — telemetry holes, untested cascade hops, correlator absent,
**process failures** (`mcp_process_failure`), **observability backend errors** (`observability_backend_error`),
log coverage gaps (`log_coverage_gap` — not mpokket), **`logs_source_profile`** (KubeSense-primary orgs),
**KubeSense metadata-only** (`kubesense_metadata_only`).]

- [ ] …

**KubeSense-primary (mpokket)** — Datadog logs are **not ingested**; KubeSense MCP (`kubesense-mcp` skill) is the log path:

- [ ] *"logs_primary: kubesense — Datadog log queries N/A."*
- [ ] *"KubeSense MCP `search-logs` with `body` attempted per `kubesense-logs` skill — [messages captured / fetch failed]."*
- [ ] *"SPL CLI attempted per kubesense-spl.md only if MCP body failed — [messages captured / no rows / API key absent]."*
- [ ] Only if both unavailable or empty: *"Cannot confirm query text from logs; APM + metrics only — ops access-log review."*

---

## Risks

> Overall: …

| Tier | Risk |
|------|------|
| **Highest** | … |
| **High** | … |
| **Medium** | … |
| **Low** | … |

---

## Lessons learned

| Lesson | Action |
|--------|--------|
| … | … |

---

## Conclusion

2–4 sentences restating the primary hypothesis, confidence band, immediate action, and what to verify next.
No internal IDs, no automation CTAs.

**When no hypothesis exceeds MEDIUM after confidence caps**, use — do **not** name a primary cause:

> No defensible root cause identified. Evidence insufficient for a causal claim. Highest-scoring alternates
> did not exceed MEDIUM after caps. Additional telemetry required: [specific gaps]. See Evidence coverage.

**When confidence is UNKNOWN or primary is `inconclusive`**, use:

> No defensible root cause identified. Evidence insufficient for a causal claim. Additional telemetry
> required: [specific gaps]. Ranked alternates and investigation follow-ups are in Gaps.

**When cause is established:**

> The most likely root cause is a **deploy regression** from MR !482 (HIGH confidence). Roll back or
> hotfix the `TransferMoneyHandler` validation change, then confirm 5xx rate returns to baseline within
> 30 minutes. Re-run observability checks if errors persist after rollback.

---

## Appendix — machine metadata (chat / file only)

**Do not** include this block in Confluence/wiki export or Jira narrative paste. Spec:
[reference/assessment-metadata.md](reference/assessment-metadata.md).

```yaml
assessment_metadata:
  assessment_type: full
  started: "<ISO-8601>"
  finished: "<ISO-8601>"
  service: "<service>"
  incident_window:
    from: "<ISO-8601>"
    to: "<ISO-8601>"
  primary_hypothesis: deploy_regression
  confidence: high
  assessment_complete: true
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

On re-run with prior footer: add `history` with `investigation_iteration`, `first_investigation`,
`prior_investigation`. Omit `history` on first investigation.

---

## Post-RCA actions

Structured follow-ups after the report — fill every row; use `—` when not applicable.

| Action | Target | Owner | Priority | ETA | Notes |
|--------|--------|-------|----------|-----|-------|
| **Follow-up Jira** | `<INC-#### or new ticket>` | `<team/person>` | P0/P1 | `<date>` | Link this RCA; set priority from confidence |
| **Update runbook** | `<runbook path or Confluence page>` | `<team/person>` | P1 | `<sprint>` | Add detection steps, rollback, escalation |
| **PR review** | `<MR !#### or repo/branch>` | `<reviewer>` | P0 | `<date>` | When `deploy_regression` — invoke **pr-review** on causative MR |

Present this table in chat after the executive summary. Read-only boundary: offer ticket text; do not
write to Jira unless the user explicitly requests and write tools are available.

---

## K8s skill handoff (infra capacity confirmed)

When primary or supporting hypothesis is **`infra_capacity`** (OOM, throttle, crashloop, HPA max),
append a paste-ready handoff block for **k8s-overprovisioning-datadog**:

```markdown
### Handoff → k8s-overprovisioning-datadog

**Service:** `<kube_deployment or APM service>`
**Window:** `<from>` → `<to>` UTC (incident window + 7d trailing for utilization)
**Symptoms:** `<OOM count / throttle % / crashloop / HPA at max>`
**Evidence bundle:**
- Fleet CPU p95: `<value>` (% of request if known)
- Memory peak (worst pod): `<value>`
- Throttle rate (7d): `<value>`
- Replicas / HPA: `<current / min / max>`
- Recent deploy: `<sha or MR if relevant>`
**RCA link:** `<path or URL to this report>`
**Ask:** Right-size / overprovisioned assessment with focus on `<CPU | memory | replicas>`
```

Copy this block into chat so the user can paste it into a k8s skill invocation.

---

## Confluence / wiki export (optional)

When the user asks for wiki-ready output, render an additional **Confluence-friendly** section using
the mapping below. **Strip Appendix — machine metadata.** No Confluence MCP required — output markdown the user can paste.

| Report section | Wiki heading | Body content (include) | Confluence tip |
|----------------|--------------|------------------------|----------------|
| Executive summary | `h2. Summary` | Window, primary hypothesis, confidence band, one-line reason | Lead with window + primary hypothesis |
| Incident scope | `h2. Scope` | Service, env, incident class, window | Include incident class |
| Customer impact | `h2. Customer impact` | All seven customer-impact fields | Unknown OK |
| Detection analysis | `h2. Detection` | detected_by, MTTD, monitoring gap | MTTD + monitoring gap |
| Unified timeline | `h2. Timeline` | Full timeline table (time, event, source, evidence quality) | Evidence quality on every row |
| Causal chain | `h2. Causal chain` | Propagation narrative with `↓` between hops | Not parallel bullets only |
| Causal graph | `h2. Causal graph` | Mermaid or acyclic vertical chain | Acyclic vertical chain |
| Initiating event / trigger / root cause | `h2. Root cause` | Five layers when applicable | Distinguish trigger vs root cause |
| Ranked hypotheses | `h2. Hypotheses` | Table + supporting/contradicting bullets per hypothesis | Include contradicting evidence |
| Evidence matrix | `h2. Evidence matrix` | Material signals with quality + freshness | No raw JSON |
| Evidence coverage | `h2. Evidence coverage` | Completeness %, ceiling, blocking gaps | Completeness % + ceiling |
| Five whys | `h2. Five whys` | 3–5 row table | Table |
| Known vs unknown | `h2. Known vs unknown` | Two bullet lists | Explicit Unknown bullets |
| Blast radius | `h2. Blast radius` | Tree/table + dependency explanation sentence | Upstream top-3 when ES/Kafka |
| Trigger workload analysis | `h2. Trigger workload` | Workload table or Unknown after attempts | Unknown OK after attempts |
| Query execution profile | `h2. Query execution profile` | Phase 1 APM table | OpenSearch/ES required |
| Executed queries investigated | `h2. Queries investigated` | Attempts checklist + top queries table | Empty table OK if documented |
| Key metrics snapshot | `h2. Metrics` | Metric table for infra primary | Table |
| Recovery analysis | `h2. Recovery` | Effect, verification, residual risk, MTTR | MTTR when known |
| Ruled out | `h2. Ruled out` | Bullet list with reason | One line per alternate |
| Resolution & remediation | `h2. Resolution` | Mitigation vs permanent split | Separate immediate vs permanent |
| Corrective actions | `h2. Corrective actions` | Action table (owner, priority, ETA) | Immediate fixes |
| Preventive actions | `h2. Preventive actions` | Action table | Tests, alerts, architecture |
| Gaps | `h2. Investigation gaps` | Checkbox list from report Gaps section | Copy verbatim |
| Risks | `h2. Risks` | Overall sentence + tiered table | Overall sentence first |
| Lessons learned | `h2. Lessons learned` | Lesson / Action table | 3–6 rows |
| Conclusion | `h2. Conclusion` | Primary hypothesis or Unknown path | Unknown when inconclusive |
| Post-RCA actions | `h2. Post-incident actions` | Action table with owners | Jira/runbook/PR rows |
| Appendix: queries | `h2. Appendix — Queries` | Query reference list | Collapse under `{expand}` |

Avoid `#` headings in Confluence paste — use `h2.` / `h3.` wiki markup or let Confluence auto-convert
from markdown. Strip internal-only debug lines and **`assessment_metadata`**.

---

## Appendix: query references

- `datadog: trace.servlet.request.errors{service:neo-disbursement-service}`
- `kubesense: analyze-logs level=ERROR groupBy workload` *(mpokket — use `workload`, not `service`)*
- `kubesense-mcp: search-logs body field workload=<workload>` *(primary log text path)*
- `kubesense-spl: scripts/kubesense_logs.py <workload> --evidence` *(fallback when MCP body fails)*
- `jira: project=INC AND created >= …`
```

---

## Quality checklist

Evidence quality thresholds: [reference/thresholds.md](reference/thresholds.md). Evidence matrix:
Evidence coverage: [reference/evidence-coverage.md](reference/evidence-coverage.md). Jira paste template:
[reference/jira-comment-template.md](reference/jira-comment-template.md). Depth bar:
[reference/root-cause-depth.md](reference/root-cause-depth.md).

- [ ] **Section order** matches mandatory schema (exec summary through Conclusion)
- [ ] **Incident class** set in scope (from Phase 4 mapping)
- [ ] **Customer impact** — all seven fields present (Unknown OK)
- [ ] **Detection analysis** — detected_by, MTTD, monitoring gap
- [ ] **Unified timeline** — Evidence quality column on every row
- [ ] **Causal graph** — acyclic; feedback loops in prose only
- [ ] **Initiating event** distinguished from trigger and root cause
- [ ] **Ranked hypotheses** — supporting and contradicting evidence blocks per hypothesis
- [ ] **Evidence coverage** — completeness %, confidence ceiling, blocking gaps
- [ ] **Hypothesis dedup** — no split causal chain as competing H1/H2/H3
- [ ] **Evidence matrix** — Evidence quality + freshness on material signals
- [ ] Primary hypothesis stated with confidence badge **and** one-line reason
- [ ] **Layered root cause** when `infra_capacity`, `query_governance`, or `dependency_failure` ≥ MEDIUM — failure / trigger / root cause / contributing / systemic
- [ ] **Causal chain** shows propagation (`↓`), not only parallel timeline events
- [ ] **Five whys** table present (3–5 rows) on complete RCAs
- [ ] **Known vs unknown** section with explicit Unknown bullets where applicable
- [ ] **Evidence-safe wording** — no "undersized" without proof; prefer headroom / insufficient capacity
- [ ] **Confidence** — band + Reason ✓ / Remaining uncertainty; integer scores in Ranked hypotheses only (no decimals in narrative)
- [ ] **Recovery analysis** — mitigation, effect, verification, residual risk, MTTR
- [ ] **Lessons learned** table (3–6 rows) on complete RCAs
- [ ] **Query execution profile** when OpenSearch/Elasticsearch — Phase 1 `aggregate_spans` table (resource + caller + status)
- [ ] **Executed queries investigated** when search/DB saturation — attempts logged; top queries table or documented empty
- [ ] **Blast radius** includes dependency explanation sentence + upstream top-3 callers when ES/Redis/Kafka
- [ ] **Log coverage fallback** — KubeSense attempted when Datadog empty for blast-radius services (mandatory ES/OpenSearch)
- [ ] **Process failure** flagged when trigger Unknown and KubeSense skipped while ✅
- [ ] **Risks** tiered (Highest / High / Medium / Low), not flat list only
- [ ] **Resolution** splits immediate mitigation vs permanent fixes
- [ ] **Corrective actions** and **Preventive actions** in separate sections with owner / priority / ETA
- [ ] **Conclusion** — no primary when all hypotheses ≤ MEDIUM after caps
- [ ] At least one observability signal OR explicit gap noted (minimum evidence gate respected)
- [ ] Signal density classified (strong / sparse / none) when Phase 1 completed
- [ ] Every counted signal `detected_at` within `[window.from_time, window.to_time]`
- [ ] Deploy timeline checked (±30 min before window)
- [ ] Jira searched even if no ticket found
- [ ] No root cause stated as certainty when confidence is LOW/UNKNOWN
- [ ] Deep links included for every evidence row
- [ ] `sample_messages` deduplicated across sources before Phase 4 ranking
- [ ] If ≥3 similar incidents found in Phase 3 recurrence check: `recurrence_history` populated and report severity escalated to "Systemic / requires architectural fix"
- [ ] If top-2 hypothesis raw scores within 20% of each other: multi-cause co-cause documented with `"causality": "multi-cause"` and both hypotheses reported
- [ ] **Blast radius** tree/table when ≥2 downstream services affected
- [ ] **Key metrics snapshot** when `infra_capacity` primary (or N/A noted)
- [ ] Post-RCA actions table populated (Jira, runbook, PR review rows)
- [ ] When `infra_capacity` confirmed: K8s handoff block included in chat output
- [ ] Confluence export requested → wiki heading mapping applied; **no** `assessment_metadata` in wiki body
- [ ] oss-obs path: confidence capped at MEDIUM; `source: prometheus` or `source: loki` on signals
- [ ] Primary hypothesis shows **Confidence** band + Reason / Remaining uncertainty (no decimal in body)
- [ ] **Risks** opens with `Overall:` + tiered table
- [ ] **Conclusion** present as last narrative section before appendix / optional exports
- [ ] **`assessment_metadata`** only in Appendix — machine metadata (chat/file), not Confluence/Jira narrative ([assessment-metadata.md](reference/assessment-metadata.md))
- [ ] Report body has no agent mode instructions (`Type ACT`, `PLAN/ACT`, posting confirmations) — those belong in chat only ([post-action-templates.md](../docs/skill-framework/shared/post-action-templates.md))

## Human-report rules

1. **Confidence display** — band + Reason ✓ / Remaining uncertainty; integer hypothesis scores in Ranked hypotheses only; decimals in `assessment_metadata`.
2. **Root cause depth** — initiating event / trigger / root cause / contributing / systemic; infrastructure symptom ≠ root cause.
3. **Anti-repetition** — headline metrics once in executive summary.
4. **Risks framing** — `Overall:` then tiered table (Highest → Low).
5. **Recovery MTTR** — recovery timeline when mitigation applied.
6. **Lessons learned** — leadership table distinct from P0/P1/P2 tasks.
7. **Conclusion** — last narrative section before appendix.
8. **No agent instructions in report body** — post-actions in chat per [post-action-templates.md](../docs/skill-framework/shared/post-action-templates.md).
9. **Machine metadata** — `assessment_metadata` in Appendix only for human exports.
