# Root cause depth — senior RCA bar

Load in **Phase 5** when rendering the report. Applies to every complete RCA; **required** extra sections
when primary hypothesis is `infra_capacity` or `dependency_failure` with confidence ≥ MEDIUM.

Infrastructure symptoms (CPU 99%, OOM, queue full, thread-pool rejections) are **confirmed failures** —
not sufficient root cause on their own. Always separate five layers:

| Layer | Question | If unknown |
|-------|----------|------------|
| **Confirmed failure** | What broke? | State the observable failure with evidence |
| **Initiating event** | What first disturbed the system? | **Unknown** — e.g. traffic spike before deploy failure |
| **Immediate trigger** | What directly caused the failure? | **Unknown** — do not invent a query, deploy, or workload |
| **Root cause** | Why did the system fail? | Process/design gap (missing test, no admission control) |
| **Contributing factors** | What amplified impact? | Shared cluster, missing circuit breaker, traffic shape |
| **Underlying / systemic cause** | Why could the org allow this? | Governance, alerting gaps, missing perf regression suite |

### Initiating event vs trigger vs root cause

The **initiating event** is not always the **trigger**. A deploy may be root cause while a traffic spike
initiated the failure path.

| Layer | Example (cache miss under load) |
|-------|----------------------------------|
| **Initiating event** | Marketing traffic spike at 14:00 |
| **Immediate trigger** | Cache stampede after deploy changed TTL |
| **Root cause** | Deploy removed cache warming; missing load test |
| **Contributing factors** | Shared Redis cluster; no rate limit |
| **Systemic cause** | No perf regression suite for cache paths |

### Trigger vs root cause vs contributing factors (deploy regression)

Do not conflate proximate events with systemic gaps.

| Layer | Example (N+1 deploy regression) |
|-------|----------------------------------|
| **Trigger** | Production deploy at 14:03 introduced expensive OpenSearch query |
| **Root cause** | Missing integration test for query path |
| **Contributing factors** | Shared OpenSearch cluster; no query timeout |
| **Systemic cause** | No performance regression test in CI |

**Preventive action** targets **root cause** and **systemic cause**, not the trigger alone.

## Evidence-safe wording (systemic layer)

Do **not** assert sizing conclusions the evidence does not prove.

| Avoid unless proven | Prefer |
|---------------------|--------|
| "Undersized instances/cluster" | "Cluster exhausted available compute headroom for the observed workload" |
| "Wrong instance type" | "Capacity was insufficient for the workload presented during the incident" |
| "We need bigger nodes" | "A single workload exhausted shared search capacity" (when shared dependency) |

A buggy wildcard query or aggregation explosion might have saturated even larger nodes — do not claim
undersizing without a sizing study or baseline comparison.

## Causal cascade (not just parallel timeline)

Show **propagation** with `↓` when one failure caused the next. Include a **recovery cascade** when
mitigation was applied:

```text
05:40 UTC — heavy `GET /metadata/_search` from metadata-api (APM — Phase 1; query_governance signal)
↓
Search thread pool saturated
↓
CPU reaches 99%
↓
~2.09M search rejections
↓
Application failures across seven services

--- recovery ---
06:30 UTC — Blue/Green scale-up initiated
↓
06:37 UTC — CPU begins dropping
↓
06:42 UTC — Search queue drains
↓
06:49 UTC — Traffic normalized
```

When a **volume spike** (throughput ≥2× baseline) drove saturation, show the traffic spike in the chain.
When throughput was **flat or <2× baseline**, prefer the **expensive-query branch** narrative — a single
expensive query can saturate CPU while request **counts stay flat or decline**. Mandatory checks:
[query-investigation.md](query-investigation.md) §Phase 1 — Expensive-query onset signature.

**Anti-pattern:** attributing onset to a downstream BFF `traffic_anomaly` change story when the **ES
client service** request rate did not rise ≥2× — run expensive-query investigation first.

Do not default to "search volume spike" without throughput evidence.

The **Unified timeline** table stays chronological (incident + remediation rows) with **Evidence quality** per row.
The **Causal chain** explains mechanism in prose. The **Causal graph** is a compact vertical `↓` chain from
trigger through intermediate failures to **customer-visible symptoms** — use for reviewer scanability.

Example causal graph:

