# Manual Hypothesis Scoring (CLI fallback)

Use this when the `incident-rca` Python correlator is **not installed**. It reproduces the correlator's
ranking so an agent can rank hypotheses by hand from the evidence bundle. When you use this path, say so
in the report's **Gaps** section: *"Hypotheses ranked manually — correlator CLI not installed."*

## Signals and weights

Each hypothesis accumulates points from the signals below. Weights are relative; the absolute number
does not matter — the **ranking** and the **confidence band** do.

| Hypothesis | Signal | Weight |
|------------|--------|--------|
| `deploy_regression` | Deploy/change event 0–15 min before first error spike, same service | 5 |
| `deploy_regression` | Deploy/change event 15–60 min before spike, same service | 3 |
| `deploy_regression` | Suspect diff touches the failing path (`get_commit_diff` / changeset) | 3 |
| `deploy_regression` | Jira comment attributes the incident to a deploy | 1 |
| `configuration_change` | Config/env mutation 0–15 min before first error spike, same service, no code deploy | 5 |
| `configuration_change` | Config/env mutation 15–30 min before spike, same service, no code deploy | 3 |
| `configuration_change` | No `deployment` / build event in window on same service | 2 |
| `infra_capacity` | OOM kill in window | 4 |
| `infra_capacity` | Pod restarts / crashloopbackoff in window | 3 |
| `infra_capacity` | HPA at max replicas during window | 2 |
| `infra_capacity` | No deploy/change event in window | 2 |
| `query_governance` | `expensive_query_flag` — exec_rate <10/min and p95 >30s on top resource under saturation | 5 |
| `query_governance` | Wildcard or heavy aggregation pattern in query text / resource_name | 3 |
| `query_governance` | Saturation (CPU/thread-pool/queue) without throughput spike (<2× baseline) | 3 |
| `query_governance` | **CPU↑ + ES `elasticsearch_requests` flat or declining at onset** (expensive-query signature) | 4 |
| `query_governance` | APM wildcard / cross-index (`POST /?/_search`, unscoped `/_search`) in onset slice | 4 |
| `query_governance` | Caller service request rate <2× baseline at onset (traffic spike ruled out) | 3 |
| `query_governance` | `service_owner_finding` — backend logs confirm malformed/long query text | 5 |
| `query_governance` | Top `@base_service` caller in first 10 min window | 2 |
| `query_governance` | Slowlog evidence (`took_millis` >30s or ingested slowlog line) | 2 |
| `query_governance` | No deploy on identified client service in window | 2 |
| `query_governance` | `duplicate_request_burst` — identical/near-identical request body repeating ≥2× within a ≤5s window | 3 |
| `query_governance` | `body_length` outlier on one workload vs. others in onset slice (even without text content) | 2 |
| `dependency_failure` | Downstream/cascade errors in `sample_messages` (timeouts, connection refused) | 4 |
| `dependency_failure` | Multiple services spike together | 2 |
| `external_third_party` | Bank/Kafka/3rd-party HTTP errors in messages, no deploy | 4 |
| `external_third_party` | External status-page/incident referenced in ticket | 2 |
| `known_issue_match` | `known_issue_matches` populated and symptom matches | 5 |
| `feature_flag_regression` | Feature flag change 0–15 min before spike, same service | 5 |
| `feature_flag_regression` | Feature flag change 15–30 min before spike, same service | 3 |
| `feature_flag_regression` | Flag event (`feature_flag` in `get_change_stories`) targets the failing path | 3 |
| `kafka_lag_spike` | Consumer group lag > 10× normal baseline in window | 4 |
| `kafka_lag_spike` | Consumer group rebalance or thread restart in window | 3 |
| `kafka_lag_spike` | No deploy / infrastructure change event in window | 2 |
| `kafka_lag_spike` | Service is a confirmed Kafka consumer (from traces or topology) | 1 |
| `inconclusive` | No overlapping evidence across sources | (wins by default when all others ≈ 0) |

## Scoring formula

