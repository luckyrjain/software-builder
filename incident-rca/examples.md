# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).
Full report structure: [report-template.md](report-template.md).

## Skill routing keywords

Used by skill discovery when the YAML `description` is truncated:

| Category | Phrases |
|----------|---------|
| **Core** | RCA, root cause analysis, post-incident investigation, postmortem, what caused |
| **Symptoms** | outage, error spike, 5xx, latency incident, consumer lag, SLO breach |
| **Anchors** | INC-, P1, P2, on-call, deploy regression |
| **Time** | time range, last Tuesday, between HH:MM and HH:MM |

**Do not route here:** MR/PR review → **pr-review**; K8s rightsizing → **k8s-overprovisioning-datadog**;
live rollback → out of scope.

## Invocation table

| # | User says | Behavior |
|---|-----------|----------|
| 1 | "RCA for `neo-disbursement-service` 14:00–16:00 UTC" | Phase 0→5; window from user |
| 2 | "RCA for INC-4521" | Phase 0b anchor → 1→5 |
| 3 | "Root cause last Tuesday 2–4pm Kafka lag" | Org-wide Phase 1 discovery |
| 4 | "RCA neo-disbursement — logs unavailable" | slo_breach fallback path |
| 5 | "Post-incident review payout-worker" | Standard pipeline |
| 6 | "What caused the 5xx spike?" | Symptom-only; service discovery |
| 7 | "RCA with correlator CLI missing" | manual-scoring degraded path |
| 8 | "Review MR !482 for security" | **Wrong skill** → pr-review |
| 9 | "Post RCA to Confluence / Slack summary for #incidents" | Phase 5 report → offer wiki paste or Slack brief on user confirm | [post-action-templates §4](../docs/skill-framework/shared/post-action-templates.md#4-slack-incident-channel-brief) |

---

### Scenario: Happy path — deploy regression

**User:** "RCA for `neo-disbursement-service` 2026-06-28 14:00–16:00 UTC — 5xx spike on transfer-money"

**Agent:**
1. Phase 0 (Detect) — MCP profile; Datadog ✅, GitLab ✅, Jenkins ✅, CLI ✅
2. Phase 1 (Gather) — error rate spike 14:45; deploy change story 14:20
3. Phase 2–3 — MR !482 merged; INC-4521 corroborates
4. Phase 4 (Rank) — CLI ranks `deploy_regression` HIGH
5. Phase 5 (Report) — manager-ready report + Post-RCA actions

**Expected fragments:**

```
**RCA MCP profile:** Datadog ✅ | KubeSense ❌ | GitLab ✅ | Jenkins ✅ | Jira ✅ | CLI ✅
```

```
## Executive summary

Between 2026-06-28 14:00–16:00 UTC, neo-disbursement-service experienced a 5xx spike on transfer-money.
**Primary:** deploy_regression — deploy at 14:20 UTC preceded the 12% 5xx spike at 14:45;
`get_commit_diff` shows MR !482 changed `TransferMoneyHandler`.
**Alternate ruled out:** infra_capacity — no OOM/restarts.
**Action:** roll back / hotfix MR !482.
```

```
**Confidence:** HIGH

**Reason**
✓ Signal agreement — deploy at 14:20 UTC; 5xx spike at 14:45 UTC (within 60 min window)
✓ Source diversity — Datadog error rate + GitLab change story
✓ Counter-evidence — infra_capacity ruled out (no OOM/restarts)

**Remaining uncertainty**
- (none for deploy regression on this path)
```

```
## Risks

Overall: Rollback of MR !482 is the safest immediate mitigation; validate transfer-money in staging if hotfix path chosen.

- **Sparse logs after 15:30** — secondary ranking weaker outside peak window
```

```
## Conclusion

Deploy regression from MR !482 is the most likely root cause (HIGH confidence). Roll back or hotfix the validation change in `TransferMoneyHandler`, then confirm 5xx rate returns to baseline within 30 minutes.
```

**Golden `assessment_metadata` footer:**

```yaml
assessment_metadata:
  assessment_type: full
  started: "2026-06-28T15:00:00Z"
  finished: "2026-06-28T15:22:00Z"
  service: neo-disbursement-service
  incident_window:
    from: "2026-06-28T14:00:00Z"
    to: "2026-06-28T16:00:00Z"
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

---

### Scenario: Multi-cause incident

**User:** "RCA checkout-api 2026-06-28 10:00–12:00 UTC — OOM and deploy at 10:15"

**Agent:**
1. Phase 1 — OOM kills + error spike; deploy at 10:15
2. Phase 4 — raw scores within 20% for `deploy_regression` and `infra_capacity`
3. Phase 5 — multi-cause report

**Expected fragments:**

```
**Primary:** deploy_regression (score 0.52, **MEDIUM**)
**Co-cause:** infra_capacity (score 0.48, **MEDIUM**)
**Causality:** multi-cause — evidence supports both a risky deploy and memory pressure; do not optimize for one while ignoring the other.
```

```
**Confidence:** MEDIUM

**Reason**
✓ Signal agreement — deploy at 10:15 + OOM kills in same window
✓ Competing hypothesis — infra_capacity within 20% raw score (multi-cause)
✓ Source diversity — Datadog infra + GitLab change story
```

```
## Conclusion

Treat as **multi-cause**: address memory pressure (infra_capacity) and review MR !901 deploy risk in parallel. Do not close the incident after rollback alone without validating pod memory limits.
```

```
| Hypothesis | Score | Confidence | Rationale |
|------------|-------|------------|-----------|
| deploy_regression | 0.52 | MEDIUM | MR !901 at 10:15; diff touches checkout handler |
| infra_capacity | 0.48 | MEDIUM | OOMKilled × 8; no deploy on memory limit change |
```

---

### Scenario: oss-obs degraded mode

**User:** "RCA payment-api 2026-06-28 — no Datadog; I have Prometheus metrics"

**Agent:**
1. Phase 0 — Datadog ❌, KubeSense ❌; announce `oss-obs` degraded profile
2. Phase 1 — user-pasted PromQL: `rate(http_requests_total{status=~"5.."}[5m])` confirms 5xx spike
3. Phase 4 — manual scoring; cap **MEDIUM**

**Expected fragments:**

```
**RCA MCP profile:** Datadog ❌ | KubeSense ❌ | oss-obs ✅ (Prometheus manual) | GitLab ✅ | CLI ❌
**Degraded:** Grafana/Prometheus MCP not supported in v1 — using user-supplied PromQL results.
```

```
**Primary:** slo_breach (**MEDIUM**) — error budget burn visible in PromQL; no Datadog change stories.
**Gaps:** Single observability stack (Prometheus only); deploy correlation weaker without `get_change_stories`.
**Confidence cap:** MEDIUM — oss-obs path; cannot exceed MEDIUM on single stack.
```

---

### Scenario: Partial RCA — investigation stopped early

**User:** "RCA api-gateway 12:00–12:30 UTC" → after Phase 1: "stop here"

**Agent:**
1. Phase 1 — 1 weak signal (sparse per thresholds)
2. User says *"stop here"* → skip Phases 2–4
3. Phase 5 partial report

**Expected fragments:**

```
**Phase 1 complete:** 1 error signal, 0 infra signals. Sparse — proceed to change correlation?
```

```
## Investigation status: PARTIAL

**Primary hypothesis:** inconclusive (**UNKNOWN**)
**Reason:** User stopped after Phase 1; signal too thin for deploy correlation.
**Collected:** 3 error log samples at 12:18 UTC (api-gateway); magnitude <2× baseline.
**Gaps:** No deploy timeline checked; correlator not invoked.
**Next steps:** Widen window to ±2h; re-run with Jenkins/GitLab enabled; or continue to Phase 2 on request.
```

---

### Scenario: Jira-anchored (Phase 0b)

**User:** "RCA for INC-4521"

**Agent:**
1. Phase 0b — parse ticket: issues started ~14:25; `from_time = 14:25`; `analysis_from_time = 14:10`
2. Phase 1–5 — standard pipeline

**Expected fragments:**

```
**Window:** Incident start (reported): `2026-06-28T14:25:00Z` | Query start (backstroke): `2026-06-28T14:10:00Z` | End: `2026-06-28T16:00:00Z`
```

```
Anchored from INC-4521. **Primary:** deploy_regression (**HIGH**).
Ticket comment ("started after 14:30 deploy") corroborates telemetry.
```

---

### Scenario: PagerDuty absent — slo_breach only

**User:** "RCA payment-api 2026-06-28 — no logs in Datadog"

**Agent:**
1. Phase 0 (Detect) — Datadog ✅; logs empty in window; PagerDuty ❌
2. Phase 1 (Gather) — slo_breach path: burn rate, traces, war-room signals
3. If still only slo_breach → Phase 5 partial report; skip Phases 2–3

**Expected fragments:**

```
**Primary:** slo_breach (**MEDIUM**) — error budget burn 340% in window; logs unavailable.
**Gaps:** Log samples missing — ranking from SLO + traces only.
**Escalation:** Confirm log retention policy; check sampling rate; try APM spans.
```

---

### Scenario: feature_flag_regression

**User:** "RCA rewards-api 2026-06-27 09:00–10:00 UTC — errors after flag toggle"

**Agent:**
1. Phase 1 — error spike 09:22
2. Phase 2 — `get_change_stories` shows `feature_flag` event `enable-new-checkout` at 09:18
3. Phase 4 — `feature_flag_regression` wins

**Expected fragments:**

```
**Primary:** feature_flag_regression (score 0.91, **HIGH**)
**Reason:** Flag `enable-new-checkout` toggled at 09:18 UTC; 5xx spike at 09:22 on same service; no code deploy in window.
**Evidence:** Datadog change story + error_rate signal (2 independent types).
```

---

### Scenario: dependency_failure cascade

**User:** "RCA order-api 2026-06-26 — upstream timeouts to inventory-service"

**Agent:**
1. Phase 1 — order-api timeouts in logs
2. Phase 1 pivot — inventory-service error spike; payment-db healthy
3. Phase 4 — chain `order-api → inventory-service` (root)

**Expected fragments:**

```
**Primary:** dependency_failure (**MEDIUM**)
**Chain:** order-api → inventory-service (root)
**Reason:** inventory-service 503s at 11:05; order-api propagation at 11:06; payment-db healthy.
**Gaps:** Deep cascade beyond 2 hops not traced — recommend distributed tracing for full chain.
```

---

### Scenario: Handoff to k8s after infra_capacity

**User:** "RCA checkout-api — OOMKilled pods"

**Agent:**
1. Phase 4 — `infra_capacity` primary
2. Phase 5 — report + k8s handoff block

**Expected fragments:**

```
### Handoff → k8s-overprovisioning-datadog

**Service:** `checkout-api`
**Env:** `prod`
**Window:** `2026-06-28T10:00Z` – `2026-06-28T12:00Z`
**Trigger:** infra_capacity — OOMKilled × 12
**Ask:** "Assess rightsizing for checkout-api in prod"
```

---

### Scenario: OpenSearch / infra_capacity saturation (senior depth bar)

**User:** "RCA for OpenSearch cluster 2026-06-28 05:30–06:30 UTC — search failures across seven services"

**Agent:**
1. Phase 1 — CPU 99%, search throughput → 0, 2.09M thread-pool rejections; deploys ruled out;
   **ES APM pass** — `aggregate_spans` (`service:elasticsearch`, group by `resource_name` +
   `@base_service`) → top `GET /metadata/_search` from metadata-api
2. Phase 3 — **query investigation** follow-up: logs for slowlog (none ingested)
3. Phase 4 — `query_governance` primary (**MEDIUM**–**HIGH**); **`infra_capacity` co-cause** (multi-cause)
4. Phase 5 — layered root cause, **Query execution profile**, **Executed queries investigated**,
   recovery MTTR, lessons learned

**Expected fragments:**

```
## Executive summary

Between 05:30–06:49 UTC, OpenSearch search failures degraded seven downstream services. CPU reached 99%,
search throughput collapsed, and ~2.09M searches were rejected. Blue/Green scale-up restored service by
06:49. Leading hypothesis: **query_governance** (**MEDIUM**–**HIGH**) with **`infra_capacity` co-cause**
(multi-cause). Immediate trigger: heavy `GET /metadata/_search` from metadata-api at onset (APM). Mitigation:
vertical scale — not a permanent fix; introduce query governance.
```

```
## Causal chain

05:40 UTC — heavy `GET /metadata/_search` from metadata-api (APM — Phase 1; expensive query under flat throughput)
↓
Search thread pool saturated
↓
CPU reaches 99%
↓
~2.09M search rejections
↓
Seven downstream services degraded

--- recovery ---
06:30 UTC — Blue/Green scale-up initiated
↓
06:37 UTC — CPU begins dropping
↓
06:42 UTC — Search queue drains
↓
06:49 UTC — Traffic normalized
```

```
### Confirmed failure
OpenSearch search nodes exhausted CPU; search thread pool saturated (~2.09M rejections — see Key metrics).

### Immediate trigger
Heavy `GET /metadata/_search` from **metadata-api** at onset (Phase 1 APM — `aggregate_spans`). Exact
query text unconfirmed — slowlog not in Datadog. See **Query execution profile** and Executed queries.

### Underlying / systemic cause
The cluster exhausted available compute headroom for the observed workload; shared cluster lacked
workload isolation — a single workload could exhaust search capacity.
```

```
## Query execution profile

APM client spans during incident window (`aggregate_spans`: `service:elasticsearch`, group by
`resource_name` + `@base_service`).

| Resource / index | Caller (@base_service) | HTTP status | Span count | p95 (ms) | Error count | Link |
|------------------|------------------------|-------------|------------|----------|-------------|------|
| `GET /metadata/_search` | metadata-api | 503 | 1200 | 4200 | 890 | [traces](…) |
| `GET /crm/_search` | crm-api | 503 | 340 | 3100 | 210 | [traces](…) |
```

```
## Executed queries investigated

### Investigation attempts
- [x] `aggregate_spans` GROUP BY resource_name + @base_service — **Phase 1** (see Query execution profile)
- [x] `analyze_datadog_logs` for `slowlog` / `rejected_execution` — no slowlog stream ingested
- [ ] DBM — N/A (OpenSearch)
- [ ] Engine slow log pull — **pending ops** (not in Datadog)

### Top queries / workloads

| Rank | Query / resource | Client | Pattern | Count / p95 | Source | Link |
|------|------------------|--------|---------|-------------|--------|------|
| 1 | `GET /metadata/_search` | metadata-api | wildcard (suspected) | 1.2k / 4.2s | aggregate_spans | [traces](…) |
```

```
### Trigger workload analysis

| Field | Value |
|-------|-------|
| Index / table | `metadata` (suspected) |
| Query pattern | wildcard (suspected) — unconfirmed without slowlog |
| Client service(s) | metadata-api, crm-api |
| Legitimate vs abusive | **Unknown** |
```

```
## Blast radius

> All seven affected services depended on OpenSearch for master-data lookups, making the shared cluster a common point of failure.

OpenSearch
├── metadata
├── crm
├── onboarding
└── …
```

```
## Recovery timeline

| Milestone | Time (UTC) | Notes |
|-----------|------------|-------|
| Symptom onset | 05:40 | CPU spike |
| First alert | 06:02 | CPU monitor |
| Mitigation started | 06:30 | Blue/Green deploy |
| Recovery confirmed | 06:49 | Traffic normalized |

**MTTR:** ~69 min from onset — primary delay: diagnosis + Blue/Green deployment duration.
```

```
## Risks

| Tier | Risk |
|------|------|
| **Highest** | Unknown triggering query |
| **High** | Shared cluster without tenant isolation |
| **Medium** | CPU/thread-pool alerts fired late |
```

```
## Lessons learned

| Lesson | Action |
|--------|--------|
| Shared infrastructure increased blast radius | Evaluate workload isolation |
| Triggering query couldn't be identified | Enable slow logs by default |
| Scaling resolved symptoms but not cause | Introduce query governance |
```

```
**Primary:** query_governance (score 0.55, **MEDIUM**–**HIGH**)
**Co-cause:** infra_capacity (score 0.45, **MEDIUM**)
**Causality:** multi-cause — expensive query workload exhausted shared cluster headroom; scaling mitigated symptoms only.
```

```
**Confidence:** MEDIUM–HIGH

**Reason**
✓ APM identifies top workload + caller in first 10m
✓ Infra metrics corroborate saturation; throughput flat (<2× baseline)
✓ Deploy ruled out on client services

**Remaining uncertainty**
- Exact query text unconfirmed — slowlog not in Datadog
```

`assessment_metadata` (with `primary_hypothesis: query_governance`, `primary_score: 0.55`) appears only under **Appendix — machine metadata**.

---

### Scenario: CLI absent (manual scoring)

Same as happy path but `incident-rca --help` fails.

**Expected fragments:**

```
**Gaps:** Hypotheses ranked manually — correlator CLI not installed.
**Primary:** deploy_regression (**HIGH**) — manual scoring per reference/manual-scoring.md.
```