```text
Deploy (MR !482)
↓
OpenSearch query regression
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

Label nodes **(Observed)** or **(Inferred)** when not directly logged. Graph must be **acyclic** — describe
feedback loops (retries ↔ latency) in prose after the graph. **Recovery timeline** answers MTTR — see below.

## Anti-repetition (executive readability)

State headline metrics **once** in the **Executive summary**. Later sections add interpretation, not
duplicate numbers.

| Section | Role |
|---------|------|
| Executive summary | Headline facts (CPU 99%, rejections, mitigation, outcome) — once |
| Root cause layers | Interpretation — cross-reference metrics, do not re-list all figures |
| Evidence table | Source + finding + link — not a metric dump |
| Key metrics snapshot | Time-bucket detail for investigators |
| Known vs unknown | Facts vs gaps — no third copy of the same CPU % |

Use *"see Key metrics snapshot"* or *"as summarized above"* instead of repeating 2.09M rejections in
five sections.

## Mechanism narrative (plain language)

When thread pools, queues, circuit breakers, or backpressure drove the incident, add 2–4 sentences a
non-specialist can follow.

## Five whys

Short table — stop at **Unknown** rather than speculate (3–5 rows). Last row should reach trigger or
systemic layer when evidence allows.

## What we know vs what we don't know

### Confirmed / ### Unknown — listing **Unknown** increases trust.

## Trigger workload analysis

After running [query-investigation.md](query-investigation.md) in Phase 3. The workload may still be
**Unknown** — but only after documented attempts (APM spans, logs, DBM). Fill:

| Field | Value |
|-------|-------|
| Index / table | |
| Query pattern | |
| Client service(s) | |
| Legitimate vs abusive | |

If slow logs are not in Datadog, list ops pull under P0 — see query-investigation §Step 5.

## Client-side / user-behavior triggers (Datadog RUM)

When server-side signals are inconclusive but users report UI impact, query RUM per
[query-playbook.md](query-playbook.md) §RUM. Corroborate with logs/APM before attributing to users.
Load RUM in Phase 1 when UI/checkout symptoms dominate or server telemetry is clean.

## JVM watchdog / CWJ triggers

When search/DB JVM nodes stall without query text, apply CWJ heuristics from
[query-playbook.md](query-playbook.md) §CloudWatch / JVM watchdog. User-named metrics override the
heuristic list — record override in `query_references[]`.

## Infra ruled-out depth

When ruling out JVM / memory: note GC pauses, heap, circuit breakers, cache eviction — or **Not checked**.

## Capacity snapshot metrics

Key metrics snapshot table for incident window — see [query-playbook.md](query-playbook.md) §Infra
capacity snapshot.

## Blast radius (multi-service)

Tree or table **plus one sentence** explaining why those services fail together. Structure:

1. **Primary service** or saturated dependency at the root.
2. **Dependency tree** — downstream consumers.
3. **Upstream mandate** — top-3 `@base_service` callers in the **first 10 min** when OpenSearch/ES,
   Redis, or Kafka is involved.

> All affected services depended on OpenSearch for master-data lookups, making the shared cluster a
> common point of failure.

## Recovery timeline (MTTR)

Required on complete RCAs when mitigation was applied. Answers: *Why did recovery take N minutes?*

| Milestone | Time (UTC) | Notes |
|-----------|------------|-------|
| Detection / symptom onset | | |
| First alert / page | | |
| Decision / escalation | | |
| Mitigation started | | e.g. Blue/Green deploy initiated |
| Mitigation complete | | |
| Recovery confirmed | | errors/latency back to baseline |

Note delays: diagnosis time, approval, deployment duration, queue drain. Cross-link **Unified timeline**
remediation rows.

## Resolution & remediation split

| Section | Content |
|---------|---------|
| **Immediate mitigation** | What restored service — not the permanent fix |
| **Permanent fixes** | Cross-link P0/P1/P2 |

## Lessons learned (leadership)

Turn the RCA into an improvement plan — 3–6 rows:

| Lesson | Action |
|--------|--------|
| Shared infrastructure increased blast radius | Evaluate workload isolation |
| CPU alerts fired too late | Add earlier predictive alerts |
| Triggering query couldn't be identified | Enable slow logs by default |

Distinct from P0/P1/P2 (operational tasks) — lessons are durable organizational takeaways.

## Risks (tiered)

After `Overall:` one sentence, prioritize — do not use a flat unordered list:

| Tier | Example |
|------|---------|
| **Highest** | Unknown triggering query |
| **High** | Shared cluster without isolation |
| **Medium** | Insufficient alerts; no admission control |
| **Low** | Runbook update needed |

## Recommended actions (P0 / P1 / P2)

Remediation tiers — keep **Gaps** for investigation follow-up only.

## Confidence display (executive reports)

Use **band + checklist** — avoid decimal scores in the narrative body. Readers rarely gain value from
0.82 vs 0.85.

```text
**Confidence:** HIGH

**Reason**
✓ Infra metrics corroborate saturation
✓ APM errors align with timeline
✓ Deploy ruled out

**Remaining uncertainty**
- Triggering query not identified
```

Numeric `primary_score` belongs in **`assessment_metadata.precision`** only — not Confluence/Jira paste.
See [thresholds.md](thresholds.md).

## `assessment_metadata` placement

Machine-readable footer — **not** an executive artifact.

- Report file: **Appendix — machine metadata** only
- Chat: when writing full report to disk
- **Omit** from Confluence/wiki export and Jira narrative unless another system parses it automatically

Spec: [assessment-metadata.md](assessment-metadata.md).