```
raw_score(h)        = sum of matched signal weights for hypothesis h
normalized(h)       = raw_score(h) / sum(raw_score(all h))   # legacy; prefer adjusted() in evidence-quality.md
primary             = argmax(raw_score)
ruled_out           = { h : raw_score(h) < 0.5 * raw_score(primary) }
```

**Display scores (0–100):** when CLI absent, apply the full formula in
[evidence-quality.md](evidence-quality.md) §Hypothesis score algorithm (quality_bonus, source_bonus,
counter_penalty, gap_penalty on top of raw_score). CLI output overrides manual computation when present.

**Cross-hypothesis penalty:** when a `deploy_regression` deploy event exists in the window on the **same service**, subtract 2 from the raw `infra_capacity` score and 2 from the raw `external_third_party` score. When a `configuration_change` event exists with no code deploy, subtract 2 from raw `deploy_regression` (config-only spike). When `query_governance` raw score ≥5, subtract 2 from raw `infra_capacity` (query workload explains saturation). A deploy in the window creates a competing explanation that lowers confidence in pure-infra and pure-external causes. Apply penalties before normalization.

## Confidence band (apply the guardrails)

| Confidence | Required |
|------------|----------|
| **HIGH** | ≥2 **independent signal types** agree (e.g. a change story **and** an error spike; or a feature flag event **and** an error spike) **and** counter-evidence/alternates stated **and** every counted signal's `detected_at` falls within `[window.from_time, window.to_time]` |
| **MEDIUM** | One strong signal, **or** only one source responded (hard cap — never exceed MEDIUM on a single source) — signals must still be within the incident window |
| **LOW** | Circumstantial / timing-only overlap, **or** signals outside the incident window |
| **UNKNOWN** | No overlapping evidence — `inconclusive` wins |

**Signal timing rule:** before assigning HIGH or MEDIUM, verify each signal timestamp lies inside the
incident window. A log spike or metric anomaly detected after `window.to_time` (e.g. 55 min later)
cannot count toward HIGH/MEDIUM — note it as out-of-window context only.

Independent signal **types** means different evidence kinds (deploy change, error metric, log pattern,
infra metric, ticket) — two Datadog log queries are **one** type, not two.

## Worked example

Evidence: Datadog `get_change_stories` shows a `deployment` at 14:20; `analyze_datadog_logs` shows the
5xx spike starting 14:45 on the same service; `get_commit_diff` shows the deploy changed
`TransferMoneyHandler` (the failing path); no OOM/restarts; INC-4521 opened 14:50.

```
deploy_regression: 3 (15–60 min before) + 3 (diff touches path) + 1 (ticket) = 7
infra_capacity:    0
external_third_party: 0
=> normalized(deploy_regression) = 7 / 7 = 1.0
=> primary = deploy_regression, others ruled out (< 3.5)
```

Confidence: **HIGH** — two independent signal types (deploy change story + error-rate spike), diff
corroborates, alternate `infra_capacity` considered and rejected (no OOM/restarts in window).

### Worked example — query_governance + infra_capacity multi-cause

Evidence: OpenSearch CPU 99%, thread-pool rejections 2.09M, search throughput flat (<1.2× baseline).
Phase 1 APM: top `GET /metadata/_search` from metadata-api, p95 4200ms, ~20/min exec rate. No deploy on
metadata-api. Slowlog not in Datadog.

```
query_governance: 5 (expensive_query_flag) + 3 (saturation w/o throughput spike) + 2 (top caller first 10m) + 2 (no client deploy) = 12
infra_capacity:   4 (CPU saturation proxy via thread-pool) + 2 (no deploy) = 6 → −2 cross-hypothesis = 4
=> primary = query_governance; co-cause infra_capacity (within 20% after penalty — report multi-cause)
```

Confidence: **MEDIUM** — all evidence (OpenSearch CPU/thread-pool metrics, APM top-caller trace) comes
from a single observability source (Datadog); the single-source cap ([thresholds.md](thresholds.md))
applies regardless of internal signal-type diversity. Would require a second independent observability
source (e.g. KubeSense log corroboration) to clear HIGH. Trigger partially established via APM; slowlog
gap noted under Remaining uncertainty.
